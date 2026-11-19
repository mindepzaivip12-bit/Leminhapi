import os
import math
import hashlib
import traceback
from datetime import datetime
from collections import defaultdict
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
MAX_CONFIDENCE = 90
RESET_ID = 0

# =====================================================================
# ADAPTIVE LEARNING TRACKING (v3)
# =====================================================================
ALGO_RECENT_STATS = defaultdict(lambda: {"win": 0, "lose": 0})
ADAPTIVE_WINDOW = 20
CALIBRATION_BUCKETS = defaultdict(lambda: {"win": 0, "lose": 0})
CALIBRATION_READY = False
FLIP_STATS = {"win": 0, "lose": 0, "consecutive_loss": 0}

# =====================================================================
# HTML TEMPLATE (giữ nguyên 100% như bản cũ)
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-page: #0f172a; --bg-card: #1e293b; --text-main: #f8fafc;
        --text-muted: #94a3b8; --border-color: #334155;
        --tai-color: #38bdf8; --tai-bg: rgba(56, 189, 248, 0.15);
        --xiu-color: #f472b6; --xiu-bg: rgba(244, 114, 182, 0.15);
        --win-color: #34d399; --win-bg: rgba(52, 211, 153, 0.15);
        --lose-color: #f87171; --lose-bg: rgba(248, 113, 113, 0.15);
        --wait-color: #fbbf24; --wait-bg: rgba(251, 191, 36, 0.15);
        --recovery-color: #fb923c; --recovery-bg: rgba(251, 146, 60, 0.15);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: var(--text-main); min-height: 100vh; padding-bottom: 40px; }
    .header { background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-color); padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
    .header-title { font-size: 22px; font-weight: 800; color: #38bdf8; display: flex; align-items: center; gap: 10px; text-shadow: 0 0 20px rgba(56, 189, 248, 0.4); }
    .header-title span { font-size: 11px; background: linear-gradient(135deg, #38bdf8, #ec4899); color: #fff; padding: 4px 12px; border-radius: 20px; font-weight: 800; letter-spacing: 1px; box-shadow: 0 0 15px rgba(236, 72, 153, 0.4); }
    .header-actions { display: flex; gap: 12px; align-items: center; }
    .time-update { font-size: 12px; color: var(--text-muted); font-weight: 600; }
    .btn-refresh { background: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); width: 38px; height: 38px; border-radius: 10px; font-weight: 700; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: 0.2s; }
    .btn-refresh:hover { background: var(--border-color); transform: rotate(180deg); }
    .btn-reset { background: rgba(248, 113, 113, 0.2); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 8px 16px; border-radius: 10px; font-weight: 700; font-size: 13px; cursor: pointer; transition: 0.2s; }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 15px rgba(248, 113, 113, 0.4); }
    .stats-bar { max-width: 800px; margin: 24px auto 16px; padding: 0 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .stat-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 16px 10px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px; letter-spacing: 0.3px; }
    .stat-value { font-size: 22px; font-weight: 800; color: var(--text-main); }
    .stat-value.win { color: var(--win-color); text-shadow: 0 0 15px rgba(52, 211, 153, 0.4); }
    .stat-value.loss { color: var(--lose-color); text-shadow: 0 0 15px rgba(248, 113, 113, 0.4); }
    .stat-value.rate { color: var(--tai-color); text-shadow: 0 0 15px rgba(56, 189, 248, 0.4); }
    .table-wrapper { max-width: 800px; margin: 0 auto; padding: 0 16px; }
    .table-container { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); max-height: 70vh; overflow-y: auto; }
    .data-table { width: 100%; border-collapse: separate; border-spacing: 0; }
    .data-table th { background: #111827; color: var(--text-muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 16px 12px; text-align: center; border-bottom: 1px solid var(--border-color); position: sticky; top: 0; z-index: 10; }
    .data-table td { padding: 14px 12px; text-align: center; border-bottom: 1px solid var(--border-color); font-size: 14px; font-weight: 600; }
    .data-table tr:last-child td { border-bottom: none; }
    .data-table tr:hover { background: rgba(255, 255, 255, 0.02); }
    .row-next { background: rgba(14, 165, 233, 0.08); border-left: 4px solid var(--tai-color); }
    .row-next.recovery { background: rgba(251, 146, 60, 0.1); border-left: 4px solid var(--recovery-color); }
    .badge { display: inline-block; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; min-width: 70px; text-align: center; }
    .badge-tai { background: var(--tai-bg); color: var(--tai-color); border: 1px solid rgba(56, 189, 248, 0.3); box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); }
    .badge-xiu { background: var(--xiu-bg); color: var(--xiu-color); border: 1px solid rgba(244, 114, 182, 0.3); box-shadow: 0 0 10px rgba(244, 114, 182, 0.2); }
    .badge-empty { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); }
    .recovery-badge { display: inline-block; margin-left: 6px; padding: 2px 8px; border-radius: 8px; font-size: 10px; font-weight: 800; background: var(--recovery-bg); color: var(--recovery-color); border: 1px solid var(--recovery-color); box-shadow: 0 0 10px rgba(251, 146, 60, 0.3); animation: pulse 1.5s infinite; letter-spacing: 0.5px; }
    .status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; padding: 6px 14px; border-radius: 20px; }
    .st-win { background: var(--win-bg); color: var(--win-color); border: 1px solid rgba(52, 211, 153, 0.3); }
    .st-lose { background: var(--lose-bg); color: var(--lose-color); border: 1px solid rgba(248, 113, 113, 0.3); }
    .st-wait { background: var(--wait-bg); color: var(--wait-color); border: 1px solid rgba(251, 191, 36, 0.3); animation: pulse 1.5s infinite; }
    .st-recover { background: var(--recovery-bg); color: var(--recovery-color); border: 1px solid var(--recovery-color); animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .dice-text { font-size: 11px; color: var(--text-muted); display: block; margin-top: 4px; font-weight: 500; }
    .conf-badge { font-size: 11px; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 2px 8px; border-radius: 10px; margin-top: 4px; display: inline-block; font-weight: 700; }
    .conf-badge.high { color: #34d399; background: rgba(52, 211, 153, 0.15); box-shadow: 0 0 10px rgba(52, 211, 153, 0.2); }
    .loading { text-align: center; padding: 40px; color: var(--tai-color); font-weight: 600; }
    @media (max-width: 500px) {
        .data-table th, .data-table td { padding: 10px 6px; font-size: 12px; }
        .badge { padding: 4px 8px; font-size: 11px; min-width: 50px; }
        .header-title { font-size: 18px; }
        .time-update { display: none; }
        .stats-bar { grid-template-columns: repeat(2, 1fr); }
        .stat-value { font-size: 18px; }
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-title">LE MINH <span>MD5 v3</span></div>
    <div class="header-actions">
        <div class="time-update" id="time-update">--:--:--</div>
        <button class="btn-refresh" onclick="fetchData()">↻</button>
        <button class="btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>

<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Thua</div><div class="stat-value loss" id="stat-lose">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ thắng</div><div class="stat-value rate" id="stat-rate">0%</div></div>
</div>

<div class="table-wrapper">
    <div class="table-container">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Phiên</th>
                    <th>Dự đoán</th>
                    <th>Kết quả</th>
                    <th>Trạng thái</th>
                </tr>
            </thead>
            <tbody id="table-body">
                <tr><td colspan="4" class="loading">Đang kết nối Server...</td></tr>
            </tbody>
        </table>
    </div>
</div>

<script>
let isResetting = false;

function animateNumber(el, target, suffix = '') {
    const start = parseInt(el.innerText.replace(/[^0-9]/g, '')) || 0;
    if (start === target) { el.innerText = target + suffix; return; }
    const duration = 500;
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
        const now = new Date();
        document.getElementById('time-update').innerText = now.toLocaleTimeString('vi-VN');
        renderTable(data.rows || [], data.stats || {});
    } catch (e) { console.error("Lỗi tải dữ liệu:", e); }
}

function renderTable(rows, stats) {
    const tbody = document.getElementById('table-body');
    const total = stats.total || 0;
    const correct = stats.correct || 0;
    const wrong = total - correct;
    animateNumber(document.getElementById('stat-total'), total);
    animateNumber(document.getElementById('stat-win'), correct);
    animateNumber(document.getElementById('stat-lose'), wrong);
    const rate = total > 0 ? (correct / total) * 100 : 0;
    animateNumber(document.getElementById('stat-rate'), Math.round(rate), '%');

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading">Không có dữ liệu. Hãy đợi phiên mới.</td></tr>';
        return;
    }
    let html = '';
    rows.forEach((row) => {
        let trClass = '';
        if (row.is_next) trClass = row.recovery_flipped ? 'class="row-next recovery"' : 'class="row-next"';
        let predHtml = `<span class="badge badge-empty">-</span>`;
        if (row.prediction === "Tài") predHtml = `<span class="badge badge-tai">TÀI</span>`;
        if (row.prediction === "Xỉu") predHtml = `<span class="badge badge-xiu">XỈU</span>`;
        let recBadge = "";
        if (row.recovery_flipped) {
            recBadge = `<span class="recovery-badge" title="Auto-flip do thua ${row.loss_streak || 0} lần">⚡</span>`;
        }
        let confHtml = "";
        if (row.conf && row.prediction !== "-") {
            const cls = row.conf >= 70 ? 'conf-badge high' : 'conf-badge';
            confHtml = `<div class="${cls}">${row.conf}%</div>`;
        }
        let predFull = `<div style="display:flex; flex-direction:column; align-items:center; gap:2px;">${predHtml}${confHtml}${recBadge}</div>`;
        let resultHtml = `<span class="badge badge-empty">-</span>`;
        if (row.result === "Tài") resultHtml = `<span class="badge badge-tai">TÀI</span>`;
        if (row.result === "Xỉu") resultHtml = `<span class="badge badge-xiu">XỈU</span>`;
        let diceDisplay = "";
        if (row.dice !== "? + ? + ?") {
            const p = row.dice.split(" + ");
            const sum = parseInt(p[0]) + parseInt(p[1]) + parseInt(p[2]);
            diceDisplay = `<span class="dice-text">${row.dice} (${sum})</span>`;
        }
        let resultFull = `<div style="display:flex; flex-direction:column; align-items:center;">${resultHtml}${diceDisplay}</div>`;
        let statusHtml = '';
        if (row.is_next) {
            statusHtml = row.recovery_flipped
                ? `<span class="status st-recover">⚡ Đảo chiều</span>`
                : `<span class="status st-wait">Chờ kết quả</span>`;
        } else if (row.is_correct === true) {
            statusHtml = `<span class="status st-win">✔ THẮNG</span>`;
        } else if (row.is_correct === false) {
            statusHtml = `<span class="status st-lose">✖ THUA</span>`;
        } else {
            statusHtml = `<span class="status" style="color:var(--text-muted)">-</span>`;
        }
        html += `<tr ${trClass}><td>#${row.phien}</td><td>${predFull}</td><td>${resultFull}</td><td>${statusHtml}</td></tr>`;
    });
    tbody.innerHTML = html;
}

async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', text: "Toàn bộ lịch sử hiển thị sẽ bị xoá và bắt đầu lại từ đầu!",
        icon: 'warning', background: '#1e293b', color: '#f8fafc',
        showCancelButton: true, confirmButtonColor: '#0ea5e9', cancelButtonColor: '#64748b',
        confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, background: '#1e293b', color: '#f8fafc', didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Thành công!', text: 'Đã xoá lịch sử và bắt đầu lại.', icon: 'success', background: '#1e293b', color: '#f8fafc', confirmButtonColor: '#0ea5e9' });
                    isResetting = false; fetchData();
                } else { throw new Error(data.message); }
            } catch (error) {
                Swal.fire({title: 'Lỗi!', text: 'Không thể reset: ' + error.message, icon: 'error', background: '#1e293b', color: '#f8fafc'});
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

# =====================================================================
# UTILS
# =====================================================================
def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"

def format_tx(results, length):
    if len(results) < length: return None
    return "-".join("T" if r == "Tài" else "X" for r in results[:length])

def encode_tx(results, length):
    if not results or len(results) < length: return None
    return "".join("T" if r == "Tài" else "X" for r in results[:length])

# =====================================================================
# PHÂN LOẠI CẦU 5P — 4 NHÃN
# =====================================================================
def classify_5p_pattern(results):
    if len(results) < 5:
        return ("Chưa đủ", None, 0)
    last5 = results[:5]
    alt_count = sum(1 for i in range(4) if last5[i] != last5[i+1])
    t_count = sum(1 for r in last5 if r == "Tài")
    x_count = 5 - t_count

    if alt_count == 4:
        return ("ĐẢO", _opp(last5[0]), 88)
    if alt_count == 0:
        return ("THUẬN", last5[0], 85)
    if alt_count == 3:
        return ("NGHỊCH", _opp(last5[0]), 70)
    if alt_count in (1, 2):
        pred = "Tài" if t_count > x_count else ("Xỉu" if x_count > t_count else _opp(last5[0]))
        return ("1-1", pred, 65)
    return ("1-1", _opp(last5[0]), 60)

# =====================================================================
# MULTI-WINDOW MD5 ENGINE (v3)
# =====================================================================
MD5_WINDOWS = (3, 4, 5, 6, 7, 8)

def learn_md5_deep_5p(valid):
    """Trả về dict {window: {hash: {Tài:n, Xỉu:n}}}."""
    dbs = {}
    n = len(valid)
    for w in MD5_WINDOWS:
        db = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
        if n >= w + 3:
            for i in range(w, n):
                hist = [v['result'] for v in valid[i-w:i]][::-1]
                tx = encode_tx(hist, w)
                if not tx: continue
                h = hashlib.md5(f"lm_mw{w}|{tx}".encode()).hexdigest()
                db[h][valid[i]['result']] += 1
        dbs[w] = db
    return dbs

def lookup_md5_deep_5p(results, dbs):
    """Aggregate kết quả từ nhiều cửa sổ MD5 → (pred, conf, p_tai)."""
    if not isinstance(dbs, dict) or not dbs:
        return (None, 0, None)

    weighted_tai = 0.0
    weighted_xiu = 0.0
    active_windows = 0
    max_window_hit = 0

    for w, db in dbs.items():
        if len(results) < w: continue
        tx = encode_tx(results, w)
        if not tx: continue
        h = hashlib.md5(f"lm_mw{w}|{tx}".encode()).hexdigest()
        if h not in db: continue
        counts = db[h]
        total = counts["Tài"] + counts["Xỉu"]
        if total < 2: continue
        p_tai = (counts["Tài"] + 1) / (total + 2)
        sample_factor = min(1.0, math.log(total + 1) / math.log(8))
        weight = (w / 5.0) * (0.5 + 0.5 * sample_factor)
        weighted_tai += p_tai * weight
        weighted_xiu += (1 - p_tai) * weight
        active_windows += 1
        if w > max_window_hit: max_window_hit = w

    if active_windows == 0:
        return (None, 0, None)

    total_w = weighted_tai + weighted_xiu
    p_tai_agg = weighted_tai / total_w if total_w > 0 else 0.5
    extremity = abs(p_tai_agg - 0.5) * 2
    conf = 55 + extremity * 28 + min(active_windows, 4) * 1.5 + max_window_hit * 0.5

    if p_tai_agg >= 0.62:
        return ("Tài", int(min(MAX_CONFIDENCE, conf)), p_tai_agg)
    if p_tai_agg <= 0.38:
        return ("Xỉu", int(min(MAX_CONFIDENCE, conf)), p_tai_agg)
    return (None, 0, p_tai_agg)

# =====================================================================
# 3 THUẬT TOÁN CƠ BẢN
# =====================================================================
def algo_streak_break(results):
    if len(results) < 20: return None
    current_streak = 1
    r0 = results[0]
    for r in results[1:]:
        if r == r0: current_streak += 1
        else: break
    if current_streak < 2: return None

    streaks = []
    cur_val = results[0]; cur_len = 1
    for r in results[1:60]:
        if r == cur_val: cur_len += 1
        else: streaks.append(cur_len); cur_val = r; cur_len = 1
    if cur_len > 0: streaks.append(cur_len)
    if len(streaks) < 5: return None

    ss = sorted(streaks)
    p75 = ss[int(len(ss) * 0.75)]
    p50 = ss[int(len(ss) * 0.50)]

    if current_streak > p75: return (_opp(r0), 76, "streak_break")
    if current_streak > p50 + 1: return (_opp(r0), 68, "streak_break_soft")
    if 2 <= current_streak <= p50: return (r0, 62, "streak_continue")
    return None

def algo_bigram_markov(results):
    if len(results) < 20: return None
    key = (results[1], results[0])
    counts = {"Tài": 0, "Xỉu": 0}
    for i in range(min(len(results) - 2, 80)):
        if (results[i+2], results[i+1]) == key:
            counts[results[i]] += 1
    total = counts["Tài"] + counts["Xỉu"]
    if total < 8: return None
    p_tai = counts["Tài"] / total
    if p_tai >= 0.65: return ("Tài", 74, "bigram_markov")
    if p_tai <= 0.35: return ("Xỉu", 74, "bigram_markov")
    if p_tai >= 0.58: return ("Tài", 62, "bigram_markov_soft")
    if p_tai <= 0.42: return ("Xỉu", 62, "bigram_markov_soft")
    return None

def algo_momentum_reversal(results):
    if len(results) < 8: return None
    b = [1 if r == "Tài" else 0 for r in results[:8]]
    weights = [1.5, 1.3, 1.1, 0.9, 0.7, 0.5, 0.4, 0.3]
    momentum = sum(b[i] * weights[i] for i in range(8)) / sum(weights)
    last_2 = b[:2]; last_3 = b[:3]

    if all(x == 1 for x in last_3) and momentum < 0.7:
        return ("Xỉu", 70, "momentum_reversal_down")
    if all(x == 0 for x in last_3) and momentum > 0.3:
        return ("Tài", 70, "momentum_reversal_up")
    if momentum >= 0.75 and sum(last_2) == 2:
        return ("Tài", 66, "momentum_strong_up")
    if momentum <= 0.25 and sum(last_2) == 0:
        return ("Xỉu", 66, "momentum_strong_down")
    return None

# =====================================================================
# 3 THUẬT TOÁN NÂNG CAO v3
# =====================================================================
def algo_sequence_match(results, min_len=4, max_len=10):
    n = len(results)
    if n < min_len + 3: return None
    best_len = 0
    tally = {"Tài": 0, "Xỉu": 0}
    for L in range(min_len, min(max_len + 1, n)):
        suffix = tuple(results[:L])
        for i in range(L, n):
            if i - 1 < 0: continue
            if tuple(results[i:i+L]) == suffix:
                tally[results[i-1]] += 1
                if L > best_len: best_len = L
    total = tally["Tài"] + tally["Xỉu"]
    if total < 3 or best_len < min_len: return None
    p_tai = tally["Tài"] / total
    strength = min(1.0, (best_len - 3) / 7) * 0.6 + min(1.0, total / 10) * 0.4
    if p_tai >= 0.70: return ("Tài", min(85, int(62 + strength * 20)), f"seq_L{best_len}_n{total}")
    if p_tai <= 0.30: return ("Xỉu", min(85, int(62 + strength * 20)), f"seq_L{best_len}_n{total}")
    if p_tai >= 0.60: return ("Tài", int(58 + strength * 10), f"seq_soft_L{best_len}")
    if p_tai <= 0.40: return ("Xỉu", int(58 + strength * 10), f"seq_soft_L{best_len}")
    return None

def algo_trigram_markov(results):
    if len(results) < 30: return None
    key = (results[2], results[1], results[0])
    counts = {"Tài": 0, "Xỉu": 0}
    for i in range(min(len(results) - 3, 100)):
        if (results[i+3], results[i+2], results[i+1]) == key:
            counts[results[i]] += 1
    total = counts["Tài"] + counts["Xỉu"]
    if total < 5: return None
    p_tai = counts["Tài"] / total
    if p_tai >= 0.70: return ("Tài", 78, "trigram_markov")
    if p_tai <= 0.30: return ("Xỉu", 78, "trigram_markov")
    if p_tai >= 0.60: return ("Tài", 64, "trigram_markov_soft")
    if p_tai <= 0.40: return ("Xỉu", 64, "trigram_markov_soft")
    return None

def algo_entropy_regime(results, window=12):
    if len(results) < window: return None
    sub = results[:window]
    p_tai = sum(1 for r in sub if r == "Tài") / window
    p_xiu = 1 - p_tai
    if p_tai == 0 or p_xiu == 0:
        entropy = 0.0
    else:
        entropy = -(p_tai * math.log2(p_tai) + p_xiu * math.log2(p_xiu))
    return {"entropy": round(entropy, 3), "p_tai": round(p_tai, 3)}

# =====================================================================
# ADAPTIVE WEIGHT + BAYESIAN CALIBRATION
# =====================================================================
def _get_adaptive_weight(algo_name, base_w):
    stat = ALGO_RECENT_STATS[algo_name]
    total = stat["win"] + stat["lose"]
    if total < 8: return base_w
    wr = stat["win"] / total
    shrink = min(1.0, total / 25.0)
    raw_factor = 0.6 + wr * 0.8
    factor = 1.0 + (raw_factor - 1.0) * shrink
    factor = max(0.5, min(1.5, factor))
    return base_w * factor

def _update_recent_stats(results, md5_dbs):
    global ALGO_RECENT_STATS
    ALGO_RECENT_STATS.clear()
    if len(results) < 20: return
    limit = min(ADAPTIVE_WINDOW, len(results) - 6)
    algo_fns = [algo_streak_break, algo_bigram_markov, algo_momentum_reversal,
                algo_trigram_markov, algo_sequence_match]
    for i in range(1, limit):
        hist = results[i:]
        actual = results[i - 1]
        try:
            label, pred, _ = classify_5p_pattern(hist)
            if pred:
                k = f"pattern:{label}"
                ALGO_RECENT_STATS[k]["win" if pred == actual else "lose"] += 1
        except Exception: pass
        for fn in algo_fns:
            try:
                s = fn(hist)
                if s:
                    k = s[2]
                    ALGO_RECENT_STATS[k]["win" if s[0] == actual else "lose"] += 1
            except Exception: pass

def _update_calibration(valid, md5_dbs):
    global CALIBRATION_BUCKETS, CALIBRATION_READY
    CALIBRATION_BUCKETS.clear()
    n = len(valid)
    if n < 30:
        CALIBRATION_READY = False
        return
    limit = min(60, n - 10)
    for i in range(1, limit):
        hist = [v['result'] for v in valid[:i]][::-1]
        if len(hist) < 6: continue
        try:
            pred, conf = compute_prediction(hist, md5_dbs, _skip_calibration=True)
        except Exception:
            continue
        if pred not in ("Tài", "Xỉu"): continue
        actual = valid[i]['result']
        bucket = (conf // 5) * 5
        CALIBRATION_BUCKETS[bucket]["win" if pred == actual else "lose"] += 1
    CALIBRATION_READY = True

def _calibrate_confidence(conf):
    if not CALIBRATION_READY: return conf
    bucket = (conf // 5) * 5
    stat = CALIBRATION_BUCKETS.get(bucket)
    if not stat: return conf
    total = stat["win"] + stat["lose"]
    if total < 12: return conf
    real_wr = stat["win"] / total * 100
    calibrated = conf * 0.65 + real_wr * 0.35
    return int(max(55, min(MAX_CONFIDENCE, calibrated)))

def _detect_overfit_guard(results):
    if len(results) < 10: return False
    def _alt(sub):
        if len(sub) < 5: return None
        return sum(1 for i in range(4) if sub[i] != sub[i+1])
    old = _alt(results[5:10])
    new = _alt(results[:5])
    if old is None or new is None: return False
    return abs(old - new) >= 3

# =====================================================================
# DỰ ĐOÁN CHÍNH v3
# =====================================================================
def compute_prediction(results, md5_dbs, _skip_calibration=False):
    if not results: return ("Tài", 52)
    if len(results) < 5: return (_opp(results[0]), 55)

    _update_recent_stats(results, md5_dbs)
    overfit = _detect_overfit_guard(results)
    ent_info = algo_entropy_regime(results, 12)
    high_entropy = ent_info is not None and ent_info["entropy"] > 0.92

    pattern_label, pattern_pred, pattern_conf = classify_5p_pattern(results)
    md5_pred, md5_conf, md5_p_tai = lookup_md5_deep_5p(results, md5_dbs)
    streak_sig = algo_streak_break(results)
    bigram_sig = algo_bigram_markov(results)
    momentum_sig = algo_momentum_reversal(results)
    trigram_sig = algo_trigram_markov(results)
    seq_sig = algo_sequence_match(results)

    # TẦNG 1: Siêu tín hiệu
    if md5_pred and md5_conf >= 80:
        if pattern_pred == md5_pred:
            return (md5_pred, min(MAX_CONFIDENCE, md5_conf + 4))
        if trigram_sig and trigram_sig[0] == md5_pred:
            return (md5_pred, min(MAX_CONFIDENCE, md5_conf + 3))
        return (md5_pred, md5_conf)

    if pattern_label in ("ĐẢO", "THUẬN") and pattern_conf >= 85:
        if not md5_pred or md5_conf < 70:
            return (pattern_pred, pattern_conf)

    # TẦNG 2: Weighted Vote
    votes = {"Tài": 0.0, "Xỉu": 0.0}
    active = []

    if pattern_pred:
        w = _get_adaptive_weight(f"pattern:{pattern_label}", pattern_conf / 100 * 2.0)
        votes[pattern_pred] += w
        active.append(("pattern", pattern_pred, w))

    if md5_pred and md5_conf >= 58:
        w = _get_adaptive_weight("md5_multi", md5_conf / 100 * 2.5)
        votes[md5_pred] += w
        active.append(("md5", md5_pred, w))

    for sig, base_mult in [
        (streak_sig, 1.5), (bigram_sig, 1.8), (momentum_sig, 1.6),
        (trigram_sig, 1.7), (seq_sig, 1.9),
    ]:
        if sig:
            pred, conf, name = sig
            w = _get_adaptive_weight(name, conf / 100 * base_mult)
            votes[pred] += w
            active.append((name, pred, w))

    total_v = votes["Tài"] + votes["Xỉu"]
    if total_v == 0:
        return (_opp(results[0]), 55)

    pred = "Tài" if votes["Tài"] > votes["Xỉu"] else "Xỉu"
    win = max(votes["Tài"], votes["Xỉu"])
    ratio = win / total_v
    diff_ratio = abs(votes["Tài"] - votes["Xỉu"]) / total_v

    if diff_ratio >= 0.50 and ratio >= 0.75:
        conf = int(78 + ratio * 12)
    elif diff_ratio >= 0.25 and ratio >= 0.62:
        conf = int(66 + diff_ratio * 26)
    else:
        conf = int(56 + diff_ratio * 30)
    conf = max(55, min(MAX_CONFIDENCE, conf))

    agree = sum(1 for _, p, _ in active if p == pred)
    disagree = len(active) - agree
    if agree >= 5 and disagree == 0:
        conf = min(MAX_CONFIDENCE, conf + 7)
    elif agree >= 4 and disagree <= 1:
        conf = min(MAX_CONFIDENCE, conf + 4)
    elif disagree >= 3:
        conf = max(55, conf - 10)

    if overfit: conf = max(55, conf - 8)
    if high_entropy: conf = max(55, conf - 6)

    if md5_pred == pred and md5_conf >= 70 and conf < 78:
        conf = min(80, conf + 4)

    if not _skip_calibration:
        conf = _calibrate_confidence(conf)

    return (pred, conf)

# =====================================================================
# RECOVERY
# =====================================================================
def apply_recovery(base_pred, conf, loss_streak, results):
    if loss_streak < 2:
        return (base_pred, conf, False)
    if _detect_overfit_guard(results):
        return (base_pred, max(55, conf - 5), False)
    if FLIP_STATS["consecutive_loss"] >= 2:
        return (base_pred, max(55, conf - 3), False)
    if loss_streak == 2:
        return (_opp(base_pred), max(62, conf - 5), True)
    return (_opp(base_pred), min(MAX_CONFIDENCE, max(conf, 78)), True)

def compute_loss_streak(valid, md5_dbs):
    if len(valid) < 5: return 0
    streak = 0
    for i in range(len(valid) - 1, len(valid) - 10, -1):
        if i < 5: break
        hist = [v['result'] for v in valid[:i]][::-1]
        pred, _ = compute_prediction(hist, md5_dbs)
        if pred == valid[i]['result']: break
        streak += 1
    return streak

# =====================================================================
# API
# =====================================================================
def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(API_URL_MD5, timeout=8, headers=headers)
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
                return rows, True
    except Exception as e:
        print(f"[API ERROR]: {e}")
    return [], False

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/history')
def history():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if raw_rows:
            for row in raw_rows: HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0}})

        md5_dbs = learn_md5_deep_5p(valid)
        _update_calibration(valid, md5_dbs)
        loss_streak = compute_loss_streak(valid, md5_dbs)

        out = []; correct_count = 0; total_past = 0
        history_for_next = [v['result'] for v in valid][::-1]

        base_pred, base_conf = compute_prediction(history_for_next, md5_dbs)
        next_pred, next_conf, flipped = apply_recovery(base_pred, base_conf, loss_streak, history_for_next)

        out.append({
            'phien': valid[-1]['phien'] + 1, 'is_next': True,
            'prediction': next_pred, 'result': 'Chờ...', 'dice': "? + ? + ?",
            'is_correct': None, 'conf': next_conf,
            'recovery_flipped': flipped, 'loss_streak': loss_streak
        })

        for i in range(len(valid) - 1, max(-1, len(valid) - 150), -1):
            hist = [v['result'] for v in valid[:i]][::-1]
            pred, conf = compute_prediction(hist, md5_dbs) if len(hist) >= 5 else ("-", 50)
            is_correct = (pred == valid[i]['result']) if pred != "-" else None
            if is_correct is not None: total_past += 1
            if is_correct: correct_count += 1
            out.append({
                'phien': valid[i]['phien'], 'is_next': False, 'prediction': pred,
                'result': valid[i]['result'], 'dice': valid[i]['dice'],
                'is_correct': is_correct, 'conf': conf, 'recovery_flipped': False
            })

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count},
            'calibration': {str(k): v for k, v in CALIBRATION_BUCKETS.items()} if CALIBRATION_READY else {}
        })
    except Exception as e:
        return jsonify({'error': str(e), 'rows': [], 'stats': {'total': 0, 'correct': 0}})

