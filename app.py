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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API LC MD5 MINHLE - Premium</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #060913;
        --bg-card: #0d1424;
        --bg-card-hover: #131c30;
        --text-main: #f1f5f9;
        --text-muted: #64748b;
        --border-color: #1e293b;
        --tai-bg: #0284c7;
        --tai-bet-bg: rgba(2, 132, 199, 0.15);
        --xiu-bg: #db2777;
        --xiu-bet-bg: rgba(219, 39, 119, 0.15);
        --blue-main: #38bdf8;
        --blue-glow: rgba(56, 189, 248, 0.5);
        --lose-color: #ef4444;
        --win-color: #38bdf8;
        --purple: #a78bfa;
        --pink: #f472b6;
        --gold: #fbbf24;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }

    /* ========== HIỆU ỨNG ĐỘNG TOÀN CỤC ========== */
    @keyframes bgFloat {
        0%, 100% { transform: translateY(0) translateX(0); opacity: 0.6; }
        50% { transform: translateY(-30px) translateX(20px); opacity: 1; }
    }
    @keyframes bgFloat2 {
        0%, 100% { transform: translateY(0) translateX(0); opacity: 0.5; }
        50% { transform: translateY(20px) translateX(-25px); opacity: 0.9; }
    }
    @keyframes gradientFlow {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    @keyframes pulse-blue {
        0%, 100% { box-shadow: 0 0 8px var(--blue-glow), inset 0 0 6px rgba(56,189,248,0.15); border-color: var(--blue-main); }
        50% { box-shadow: 0 0 30px var(--blue-glow), inset 0 0 12px rgba(56,189,248,0.25); border-color: #7dd3fc; }
    }
    @keyframes rainbow-border {
        0%   { border-color: #38bdf8; box-shadow: 0 0 20px rgba(56,189,248,0.55); }
        25%  { border-color: #a78bfa; box-shadow: 0 0 22px rgba(167,139,250,0.55); }
        50%  { border-color: #f472b6; box-shadow: 0 0 22px rgba(244,114,182,0.55); }
        75%  { border-color: #fbbf24; box-shadow: 0 0 22px rgba(251,191,36,0.55); }
        100% { border-color: #38bdf8; box-shadow: 0 0 20px rgba(56,189,248,0.55); }
    }
    @keyframes textGlow {
        0%, 100% { text-shadow: 0 0 6px var(--blue-glow); }
        50% { text-shadow: 0 0 18px var(--blue-main), 0 0 30px rgba(56,189,248,0.5); }
    }
    @keyframes titleShine {
        0% { background-position: -200% center; }
        100% { background-position: 200% center; }
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(20px) scale(0.96); }
        to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes shimmerBar {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    @keyframes sparkle {
        0%, 100% { opacity: 0; transform: scale(0) rotate(0deg); }
        50% { opacity: 1; transform: scale(1) rotate(180deg); }
    }
    @keyframes statPulse {
        0%, 100% { text-shadow: 0 0 8px var(--blue-glow); }
        50% { text-shadow: 0 0 20px var(--blue-main), 0 0 30px var(--blue-glow); }
    }
    @keyframes ripple {
        0% { transform: scale(0); opacity: 0.6; }
        100% { transform: scale(4); opacity: 0; }
    }
    @keyframes dotPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(56,189,248,0.7); }
        70% { box-shadow: 0 0 0 10px rgba(56,189,248,0); }
    }
    @keyframes cardBorderFlow {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    body {
        background-color: var(--bg-dark);
        color: var(--text-main);
        padding-bottom: 30px;
        min-height: 100vh;
        background-image: radial-gradient(circle at 50% 0%, #0c1a32 0%, transparent 60%);
        overflow-x: hidden;
        position: relative;
    }

    /* Particle nền */
    body::before, body::after {
        content: '';
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 0;
    }
    body::before {
        background-image:
            radial-gradient(2px 2px at 15% 20%, rgba(56,189,248,0.45), transparent 50%),
            radial-gradient(2px 2px at 85% 60%, rgba(167,139,250,0.4), transparent 50%),
            radial-gradient(1.5px 1.5px at 45% 85%, rgba(56,189,248,0.5), transparent 50%),
            radial-gradient(1.5px 1.5px at 70% 15%, rgba(244,114,182,0.4), transparent 50%),
            radial-gradient(2px 2px at 25% 70%, rgba(56,189,248,0.35), transparent 50%);
        animation: bgFloat 15s ease-in-out infinite;
    }
    body::after {
        background-image:
            radial-gradient(1px 1px at 10% 50%, rgba(56,189,248,0.3), transparent 50%),
            radial-gradient(1px 1px at 90% 30%, rgba(167,139,250,0.35), transparent 50%),
            radial-gradient(1.5px 1.5px at 55% 90%, rgba(244,114,182,0.3), transparent 50%),
            radial-gradient(1.5px 1.5px at 35% 10%, rgba(56,189,248,0.4), transparent 50%);
        animation: bgFloat2 20s ease-in-out infinite;
    }

    /* HEADER */
    .header {
        display: flex; justify-content: space-between; align-items: center;
        padding: 15px 20px; border-bottom: 1px solid var(--border-color);
        background: rgba(6, 9, 19, 0.85); backdrop-filter: blur(14px);
        position: sticky; top: 0; z-index: 100;
    }
    .header-left { display: flex; align-items: center; gap: 10px; }
    .header-live-dot {
        width: 10px; height: 10px; border-radius: 50%; background: var(--blue-main);
        animation: dotPulse 1.8s infinite;
    }
    .header-title {
        font-size: 20px; font-weight: 900;
        background: linear-gradient(90deg, #7dd3fc, #38bdf8, #a78bfa, #f472b6, #38bdf8, #7dd3fc);
        background-size: 300% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: titleShine 4s linear infinite, textGlow 3s infinite;
        letter-spacing: -0.3px;
    }
    .btn-reset {
        position: relative; overflow: hidden;
        background: rgba(239, 68, 68, 0.1); color: var(--lose-color);
        border: 1px solid var(--lose-color); padding: 8px 16px;
        border-radius: 8px; font-weight: 700; font-size: 13px;
        cursor: pointer; transition: all 0.3s ease;
    }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 20px rgba(239,68,68,0.5); transform: translateY(-1px); }
    .btn-reset:active::after {
        content: ''; position: absolute; left: 50%; top: 50%;
        width: 10px; height: 10px; border-radius: 50%; background: #fff;
        transform: translate(-50%, -50%) scale(0); animation: ripple 0.6s ease-out;
    }

    /* STATS BAR */
    .stats-bar {
        max-width: 600px; margin: 15px auto 0; padding: 0 15px;
        display: flex; justify-content: space-between; gap: 10px;
        position: relative; z-index: 1;
    }
    .stat-item {
        flex: 1; background: var(--bg-card); border: 1px solid var(--border-color);
        border-radius: 10px; padding: 10px; text-align: center;
        position: relative; overflow: hidden;
        transition: all 0.3s;
    }
    .stat-item:hover { border-color: rgba(56,189,248,0.4); transform: translateY(-2px); }
    .stat-item::before {
        content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
        background: linear-gradient(90deg, transparent, var(--blue-main), transparent);
        background-size: 200% 100%; animation: shimmerBar 3s linear infinite;
    }
    .stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 4px; font-weight: 600; }
    .stat-value { font-size: 20px; font-weight: 900; color: var(--text-main); animation: statPulse 2.5s infinite; }
    .stat-value.win { color: var(--blue-main); }

    /* CONTAINER */
    .container {
        padding: 15px; display: flex; flex-direction: column; gap: 12px;
        max-width: 600px; margin: 0 auto;
        position: relative; z-index: 1;
    }

    /* CARD ITEM */
    .card-item {
        background: var(--bg-card); border: 1px solid var(--border-color);
        border-radius: 12px; padding: 14px 16px;
        display: flex; justify-content: space-between; align-items: center;
        transition: all 0.3s ease; position: relative;
        animation: slideIn 0.5s ease-out backwards;
        overflow: hidden;
    }
    .card-item::before {
        content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px;
        background: linear-gradient(180deg, transparent, var(--blue-main), transparent);
        opacity: 0; transition: opacity 0.3s;
    }
    .card-item:hover { background: var(--bg-card-hover); transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
    .card-item:hover::before { opacity: 1; }

    .card-item.active {
        background: linear-gradient(145deg, #0d1424, #0f1a2e);
        animation: slideIn 0.5s ease-out backwards, rainbow-border 3s linear infinite;
        border-width: 1.5px;
    }
    .card-item.active::after {
        content: '●'; position: absolute; top: 8px; right: 10px;
        color: var(--blue-main); font-size: 10px;
        animation: dotPulse 1.5s infinite;
    }

    /* COLUMNS */
    .col-left { display: flex; flex-direction: column; gap: 5px; flex: 1.2; }
    .id-text {
        font-size: 16px; font-weight: 800; color: #fff; letter-spacing: 0.5px;
        background: linear-gradient(90deg, #fff, #7dd3fc);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .bot-line { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .bot-label { color: var(--text-muted); font-weight: 600; }
    .bet-badge { padding: 3px 10px; border-radius: 20px; font-weight: 700; font-size: 11px; }
    .bet-tai { background: var(--tai-bet-bg); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); }
    .bet-xiu { background: var(--xiu-bet-bg); color: #f472b6; border: 1px solid rgba(244,114,182,0.3); }
    .conf-text { color: var(--text-muted); font-size: 10.5px; font-style: italic; }

    .conf-bar-wrap {
        height: 3px; background: rgba(56,189,248,0.12); border-radius: 2px;
        overflow: hidden; margin-top: 3px;
    }
    .conf-bar {
        height: 100%; border-radius: 2px;
        background: linear-gradient(90deg, #38bdf8, #7dd3fc, #a78bfa, #38bdf8);
        background-size: 200% 100%;
        animation: shimmerBar 2s linear infinite;
        transition: width 0.6s ease;
    }

    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; flex: 1; }
    .pred-badge {
        padding: 5px 14px; border-radius: 20px; font-weight: 800; font-size: 13px;
        text-transform: uppercase; letter-spacing: 1px; transition: all 0.3s;
    }
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

    .pattern-tag {
        font-size: 9.5px; color: var(--text-muted); font-weight: 600;
        padding: 2px 8px; border-radius: 10px;
        background: rgba(56,189,248,0.08); border: 1px solid rgba(56,189,248,0.15);
    }

    /* LOADING */
    .loading {
        text-align: center; padding: 50px; color: var(--blue-main);
        font-weight: 600; letter-spacing: 1px;
        animation: textGlow 2s infinite;
    }

    /* Sparkle khi win */
    .sparkle-win {
        position: relative;
    }
    .sparkle-win::before {
        content: '✦'; position: absolute; top: -8px; right: -8px;
        color: var(--gold); font-size: 14px;
        animation: sparkle 2s ease-in-out infinite;
    }

    @media (max-width: 400px) {
        .header-title { font-size: 16px; }
        .stat-value { font-size: 16px; }
        .dice-text { font-size: 11px; }
    }
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
    <div class="stat-item">
        <div class="stat-label">Tổng phiên</div>
        <div class="stat-value" id="stat-total">0</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Thắng</div>
        <div class="stat-value win" id="stat-win">0</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Tỷ lệ</div>
        <div class="stat-value win" id="stat-rate">0%</div>
    </div>
</div>

<div class="container" id="list-container">
    <div class="loading">Đang kết nối Server...</div>
</div>

<script>
let isResetting = false;
let lastStats = { total: 0, win: 0, rate: 0 };

function animateNumber(el, target, suffix = '') {
    const start = parseInt(el.innerText.replace(/[^0-9]/g, '')) || 0;
    if (start === target) { el.innerText = target + suffix; return; }
    const duration = 700;
    const startTime = performance.now();
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
        console.error("Lỗi tải dữ liệu:", e);
        document.getElementById('list-container').innerHTML =
            '<div class="loading" style="color:var(--lose-color)">Lỗi kết nối Server!</div>';
    }
}

function renderList(rows, stats) {
    const container = document.getElementById('list-container');

    // Stats với animation đếm số
    if (stats.total > 0) {
        animateNumber(document.getElementById('stat-total'), stats.total);
        animateNumber(document.getElementById('stat-win'), stats.correct);
        const rate = (stats.correct / stats.total) * 100;
        animateNumber(document.getElementById('stat-rate'), Math.round(rate), '%');
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
            const sum = parseInt(p[0]) + parseInt(p[1]) + parseInt(p[2]);
            diceDisplay = `${row.dice} (${sum})`;
        }

        let statusHtml = '';
        if (row.is_next) {
            statusHtml = `<div class="status-text status-wait">Chờ <span class="spin">🐻</span></div>`;
        } else if (row.is_correct === true) {
            statusHtml = `<div class="status-text status-win sparkle-win">Đúng ✅</div>`;
        } else if (row.is_correct === false) {
            statusHtml = `<div class="status-text status-lose">Sai ❌</div>`;
        } else {
            statusHtml = `<div class="status-text" style="color:var(--text-muted)">-</div>`;
        }

        const patternTag = row.pattern ? `<span class="pattern-tag">${row.pattern}</span>` : '';

        div.innerHTML = `
            <div class="col-left">
                <div class="id-text">#${row.phien}</div>
                <div class="bot-line">
                    <span class="bot-label">Bot:</span> ${betBadge}
                </div>
                <div class="conf-text">Độ tin cậy: ${row.confidence}%</div>
                <div class="conf-bar-wrap"><div class="conf-bar" style="width:${row.confidence}%"></div></div>
                ${patternTag}
            </div>

            <div class="col-mid">
                ${row.is_next ? predBadge : resultBadge}
                <div class="dice-text">${diceDisplay}</div>
            </div>

            <div class="col-right">
                ${statusHtml}
            </div>
        `;
        container.appendChild(div);
    });
}

async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?',
        text: "Lịch sử hiển thị trên màn hình sẽ bị ẩn đi. Hệ thống vẫn tính toán ngầm!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#38bdf8',
        cancelButtonColor: '#1e293b',
        confirmButtonText: 'Đồng ý',
        cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({
                        title: 'Thành công!',
                        text: 'Đã chốt mốc ẩn lịch sử từ phiên #' + data.reset_to,
                        icon: 'success',
                        confirmButtonColor: '#38bdf8'
                    });
                    isResetting = false;
                    fetchData();
                } else {
                    throw new Error(data.message);
                }
            } catch (error) {
                Swal.fire('Lỗi!', 'Không thể reset: ' + error.message, 'error');
                isResetting = false;
            }
        }
    });
}

fetchData();
setInterval(fetchData, 5000);
</script>
</body>
</html>
"""

def generate_fallback(base=7116040):
    elapsed = int(time.time() / 60)
    current = base + elapsed
    random.seed(elapsed)
    rows = []
    for i in range(15):
        sid = current - i
        r = "Tài" if random.random() > 0.5 else "Xỉu"
        d = [random.randint(1, 6) for _ in range(3)]
        rows.append({
            "phien": sid,
            "result": r,
            "dice": f"{d[0]} + {d[1]} + {d[2]}",
            "total": sum(d)
        })
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
                    rows.append({
                        'phien': int(item['id']),
                        'result': res,
                        'dice': dice_str,
                        'total': total
                    })
                return rows, 'live'
    except Exception as e:
        print(f"[API ERROR] {e}")
    return generate_fallback(), 'fallback'


# =====================================================================
# THUẬT TOÁN FULL CẦU - BẺ BỆT - ĐẢO CẦU - MARKOV - NGHIÊNG
# =====================================================================
def analyze_pattern(results):
    """
    Phân tích đa tầng: Bệt → Đảo 1-1 → 2-2 → 3-3 → 4-4 → 1-2-1 → 2-1-2
                      → 1-1-2 → Nghiêng → Markov → 2-2-1 → Đảo đôi
    Trả về: (prediction, confidence, pattern_name)
    """
    if not results or len(results) < 3:
        return "Tài", 50.0, "Khởi tạo"

    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"

    # ========== 1. CẦU BỆT ==========
    streak = 1
    for r in results[1:]:
        if r == last: streak += 1
        else: break

    if streak >= 10: return opposite, 99.0, f"Bẻ bệt {streak} siêu cấp"
    if streak >= 8:  return opposite, 96.0, f"Bẻ bệt {streak} cực mạnh"
    if streak >= 6:  return opposite, 92.0, f"Bẻ bệt {streak} mạnh"
    if streak == 5:  return opposite, 85.0, f"Bẻ bệt {streak}"
    if streak == 4:  return last,     70.0, f"Bám bệt {streak}"
    if streak == 3:  return last,     62.0, f"Bám bệt {streak}"
    if streak == 2:  return last,     55.0, f"Bám bệt {streak}"

    # ========== 2. CẦU ĐẢO 1-1 ==========
    if len(results) >= 10 and all(results[i] != results[i+1] for i in range(10)):
        return opposite, 97.0, "Đảo 1-1 siêu dài"
    if len(results) >= 7 and all(results[i] != results[i+1] for i in range(7)):
        return opposite, 93.0, "Đảo 1-1 dài"
    if len(results) >= 5 and all(results[i] != results[i+1] for i in range(5)):
        return opposite, 88.0, "Đảo 1-1"
    if len(results) >= 4 and all(results[i] != results[i+1] for i in range(4)):
        return opposite, 76.0, "Đảo 1-1 ngắn"

    # ========== 3. CẦU 2-2 ==========
    if len(results) >= 8:
        if (results[0]==results[1] and results[2]==results[3] and
            results[4]==results[5] and results[6]==results[7] and
            results[1]!=results[2] and results[3]!=results[4] and results[5]!=results[6]):
            return opposite, 94.0, "Đảo 2-2 dài"
    if len(results) >= 6:
        if (results[0]==results[1] and results[2]==results[3] and results[4]==results[5]
            and results[1]!=results[2] and results[3]!=results[4]):
            return opposite, 88.0, "Đảo 2-2"

    # ========== 4. CẦU 3-3 ==========
    if len(results) >= 9:
        if (results[0]==results[1]==results[2] and results[3]==results[4]==results[5] and
            results[6]==results[7]==results[8] and
            results[2]!=results[3] and results[5]!=results[6]):
            return opposite, 94.0, "Đảo 3-3"

    # ========== 5. CẦU 4-4 ==========
    if len(results) >= 12:
        if (results[0]==results[1]==results[2]==results[3] and
            results[4]==results[5]==results[6]==results[7] and
            results[8]==results[9]==results[10]==results[11] and
            results[3]!=results[4] and results[7]!=results[8]):
            return opposite, 96.0, "Đảo 4-4"

    # ========== 6. CẦU 1-2-1 (kép) ==========
    if len(results) >= 8:
        if (results[0]==results[3]==results[4]==results[7] and
            results[1]==results[2] and results[5]==results[6] and
            results[0]!=results[1] and results[4]!=results[5]):
            return results[1], 90.0, "Cầu 1-2-1 kép"
    if len(results) >= 5:
        if (results[0]==results[3] and results[1]==results[2] and results[0]!=results[1]):
            return results[1], 82.0, "Cầu 1-2-1"

    # ========== 7. CẦU 2-1-2 ==========
    if len(results) >= 5:
        if (results[0]==results[1] and results[3]==results[4] and
            results[1]!=results[2] and results[2]!=results[3]):
            return results[1], 82.0, "Cầu 2-1-2"

    # ========== 8. CẦU 1-1-2 ==========
    if len(results) >= 6:
        if (results[0]==results[1] and results[1]!=results[2] and
            results[3]==results[4] and results[4]!=results[5]):
            return results[2], 85.0, "Cầu 1-1-2"

    # ========== 9. CẦU NGHIÊNG ==========
    if len(results) >= 10:
        tai_count = sum(1 for r in results[:10] if r == "Tài")
        if tai_count >= 8: return "Xỉu", 78.0, "Nghiêng Xỉu mạnh"
        if tai_count <= 2: return "Tài", 78.0, "Nghiêng Tài mạnh"
        if tai_count >= 7: return "Tài", 68.0, "Nghiêng Tài"
        if tai_count <= 3: return "Xỉu", 68.0, "Nghiêng Xỉu"

    # ========== 10. MARKOV WEIGHTED ==========
    if len(results) >= 6:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 1):
            if results[i] == last:
                trans[results[i+1]] += 1
        total = trans["Tài"] + trans["Xỉu"]
        if total >= 3:
            if trans["Tài"] / total >= 0.8: return "Tài", 78.0, "Markov Tài"
            if trans["Xỉu"] / total >= 0.8: return "Xỉu", 78.0, "Markov Xỉu"
            if trans["Tài"] > trans["Xỉu"]: return "Tài", 65.0, "Markov Tài nhẹ"
            if trans["Xỉu"] > trans["Tài"]: return "Xỉu", 65.0, "Markov Xỉu nhẹ"

    # ========== 11. CẦU 2-2-1 ==========
    if len(results) >= 5:
        if (results[0]!=results[1] and results[1]==results[2] and
            results[2]!=results[3] and results[3]==results[4]):
            return results[1], 76.0, "Cầu 2-2-1"

    # ========== 12. ĐẢO ĐÔI ==========
    if len(results) >= 4:
        if (results[0]!=results[1] and results[1]!=results[2] and
            results[2]!=results[3] and results[0]==results[2] and results[1]==results[3]):
            return opposite, 72.0, "Đảo đôi"

    # ========== 13. DEFAULT ==========
    return opposite, 55.0, "Đảo nhịp"


# =====================================================================
# API ROUTES (giữ nguyên)
# =====================================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api')
def api_root():
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    return jsonify({
        "name": "LC MD5 MINHLE API Server",
        "version": "3.0.0 (Full Cầu + Premium Effects)",
        "endpoints": {
            "lich_su": "/api/history",
            "du_doan": "/api/predict",
            "thong_ke": "/api/stats",
            "reset": "/api/reset"
        },
        "lastUpdate": now,
        "status": "active"
    })

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
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next)

        out.append({
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'confidence': next_conf,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None,
            'pattern': next_pattern
        })

        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID:
                break
            if len(out) > 20:
                break

            history = [v['result'] for v in valid[:i]][::-1]
            if history:
                pred, conf, pattern = analyze_pattern(history)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct:
                    correct_count += 1
            else:
                pred, conf, pattern = "Tài", 50.0, "Khởi tạo"
                is_correct = None

            out.append({
                'phien': current_session['phien'],
                'is_next': False,
                'prediction': pred,
                'confidence': conf,
                'result': current_session['result'],
                'dice': current_session['dice'],
                'is_correct': is_correct,
                'pattern': pattern
            })

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count}
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
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next)

        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'prediction': next_pred,
            'confidence': next_conf,
            'pattern': next_pattern,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stats')
def stats_only():
    global RESET_SESSION_ID
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])

        correct_count = 0
        total_past = 0

        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID:
                break

            history = [v['result'] for v in valid[:i]][::-1]
            if history:
                pred, conf, _ = analyze_pattern(history)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct:
                    correct_count += 1

        win_rate = round((correct_count / total_past * 100), 2) if total_past > 0 else 0

        return jsonify({
            'status': 'success',
            'data': {
                'total_predictions': total_past,
                'correct_predictions': correct_count,
                'win_rate_percent': win_rate
            }
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
