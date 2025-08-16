# app.py
import os
import time
import socket
from datetime import datetime

from flask import Flask, jsonify, render_template, send_from_directory

# psutil は任意依存（未インストールでも動作するようフォールバック）
try:
    import psutil  # type: ignore
except Exception:
    psutil = None

app = Flask(__name__)

# アプリケーションタイトル（初期表示用。実表示は i18n が上書き）
APP_TITLE = "Global DMS"

# /logo 配下から画像を配信
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_DIR = os.path.join(BASE_DIR, "logo")
os.makedirs(LOGO_DIR, exist_ok=True)  # 無ければ作成

def _linux_cpu_percent(interval: float = 0.1):
    """/proc/stat から CPU 使用率(%) を概算（Linux 限定）。"""
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
        if dt <= 0: return None
        return round((1 - (di / dt)) * 100, 1)
    except Exception:
        return None

def _linux_memory():
    """/proc/meminfo からメモリ使用量を概算（GB, %）。Linux 限定。"""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                info[parts[0].rstrip(":")] = int(parts[1])
        total_kb = info.get("MemTotal")
        avail_kb = info.get("MemAvailable")
        if total_kb is None: return None
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

def _local_ip():
    """同一ネットワークからアクセスする際のローカルIPを推定。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # 実通信は発生しない（ルーティング判定のみ）
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

@app.route("/")
def index():
    return render_template("index.html", app_title=APP_TITLE)

# /logo/ 配下のファイルを配信
@app.route("/logo/<path:filename>")
def serve_logo(filename):
    return send_from_directory(LOGO_DIR, filename)

@app.route("/status")
def status():
    """ステータスバー用 API。"""
    cpu = None
    memory = None
    if psutil:
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            memory = {
                "percent": round(mem.percent, 1),
                "used_gb": round(mem.used / (1024 ** 3), 1),
                "total_gb": round(mem.total / (1024 ** 3), 1),
            }
        except Exception:
            cpu = None
            memory = None
    elif os.name == "posix" and os.path.exists("/proc/stat"):
        cpu = _linux_cpu_percent(0.1)
        memory = _linux_memory()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"cpu_percent": cpu, "memory": memory, "server_time": now})

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 5050
    print("========================================")
    print(f" Global DMS を起動します")
    print(f" このPCから:           http://127.0.0.1:{port}/")
    print(f" 同一ネットワークから: http://{_local_ip()}:{port}/")
    print("========================================")
    app.run(host=host, port=port, debug=False)
