# app.py
import os
import re
import time
import socket
import platform
import subprocess
from datetime import datetime

from flask import Flask, jsonify, render_template, send_from_directory

# psutil は任意依存（未インストールでも動作するようフォールバックを実装）
try:
    import psutil  # type: ignore
except Exception:
    psutil = None

app = Flask(__name__)

# アプリケーションタイトル（初期表示用。実表示は i18n で上書きされる）
APP_TITLE = "Global DMS"

# /logo 配下から画像を配信
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_DIR = os.path.join(BASE_DIR, "logo")
os.makedirs(LOGO_DIR, exist_ok=True)  # 無ければ作成


# ===================== CPU 使用率（%）フォールバック実装 =====================

def _linux_cpu_percent(interval: float = 0.1):
    """Linux: /proc/stat から CPU 使用率(%) を概算。"""
    try:
        with open("/proc/stat") as f:
            first = f.readline().split()[1:]
        first = [int(x) for x in first]
        idle1 = first[3] + (first[4] if len(first) > 4 else 0)
        total1 = sum(first[:8]) if len(first) >= 8 else sum(first)
        time.sleep(interval)
        with open("/proc/stat") as f:
            second = f.readline().split()[1:]
        second = [int(x) for x in second]
        idle2 = second[3] + (second[4] if len(second) > 4 else 0)
        total2 = sum(second[:8]) if len(second) >= 8 else sum(second)
        dt = total2 - total1
        di = idle2 - idle1
        if dt <= 0:
            return None
        return round((1 - (di / dt)) * 100, 1)
    except Exception:
        return None


def _win_cpu_percent(interval: float = 0.1):
    """Windows: GetSystemTimes を用いて CPU 使用率(%) を計算。"""
    try:
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD),
            ]

        def filetime_to_int(ft):
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

        def read_times():
            idle = FILETIME()
            kernel = FILETIME()
            user = FILETIME()
            ok = ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
            )
            if not ok:
                return None
            return (
                filetime_to_int(idle),
                filetime_to_int(kernel),
                filetime_to_int(user),
            )

        t1 = read_times()
        if not t1:
            return None
        time.sleep(interval)
        t2 = read_times()
        if not t2:
            return None

        idle1, kernel1, user1 = t1
        idle2, kernel2, user2 = t2

        # kernel には idle を含む仕様のため、差し引いて使用時間を算出
        busy1 = (kernel1 - idle1) + user1
        busy2 = (kernel2 - idle2) + user2
        busy = busy2 - busy1
        total = (kernel2 - kernel1) + (user2 - user1)
        if total <= 0:
            return None
        return round(busy / total * 100, 1)
    except Exception:
        return None


def _darwin_cpu_percent(interval: float = 0.1):
    """
    macOS: 依存無しでの厳密な CPU% 取得は難しいため、
    1分ロードアベレージから近似（コア数で割って%化）。
    """
    try:
        load1, _, _ = os.getloadavg()
        cpus = os.cpu_count() or 1
        pct = load1 / cpus * 100.0
        # 過度な値を避けるため 0-100 に丸める
        return round(max(0.0, min(100.0, pct)), 1)
    except Exception:
        return None


def get_cpu_percent(interval: float = 0.1):
    """OSごとに最適な方法で CPU 使用率(%) を返す。"""
    # 1) psutil があれば最優先（全OS対応・精度が高い）
    if psutil:
        try:
            return psutil.cpu_percent(interval=interval)
        except Exception:
            pass

    # 2) フォールバック
    system = platform.system().lower()
    if system == "linux":
        return _linux_cpu_percent(interval)
    if system == "windows":
        return _win_cpu_percent(interval)
    if system == "darwin":
        return _darwin_cpu_percent(interval)
    return None


# ===================== メモリ使用量フォールバック実装 =====================

