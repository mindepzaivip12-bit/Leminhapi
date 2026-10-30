import os
import time
import random
import threading
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

# === GLOBAL STATE (bộ nhớ tích lũy vô hạn) ===
RESET_SESSION_ID = 0
PREDICTION_LOG = {}   # {phien: {prediction, result, confidence, is_correct}}
LOG_LOCK = threading.Lock()

# =====================================================================
# GIAO DIỆN HTML - TOOL LCMD5 LEMINH
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TOOL LCMD5 LEMINH</title>
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
        --purple: #a78bfa; --gold: #fbbf24;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    @keyframes bgFloat { 0%, 100% { transform: translateY(0) translateX(0); opacity: 0.6; } 50% { transform: translateY(-30px) translateX(20px); opacity: 1; } }
    @keyframes bgFloat2 { 0%, 100% { transform: translateY(0) translateX(0); opacity: 0.5; } 50% { transform: translateY(20px) translateX(-25px); opacity: 0.9; } }
    @keyframes rainbow-border { 0% { border-color: #38bdf8; box-shadow: 0 0 20px rgba(56,189,248,0.55); } 25% { border-color: #a78bfa; box-shadow: 0 0 22px rgba(167,139,250,0.55); } 50% { border-color: #f472b6; box-shadow: 0 0 22px rgba(244,114,182,0.55); } 75% { border-color: #fbbf24; box-shadow: 0 0 22px rgba(251,191,36,0.55); } 100% { border-color: #38bdf8; box-shadow: 0 0 20px rgba(56,189,248,0.55); } }
    @keyframes textGlow { 0%, 100% { text-shadow: 0 0 6px var(--blue-glow); } 50% { text-shadow: 0 0 18px var(--blue-main), 0 0 30px rgba(56,189,248,0.5); } }
    @keyframes titleShine { 0% { background-position: -200% center; } 100% { background-position: 200% center; } }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes slideIn { from { opacity: 0; transform: translateY(20px) scale(0.96); } to { opacity: 1; transform: translateY(0) scale(1); } }
    @keyframes shimmerBar { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
    @keyframes dotPulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(56,189,248,0.7); } 70% { box-shadow: 0 0 0 10px rgba(56,189,248,0); } }
    
    body { background-color: var(--bg-dark); color: var(--text-main); padding-bottom: 30px; min-height: 100vh; background-image: radial-gradient(circle at 50% 0%, #0c1a32 0%, transparent 60%); overflow-x: hidden; position: relative; }
    body::before, body::after { content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0; }
    body::before { background-image: radial-gradient(2px 2px at 15% 20%, rgba(56,189,248,0.45), transparent 50%), radial-gradient(2px 2px at 85% 60%, rgba(167,139,250,0.4), transparent 50%), radial-gradient(1.5px 1.5px at 45% 85%, rgba(56,189,248,0.5), transparent 50%), radial-gradient(1.5px 1.5px at 70% 15%, rgba(244,114,182,0.4), transparent 50%); animation: bgFloat 15s ease-in-out infinite; }
    body::after { background-image: radial-gradient(1px 1px at 10% 50%, rgba(56,189,248,0.3), transparent 50%), radial-gradient(1px 1px at 90% 30%, rgba(167,139,250,0.35), transparent 50%), radial-gradient(1.5px 1.5px at 55% 90%, rgba(244,114,182,0.3), transparent 50%); animation: bgFloat2 20s ease-in-out infinite; }

    .header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; border-bottom: 1px solid var(--border-color); background: rgba(6, 9, 19, 0.85); backdrop-filter: blur(14px); position: sticky; top: 0; z-index: 100; }
    .header-left { display: flex; align-items: center; gap: 10px; }
    .header-live-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--blue-main); animation: dotPulse 1.8s infinite; }
    .header-title { font-size: 20px; font-weight: 900; background: linear-gradient(90deg, #7dd3fc, #38bdf8, #a78bfa, #f472b6, #38bdf8, #7dd3fc); background-size: 300% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; animation: titleShine 4s linear infinite, textGlow 3s infinite; letter-spacing: -0.3px; }
    .btn-reset { position: relative; overflow: hidden; background: rgba(239, 68, 68, 0.1); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 8px 16px; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; transition: all 0.3s ease; }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 20px rgba(239,68,68,0.5); transform: translateY(-1px); }

    .stats-bar { max-width: 600px; margin: 15px auto 0; padding: 0 15px; display: flex; justify-content: space-between; gap: 10px; position: relative; z-index: 1; }
    .stat-item { flex: 1; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px; text-align: center; position: relative; overflow: hidden; transition: all 0.3s; }
    .stat-item:hover { border-color: rgba(56,189,248,0.4); transform: translateY(-2px); }
    .stat-item::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, var(--blue-main), transparent); background-size: 200% 100%; animation: shimmerBar 3s linear infinite; }
    .stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 4px; font-weight: 600; }
    .stat-value { font-size: 20px; font-weight: 900; color: var(--text-main); animation: textGlow 2.5s infinite; }
    .stat-value.win { color: var(--blue-main); }
    .stat-value.lose { color: var(--lose-color); }

    .container { padding: 15px; display: flex; flex-direction: column; gap: 12px; max-width: 600px; margin: 0 auto; position: relative; z-index: 1; max-height: 65vh; overflow-y: auto; }
    .container::-webkit-scrollbar { width: 6px; }
    .container::-webkit-scrollbar-thumb { background: rgba(56,189,248,0.3); border-radius: 3px; }
    .container::-webkit-scrollbar-track { background: transparent; }
    
    .card-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 16px; display: flex; justify-content: space-between; align-items: center; transition: all 0.3s ease; position: relative; animation: slideIn 0.5s ease-out backwards; overflow: hidden; }
    .card-item::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: linear-gradient(180deg, transparent, var(--blue-main), transparent); opacity: 0; transition: opacity 0.3s; }
    .card-item:hover { background: var(--bg-card-hover); transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
    .card-item:hover::before { opacity: 1; }
    .card-item.active { background: linear-gradient(145deg, #0d1424, #0f1a2e); animation: slideIn 0.5s ease-out backwards, rainbow-border 3s linear infinite; border-width: 1.5px; }
    .card-item.active::after { content: '●'; position: absolute; top: 8px; right: 10px; color: var(--blue-main); font-size: 10px; animation: dotPulse 1.5s infinite; }

    .col-left { display: flex; flex-direction: column; gap: 5px; flex: 1.4; }
    .id-text { font-size: 16px; font-weight: 800; color: #fff; letter-spacing: 0.5px; background: linear-gradient(90deg, #fff, #7dd3fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .bot-line { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .bot-label { color: var(--text-muted); font-weight: 600; }
    .bet-badge { padding: 3px 10px; border-radius: 20px; font-weight: 700; font-size: 11px; }
    .bet-tai { background: var(--tai-bet-bg); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); }
    .bet-xiu { background: var(--xiu-bet-bg); color: #f472b6; border: 1px solid rgba(244,114,182,0.3); }
    .conf-text { color: var(--text-muted); font-size: 10.5px; font-style: italic; }
    .conf-bar-wrap { height: 3px; background: rgba(56,189,248,0.12); border-radius: 2px; overflow: hidden; margin-top: 3px;}
    .conf-bar { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #38bdf8, #7dd3fc, #a78bfa, #38bdf8); background-size: 200% 100%; animation: shimmerBar 2s linear infinite; transition: width 0.6s ease; }

    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; flex: 1; }
    .pred-badge { padding: 5px 14px; border-radius: 20px; font-weight: 800; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; transition: all 0.3s; }
    .pred-tai { background: var(--tai-bg); color: #fff; box-shadow: 0 0 12px rgba(2,132,199,0.5); }
    .pred-xiu { background: var(--xiu-bg); color: #fff; box-shadow: 0 0 12px rgba(219,39,119,0.5); }
    .pred-empty { background: transparent; border: 1px dashed var(--border-color); color: var(--text-muted); }
    .dice-text { font-size: 13px; font-weight: 600; color: #cbd5e1; white-space: nowrap; }

    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.7; gap: 3px; }
    .status-text { font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 5px; }
    .status-win { color: var(--win-color); text-shadow: 0 0 12px var(--blue-glow); animation: textGlow 2s infinite; }
    .status-lose { color: var(--lose-color); }
    .status-wait { color: var(--blue-main); }
    .spin { display: inline-block; animation: spin 2s linear infinite; }
    
    .loading { text-align: center; padding: 50px; color: var(--blue-main); font-weight: 600; letter-spacing: 1px; animation: textGlow 2s infinite; }
    @media (max-width: 400px) { .header-title { font-size: 15px; } .stat-value { font-size: 16px; } .dice-text { font-size: 11px; } .id-text { font-size: 14px; } }
</style>
</head>
<body>
<div class="header">
    <div class="header-left">
        <div class="header-live-dot"></div>
        <div class="header-title">⚡ TOOL LCMD5 LEMINH</div>
    </div>
    <button class="btn-reset" onclick="confirmReset()">↻ Reset</button>
</div>
<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng phiên</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Thua</div><div class="stat-value lose" id="stat-lose">0</div></div>
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
        document.getElementById('list-container').innerHTML = '<div class="loading" style="color:var(--lose-color)">Lỗi kết nối Server!</div>';
    }
}
function renderList(rows, stats) {
    const container = document.getElementById('list-container');
    if (stats.total > 0) {
        animateNumber(document.getElementById('stat-total'), stats.total);
        animateNumber(document.getElementById('stat-win'), stats.correct);
        animateNumber(document.getElementById('stat-lose'), stats.lose);
        animateNumber(document.getElementById('stat-rate'), Math.round((stats.correct / stats.total) * 100), '%');
    } else {
        document.getElementById('stat-total').innerText = '0';
        document.getElementById('stat-win').innerText = '0';
        document.getElementById('stat-lose').innerText = '0';
        document.getElementById('stat-rate').innerText = '0%';
    }
    if (!rows.length) {
        container.innerHTML = '<div class="loading">Không có dữ liệu. Hãy đợi phiên mới.</div>';
        return;
    }
    // Chỉ render lại khi cần
    container.innerHTML = '';
    rows.forEach((row, idx) => {
        const div = document.createElement('div');
        div.className = 'card-item' + (row.is_next ? ' active' : '');
        div.style.animationDelay = (idx * 30) + 'ms';
        
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
        if (row.is_next) statusHtml = `<div class="status-text status-wait">Chờ <span class="spin">⏳</span></div>`;
        else if (row.is_correct === true) statusHtml = `<div class="status-text status-win">Đúng ✅</div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status-text status-lose">Sai ❌</div>`;
        else statusHtml = `<div class="status-text" style="color:var(--text-muted)">-</div>`;

        div.innerHTML = `
            <div class="col-left">
                <div class="id-text">#${row.phien}</div>
                <div class="bot-line"><span class="bot-label">Bot:</span> ${betBadge}</div>
                <div class="conf-text">Độ tin cậy: ${row.confidence}%</div>
                <div class="conf-bar-wrap"><div class="conf-bar" style="width:${row.confidence}%"></div></div>
            </div>
            <div class="col-mid">${row.is_next ? predBadge : resultBadge}<div class="dice-text">${diceDisplay}</div></div>
            <div class="col-right">${statusHtml}</div>
        `;
        container.appendChild(div);
    });
}
async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', 
        html: "Toàn bộ <b>lịch sử + thống kê</b> sẽ bị xóa.<br>Hệ thống đếm lại <b>từ 0</b>!",
        icon: 'warning',
        showCancelButton: true, confirmButtonColor: '#38bdf8', cancelButtonColor: '#1e293b', 
        confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Reset thành công!', text: 'Đã xóa log, bắt đầu lại từ phiên #' + data.reset_to, icon: 'success', confirmButtonColor: '#38bdf8' });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire('Lỗi!', 'Không thể reset: ' + error.message, 'error'); isResetting = false;
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
# HELPER - 81 MẪU
# =====================================================================
def build_blocks(results):
    if not results: return []
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
    return blocks

def block_class(L):
    if L == 1: return 'S'
    if L <= 3: return 'M'
    return 'L'

def encode_pattern_81(block_lengths):
    if len(block_lengths) < 4: return None
    code = 0
    for L in block_lengths[-4:]:
        code = code * 3 + {'S': 0, 'M': 1, 'L': 2}[block_class(L)]
    return code

def learn_81_patterns(results):
    stats = {}
    n = len(results)
    for k in range(10, n):
        sub = results[k:]
        blocks = build_blocks(sub)
        if len(blocks) < 5: continue
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        if code is None: continue
        current_val = blocks[0]['val']
        current_len = blocks[0]['len']
        actual_next = results[k - 1]
        continued = (actual_next == current_val)
        
        key1 = (code, min(current_len, 4))
        if key1 not in stats: stats[key1] = {'continue': 0, 'break': 0}
        stats[key1]['continue' if continued else 'break'] += 1
        
        key2 = code
        if key2 not in stats: stats[key2] = {'continue': 0, 'break': 0}
        stats[key2]['continue' if continued else 'break'] += 1
    return stats

# =====================================================================
# THUẬT TOÁN V8.0 - 12 TẦNG
# =====================================================================
def analyze_pattern(results, dice_sums=None, adaptive_boost=1.0):
    if not results or len(results) < 3:
        return "Tài", 50.0
    
    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    n = len(results)
    candidates = []  # (winner, conf, sample_size, weight)
    
    blocks = build_blocks(results)
    current_val = blocks[0]['val']
    current_len = blocks[0]['len']
    
    # === 1. CẦU BỆT (progressive) ===
    if current_len >= 10:    candidates.append((opposite, 96.0, 60, 2.0))
    elif current_len >= 8:   candidates.append((opposite, 92.0, 55, 1.8))
    elif current_len >= 6:   candidates.append((opposite, 85.0, 45, 1.5))
    elif current_len == 5:   candidates.append((opposite, 74.0, 35, 1.2))
    elif current_len == 4:   candidates.append((current_val, 62.0, 30, 0.9))
    elif current_len == 3:   candidates.append((current_val, 56.0, 25, 0.6))
    
    # === 2. ĐẢO 1-1 ===
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]: alt_len += 1
        else: break
    if alt_len >= 12:    candidates.append((opposite, 95.0, 50, 1.9))
    elif alt_len >= 10:  candidates.append((opposite, 92.0, 45, 1.7))
    elif alt_len >= 7:   candidates.append((opposite, 84.0, 35, 1.4))
    elif alt_len >= 5:   candidates.append((opposite, 76.0, 28, 1.1))
    elif alt_len >= 3:   candidates.append((opposite, 65.0, 20, 0.7))
    
    # === 3. ĐẢO KHỐI (2-2, 3-3, 1-2-1, 2-1-2) ===
    if len(blocks) >= 3:
        is_alt = all(blocks[i]['val'] != blocks[i-1]['val'] for i in range(1, min(len(blocks), 8)))
        if is_alt:
            p1, p2 = blocks[1]['len'], blocks[2]['len']
            if p1 == p2 and p1 >= 2:
                cycle = p1
                if current_len < cycle: candidates.append((current_val, 92.0, 40, 1.8))
                elif current_len == cycle: candidates.append((opposite, 95.0, 45, 2.0))
                else: candidates.append((opposite, 75.0, 30, 1.2))
            if len(blocks) >= 4:
                p3 = blocks[3]['len']
                if p1 == p3 and p2 != p1 and p1 <= 5:
                    candidates.append((opposite, 85.0, 35, 1.5))
                if p2 == p3 and p1 != p2 and p2 <= 5:
                    candidates.append((opposite, 78.0, 30, 1.2))
    
    # === 4. HỆ THỐNG 81 MẪU (Laplace Smoothing) ===
    if len(blocks) >= 5:
        stats = learn_81_patterns(results)
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        if code is not None:
            for key in [(code, min(current_len, 4)), code]:
                if key in stats:
                    s = stats[key]
                    total = s['continue'] + s['break']
                    if total >= 2:
                        # Laplace smoothing
                        cont_rate = (s['continue'] + 1) / (total + 2)
                        conf_val = 50 + abs(cont_rate - 0.5) * 100
                        if cont_rate >= 0.63:
                            candidates.append((current_val, min(conf_val, 90), total, 1.4))
                        elif cont_rate <= 0.37:
                            candidates.append((opposite, min(conf_val, 90), total, 1.4))
                        break
    
    # === 5. N-GRAM (dò lịch sử) ===
    for ns in [10, 8, 7, 6, 5, 4]:
        if n < ns + 1: continue
        current_seq = tuple(results[:ns])
        match_tai, match_xiu = 0, 0
        for i in range(len(results) - ns):
            if tuple(results[i:i+ns]) == current_seq and i + ns < len(results):
                if results[i+ns] == "Tài": match_tai += 1
                else: match_xiu += 1
        total_m = match_tai + match_xiu
        if total_m >= 2 and match_tai != match_xiu:
            winner = "Tài" if match_tai > match_xiu else "Xỉu"
            ratio = max(match_tai, match_xiu) / total_m
            if ratio >= 0.6:
                weight = 0.8 + ns / 12.0
                candidates.append((winner, 55 + ratio * 25, total_m, weight))
                break
    
    # === 6. MARKOV TRANSITION ===
    if n >= 10:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 1):
            if results[i] == last: trans[results[i + 1]] += 1
        total_t = trans["Tài"] + trans["Xỉu"]
        if total_t >= 3 and trans["Tài"] != trans["Xỉu"]:
            winner = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            ratio = max(trans["Tài"], trans["Xỉu"]) / total_t
            candidates.append((winner, 58 + ratio * 20, total_t, 1.0))
    
    # === 7. DICE BIAS ===
    if dice_sums and len(dice_sums) >= 5:
        avg_recent = sum(dice_sums[:10]) / min(10, len(dice_sums))
        if avg_recent >= 12.0: candidates.append(("Tài", 62.0, 10, 0.8))
        elif avg_recent <= 8.5: candidates.append(("Xỉu", 62.0, 10, 0.8))
    
    # === 8. MOMENTUM ===
    if n >= 10:
        r5_tai = results[:5].count("Tài")
        r10_tai = results[:10].count("Tài")
        if r5_tai >= 4 and r10_tai <= 5: candidates.append(("Xỉu", 62.0, 10, 0.9))
        elif r5_tai <= 1 and r10_tai >= 5: candidates.append(("Tài", 62.0, 10, 0.9))
    
    # === 9. ZIGZAG NGẮN ===
    if n >= 4:
        if results[0] != results[1] and results[1] != results[2] and results[2] != results[3]:
            candidates.append((opposite, 70.0, 8, 0.8))
    
    # === 10. SKEW DETECTION (cầu nghiêng 20 phiên) ===
    if n >= 20:
        tai_ratio = results[:20].count("Tài") / 20
        if tai_ratio >= 0.65:
            candidates.append(("Xỉu", 63.0, 20, 1.0))
        elif tai_ratio <= 0.35:
            candidates.append(("Tài", 63.0, 20, 1.0))
    
    # === 11. STREAK-AWARE (đang có streak dài) ===
    if current_len >= 3:
        # Nếu 3 phiên vừa rồi cùng kết quả → tăng nhẹ weight cho bẻ
        candidates.append((opposite, 58.0, 5, 0.5))
    
    # === 12. DRAGON-TIGER (T-X alternation sâu) ===
    if n >= 6:
        seg = results[:6]
        if all(seg[i] != seg[i+1] for i in range(5)):
            candidates.append((opposite, 72.0, 6, 1.0))
    
    # === VOTING ===
    if not candidates:
        return opposite, 53.0
    
    tai_score = sum(c[1] * c[3] for c in candidates if c[0] == "Tài")
    xiu_score = sum(c[1] * c[3] for c in candidates if c[0] == "Xỉu")
    
    if tai_score == xiu_score:
        return opposite, round(min(97.5, 53.0 * adaptive_boost), 1)
    
    winner = "Tài" if tai_score > xiu_score else "Xỉu"
    winner_score = max(tai_score, xiu_score)
    total_score = tai_score + xiu_score
    agree_ratio = winner_score / total_score
    
    best_conf = max((c[1] for c in candidates if c[0] == winner), default=55.0)
    final_conf = best_conf * (0.72 + agree_ratio * 0.28)
    final_conf *= adaptive_boost
    
    return winner, round(min(97.5, final_conf), 1)

# =====================================================================
# ADAPTIVE BOOST - Dựa trên accuracy 15 phiên gần
# =====================================================================
def get_adaptive_boost():
    with LOG_LOCK:
        recent = [(p, rec) for p, rec in PREDICTION_LOG.items() 
                  if p > RESET_SESSION_ID and rec.get('is_correct') is not None]
    if len(recent) < 10:
        return 1.0
    recent.sort(key=lambda x: x[0])
    recent = recent[-15:]
    acc = sum(1 for _, r in recent if r['is_correct']) / len(recent)
    if acc >= 0.70: return 1.05
    if acc >= 0.60: return 1.02
    if acc <= 0.40: return 0.92
    if acc <= 0.50: return 0.97
    return 1.0

# =====================================================================
# FETCH DỮ LIỆU
# =====================================================================
def generate_fallback(base=7116040):
    elapsed = int(time.time() / 60)
    current = base + elapsed
    random.seed(elapsed)
    rows = []
    for i in range(40):
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
                    res_raw = str(item.get('resultTruyenThong', '')).upper().strip()
                    res = "Tài" if res_raw == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
                    total = item.get('point', sum(dices))
                    rows.append({'phien': int(item['id']), 'result': res, 'dice': dice_str, 'total': total})
                return rows, 'live'
    except Exception as e:
        print(f"[API ERROR] {e}")
    return generate_fallback(), 'fallback'

# =====================================================================
# LOG UPDATE - TÍCH LŨY VÔ HẠN
# =====================================================================
def update_prediction_log(valid):
    """
    Cập nhật log cho từng phiên chưa có.
    Prediction được tính 1 lần duy nhất từ history trước phiên đó.
    -> Đảm bảo đúng/sai CHUẨN XÁC (không leak future).
    """
    with LOG_LOCK:
        for i, sess in enumerate(valid):
            phien = sess['phien']
            if phien in PREDICTION_LOG:
                continue
            history = [v['result'] for v in valid[:i]][::-1]
            dice = [v.get('total', 0) for v in valid[:i]][::-1]
            if len(history) < 3:
                continue
            pred, conf = analyze_pattern(history, dice)
            PREDICTION_LOG[phien] = {
                'prediction': pred,
                'result': sess['result'],
                'confidence': conf,
                'is_correct': (pred == sess['result'])
            }

def compute_stats():
    with LOG_LOCK:
        total = 0
        correct = 0
        for phien, rec in PREDICTION_LOG.items():
            if phien > RESET_SESSION_ID and rec.get('is_correct') is not None:
                total += 1
                if rec['is_correct']:
                    correct += 1
    return total, correct

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
        
        # Cập nhật log tích lũy
        update_prediction_log(valid)
        
        # Stats vô hạn từ log
        total_past, correct_count = compute_stats()
        
        # Prediction cho phiên TIẾP THEO (dùng adaptive boost)
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        boost = get_adaptive_boost()
        next_pred, next_conf = analyze_pattern(history_for_next, dice_for_next, boost)
        
        out = [{
            'phien': next_phien, 'is_next': True, 'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None
        }]
        
        # Hiển thị 50 phiên gần nhất (không giới hạn stats)
        MAX_DISPLAY = 50
        displayed = 0
        with LOG_LOCK:
            for i in range(len(valid) - 1, -1, -1):
                if displayed >= MAX_DISPLAY: break
                current_session = valid[i]
                if current_session['phien'] <= RESET_SESSION_ID: break
                
                phien = current_session['phien']
                rec = PREDICTION_LOG.get(phien)
                if rec:
                    out.append({
                        'phien': phien, 'is_next': False,
                        'prediction': rec['prediction'], 'confidence': rec['confidence'],
                        'result': rec['result'], 'dice': current_session['dice'],
                        'is_correct': rec['is_correct']
                    })
                    displayed += 1
        
        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count, 'lose': total_past - correct_count}
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict')
def predict_only():
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404
        
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        boost = get_adaptive_boost()
        next_pred, next_conf = analyze_pattern(history_for_next, dice_for_next, boost)
        
        return jsonify({
            'status': 'success', 'next_session': next_phien, 'prediction': next_pred,
            'confidence': next_conf, 'adaptive_boost': round(boost, 3),
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID, PREDICTION_LOG
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if valid:
            RESET_SESSION_ID = valid[-1]['phien']
            with LOG_LOCK:
                PREDICTION_LOG = {}  # XÓA LOG → đếm lại từ 0
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
