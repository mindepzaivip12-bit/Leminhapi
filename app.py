import os
import re
import math
import time
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
RESET_SESSION_ID = 0

ALL_81_PATTERNS = {}
for _i in range(81):
    _sig = ''
    _temp = _i
    for _ in range(4):
        _sig = 'SML'[_temp % 3] + _sig
        _temp //= 3
    ALL_81_PATTERNS[_i] = _sig

# =====================================================================
# FILTER ẨN CẦU KHÔNG MUỐN HIỂN THỊ
# =====================================================================
HIDDEN_PATTERN_PREFIXES = ("Chuyền kỳ", "N-gram", "Bias XX")

def should_hide_pattern(p: str) -> bool:
    if not p:
        return False
    if p.startswith(HIDDEN_PATTERN_PREFIXES):
        return True
    if re.match(r"^Cầu \d+-\d+-\d+$", p):
        return True
    return False

def filter_display_patterns(patterns):
    filtered = [p for p in patterns if not should_hide_pattern(p)]
    return filtered if filtered else ["Tổng hợp"]

# =====================================================================
# HTML
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LC MD5 LEMINH - V8.0</title>
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
        --purple: #a78bfa; --pink: #f472b6; --gold: #fbbf24; --green: #22c55e;
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
    .container { padding: 15px; display: flex; flex-direction: column; gap: 12px; max-width: 600px; margin: 0 auto; position: relative; z-index: 1; }
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
    .conf-bar-wrap { height: 3px; background: rgba(56,189,248,0.12); border-radius: 2px; overflow: hidden; margin-top: 3px; margin-bottom: 4px;}
    .conf-bar { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #38bdf8, #7dd3fc, #a78bfa, #38bdf8); background-size: 200% 100%; animation: shimmerBar 2s linear infinite; transition: width 0.6s ease; }
    .pattern-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
    .pattern-tag { font-size: 9.5px; color: #94a3b8; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); display: inline-block; }
    .pattern-tag.hot { color: var(--gold); border-color: rgba(251,191,36,0.35); background: rgba(251,191,36,0.1); }
    .pattern-tag.sys { color: var(--purple); border-color: rgba(167,139,250,0.35); background: rgba(167,139,250,0.1); }
    .pattern-tag.markov { color: #38bdf8; border-color: rgba(56,189,248,0.35); background: rgba(56,189,248,0.1); }
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
    @media (max-width: 400px) { .header-title { font-size: 16px; } .stat-value { font-size: 16px; } .dice-text { font-size: 11px; } .pattern-tag { font-size: 8.5px; } }
</style>
</head>
<body>
<div class="header">
    <div class="header-left">
        <div class="header-live-dot"></div>
        <div class="header-title">⚡ LC MD5 LEMINH • V8.0</div>
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
function getTagClass(p) {
    if (p.indexOf('Mẫu') >= 0) return 'sys';
    if (p.indexOf('Markov') >= 0 || p.indexOf('Cân bằng') >= 0 || p.indexOf('Fibonacci') >= 0 ||
        p.indexOf('Tổng hợp') >= 0) return 'markov';
    if (p.indexOf('bệt') >= 0 || p.indexOf('Bẻ') >= 0 || p.indexOf('Bám') >= 0 ||
        p.indexOf('Đảo') >= 0 || p.indexOf('Nghiêng') >= 0 ||
        p.indexOf('Bậc thang') >= 0 || p.indexOf('2-2-1-1') >= 0 ||
        p.indexOf('Vượt') >= 0 || p.indexOf('Lệch') >= 0) return 'hot';
    return '';
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
        if (row.is_next) statusHtml = `<div class="status-text status-wait">Chờ <span class="spin">⏳</span></div>`;
        else if (row.is_correct === true) statusHtml = `<div class="status-text status-win">Đúng ✅</div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status-text status-lose">Sai ❌</div>`;
        else statusHtml = `<div class="status-text" style="color:var(--text-muted)">-</div>`;
        let patternTagsHtml = '';
        if (row.patterns && row.patterns.length > 0) {
            patternTagsHtml = row.patterns.map(p => {
                return `<span class="pattern-tag ${getTagClass(p)}">${p}</span>`;
            }).join('');
        } else if (row.pattern) {
            patternTagsHtml = `<span class="pattern-tag ${getTagClass(row.pattern)}">${row.pattern}</span>`;
        }
        div.innerHTML = `
            <div class="col-left">
                <div class="id-text">#${row.phien}</div>
                <div class="bot-line"><span class="bot-label">Bot:</span> ${betBadge}</div>
                <div class="conf-text">Độ tin cậy: ${row.confidence}%</div>
                <div class="conf-bar-wrap"><div class="conf-bar" style="width:${row.confidence}%"></div></div>
                <div class="pattern-list">${patternTagsHtml}</div>
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
# HELPERS - HỆ THỐNG 81 MẪU
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
# THUẬT TOÁN V8.0 - 14 LOẠI CẦU
# =====================================================================
def analyze_pattern(results, dice_sums=None):
    if not results or len(results) < 3:
        return "Tài", 50.0, ["Khởi tạo"]
    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    n = len(results)
    candidates = []
    blocks = build_blocks(results)
    current_val = blocks[0]['val']
    current_len = blocks[0]['len']

    # 1. Cầu bệt
    if current_len >= 12:   candidates.append((opposite, 97.0, f"Bẻ bệt cực đại ({current_len})", 96))
    elif current_len >= 10: candidates.append((opposite, 94.0, f"Bẻ bệt {current_len}", 92))
    elif current_len >= 8:  candidates.append((opposite, 88.0, f"Bẻ bệt {current_len}", 85))
    elif current_len >= 6:  candidates.append((opposite, 80.0, f"Bẻ bệt {current_len}", 75))
    elif current_len == 5:  candidates.append((opposite, 70.0, "Bẻ bệt 5", 65))
    elif current_len == 4:  candidates.append((current_val, 62.0, "Bám bệt 4", 58))
    elif current_len == 3:  candidates.append((current_val, 57.0, "Bám bệt 3", 53))
    elif current_len == 2:  candidates.append((current_val, 53.0, "Bám bệt 2", 50))

    # 2. Cầu đảo 1-1
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]: alt_len += 1
        else: break
    if alt_len >= 12:   candidates.append((opposite, 94.0, f"Đảo 1-1 dài ({alt_len})", 92))
    elif alt_len >= 9:  candidates.append((opposite, 88.0, f"Đảo 1-1 ({alt_len})", 84))
    elif alt_len >= 6:  candidates.append((opposite, 80.0, f"Đảo 1-1 ({alt_len})", 75))
    elif alt_len >= 4:  candidates.append((opposite, 72.0, f"Đảo 1-1 ngắn ({alt_len})", 65))

    # 3. Cầu đảo khối
    if len(blocks) >= 3:
        is_alt = all(blocks[i]['val'] != blocks[i-1]['val'] for i in range(1, min(len(blocks), 8)))
        if is_alt:
            p1, p2 = blocks[1]['len'], blocks[2]['len']
            if p1 == p2 and p1 >= 2:
                cycle = p1
                if current_len < cycle:   candidates.append((current_val, 93.0, f"Bám {cycle}-{cycle} dở", 92))
                elif current_len == cycle: candidates.append((opposite, 95.0, f"Bẻ {cycle}-{cycle}", 94))
                else:                     candidates.append((opposite, 85.0, f"Vượt {cycle}-{cycle}", 80))
            if len(blocks) >= 4:
                p3 = blocks[3]['len']
                if p1 == p3 and p2 != p1 and p1 <= 5:
                    candidates.append((opposite, 84.0, f"Cầu {p1}-{p2}-{p1}", 80))
                if p1 + 1 == p2 and p2 + 1 == p3:
                    candidates.append((opposite, 78.0, f"Bậc thang {p1}-{p2}-{p3}", 72))

    # 4. Cầu nghiêng
    for period in [2, 3, 4, 5]:
        if n >= period * 3:
            ok = True
            for i in range(period * 2):
                if results[i] != results[i + period]: ok = False; break
            if ok:
                candidates.append((results[period - 1], 82.0, f"Nghiêng kỳ {period}", 78))
                break

    # 5. Cầu chuyền
    if len(blocks) >= 4:
        classes = [block_class(b['len']) for b in blocks[:6]]
        for plen in [2, 3]:
            if len(classes) >= plen * 2:
                ok = True
                for i in range(plen):
                    if classes[i] != classes[i + plen]: ok = False; break
                if ok:
                    hint = blocks[plen]['len']
                    if current_len < hint:
                        candidates.append((current_val, 78.0, f"Chuyền kỳ {plen} (tiếp)", 74))
                    else:
                        candidates.append((opposite, 78.0, f"Chuyền kỳ {plen} (gãy)", 74))
                    break

    # 6. Hệ thống 81 mẫu
    if len(blocks) >= 5:
        stats = learn_81_patterns(results)
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        sig = pattern_signature(four_lens)
        if code is not None:
            for key in [(code, min(current_len, 4)), code]:
                if key in stats:
                    s = stats[key]
                    total = s['continue'] + s['break']
                    if total >= 2:
                        cr = s['continue'] / total
                        if cr >= 0.6:
                            candidates.append((current_val, 54 + cr * 35, f"Mẫu#{code+1:02d} [{sig}] Tiếp", 74))
                        elif cr <= 0.4:
                            candidates.append((opposite, 54 + (1 - cr) * 35, f"Mẫu#{code+1:02d} [{sig}] Gãy", 74))
                        break

    # 7. N-gram
    for ns in [10, 9, 8, 7, 6, 5, 4]:
        if n < ns + 2: continue
        current_seq = tuple(results[:ns])
        mt, mx = 0, 0
        for i in range(1, len(results) - ns + 1):
            if tuple(results[i:i+ns]) == current_seq:
                if results[i-1] == "Tài": mt += 1
                else: mx += 1
        tm = mt + mx
        if tm >= 2 and mt != mx:
            winner = "Tài" if mt > mx else "Xỉu"
            ratio = max(mt, mx) / tm
            if ratio >= 0.55:
                candidates.append((winner, 52 + ratio * 30, f"N-gram {ns} ({mt}T-{mx}X)", 62 + ns))
                break

    # 8. Markov
    if n >= 8:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(1, len(results)):
            if results[i] == last: trans[results[i-1]] += 1
        tt = trans["Tài"] + trans["Xỉu"]
        if tt >= 3 and trans["Tài"] != trans["Xỉu"]:
            winner = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            ratio = max(trans["Tài"], trans["Xỉu"]) / tt
            candidates.append((winner, 58 + ratio * 20, f"Markov ({trans['Tài']}T-{trans['Xỉu']}X)", 58))

    # 9. Bias xúc xắc
    if dice_sums and len(dice_sums) >= 5:
        avg = sum(dice_sums[:10]) / min(10, len(dice_sums))
        if avg >= 12.0:  candidates.append(("Tài", 66.0, f"Bias XX Tài ({avg:.1f})", 62))
        elif avg <= 8.5: candidates.append(("Xỉu", 66.0, f"Bias XX Xỉu ({avg:.1f})", 62))

    # 10. Cân bằng tần suất
    if n >= 20:
        r20 = results[:20]
        tc = r20.count("Tài")
        if tc >= 15:  candidates.append(("Xỉu", 70.0, f"Cân bằng (Tài {tc}/20)", 65))
        elif tc <= 5: candidates.append(("Tài", 70.0, f"Cân bằng (Xỉu {20-tc}/20)", 65))

    # === 10b. LỆCH PHIÊN (đa cửa sổ + Z-score) ===
    for win_size in [10, 15, 20, 30, 50]:
        if n < win_size: continue
        window = results[:win_size]
        tai_count = window.count("Tài")
        xiu_count = win_size - tai_count
        expected = win_size / 2
        std = math.sqrt(win_size * 0.25)
        z = (tai_count - expected) / std if std > 0 else 0
        deviation = abs(tai_count - xiu_count) / win_size
        if abs(z) >= 1.5 and deviation >= 0.2:
            if z > 0:
                conf = min(88.0, 60 + abs(z) * 8)
                candidates.append(("Xỉu", conf, f"Lệch phiên {win_size} (Tài {tai_count}/{win_size})", 70))
            else:
                conf = min(88.0, 60 + abs(z) * 8)
                candidates.append(("Tài", conf, f"Lệch phiên {win_size} (Xỉu {xiu_count}/{win_size})", 70))
            break

    # 11. Fibonacci
    if len(blocks) >= 3:
        lens = [b['len'] for b in blocks[:4]]
        if len(lens) >= 3 and lens[0] == lens[1] + lens[2]:
            candidates.append((opposite, 75.0, "Fibonacci", 70))

    # 12. Cầu 2-2-1-1
    if len(blocks) >= 4:
        last4 = [b['len'] for b in blocks[:4]]
        if last4[:2] == [2, 2] and last4[2:4] == [1, 1]:
            candidates.append((opposite if current_len == 1 else current_val, 76.0, "Cầu 2-2-1-1", 72))

    # 13. Lệch mạnh cục bộ
    if n >= 30:
        l15 = results[:15]
        t15 = l15.count("Tài")
        if t15 >= 11:  candidates.append(("Xỉu", 68.0, f"Lệch mạnh Tài {t15}/15", 63))
        elif t15 <= 4: candidates.append(("Tài", 68.0, f"Lệch mạnh Xỉu {15-t15}/15", 63))

    # Voting system
    if not candidates:
        return opposite, 55.0, ["Đảo nhịp (Mặc định)"]

    tai_score = sum(c[1] for c in candidates if c[0] == "Tài") * 0.7 + sum(c[3] for c in candidates if c[0] == "Tài") * 0.3
    xiu_score = sum(c[1] for c in candidates if c[0] == "Xỉu") * 0.7 + sum(c[3] for c in candidates if c[0] == "Xỉu") * 0.3
    winner = "Tài" if tai_score > xiu_score else "Xỉu"
    win_patterns = [c[2] for c in candidates if c[0] == winner]
    win_patterns.sort(key=lambda name: next((c[3] for c in candidates if c[2] == name), 0), reverse=True)
    agree = tai_score if winner == "Tài" else xiu_score
    total = tai_score + xiu_score
    ratio = agree / total if total > 0 else 0
    best = max((c[1] for c in candidates if c[0] == winner), default=55.0)
    final_conf = best * (0.85 + ratio * 0.15)

    if not win_patterns:
        win_patterns = [f"Tổng hợp ({len(candidates)} tín hiệu)"]

    win_patterns = filter_display_patterns(win_patterns)

    return winner, round(min(98.0, final_conf), 1), win_patterns

# =====================================================================
# FETCH DỮ LIỆU - FALLBACK DETERMINISTIC (KHÔNG RANDOM)
# =====================================================================
def generate_fallback(base=7116040):
    elapsed = int(time.time() / 60)
    current = base + elapsed
    rows = []
    for i in range(60):
        sid = current - i
        h1 = (sid * 2654435761) & 0xFFFFFFFF
        h2 = (sid * 1664525 + 1013904223) & 0xFFFFFFFF
        h3 = (sid * 2246822519) & 0xFFFFFFFF
        d1, d2, d3 = (h1 % 6) + 1, (h2 % 6) + 1, (h3 % 6) + 1
        total = d1 + d2 + d3
        r = "Tài" if total >= 11 else "Xỉu"
        rows.append({"phien": sid, "result": r, "dice": f"{d1} + {d2} + {d3}", "total": total})
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
# HELPER BÁO KẾT QUẢ KIỂU GAME
# =====================================================================
def _build_session_result(session):
    dice = session.get('dice', '? + ? + ?')
    try:
        dice_arr = [int(x.strip()) for x in dice.split('+')]
    except Exception:
        dice_arr = []
    return {
        'phien': session['phien'],
        'result': session['result'],
        'dice': dice,
        'dice_array': dice_arr,
        'total': session.get('total', sum(dice_arr) if dice_arr else 0),
    }

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

        latest = valid[-1]
        next_phien = latest['phien'] + 1
        hist_next = [v['result'] for v in valid][::-1]
        dice_next = [v.get('total', 0) for v in valid][::-1]
        pred, conf, patterns = analyze_pattern(hist_next, dice_next)

        out.append({
            'phien': next_phien, 'is_next': True, 'prediction': pred, 'confidence': conf,
            'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None, 'patterns': patterns
        })

        for i in range(len(valid) - 1, -1, -1):
            cs = valid[i]
            if cs['phien'] <= RESET_SESSION_ID: break
            if len(out) > 20: break
            hl = [v['result'] for v in valid[:i]][::-1]
            dl = [v.get('total', 0) for v in valid[:i]][::-1]
            if hl:
                pred, conf, patterns = analyze_pattern(hl, dl)
                ok = (pred == cs['result'])
                total_past += 1
                if ok: correct_count += 1
            else:
                pred, conf, patterns = "Tài", 50.0, ["Khởi tạo"]
                ok = None
            out.append({
                'phien': cs['phien'], 'is_next': False, 'prediction': pred, 'confidence': conf,
                'result': cs['result'], 'dice': cs['dice'],
                'is_correct': ok, 'patterns': patterns
            })

        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict')
def predict_only():
    try:
        raw, source = fetch_sessions()
        valid = sorted(raw, key=lambda x: x['phien'])
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404
        latest = valid[-1]
        hn = [v['result'] for v in valid][::-1]
        dn = [v.get('total', 0) for v in valid][::-1]
        pred, conf, patterns = analyze_pattern(hn, dn)
        return jsonify({
            'status': 'success',
            'source': source,
            'current': _build_session_result(latest),
            'next_session': latest['phien'] + 1,
            'prediction': pred,
            'bet': pred.upper(),
            'confidence': conf,
            'patterns': patterns,
            'updated_at': datetime.now().strftime('%H:%M:%S'),
            'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/game')
def game_status():
    try:
        raw, source = fetch_sessions()
        valid = sorted(raw, key=lambda x: x['phien'])
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404

        current = valid[-1]
        current_out = _build_session_result(current)

        history = [v['result'] for v in valid][::-1]
        dice_hist = [v.get('total', 0) for v in valid][::-1]
        pred, conf, patterns = analyze_pattern(history, dice_hist)
        next_out = {
            'phien': current['phien'] + 1,
            'prediction': pred,
            'bet': pred.upper(),
            'confidence': conf,
            'patterns': patterns,
        }

        last_check = None
        if len(valid) >= 2:
            prev_hist = [v['result'] for v in valid[:-1]][::-1]
            prev_dice = [v.get('total', 0) for v in valid[:-1]][::-1]
            if prev_hist:
                prev_pred, prev_conf, _ = analyze_pattern(prev_hist, prev_dice)
                last_check = {
                    'phien': current['phien'],
                    'predicted': prev_pred,
                    'actual': current['result'],
                    'correct': prev_pred == current['result'],
                    'confidence': prev_conf,
                }

        recent_10 = [_build_session_result(v) for v in valid[-10:][::-1]]

        correct_count = 0
        total_past = 0
        limit = min(len(valid) - 1, 20)
        for i in range(len(valid) - 1, len(valid) - 1 - limit, -1):
            if i < 0: break
            cs = valid[i]
            if cs['phien'] <= RESET_SESSION_ID: break
            hl = [v['result'] for v in valid[:i]][::-1]
            dl = [v.get('total', 0) for v in valid[:i]][::-1]
            if not hl: continue
            p, _, _ = analyze_pattern(hl, dl)
            total_past += 1
            if p == cs['result']:
                correct_count += 1

        return jsonify({
            'status': 'success',
            'source': source,
            'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'current': current_out,
            'next': next_out,
            'last_check': last_check,
            'recent_10': recent_10,
            'stats': {
                'total': total_past,
                'correct': correct_count,
                'rate': round((correct_count / total_past * 100), 1) if total_past > 0 else 0,
            },
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/result/<int:session_id>')
def session_result(session_id):
    try:
        raw, _ = fetch_sessions()
        valid = sorted(raw, key=lambda x: x['phien'])
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404

        latest_id = valid[-1]['phien']

        if session_id > latest_id:
            if session_id == latest_id + 1:
                hist = [v['result'] for v in valid][::-1]
                dice_hist = [v.get('total', 0) for v in valid][::-1]
                pred, conf, patterns = analyze_pattern(hist, dice_hist)
                return jsonify({
                    'status': 'success',
                    'phien': session_id,
                    'is_finished': False,
                    'prediction': pred,
                    'bet': pred.upper(),
                    'confidence': conf,
                    'patterns': patterns,
                    'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                })
            return jsonify({'status': 'error', 'message': 'Phiên vượt quá tương lai'}), 400

        target = next((v for v in valid if v['phien'] == session_id), None)
        if not target:
            return jsonify({'status': 'error', 'message': f'Không tìm thấy phiên #{session_id}'}), 404

        idx = valid.index(target)
        hl = [v['result'] for v in valid[:idx]][::-1]
        dl = [v.get('total', 0) for v in valid[:idx]][::-1]
        pred, conf, patterns = (analyze_pattern(hl, dl) if hl else ("Tài", 50.0, ["Khởi tạo"]))

        return jsonify({
            'status': 'success',
            'phien': target['phien'],
            'is_finished': True,
            'result': target['result'],
            'dice': target['dice'],
            'total': target.get('total', 0),
            'prediction': pred,
            'bet': pred.upper(),
            'confidence': conf,
            'patterns': patterns,
            'is_correct': pred == target['result'],
            'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        raw, _ = fetch_sessions()
        valid = sorted(raw, key=lambda x: x['phien'])
        if valid:
            RESET_SESSION_ID = valid[-1]['phien']
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