@app.route('/api/predict')
def predict():
    global RESET_ID
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            for row in raw_rows: HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid: return jsonify({'error': 'Chưa có dữ liệu'})

        results = [v['result'] for v in valid][::-1]
        md5_dbs = learn_md5_deep_5p(valid)
        loss_streak = compute_loss_streak(valid, md5_dbs)

        base_pred, base_conf = compute_prediction(results, md5_dbs)
        pred, conf, flipped = apply_recovery(base_pred, base_conf, loss_streak, results)

        pattern_label, pattern_pred, pattern_conf = classify_5p_pattern(results)
        md5_pred, md5_conf, md5_p_tai = lookup_md5_deep_5p(results, md5_dbs)
        streak_sig = algo_streak_break(results)
        bigram_sig = algo_bigram_markov(results)
        momentum_sig = algo_momentum_reversal(results)
        trigram_sig = algo_trigram_markov(results)
        seq_sig = algo_sequence_match(results)
        ent = algo_entropy_regime(results, 12)

        return jsonify({
            'version': 'v3',
            'last_phien': valid[-1]['phien'], 'next_phien': valid[-1]['phien'] + 1,
            'prediction': pred, 'confidence': conf, 'recovery_flipped': flipped,
            'loss_streak': loss_streak,
            'overfit_guard': _detect_overfit_guard(results),
            'entropy': ent,
            'ls_5p': format_tx(results, 5),
            'signals': {
                'pattern': {'label': pattern_label, 'pred': pattern_pred, 'conf': pattern_conf},
                'md5': {'pred': md5_pred, 'conf': md5_conf,
                        'p_tai': round(md5_p_tai, 3) if md5_p_tai is not None else None},
                'streak': {'pred': streak_sig[0] if streak_sig else None,
                           'conf': streak_sig[1] if streak_sig else 0,
                           'algo': streak_sig[2] if streak_sig else None},
                'bigram': {'pred': bigram_sig[0] if bigram_sig else None,
                           'conf': bigram_sig[1] if bigram_sig else 0,
                           'algo': bigram_sig[2] if bigram_sig else None},
                'momentum': {'pred': momentum_sig[0] if momentum_sig else None,
                             'conf': momentum_sig[1] if momentum_sig else 0,
                             'algo': momentum_sig[2] if momentum_sig else None},
                'trigram': {'pred': trigram_sig[0] if trigram_sig else None,
                            'conf': trigram_sig[1] if trigram_sig else 0,
                            'algo': trigram_sig[2] if trigram_sig else None},
                'sequence': {'pred': seq_sig[0] if seq_sig else None,
                             'conf': seq_sig[1] if seq_sig else 0,
                             'algo': seq_sig[2] if seq_sig else None},
            },
            'adaptive_stats': dict(ALGO_RECENT_STATS),
            'calibration': {str(k): v for k, v in CALIBRATION_BUCKETS.items()} if CALIBRATION_READY else {},
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/lc79md5')
def lc79md5_api():
    global RESET_ID
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            for row in raw_rows: HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'id': '@cskhleminh', 'phien': '-', 'ket_qua': '-',
                            'du_doan': '-', 'do_tin_cay': '50%'})

        results = [v['result'] for v in valid][::-1]
        md5_dbs = learn_md5_deep_5p(valid)
        loss_streak = compute_loss_streak(valid, md5_dbs)

        base_pred, base_conf = compute_prediction(results, md5_dbs)
        pred, conf, flipped = apply_recovery(base_pred, base_conf, loss_streak, results)

        last = valid[-1]
        ket_qua = f"{last['result'].lower()} {last['dice'].replace(' + ', '-')}"

        return jsonify({
            'id': '@cskhleminh', 'phien': str(last['phien'] + 1),
            'ket_qua': ket_qua, 'du_doan': pred, 'do_tin_cay': f"{conf}%"
        })
    except Exception as e:
        return jsonify({'id': '@cskhleminh', 'phien': '-', 'ket_qua': '-',
                        'du_doan': '-', 'do_tin_cay': '50%', 'error': str(e)})