def _linux_memory():
    """Linux: /proc/meminfo からメモリ使用量を概算（GB, %）。"""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                info[parts[0].rstrip(":")] = int(parts[1])
        total_kb = info.get("MemTotal")
        avail_kb = info.get("MemAvailable")
        if total_kb is None:
            return None
        if avail_kb is None:
            avail_kb = info.get("MemFree", 0) + info.get("Buffers", 0) + info.get("Cached", 0)
        used_kb = total_kb - avail_kb
        return {
            "percent": round(used_kb / total_kb * 100, 1),
            "used_gb": round(used_kb / 1024 / 1024, 1),
            "total_gb": round(total_kb / 1024 / 1024, 1),
        }
    except Exception:
        return None


def _win_memory():
    """Windows: GlobalMemoryStatusEx からメモリ使用量（GB, %）。"""
    try:
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        if not ok:
            return None

        total = int(stat.ullTotalPhys)
        avail = int(stat.ullAvailPhys)
        used = total - avail
        return {
            "percent": round(used / total * 100, 1),
            "used_gb": round(used / (1024 ** 3), 1),
            "total_gb": round(total / (1024 ** 3), 1),
        }
    except Exception:
        return None


def _darwin_memory():
    """macOS: sysctl / vm_stat を用いてメモリ使用量（GB, %）を概算。"""
    try:
        # 総メモリ（バイト）
        memsize = int(subprocess.check_output(
            ["/usr/sbin/sysctl", "-n", "hw.memsize"]
        ).strip())
        # ページサイズ（バイト）
        pagesize = int(subprocess.check_output(
            ["/usr/sbin/sysctl", "-n", "hw.pagesize"]
        ).strip())

        vm = subprocess.check_output(["/usr/bin/vm_stat"]).decode("utf-8", errors="ignore")
        # 例: "Pages free:                               12345."
        pages = {}
        for line in vm.splitlines():
            m = re.match(r"^([^:]+):\s+(\d+)\.", line)
            if m:
                key = m.group(1).strip()
                pages[key] = int(m.group(2))

        # ざっくり「空き」に近いページ：free + speculative
        free_pages = pages.get("Pages free", 0) + pages.get("Pages speculative", 0)
        avail = free_pages * pagesize
        used = memsize - avail
        return {
            "percent": round(used / memsize * 100, 1),
            "used_gb": round(used / (1024 ** 3), 1),
            "total_gb": round(memsize / (1024 ** 3), 1),
        }
    except Exception:
        return None


def get_memory():
    """OSごとに最適な方法でメモリ使用量（GB, %）を返す。"""
    # 1) psutil があれば最優先（全OS対応・精度が高い）
    if psutil:
        try:
            mem = psutil.virtual_memory()
            return {
                "percent": round(mem.percent, 1),
                "used_gb": round(mem.used / (1024 ** 3), 1),
                "total_gb": round(mem.total / (1024 ** 3), 1),
            }
        except Exception:
            pass

    # 2) フォールバック
    system = platform.system().lower()
    if system == "linux":
        return _linux_memory()
    if system == "windows":
        return _win_memory()
    if system == "darwin":
        return _darwin_memory()
    return None


# ===================== ユーティリティ =====================

def _local_ip():
    """同一ネットワークからアクセスする際のローカルIPを推定。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # 実通信は発生しない（ルーティング判定のみ）
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


# ===================== ルーティング =====================

@app.route("/")
def index():
    return render_template("index.html", app_title=APP_TITLE)


# /logo/ 配下のファイルを配信（index.html から url_for('serve_logo', ...) で参照）
@app.route("/logo/<path:filename>")
def serve_logo(filename):
    return send_from_directory(LOGO_DIR, filename)


@app.route("/status")
def status():
    """ステータスバー用 API。CPU% とメモリ情報を返す。"""
    cpu = get_cpu_percent(0.1)
    memory = get_memory()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"cpu_percent": cpu, "memory": memory, "server_time": now})


# ===================== エントリポイント =====================

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 5050
    print("========================================")
    print(" Global DMS を起動します")
    print(f" このPCから:           http://127.0.0.1:{port}/")
    print(f" 同一ネットワークから: http://{_local_ip()}:{port}/")
    print("========================================")
    app.run(host=host, port=port, debug=False)
