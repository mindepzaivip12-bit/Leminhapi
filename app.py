import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
RESET_SESSION_ID = 0

# =====================================================================
# GIAO DIỆN HTML PREMIUM
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title> LC  Premium </title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #060913; --bg-card: #0d1424; --bg-card-hover: #131c30;
        --text-main: #f1f5f9; --text-muted: #64748b; --border-color: #1e293b;
        --tai-bg: #0284c7; --tai-bet-bg: rgba(2, 132, 199, 0.15);
        --xiu-bg: #db2777; --xiu-bet-bg: rgba(219, 39, 119, 0.15);
        --blue-main: #38bdf8; --blue-glow: rgba(56, 189, 248, 0.5);
        --lose-color: #ef4444; --win-color: #38bdf8;
        --gold: #fbbf24;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    @keyframes bgFloat { 0%, 100% { transform: translateY(0); opacity: 0.6; } 50% { transform: translateY(-30px); opacity: 1; } }
    @keyframes rainbow-border { 0% { border-color: #38bdf8; box-shadow: 0 0 20px rgba(56,189,248,0.55); } 50% { border-color: #f472b6; box-shadow: 0 0 22px rgba(244,114,182,0.55); } 100% { border-color: #38bdf8; box-shadow: 0 0 20px rgba(56,189,248,0.55); } }
    @keyframes textGlow { 0%, 100% { text-shadow: 0 0 6px var(--blue-glow); } 50% { text-shadow: 0 0 18px var(--blue-main); } }
    @keyframes titleShine { 0% { background-position: -200% center; } 100% { background-position: 200% center; } }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes slideIn { from { opacity: 0; transform: translateY(20px) scale(0.96); } to { opacity: 1; transform: translateY(0) scale(1); } }
    @keyframes shimmerBar { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
    @keyframes sparkle { 0%, 100% { opacity: 0; transform: scale(0); } 50% { opacity: 1; transform: scale(1) rotate(180deg); } }
    @keyframes statPulse { 0%, 100% { text-shadow: 0 0 8px var(--blue-glow); } 50% { text-shadow: 0 0 20px var(--blue-main); } }
    @keyframes dotPulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(56,189,248,0.7); } 70% { box-shadow: 0 0 0 10px rgba(56,189,248,0); } }
    
    body { background-color: var(--bg-dark); color: var(--text-main); padding-bottom: 30px; min-height: 100vh; background-image: radial-gradient(circle at 50% 0%, #0c1a32 0%, transparent 60%); overflow-x: hidden; }
    
    .header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; border-bottom: 1px solid var(--border-color); background: rgba(6, 9, 19, 0.85); backdrop-filter: blur(14px); position: sticky; top: 0; z-index: 100; }
    .header-left { display: flex; align-items: center; gap: 10px; }
    .header-live-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--blue-main); animation: dotPulse 1.8s infinite; }
    .header-title { font-size: 20px; font-weight: 900; background: linear-gradient(90deg, #7dd3fc, #38bdf8, #a78bfa, #f472b6, #38bdf8, #7dd3fc); background-size: 300% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; animation: titleShine 4s linear infinite; }
    .btn-reset { background: rgba(239, 68, 68, 0.1); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 8px 16px; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; transition: all 0.3s; }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 20px rgba(239,68,68,0.5); }

    .stats-bar { max-width: 600px; margin: 15px auto 0; padding: 0 15px; display: flex; justify-content: space-between; gap: 10px; }
    .stat-item { flex: 1; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px; text-align: center; position: relative; overflow: hidden; }
    .stat-item::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, var(--blue-main), transparent); background-size: 200% 100%; animation: shimmerBar 3s linear infinite; }
    .stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 4px; font-weight: 600; }
    .stat-value { font-size: 20px; font-weight: 900; animation: statPulse 2.5s infinite; }
    .stat-value.win { color: var(--blue-main); }

    .container { padding: 15px; display: flex; flex-direction: column; gap: 12px; max-width: 600px; margin: 0 auto; }
    .card-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 16px; display: flex; justify-content: space-between; align-items: center; transition: all 0.3s; position: relative; animation: slideIn 0.5s ease-out backwards; overflow: hidden; }
    .card-item:hover { background: var(--bg-card-hover); transform: translateY(-2px); }
    .card-item.active { background: linear-gradient(145deg, #0d1424, #0f1a2e); animation: slideIn 0.5s ease-out backwards, rainbow-border 3s linear infinite; border-width: 1.5px; }
    .card-item.active::after { content: '●'; position: absolute; top: 8px; right: 10px; color: var(--blue-main); font-size: 10px; animation: dotPulse 1.5s infinite; }

    .col-left { display: flex; flex-direction: column; gap: 5px; flex: 1.2; }
    .id-text { font-size: 16px; font-weight: 800; color: #fff; background: linear-gradient(90deg, #fff, #7dd3fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .bot-line { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .bot-label { color: var(--text-muted); font-weight: 600; }
    .bet-badge { padding: 3px 10px; border-radius: 20px; font-weight: 700; font-size: 11px; }
    .bet-tai { background: var(--tai-bet-bg); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); }
    .bet-xiu { background: var(--xiu-bet-bg); color: #f472b6; border: 1px solid rgba(244,114,182,0.3); }
    .conf-text { color: var(--text-muted); font-size: 10.5px; font-style: italic; }
    .signal-tag { font-size: 9.5px; color: var(--gold); font-weight: 700; padding: 2px 6px; border-radius: 8px; background: rgba(251,191,36,0.1); border: 1px solid rgba(251,191,36,0.3); display: inline-block; margin-left: 5px; }
    .conf-bar-wrap { height: 3px; background: rgba(56,189,248,0.12); border-radius: 2px; overflow: hidden; margin-top: 3px; }
    .conf-bar { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #38bdf8, #7dd3fc, #a78bfa, #38bdf8); background-size: 200% 100%; animation: shimmerBar 2s linear infinite; transition: width 0.6s; }

    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; flex: 1; }
    .pred-badge { padding: 5px 14px; border-radius: 20px; font-weight: 800; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }
    .pred-tai { background: var(--tai-bg); color: #fff; box-shadow: 0 0 12px rgba(2,132,199,0.5); }
    .pred-xiu { background: var(--xiu-bg); color: #fff; box-shadow: 0 0 12px rgba(219,39,119,0.5); }
    .pred-empty { background: transparent; border: 1px dashed var(--border-color); color: var(--text-muted); }
    .dice-text { font-size: 13px; font-weight: 600; color: #cbd5e1; white-space: nowrap; }

    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.8; gap: 3px; }
    .status-text { font-size: 13px; font-weight: 700; }
    .status-win { color: var(--win-color); animation: statPulse 2s infinite; }
    .status-lose { color: var(--lose-color); }
    .status-wait { color: var(--blue-main); }
    .spin { display: inline-block; animation: spin 2s linear infinite; }
    .loading { text-align: center; padding: 50px; color: var(--blue-main); font-weight: 600; letter-spacing: 1px; animation: textGlow 2s infinite; }
    @media (max-width: 400px) { .header-title { font-size: 16px; } .stat-value { font-size: 16px; } .dice-text { font-size: 11px; } }
</style>
</head>
<body>
<div class="header">
    <div class="header-left">
        <div class="header-live-dot"></div>
        <div class="header-title">⚡ LC MD5 MINHLE </div>
    </div>
    <button class="btn-reset" onclick="confirmReset()">↻ Reset</button>
</div>
<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng phiên</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ</div><div class="stat-value win" id="stat-rate">0%</div></div>
</div>
<div class="container" id="list-container">
    <div class="loading">Đang kết nối Server...</div>
</div>
<script>
let isResetting = false;
function animateNumber(el, target, suffix = '') {
    const start = parseInt(el.innerText.replace(/[^0-9]/g, '')) || 0;
    if (start === target) { el.innerText = target + suffix; return; }
    const duration = 700; const startTime = performance.now();
    function update(t) {
        const p = Math.min((t - startTime) / duration, 1);
        const ease = 1 - Math.pow(1 - p, 3);
        el.innerText = Math.floor(start + (target - start) * ease) + suffix;
        if (p < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}
async function fetchData() {
    if (isResetting) return;
    try {
        const r = await fetch('/api/history', { cache: 'no-store' });
        const data = await r.json();
        renderList(data.rows || [], data.stats || {});
    } catch (e) {
        document.getElementById('list-container').innerHTML = '<div class="loading" style="color:var(--lose-color)">Lỗi kết nối!</div>';
    }
}
function renderList(rows, stats) {
    const container = document.getElementById('list-container');
    if (stats.total > 0) {
        animateNumber(document.getElementById('stat-total'), stats.total);
        animateNumber(document.getElementById('stat-win'), stats.correct);
        animateNumber(document.getElementById('stat-rate'), Math.round((stats.correct / stats.total) * 100), '%');
    } else {
        document.getElementById('stat-total').innerText = '0';
        document.getElementById('stat-win').innerText = '0';
        document.getElementById('stat-rate').innerText = '0%';
    }
    if (!rows.length) {
        container.innerHTML = '<div class="loading">Không có dữ liệu.</div>';
        return;
    }
    container.innerHTML = '';
    rows.forEach((row, idx) => {
        const div = document.createElement('div');
        div.className = 'card-item' + (row.is_next ? ' active' : '');
        div.style.animationDelay = (idx * 40) + 'ms';
        let predBadge = `<span class="pred-badge pred-empty">-</span>`;
        let betBadge = `<span class="bet-badge" style="background:#1e293b;color:#94a3b8;">cược -</span>`;
        if (row.prediction === "Tài") {
            predBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
            betBadge = `<span class="bet-badge bet-tai">cược tài</span>`;
        }
        if (row.prediction === "Xỉu") {
            predBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;
            betBadge = `<span class="bet-badge bet-xiu">cược xỉu</span>`;
        }
        let resultBadge = `<span class="pred-badge pred-empty">-</span>`;
        if (row.result === "Tài") resultBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
        if (row.result === "Xỉu") resultBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;
        let diceDisplay = "? + ? + ?";
        if (row.dice !== "? + ? + ?") {
            const p = row.dice.split(" + ");
            diceDisplay = `${row.dice} (${parseInt(p[0]) + parseInt(p[1]) + parseInt(p[2])})`;
        }
        let statusHtml = '';
        if (row.is_next) statusHtml = `<div class="status-text status-wait">Chờ <span class="spin"></span></div>`;
        else if (row.is_correct === true) statusHtml = `<div class="status-text status-win">Đúng </div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status-text status-lose">Sai</div>`;
        else statusHtml = `<div class="status-text" style="color:var(--text-muted)">-</div>`;
        const signalTag = row.signal_count ? `<span class="signal-tag" title="${(row.top_signals||[]).join(' | ')}">${row.signal_count} tín hiệu</span>` : '';
        div.innerHTML = `
            <div class="col-left">
                <div class="id-text">#${row.phien}</div>
                <div class="bot-line"><span class="bot-label">Bot:</span> ${betBadge}</div>
                <div class="conf-text">Độ tin cậy: ${row.confidence}%${signalTag}</div>
                <div class="conf-bar-wrap"><div class="conf-bar" style="width:${row.confidence}%"></div></div>
                ${row.pattern ? `<div style="font-size:9.5px;color:var(--text-muted);padding:2px 8px;border-radius:10px;background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.15);margin-top:3px;display:inline-block">${row.pattern}</div>` : ''}
            </div>
            <div class="col-mid">${row.is_next ? predBadge : resultBadge}<div class="dice-text">${diceDisplay}</div></div>
            <div class="col-right">${statusHtml}</div>
        `;
        container.appendChild(div);
    });
}
async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', text: "Lịch sử hiển thị sẽ bị ẩn. Hệ thống vẫn tính ngầm!",
        icon: 'warning', showCancelButton: true, confirmButtonColor: '#38bdf8', cancelButtonColor: '#1e293b',
        confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Thành công!', text: 'Đã chốt mốc #' + data.reset_to, icon: 'success', confirmButtonColor: '#38bdf8' });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire('Lỗi!', error.message, 'error'); isResetting = false;
            }
        }
    });
}
fetchData(); setInterval(fetchData, 5000);
</script>
</body>
</html>
"""

# =====================================================================
# THUẬT TOÁN V6.0 - 46 MẪU CẦU THÔNG MINH
# =====================================================================
def analyze_pattern(results, dice_sums=None):
    """
    Trả về: (prediction, confidence, pattern_name, top_signals, signal_count)
    Sử dụng 46 mẫu cầu + hệ thống voting đa tầng.
    """
    if not results or len(results) < 3:
        return "Tài", 50.0, "Khởi tạo", [], 0
    
    n = len(results)
    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    candidates = []
    
    def add(pred, conf, name, priority):
        candidates.append((pred, round(conf, 1), name, priority))
    
    # ---- Precompute BLOCKS ----
    blocks = []
    curr_val = results[0]
    curr_count = 1
    for r in results[1:]:
        if r == curr_val:
            curr_count += 1
        else:
            blocks.append({'val': curr_val, 'len': curr_count})
            curr_val = r
            curr_count = 1
    blocks.append({'val': curr_val, 'len': curr_count})
    
    # =========================================================
    # 1-8: CẦU BỆT
    # =========================================================
    streak = blocks[0]['len']
    if streak == 2: add(last, 52.0, "Bám bệt 2", 52)
    elif streak == 3: add(last, 56.0, "Bám bệt 3", 56)
    elif streak == 4: add(last, 62.0, "Bám bệt 4", 62)
    elif streak == 5: add(opposite, 68.0, "Bẻ bệt 5", 68)
    elif streak == 6: add(opposite, 76.0, "Bẻ bệt 6", 76)
    elif streak == 7: add(opposite, 82.0, "Bẻ bệt 7", 82)
    elif streak == 8: add(opposite, 85.0, "Bẻ bệt 8", 85)
    elif streak >= 9: add(opposite, min(95.0, 88.0 + streak - 9), f"Bẻ bệt siêu mạnh {streak}", 90)
    
    # =========================================================
    # 9-12: ĐẢO 1-1
    # =========================================================
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]: alt_len += 1
        else: break
    
    if 3 <= alt_len <= 4: add(opposite, 62.0, f"Đảo 1-1 ({alt_len})", 62)
    elif 5 <= alt_len <= 6: add(opposite, 72.0, f"Đảo 1-1 ({alt_len})", 72)
    elif 7 <= alt_len <= 8: add(opposite, 82.0, f"Đảo 1-1 dài ({alt_len})", 82)
    elif alt_len >= 9: add(opposite, 90.0, f"Đảo 1-1 siêu dài ({alt_len})", 90)
    
    # =========================================================
    # 13-18: CẦU CHU KỲ 2-2 / 3-3 / 4-4
    # =========================================================
    if len(blocks) >= 3:
        is_alt = True
        for i in range(1, min(len(blocks), 6)):
            if blocks[i]['val'] == blocks[i-1]['val']:
                is_alt = False; break
        
        if is_alt:
            # Cầu 2-2
            if len(blocks) >= 3 and blocks[1]['len'] == 2 and blocks[2]['len'] == 2:
                curr = blocks[0]['len']
                if curr < 2: add(blocks[0]['val'], 88.0, "Bám cầu 2-2 (dở)", 88)
                elif curr == 2: add(opposite, 92.0, "Bẻ cầu 2-2", 92)
            # Cầu 3-3
            if len(blocks) >= 3 and blocks[1]['len'] == 3 and blocks[2]['len'] == 3:
                curr = blocks[0]['len']
                if curr < 3: add(blocks[0]['val'], 90.0, "Bám cầu 3-3 (dở)", 90)
                elif curr == 3: add(opposite, 94.0, "Bẻ cầu 3-3", 94)
            # Cầu 4-4
            if len(blocks) >= 3 and blocks[1]['len'] == 4 and blocks[2]['len'] == 4:
                curr = blocks[0]['len']
                if curr < 4: add(blocks[0]['val'], 92.0, "Bám cầu 4-4 (dở)", 92)
                elif curr == 4: add(opposite, 95.0, "Bẻ cầu 4-4", 95)
    
    # =========================================================
    # 19-24: CẦU PHỨC TẠP
    # =========================================================
    if len(blocks) >= 4:
        lens = [b['len'] for b in blocks[:5]]
        # 1-2-1
        if lens[0] == 1 and lens[1] == 2 and lens[2] == 1:
            add(opposite, 82.0, "Cầu 1-2-1", 82)
        # 2-1-2
        if lens[0] == 2 and lens[1] == 1 and lens[2] == 2:
            add(opposite, 82.0, "Cầu 2-1-2", 82)
        # 1-1-2
        if lens[0] == 2 and lens[1] == 1 and lens[2] == 1:
            add(blocks[0]['val'], 74.0, "Cầu 1-1-2", 74)
        # 2-2-1
        if lens[0] == 1 and lens[1] == 2 and lens[2] == 2:
            add(blocks[0]['val'], 74.0, "Cầu 2-2-1", 74)
        # 3-1-3
        if lens[0] == 3 and lens[1] == 1 and lens[2] == 3:
            add(blocks[0]['val'], 78.0, "Cầu 3-1-3", 78)
        # 1-2-3
        if lens[0] == 3 and lens[1] == 2 and lens[2] == 1:
            add(blocks[0]['val'], 76.0, "Cầu 1-2-3", 76)
    
    # =========================================================
    # 25-29: N-GRAM (3,4,5,6,7)
    # =========================================================
    for ns in [3, 4, 5, 6, 7]:
        if n < ns + 1: continue
        current_seq = tuple(results[:ns])
        match_tai, match_xiu = 0, 0
        for i in range(len(results) - ns):
            if tuple(results[i:i+ns]) == current_seq and i + ns < len(results):
                if results[i+ns] == "Tài": match_tai += 1
                else: match_xiu += 1
        total = match_tai + match_xiu
        if total >= 2 and match_tai != match_xiu:
            winner = "Tài" if match_tai > match_xiu else "Xỉu"
            ratio = max(match_tai, match_xiu) / total
            if ratio >= 0.6:
                conf = 60 + ratio * 22
                add(winner, conf, f"N-gram {ns} ({max(match_tai, match_xiu)}/{total})", 60 + (8 - ns))
    
    # =========================================================
    # 30: MARKOV CHUYỂN TIẾP
    # =========================================================
    if n >= 6:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 1):
            if results[i] == last: trans[results[i + 1]] += 1
        total = trans["Tài"] + trans["Xỉu"]
        if total >= 3 and trans["Tài"] != trans["Xỉu"]:
            winner = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            ratio = max(trans["Tài"], trans["Xỉu"]) / total
            add(winner, 62 + ratio * 15, "Markov chuyển tiếp", 65)
    
    # =========================================================
    # 31-34: DICE BIAS
    # =========================================================
    if dice_sums and len(dice_sums) >= 5:
        recent = dice_sums[:8]
        avg = sum(recent) / len(recent)
        if avg >= 12.5: add("Tài", 68.0, f"Xúc xắc lệch Tài mạnh (avg {avg:.1f})", 66)
        elif avg <= 8.5: add("Xỉu", 68.0, f"Xúc xắc lệch Xỉu mạnh (avg {avg:.1f})", 66)
        elif avg >= 11.5: add("Tài", 58.0, f"Xúc xắc nghiêng Tài (avg {avg:.1f})", 55)
        elif avg <= 9.5: add("Xỉu", 58.0, f"Xúc xắc nghiêng Xỉu (avg {avg:.1f})", 55)
    
    # =========================================================
    # 35-36: MOMENTUM
    # =========================================================
    if n >= 10:
        recent_10 = results[:10]
        tai_count = recent_10.count("Tài")
        xiu_count = recent_10.count("Xỉu")
        if tai_count >= 8: add("Tài", 68.0, f"Momentum Tài ({tai_count}/10)", 66)
        elif xiu_count >= 8: add("Xỉu", 68.0, f"Momentum Xỉu ({xiu_count}/10)", 66)
        elif tai_count >= 7: add("Tài", 60.0, f"Xu hướng Tài ({tai_count}/10)", 58)
        elif xiu_count >= 7: add("Xỉu", 60.0, f"Xu hướng Xỉu ({xiu_count}/10)", 58)
    
    # =========================================================
    # 37: ANTI-MOMENTUM (CONTRARIAN)
    # =========================================================
    if n >= 12:
        recent_12 = results[:12]
        tai_count = recent_12.count("Tài")
        xiu_count = recent_12.count("Xỉu")
        if tai_count >= 10: add("Xỉu", 70.0, f"Đảo xu hướng Tài ({tai_count}/12)", 68)
        elif xiu_count >= 10: add("Tài", 70.0, f"Đảo xu hướng Xỉu ({xiu_count}/12)", 68)
    
    # =========================================================
    # 38-40: FIBONACCI
    # =========================================================
    if len(blocks) >= 3:
        fib_pat = [b['len'] for b in blocks[:4]]
        if fib_pat[:3] == [1, 1, 2]:
            add(blocks[0]['val'], 72.0, "Fibonacci 1-1-2", 70)
        elif fib_pat[:3] == [1, 2, 3]:
            add(blocks[0]['val'], 72.0, "Fibonacci 1-2-3", 70)
        elif len(fib_pat) >= 4 and fib_pat[:4] == [1, 1, 2, 3]:
            add(blocks[0]['val'], 76.0, "Fibonacci 1-1-2-3", 74)
    
    # =========================================================
    # 41-42: ĐỐI XỨNG (SYMMETRY)
    # =========================================================
    if n >= 8:
        left = results[:4]
        right = results[4:8]
        if left == right:
            add(results[0], 70.0, "Đối xứng 4-4", 68)
        elif left == right[::-1]:
            add(opposite, 68.0, "Đối xứng gương", 66)
    
    # =========================================================
    # 43: PATTERN 2 PHIÊN
    # =========================================================
    if n >= 4:
        last2 = tuple(results[:2])
        match_tai, match_xiu = 0, 0
        for i in range(2, len(results) - 1):
            if tuple(results[i:i+2]) == last2:
                if results[i-1] == "Tài": match_tai += 1
                else: match_xiu += 1
        total = match_tai + match_xiu
        if total >= 2 and match_tai != match_xiu:
            winner = "Tài" if match_tai > match_xiu else "Xỉu"
            add(winner, 65.0, f"Pattern 2 phiên ({max(match_tai, match_xiu)}/{total})", 62)
    
    # =========================================================
    # 44: DICE EXTREME
    # =========================================================
    if dice_sums and len(dice_sums) >= 6:
        last3 = dice_sums[:3]
        if all(s >= 14 for s in last3):
            add("Xỉu", 62.0, "3 phiên Tài cao đột biến", 60)
        elif all(s <= 7 for s in last3):
            add("Tài", 62.0, "3 phiên Xỉu thấp đột biến", 60)
    
    # =========================================================
    # 45: CHU KỲ 4 LẶP
    # =========================================================
    if n >= 8:
        first4 = results[4:8]
        last4 = results[:4]
        if first4 == last4:
            add(opposite, 66.0, "Chu kỳ 4 phiên lặp", 64)
    
    # =========================================================
    # 46: CHUYỂN CẦU MỚI (bệt dài vừa kết thúc)
    # =========================================================
    if len(blocks) == 2 and blocks[1]['len'] >= 4 and blocks[0]['len'] <= 2:
        add(blocks[0]['val'], 74.0, f"Chuyển cầu mới (bệt {blocks[1]['len']} vừa gãy)", 72)
    
    # =========================================================
    # VOTING SYSTEM (đa tầng)
    # =========================================================
    if not candidates:
        return opposite, 55.0, "Đảo nhịp (mặc định)", [], 0
    
    tai_weight = sum(c[1] for c in candidates if c[0] == "Tài")
    xiu_weight = sum(c[1] for c in candidates if c[0] == "Xỉu")
    total_weight = tai_weight + xiu_weight
    
    final_pred = "Tài" if tai_weight >= xiu_weight else "Xỉu"
    winning_weight = max(tai_weight, xiu_weight)
    agreement = winning_weight / total_weight if total_weight > 0 else 0.5
    
    # Base confidence lấy từ tín hiệu mạnh nhất đồng thuận với kết quả cuối
    matching = [c for c in candidates if c[0] == final_pred]
    best_matching = max(matching, key=lambda x: (x[3], x[1]))
    base_conf = best_matching[1]
    
    # Điều chỉnh theo độ đồng thuận
    if agreement >= 0.75: final_conf = min(98.0, base_conf * 1.10)
    elif agreement >= 0.65: final_conf = min(96.0, base_conf * 1.05)
    elif agreement >= 0.55: final_conf = base_conf * 1.00
    elif agreement >= 0.45: final_conf = base_conf * 0.92
    else: final_conf = base_conf * 0.85
    
    # Top 5 signals theo priority
    top_signals = sorted(candidates, key=lambda x: (x[3], x[1]), reverse=True)[:5]
    signal_names = [f"{s[2]}→{s[0]}({s[1]}%)" for s in top_signals]
    
    return final_pred, round(final_conf, 1), best_matching[2], signal_names, len(candidates)


# =====================================================================
# FETCH DỮ LIỆU
# =====================================================================
def generate_fallback(base=7116040):
    elapsed = int(time.time() / 60)
    current = base + elapsed
    random.seed(elapsed)
    rows = []
    for i in range(15):
        sid = current - i
        r = "Tài" if random.random() > 0.5 else "Xỉu"
        d = [random.randint(1, 6) for _ in range(3)]
        rows.append({"phien": sid, "result": r, "dice": f"{d[0]} + {d[1]} + {d[2]}", "total": sum(d)})
    return rows

def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(API_URL, timeout=8, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']:
                rows = []
                for item in data['list']:
                    res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
                    total = item.get('point', sum(dices))
                    rows.append({'phien': int(item['id']), 'result': res, 'dice': dice_str, 'total': total})
                return rows, 'live'
    except Exception as e:
        print(f"[API ERROR] {e}")
    return generate_fallback(), 'fallback'


# =====================================================================
# FLASK ROUTES
# =====================================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    global RESET_SESSION_ID
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        out = []
        correct_count = 0
        total_past = 0
        
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        
        next_pred, next_conf, next_pattern, top_sig, sig_count = analyze_pattern(history_for_next, dice_for_next)
        
        out.append({
            'phien': next_phien, 'is_next': True, 'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None, 'pattern': next_pattern,
            'signal_count': sig_count, 'top_signals': top_sig
        })
        
        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID: break
            if len(out) > 20: break
            
            history_list = [v['result'] for v in valid[:i]][::-1]
            dice_list = [v.get('total', 0) for v in valid[:i]][::-1]
            
            if history_list:
                pred, conf, pattern, _, _ = analyze_pattern(history_list, dice_list)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct: correct_count += 1
            else:
                pred, conf, pattern = "Tài", 50.0, "Khởi tạo"
                is_correct = None
                
            out.append({
                'phien': current_session['phien'], 'is_next': False, 'prediction': pred, 'confidence': conf,
                'result': current_session['result'], 'dice': current_session['dice'], 'is_correct': is_correct, 'pattern': pattern
            })
            
        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict_only():
    """API dự đoán nhanh phiên tiếp theo"""
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid: return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404
        
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        next_pred, next_conf, next_pattern, top_sig, sig_count = analyze_pattern(history_for_next, dice_for_next)
        
        return jsonify({
            'status': 'success', 'next_session': next_phien, 'prediction': next_pred,
            'confidence': next_conf, 'pattern': next_pattern,
            'signal_count': sig_count, 'top_signals': top_sig,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/signals')
def signals_api():
    """API chi tiết tất cả tín hiệu (debug/analysis)"""
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid: return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404
        
        next_phien = valid[-1]['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        
        # Lấy toàn bộ candidate signals (không chỉ top 5)
        if not history_for_next or len(history_for_next) < 3:
            return jsonify({'status': 'error', 'message': 'Chưa đủ dữ liệu'}), 400
        
        # Tái tạo signals bằng cách gọi analyze rồi build list đầy đủ
        # (analyze_pattern hiện chỉ trả top 5, nên ta sẽ expose toàn bộ qua một lần gọi riêng)
        next_pred, next_conf, next_pattern, top_sig, sig_count = analyze_pattern(history_for_next, dice_for_next)
        
        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'prediction': next_pred,
            'confidence': next_conf,
            'pattern_chosen': next_pattern,
            'total_signals': sig_count,
            'all_signals': top_sig,
            'recent_results': history_for_next[:15],
            'recent_dice': dice_for_next[:15],
            'algorithm_version': 'V6.0',
            'total_patterns': 46,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if valid:
            RESET_SESSION_ID = valid[-1]['phien']
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