@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE, ALGO_RECENT_STATS, CALIBRATION_BUCKETS, CALIBRATION_READY, FLIP_STATS
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                ALGO_RECENT_STATS.clear()
                CALIBRATION_BUCKETS.clear()
                CALIBRATION_READY = False
                FLIP_STATS.update({"win": 0, "lose": 0, "consecutive_loss": 0})
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/pattern-debug')
def pattern_debug():
    global RESET_ID
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            for row in raw_rows: HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]
        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid: return jsonify({'error': 'No data'})
        results = [v['result'] for v in valid][::-1]
        md5_dbs = learn_md5_deep_5p(valid)

        pattern_label, pattern_pred, pattern_conf = classify_5p_pattern(results)
        md5_pred, md5_conf, md5_p_tai = lookup_md5_deep_5p(results, md5_dbs)
        streak_sig = algo_streak_break(results)
        bigram_sig = algo_bigram_markov(results)
        momentum_sig = algo_momentum_reversal(results)
        trigram_sig = algo_trigram_markov(results)
        seq_sig = algo_sequence_match(results)
        ent = algo_entropy_regime(results, 12)

        return jsonify({
            'version': 'v3',
            'last_5p': format_tx(results, 5),
            'pattern': {'label': pattern_label, 'pred': pattern_pred, 'conf': pattern_conf},
            'md5': {'pred': md5_pred, 'conf': md5_conf,
                    'p_tai': round(md5_p_tai, 3) if md5_p_tai is not None else None},
            'streak': {'pred': streak_sig[0] if streak_sig else None,
                       'conf': streak_sig[1] if streak_sig else 0,
                       'algo': streak_sig[2] if streak_sig else None},
            'bigram': {'pred': bigram_sig[0] if bigram_sig else None,
                       'conf': bigram_sig[1] if bigram_sig else 0,
                       'algo': bigram_sig[2] if bigram_sig else None},
            'momentum': {'pred': momentum_sig[0] if momentum_sig else None,
                         'conf': momentum_sig[1] if momentum_sig else 0,
                         'algo': momentum_sig[2] if momentum_sig else None},
            'trigram': {'pred': trigram_sig[0] if trigram_sig else None,
                        'conf': trigram_sig[1] if trigram_sig else 0,
                        'algo': trigram_sig[2] if trigram_sig else None},
            'sequence': {'pred': seq_sig[0] if seq_sig else None,
                         'conf': seq_sig[1] if seq_sig else 0,
                         'algo': seq_sig[2] if seq_sig else None},
            'entropy': ent,
            'overfit_guard': _detect_overfit_guard(results),
            'adaptive_stats': dict(ALGO_RECENT_STATS),
            'calibration': {str(k): v for k, v in CALIBRATION_BUCKETS.items()} if CALIBRATION_READY else {},
            'md5_windows': list(MD5_WINDOWS),
            'md5_db_sizes': {w: len(db) for w, db in md5_dbs.items()},
        })
    except Exception as e:
        return jsonify({'error': str(e)})


