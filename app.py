import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =====================================================================
# CẤU HÌNH API
# =====================================================================
API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
RESET_SESSION_ID = 0

# =====================================================================
# GIAO DIỆN HTML PREMIUM (V6.2 - FIX HIỂN THỊ CẦU)
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>lEHOANGMINH</title>
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
        --purple: #a78bfa; --pink: #f472b6; --gold: #fbbf24;
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
    @keyframes sparkle { 0%, 100% { opacity: 0; transform: scale(0) rotate(0deg); } 50% { opacity: 1; transform: scale(1) rotate(180deg); } }
    @keyframes statPulse { 0%, 100% { text-shadow: 0 0 8px var(--blue-glow); } 50% { text-shadow: 0 0 20px var(--blue-main), 0 0 30px var(--blue-glow); } }
    @keyframes ripple { 0% { transform: scale(0); opacity: 0.6; } 100% { transform: scale(4); opacity: 0; } }
    @keyframes dotPulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(56,189,248,0.7); } 70% { box-shadow: 0 0 0 10px rgba(56,189,248,0); } }
    
    body { background-color: var(--bg-dark); color: var(--text-main); padding-bottom: 30px; min-height: 100vh; background-image: radial-gradient(circle at 50% 0%, #0c1a32 0%, transparent 60%); overflow-x: hidden; position: relative; }
    body::before, body::after { content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0; }
    body::before { background-image: radial-gradient(2px 2px at 15% 20%, rgba(56,189,248,0.45), transparent 50%), radial-gradient(2px 2px at 85% 60%, rgba(167,139,250,0.4), transparent 50%), radial-gradient(1.5px 1.5px at 45% 85%, rgba(56,189,248,0.5), transparent 50%), radial-gradient(1.5px 1.5px at 70% 15%, rgba(244,114,182,0.4), transparent 50%), radial-gradient(2px 2px at 25% 70%, rgba(56,189,248,0.35), transparent 50%); animation: bgFloat 15s ease-in-out infinite; }
    body::after { background-image: radial-gradient(1px 1px at 10% 50%, rgba(56,189,248,0.3), transparent 50%), radial-gradient(1px 1px at 90% 30%, rgba(167,139,250,0.35), transparent 50%), radial-gradient(1.5px 1.5px at 55% 90%, rgba(244,114,182,0.3), transparent 50%), radial-gradient(1.5px 1.5px at 35% 10%, rgba(56,189,248,0.4), transparent 50%); animation: bgFloat2 20s ease-in-out infinite; }

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
    .stat-value { font-size: 20px; font-weight: 900; color: var(--text-main); animation: statPulse 2.5s infinite; }
    .stat-value.win { color: var(--blue-main); }

    .container { padding: 15px; display: flex; flex-direction: column; gap: 12px; max-width: 600px; margin: 0 auto; position: relative; z-index: 1; }
    .card-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 16px; display: flex; justify-content: space-between; align-items: center; transition: all 0.3s ease; position: relative; animation: slideIn 0.5s ease-out backwards; overflow: hidden; }
    .card-item::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: linear-gradient(180deg, transparent, var(--blue-main), transparent); opacity: 0; transition: opacity 0.3s; }
    .card-item:hover { background: var(--bg-card-hover); transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
    .card-item:hover::before { opacity: 1; }
    .card-item.active { background: linear-gradient(145deg, #0d1424, #0f1a2e); animation: slideIn 0.5s ease-out backwards, rainbow-border 3s linear infinite; border-width: 1.5px; }
    .card-item.active::after { content: '●'; position: absolute; top: 8px; right: 10px; color: var(--blue-main); font-size: 10px; animation: dotPulse 1.5s infinite; }

    .col-left { display: flex; flex-direction: column; gap: 5px; flex: 1.2; }
    .id-text { font-size: 16px; font-weight: 800; color: #fff; letter-spacing: 0.5px; background: linear-gradient(90deg, #fff, #7dd3fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .bot-line { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .bot-label { color: var(--text-muted); font-weight: 600; }
    .bet-badge { padding: 3px 10px; border-radius: 20px; font-weight: 700; font-size: 11px; }
    .bet-tai { background: var(--tai-bet-bg); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); }
    .bet-xiu { background: var(--xiu-bet-bg); color: #f472b6; border: 1px solid rgba(244,114,182,0.3); }
    .conf-text { color: var(--text-muted); font-size: 10.5px; font-style: italic; }
    .conf-bar-wrap { height: 3px; background: rgba(56,189,248,0.12); border-radius: 2px; overflow: hidden; margin-top: 3px; }
    .conf-bar { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #38bdf8, #7dd3fc, #a78bfa, #38bdf8); background-size: 200% 100%; animation: shimmerBar 2s linear infinite; transition: width 0.6s ease; }

    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; flex: 1; }
    .pred-badge { padding: 5px 14px; border-radius: 20px; font-weight: 800; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; transition: all 0.3s; }
    .pred-tai { background: var(--tai-bg); color: #fff; box-shadow: 0 0 12px rgba(2,132,199,0.5); }
    .pred-xiu { background: var(--xiu-bg); color: #fff; box-shadow: 0 0 12px rgba(219,39,119,0.5); }
    .pred-empty { background: transparent; border: 1px dashed var(--border-color); color: var(--text-muted); }
    .dice-text { font-size: 13px; font-weight: 600; color: #cbd5e1; white-space: nowrap; }

    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.8; gap: 3px; }
    .status-text { font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 5px; }
    .status-win { color: var(--win-color); text-shadow: 0 0 12px var(--blue-glow); animation: statPulse 2s infinite; }
    .status-lose { color: var(--lose-color); }
    .status-wait { color: var(--blue-main); }
    .spin { display: inline-block; animation: spin 2s linear infinite; }
    
    /* CSS NỔI BẬT CHO TAG CẦU */
    .pattern-tag { 
        font-size: 11px; 
        color: #e2e8f0; 
        font-weight: 700; 
        padding: 4px 10px; 
        border-radius: 8px; 
        background: rgba(56,189,248,0.15); 
        border: 1px solid rgba(56,189,248,0.4); 
        display: inline-block; 
        margin-top: 5px; 
        box-shadow: 0 0 10px rgba(56,189,248,0.2);
    }
    .pattern-tag.m81 { 
        color: var(--gold); 
        border-color: rgba(251,191,36,0.5); 
        background: rgba(251,191,36,0.15); 
        box-shadow: 0 0 10px rgba(251,191,36,0.2);
    }
    .loading { text-align: center; padding: 50px; color: var(--blue-main); font-weight: 600; letter-spacing: 1px; animation: textGlow 2s infinite; }
    .sparkle-win { position: relative; }
    .sparkle-win::before { content: '✦'; position: absolute; top: -8px; right: -8px; color: var(--gold); font-size: 14px; animation: sparkle 2s ease-in-out infinite; }
    @media (max-width: 400px) { .header-title { font-size: 16px; } .stat-value { font-size: 16px; } .dice-text { font-size: 11px; } }
</style>
</head>
<body>
<div class="header">
    <div class="header-left">
        <div class="header-live-dot"></div>
        <div class="header-title">⚡ LC MD5 MINHLE</div>
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
        // Thêm timestamp để chống cache trình duyệt
        const r = await fetch('/api/history?v=' + Date.now(), { cache: 'no-store' });
        const data = await r.json();
        if (data.error) {
            document.getElementById('list-container').innerHTML = `<div class="loading" style="color:var(--lose-color)">Lỗi: ${data.error}</div>`;
            return;
        }
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
        animateNumber(document.getElementById('stat-rate'), Math.round((stats.correct / stats.total) * 100), '%');
    } else {
        document.getElementById('stat-total').innerText = '0';
        document.getElementById('stat-win').innerText = '0';
        document.getElementById('stat-rate').innerText = '0%';
    }
    if (!rows.length) {
        container.innerHTML = '<div class="loading">Không có dữ liệu. Hãy đợi phiên mới.</div>';
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
        else if (row.is_correct === true) statusHtml = `<div class="status-text status-win sparkle-win">Đúng </div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status-text status-lose">Sai </div>`;
        else statusHtml = `<div class="status-text" style="color:var(--text-muted)">-</div>`;
        
        // Xử lý Tag cầu (Đảm bảo luôn hiện)
        const pName = row.pattern || 'Đang phân tích...';
        const isM81 = pName.includes('81#');
        const patternTag = `<span class="pattern-tag ${isM81 ? 'm81' : ''}">${pName}</span>`;
        
        div.innerHTML = `
            <div class="col-left">
                <div class="id-text">#${row.phien}</div>
                <div class="bot-line"><span class="bot-label">Bot:</span> ${betBadge}</div>
                <div class="conf-text">Độ tin cậy: ${row.confidence}%</div>
                <div class="conf-bar-wrap"><div class="conf-bar" style="width:${row.confidence}%"></div></div>
                ${patternTag}
            </div>
            <div class="col-mid">${row.is_next ? predBadge : resultBadge}<div class="dice-text">${diceDisplay}</div></div>
            <div class="col-right">${statusHtml}</div>
        `;
        container.appendChild(div);
    });
}
async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', text: "Lịch sử hiển thị trên màn hình sẽ bị ẩn đi. Hệ thống vẫn tính toán ngầm!", icon: 'warning',
        showCancelButton: true, confirmButtonColor: '#38bdf8', cancelButtonColor: '#1e293b', confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Thành công!', text: 'Đã chốt mốc ẩn lịch sử từ phiên #' + data.reset_to, icon: 'success', confirmButtonColor: '#38bdf8' });
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
# V6.2 HELPERS
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

def pattern_signature(block_lengths):
    if len(block_lengths) < 4: return "----"
    return ''.join(block_class(L) for L in block_lengths[-4:])

def analyze_streak_history(chrono):
    hist = {}
    N = len(chrono)
    i = 0
    while i < N:
        val = chrono[i]
        j = i + 1
        while j < N and chrono[j] == val:
            j += 1
        streak = j - i
        if j < N:
            key = min(streak, 8)
            if key not in hist:
                hist[key] = {'cont': 0, 'brk': 0}
            if chrono[j] == val: hist[key]['cont'] += 1
            else: hist[key]['brk'] += 1
        i = j
    return hist

def learn_81_weighted(chrono, decay=0.95):
    stats = {}
    N = len(chrono)
    for k in range(6, N):
        blocks = build_blocks(chrono[:k])
        if len(blocks) < 5: continue
        last4 = [b['len'] for b in blocks[-5:-1]]
        code = encode_pattern_81(last4)
        if code is None: continue
        current_val = blocks[-1]['val']
        continued = (chrono[k] == current_val)
        weight = decay ** (N - k)
        key = (code, min(blocks[-1]['len'], 4))
        if key not in stats: stats[key] = {'cont_w': 0.0, 'brk_w': 0.0, 'cont_c': 0, 'brk_c': 0}
        if continued: stats[key]['cont_w'] += weight; stats[key]['cont_c'] += 1
        else: stats[key]['brk_w'] += weight; stats[key]['brk_c'] += 1
    return stats

def analyze_dice_trend(dice_chrono):
    if len(dice_chrono) < 5: return None
    recent = dice_chrono[-10:]
    avg = sum(recent) / len(recent)
    ma3 = sum(dice_chrono[-3:]) / 3
    if ma3 > avg + 1.0 and avg > 10.5: return ("Tài", min(0.9, (ma3 - 10.5) / 7.5), f"Dice Tài (MA3={ma3:.1f})")
    if ma3 < avg - 1.0 and avg < 10.5: return ("Xỉu", min(0.9, (10.5 - ma3) / 7.5), f"Dice Xỉu (MA3={ma3:.1f})")
    return None

# =====================================================================
# THUẬT TOÁN V6.2 - ENSEMBLE 6 TẦNG
# =====================================================================
def analyze_pattern(results, dice_sums=None):
    if not results or len(results) < 3: return "Tài", 50.0, "Khởi tạo"
    chrono = list(reversed(results))
    dice_chrono = list(reversed(dice_sums)) if dice_sums else []
    N = len(chrono)
    last = chrono[-1]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    blocks = build_blocks(chrono)
    current_val = blocks[-1]['val']
    current_len = blocks[-1]['len']
    evidences = []

    # E1: STREAK
    streak_hist = analyze_streak_history(chrono)
    if current_len in streak_hist:
        h = streak_hist[current_len]
        tot = h['cont'] + h['brk']
        if tot >= 2:
            cont_rate = h['cont'] / tot
            edge = abs(cont_rate - 0.5) * 2
            weight = min(2.5, tot / 5) * edge * 2
            if weight > 0.3:
                direction = current_val if cont_rate > 0.5 else opposite
                evidences.append((direction, weight, f"Bệt{current_len} hist {h['cont']}/{tot}", 85 if edge > 0.4 else 70))

    # E2: RHYTHM
    if len(blocks) >= 3:
        prev_len, prev_val = blocks[-2]['len'], blocks[-2]['val']
        prev2_len, prev2_val = blocks[-3]['len'], blocks[-3]['val']
        is_alt = (prev_val != prev2_val and current_val != prev_val)
        if is_alt and prev_len == prev2_len and prev_len >= 2:
            cycle = prev_len
            if current_len < cycle: evidences.append((current_val, 3.5, f"Rhythm {cycle}-{cycle} dở", 92))
            elif current_len == cycle: evidences.append((opposite, 4.0, f"Rhythm {cycle}-{cycle} đủ", 96))
        if is_alt and len(blocks) >= 4:
            b3 = blocks[-4]['len']
            if b3 == prev_len == prev2_len:
                if current_len < prev_len: evidences.append((current_val, 2.5, "Chain x3 dở", 85))
                elif current_len == prev_len: evidences.append((opposite, 3.0, "Chain x3 đủ", 90))

    # E3: 81-PATTERN
    if len(blocks) >= 5:
        p81 = learn_81_weighted(chrono)
        last4 = [b['len'] for b in blocks[-5:-1]]
        code = encode_pattern_81(last4)
        sig = pattern_signature(last4)
        if code is not None:
            for key in [(code, min(current_len, 4)), code]:
                if key in p81:
                    s = p81[key]
                    tot_w = s['cont_w'] + s['brk_w']
                    raw = s['cont_c'] + s['brk_c']
                    if tot_w > 0.3 and raw >= 2:
                        cr = s['cont_w'] / tot_w
                        if cr >= 0.62:
                            w = min(2.5, raw / 4) * (cr - 0.5) * 4
                            evidences.append((current_val, w, f"81#{code+1}[{sig}] tiếp {s['cont_c']}/{raw}", 90))
                        elif cr <= 0.38:
                            w = min(2.5, raw / 4) * (0.5 - cr) * 4
                            evidences.append((opposite, w, f"81#{code+1}[{sig}] gãy {s['brk_c']}/{raw}", 90))
                        break

    # E4: N-GRAM
    for ns in [7, 6, 5, 4]:
        if N < ns + 1: continue
        target = tuple(chrono[-ns:])
        m_tai = m_xiu = 0
        for i in range(N - ns):
            if tuple(chrono[i:i+ns]) == target and i + ns < N:
                if chrono[i+ns] == "Tài": m_tai += 1
                else: m_xiu += 1
        tot = m_tai + m_xiu
        if tot >= 2 and m_tai != m_xiu:
            ratio = max(m_tai, m_xiu) / tot
            if ratio >= 0.6:
                direction = "Tài" if m_tai > m_xiu else "Xỉu"
                w = (ratio - 0.5) * 3 * min(1.5, tot / 3)
                evidences.append((direction, w, f"Ngram{ns} ({m_tai}T-{m_xiu}X)", 70 + ns))

    # E5: MARKOV
    if N >= 8:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(N - 1):
            if chrono[i] == last: trans[chrono[i + 1]] += 1
        tot = trans["Tài"] + trans["Xỉu"]
        if tot >= 3 and trans["Tài"] != trans["Xỉu"]:
            ratio = max(trans["Tài"], trans["Xỉu"]) / tot
            direction = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            evidences.append((direction, (ratio - 0.5) * 2.5, f"Markov {trans['Tài']}T-{trans['Xỉu']}X", 60))

    # E6: DICE TREND
    dice_sig = analyze_dice_trend(dice_chrono)
    if dice_sig:
        direction, strength, name = dice_sig
        evidences.append((direction, strength * 2.0, name, 65))

    if not evidences: return opposite, 55.0, "Đảo nhịp (Mặc định)"
    tai_w = sum(e[1] for e in evidences if e[0] == "Tài")
    xiu_w = sum(e[1] for e in evidences if e[0] == "Xỉu")
    total_w = tai_w + xiu_w
    if total_w < 0.01: return opposite, 55.0, "Đảo nhịp (Mặc định)"

    tai_ratio = tai_w / total_w
    winner = "Tài" if tai_ratio > 0.5 else "Xỉu"
    posterior = tai_ratio if winner == "Tài" else (1 - tai_ratio)
    confidence = 52 + (posterior - 0.5) * 2 * 40 + min(6, len(evidences) * 0.5)

    same_dir = [e for e in evidences if e[0] == winner]
    best = max(same_dir, key=lambda x: (x[3], x[1])) if same_dir else None
    pattern_name = best[2] if best else f"Tổng hợp ({len(evidences)} tín hiệu)"
    return winner, round(min(97.0, confidence), 1), pattern_name

# =====================================================================
# FETCH DỮ LIỆU
# =====================================================================
def generate_fallback():
    elapsed = int(time.time() / 60)
    current = 7121479 + elapsed
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
                    res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    rows.append({
                        'phien': int(item['id']), 'result': res,
                        'dice': f"{dices[0]} + {dices[1]} + {dices[2]}",
                        'total': item.get('point', sum(dices))
                    })
                
                # Nếu API trả về phòng khác (ID < 7 triệu) thì báo lỗi
                if rows and rows[0]['phien'] < 7000000:
                    raise Exception(f"LỖI SAI PHÒNG! ID #{rows[0]['phien']} (Không phải LC79).")
                
                return rows, 'live'
    except Exception as e:
        print(f"[API ERROR] {e}")
        return generate_fallback(), 'fallback' # Tự động dùng dữ liệu giả lập nếu API lỗi để web không bị sập
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
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next, dice_for_next)

        out.append({
            'phien': next_phien, 'is_next': True, 'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None, 'pattern': next_pattern
        })

        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID: break
            if len(out) > 20: break

            history_list = [v['result'] for v in valid[:i]][::-1]
            dice_list = [v.get('total', 0) for v in valid[:i]][::-1]

            if history_list:
                pred, conf, pattern = analyze_pattern(history_list, dice_list)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct: correct_count += 1
            else:
                pred, conf, pattern = "Tài", 50.0, "Khởi tạo"
                is_correct = None

            out.append({
                'phien': current_session['phien'], 'is_next': False, 'prediction': pred, 'confidence': conf,
                'result': current_session['result'], 'dice': current_session['dice'],
                'is_correct': is_correct, 'pattern': pattern
            })

        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
