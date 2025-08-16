// ステータスを1秒ごとに更新してフッターへ表示
async function fetchStatus() {
    try {
        const res = await fetch("/status", { cache: "no-store" });
        const data = await res.json();

        const cpu = data.cpu_percent;
        const mem = data.memory;

        const cpuText = (cpu != null) ? `${Math.round(cpu)}%` : "N/A";

        let memText = "N/A";
        if (mem && mem.percent != null && mem.used_gb != null && mem.total_gb != null) {
            const memP = Math.round(mem.percent);
            const used = mem.used_gb.toFixed(1);
            const total = mem.total_gb.toFixed(1);
            memText = `${used}/${total} GB（${memP}%）`;
        }

        document.getElementById("status-text").textContent =
            `CPU: ${cpuText}　|　Mem: ${memText}　|　${data.server_time}`;
    } catch (e) {
        console.error(e);
        document.getElementById("status-text").textContent = "ステータス取得エラー";
    }
}

window.addEventListener("load", () => {
    fetchStatus();
    setInterval(fetchStatus, 1000);
});