# =====================================================================
# MODULE M5 CANDLE (giữ nguyên)
# =====================================================================
M5_CACHE = {}
M5_CACHE_TTL = 30

EXCHANGE_ENDPOINTS = [
    {"name": "binance", "url": "https://api.binance.com/api/v3/klines",
     "params": lambda sym, tf, lim: {"symbol": sym.upper(), "interval": tf, "limit": lim},
     "parse": lambda raw: [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
                            "l": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in raw]},
    {"name": "bybit", "url": "https://api.bybit.com/v5/market/kline",
     "params": lambda sym, tf, lim: {"category": "spot", "symbol": sym.upper(),
                                     "interval": tf.replace("m", ""), "limit": min(lim, 1000)},
     "parse": lambda raw: [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
                            "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
                           for k in reversed(raw["result"]["list"])]},
    {"name": "okx", "url": "https://www.okx.com/api/v5/market/candles",
     "params": lambda sym, tf, lim: {"instId": sym.upper().replace("USDT", "-USDT"),
                                     "bar": tf, "limit": min(lim, 300)},
     "parse": lambda raw: [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
                            "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
                           for k in reversed(raw["data"])]},
]

def m5_fetch_klines(symbol="BTCUSDT", timeframe="5m", limit=200):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    last_err = None
    for ep in EXCHANGE_ENDPOINTS:
        try:
            r = requests.get(ep["url"], params=ep["params"](symbol, timeframe, limit),
                             headers=headers, timeout=8)
            if r.status_code == 200:
                candles = ep["parse"](r.json())
                if candles and len(candles) >= 20:
                    return candles, ep["name"]
            last_err = f"{ep['name']}: HTTP {r.status_code}"
        except Exception as e:
            last_err = f"{ep['name']}: {e}"
    raise RuntimeError(f"Không lấy được nến: {last_err}")

def m5_ema(values, period):
    if len(values) < period: return [None] * len(values)
    k = 2 / (period + 1)
    out = [None] * (period - 1)
    s = sum(values[:period]) / period
    out.append(s); prev = s
    for v in values[period:]:
        prev = v * k + prev * (1 - k)
        out.append(prev)
    return out

def m5_sma(values, period):
    if len(values) < period: return [None] * len(values)
    out = [None] * (period - 1)
    s = sum(values[:period]); out.append(s / period)
    for i in range(period, len(values)):
        s += values[i] - values[i - period]
        out.append(s / period)
    return out

def m5_rsi(closes, period=14):
    if len(closes) < period + 1: return [None] * len(closes)
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    out = [None] * period
    rs = avg_g / avg_l if avg_l else 999
    out.append(100 - 100 / (1 + rs))
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rs = avg_g / avg_l if avg_l else 999
        out.append(100 - 100 / (1 + rs))
    return out

def m5_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1: return [None] * len(closes)
    trs = [None]
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    out = [None] * period
    prev = sum(trs[1:period + 1]) / period
    out.append(prev)
    for i in range(period + 1, len(trs)):
        prev = (prev * (period - 1) + trs[i]) / period
        out.append(prev)
    return out

def m5_macd(closes, fast=12, slow=26, signal=9):
    ef = m5_ema(closes, fast); es = m5_ema(closes, slow)
    macd_line = [None] * len(closes)
    for i in range(len(closes)):
        if ef[i] is not None and es[i] is not None:
            macd_line[i] = ef[i] - es[i]
    valid = [v for v in macd_line if v is not None]
    if len(valid) >= signal:
        sig_valid = m5_ema(valid, signal)
        signal_line = [None] * (len(macd_line) - len(sig_valid)) + sig_valid
    else:
        signal_line = [None] * len(macd_line)
    hist = [None] * len(closes)
    for i in range(len(closes)):
        if macd_line[i] is not None and signal_line[i] is not None:
            hist[i] = macd_line[i] - signal_line[i]
    return macd_line, signal_line, hist

def m5_bollinger(closes, period=20, mult=2.0):
    mid = m5_sma(closes, period)
    upper = [None] * len(closes); lower = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        win = closes[i - period + 1:i + 1]
        m = mid[i]
        std = math.sqrt(sum((x - m) ** 2 for x in win) / period)
        upper[i] = m + mult * std; lower[i] = m - mult * std
    return upper, mid, lower

def m5_detect_patterns(candles):
    if len(candles) < 3: return []
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]
    pats = []
    def body(c): return abs(c["c"] - c["o"])
    def rng(c): return c["h"] - c["l"] + 1e-9
    def bull(c): return c["c"] > c["o"]
    def bear(c): return c["c"] < c["o"]
    if bear(c2) and bull(c3) and c3["c"] > c2["o"] and c3["o"] < c2["c"]:
        pats.append(("bullish_engulfing", "UP"))
    if bull(c2) and bear(c3) and c3["c"] < c2["o"] and c3["o"] > c2["c"]:
        pats.append(("bearish_engulfing", "DOWN"))
    b3 = body(c3)
    lower_wick = min(c3["o"], c3["c"]) - c3["l"]
    upper_wick = c3["h"] - max(c3["o"], c3["c"])
    if b3 > 0 and lower_wick > 2 * b3 and upper_wick < b3: pats.append(("hammer", "UP"))
    if b3 > 0 and upper_wick > 2 * b3 and lower_wick < b3: pats.append(("shooting_star", "DOWN"))
    if body(c3) < 0.1 * rng(c3): pats.append(("doji", "NEUTRAL"))
    if all(bull(c) for c in (c1, c2, c3)) and c3["c"] > c2["c"] > c1["c"]:
        pats.append(("three_white_soldiers", "UP"))
    if all(bear(c) for c in (c1, c2, c3)) and c3["c"] < c2["c"] < c1["c"]:
        pats.append(("three_black_crows", "DOWN"))
    return pats

def m5_detect_trend(candles):
    closes = [c["c"] for c in candles]
    reasons = []; score = 0
    ema9 = m5_ema(closes, 9); ema21 = m5_ema(closes, 21); ema50 = m5_ema(closes, 50)
    if ema9[-1] and ema21[-1] and ema9[-1] > ema21[-1]: score += 1; reasons.append("EMA9>EMA21")
    if ema9[-1] and ema21[-1] and ema9[-1] < ema21[-1]: score -= 1; reasons.append("EMA9<EMA21")
    if ema21[-1] and ema50[-1] and ema21[-1] > ema50[-1]: score += 1; reasons.append("EMA21>EMA50")
    if ema21[-1] and ema50[-1] and ema21[-1] < ema50[-1]: score -= 1; reasons.append("EMA21<EMA50")
    if len(closes) >= 20:
        w = closes[-20:]; n = len(w); xs = list(range(n)); xm = (n - 1) / 2
        ym = sum(w) / n
        num = sum((i - xm) * (w[i] - ym) for i in range(n))
        den = sum((i - xm) ** 2 for i in range(n))
        slope = num / den if den else 0
        atr_vals = m5_atr([c["h"] for c in candles], [c["l"] for c in candles], closes, 14)
        atr_v = atr_vals[-1] or (max(closes[-20:]) - min(closes[-20:])) / 10
        norm = slope / atr_v if atr_v else 0
        if norm > 0.05: score += 1; reasons.append("slope_up")
        elif norm < -0.05: score -= 1; reasons.append("slope_down")
    rsi_vals = m5_rsi(closes, 14)
    r = rsi_vals[-1] if rsi_vals and rsi_vals[-1] is not None else 50
    if r > 60: score += 1; reasons.append(f"RSI={r:.0f}")
    elif r < 40: score -= 1; reasons.append(f"RSI={r:.0f}")
    ml, sl, hist = m5_macd(closes)
    if hist[-1] is not None:
        if hist[-1] > 0: score += 1; reasons.append("MACD+")
        else: score -= 1; reasons.append("MACD-")
    if score >= 3: trend = "UP"
    elif score <= -3: trend = "DOWN"
    else: trend = "SIDEWAY"
    return trend, score, reasons

def m5_classify_state(candles, trend):
    closes = [c["c"] for c in candles]
    reasons = []
    last = candles[-1]; prev = candles[-2] if len(candles) >= 2 else last
    pats = m5_detect_patterns(candles)
    pat_names = [p[0] for p in pats]
    pat_dirs = [p[1] for p in pats if p[1] != "NEUTRAL"]
    bullish_rev = ("hammer" in pat_names or "bullish_engulfing" in pat_names)
    bearish_rev = ("shooting_star" in pat_names or "bearish_engulfing" in pat_names)
    up_bb, mid_bb, low_bb = m5_bollinger(closes, 20)
    bb_pos = None
    if up_bb[-1] is not None and closes[-1] is not None:
        rng = up_bb[-1] - low_bb[-1]
        if rng > 0: bb_pos = (closes[-1] - low_bb[-1]) / rng
    rsis = m5_rsi(closes, 14)
    rsi_val = rsis[-1] if rsis[-1] is not None else 50
    ml, sl, hist = m5_macd(closes)
    hist_now = hist[-1] if hist[-1] is not None else 0
    hist_prev = hist[-2] if len(hist) >= 2 and hist[-2] is not None else 0
    macd_bull = hist_now > 0 and hist_now > hist_prev
    macd_bear = hist_now < 0 and hist_now < hist_prev
    b = abs(last["c"] - last["o"]); rng_c = last["h"] - last["l"] + 1e-9
    body_ratio = b / rng_c
    dao_score = 0
    if bullish_rev and trend in ("DOWN", "SIDEWAY"): dao_score += 3; reasons.append("bullish_reversal")
    if bearish_rev and trend in ("UP", "SIDEWAY"): dao_score += 3; reasons.append("bearish_reversal")
    if bb_pos is not None and bb_pos < 0.05 and trend != "UP" and bullish_rev: dao_score += 2; reasons.append("bb_oversold_reversal")
    if bb_pos is not None and bb_pos > 0.95 and trend != "DOWN" and bearish_rev: dao_score += 2; reasons.append("bb_overbought_reversal")
    if rsi_val < 30 and bullish_rev: dao_score += 1; reasons.append("rsi_oversold")
    if rsi_val > 70 and bearish_rev: dao_score += 1; reasons.append("rsi_overbought")
    thuan_score = 0
    if trend == "UP" and macd_bull and body_ratio > 0.5: thuan_score += 2; reasons.append("trend_up_momentum")
    if trend == "DOWN" and macd_bear and body_ratio > 0.5: thuan_score += 2; reasons.append("trend_down_momentum")
    if trend == "UP" and last["c"] > prev["h"]: thuan_score += 2; reasons.append("breakout_up")
    if trend == "DOWN" and last["c"] < prev["l"]: thuan_score += 2; reasons.append("breakdown_down")
    nghich_score = 0
    if trend == "UP" and (bearish_rev or (macd_bear and body_ratio < 0.4)): nghich_score += 2; reasons.append("pullback_in_uptrend")
    if trend == "DOWN" and (bullish_rev or (macd_bull and body_ratio < 0.4)): nghich_score += 2; reasons.append("bounce_in_downtrend")
    if trend == "UP" and rsi_val > 70: nghich_score += 1; reasons.append("rsi_overbought_uptrend")
    if trend == "DOWN" and rsi_val < 30: nghich_score += 1; reasons.append("rsi_oversold_downtrend")
    xuhuong_score = 0
    if trend in ("UP", "DOWN") and body_ratio > 0.6 and abs(hist_now) > abs(hist_prev): xuhuong_score += 2; reasons.append("strong_trend_candle")
    if trend != "SIDEWAY" and abs(hist_now) > 0: xuhuong_score += 1; reasons.append("macd_aligned")
    scores = {"DAO": dao_score, "THUAN": thuan_score, "NGHICH": nghich_score, "XUHUONG": xuhuong_score}
    best_state = max(scores, key=scores.get); best_score = scores[best_state]
    if best_score == 0:
        best_state = "XUHUONG" if trend == "SIDEWAY" else "THUAN"
    if best_state == "DAO":
        if any(d == "UP" for d in pat_dirs) or (bb_pos is not None and bb_pos < 0.2): signal = "BUY"
        elif any(d == "DOWN" for d in pat_dirs) or (bb_pos is not None and bb_pos > 0.8): signal = "SELL"
        else: signal = "WAIT"
    elif best_state == "THUAN":
        signal = "BUY" if trend == "UP" else ("SELL" if trend == "DOWN" else "WAIT")
    elif best_state == "NGHICH":
        signal = "WAIT"
    else:
        signal = "BUY" if trend == "UP" else ("SELL" if trend == "DOWN" else "WAIT")
    base_conf = 50 + best_score * 8
    if trend != "SIDEWAY": base_conf += 5
    if pats: base_conf += 3
    conf = int(max(40, min(95, base_conf)))
    return best_state, signal, conf, reasons

def m5_analyze(symbol="BTCUSDT", timeframe="5m", limit=200):
    key = f"{symbol.upper()}_{timeframe}"
    now = datetime.now().timestamp()
    if key in M5_CACHE:
        ts, data = M5_CACHE[key]
        if now - ts < M5_CACHE_TTL: return data
    candles, exchange = m5_fetch_klines(symbol, timeframe, limit)
    trend, trend_score, trend_reasons = m5_detect_trend(candles)
    state, signal, conf, state_reasons = m5_classify_state(candles, trend)
    last = candles[-1]
    reasons = trend_reasons + state_reasons
    seen = set(); reasons_dedup = []
    for r in reasons:
        if r not in seen: seen.add(r); reasons_dedup.append(r)
    result = {"symbol": symbol.upper(), "timeframe": timeframe,
              "timestamp": int(last["t"]), "price": round(last["c"], 6),
              "trend": trend, "state": state, "signal": signal,
              "confidence": conf, "reasons": reasons_dedup,
              "exchange": exchange, "candle_count": len(candles),
              "generated_at": datetime.now().isoformat()}
    M5_CACHE[key] = (now, result)
    return result

@app.route('/api/m5/<symbol>')
@app.route('/api/m5/<symbol>/<timeframe>')
def m5_api(symbol, timeframe="5m"):
    try:
        return jsonify(m5_analyze(symbol, timeframe, 200))
    except Exception as e:
        return jsonify({"symbol": symbol.upper(), "timeframe": timeframe,
                        "error": str(e), "trend": "SIDEWAY", "state": "XUHUONG",
                        "signal": "WAIT", "confidence": 0, "reasons": [f"error: {e}"]})

@app.route('/api/m5/batch')
@app.route('/api/m5/batch/<symbols>')
def m5_batch(symbols="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"):
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:10]
    out = {}
    for s in sym_list:
        try: out[s] = m5_analyze(s, "5m", 200)
        except Exception as e: out[s] = {"symbol": s, "error": str(e)}
    return jsonify({"count": len(out), "results": out})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
