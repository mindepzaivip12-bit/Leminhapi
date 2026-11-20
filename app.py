import os
import math
import hashlib
import time
import traceback
from datetime import datetime
from collections import defaultdict, Counter, deque
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
# CACHE ĐA TẦNG
# =====================================================================
_MD5_DB_CACHE = {"key": None, "value": None, "ts": 0}
_CALIB_CACHE = {"key": None, "value": None, "ts": 0}
_PRED_CACHE = {"key": None, "value": None, "ts": 0}
_LOSS_STREAK_CACHE = {"key": None, "value": 0, "ts": 0}
_CACHE_TTL = 5.0
_PRED_CACHE_TTL = 4.0

# =====================================================================
# ADAPTIVE LEARNING
# =====================================================================
ALGO_RECENT_STATS = defaultdict(lambda: {"win": 0, "lose": 0})
ADAPTIVE_WINDOW = 25
CALIBRATION_BUCKETS = defaultdict(lambda: {"win": 0, "lose": 0})
CALIBRATION_READY = False
FLIP_STATS = {"win": 0, "lose": 0, "consecutive_loss": 0}
META_WEIGHTS = {}

# =====================================================================
# HTML TEMPLATE
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 v5</title>
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
    <div class="header-title">LE MINH <span>MD5 v5</span></div>
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
            recBadge = `<span class="recovery-badge" title="Auto-flip">⚡</span>`;
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
        title: 'Xác nhận Reset?', text: "Toàn bộ lịch sử hiển thị sẽ bị xoá!",
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
                    Swal.fire({ title: 'Thành công!', text: 'Đã xoá lịch sử.', icon: 'success', background: '#1e293b', color: '#f8fafc', confirmButtonColor: '#0ea5e9' });
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

def _b(r):
    return 1 if r == "Tài" else 0

# =====================================================================
# PHÂN LOẠI CẦU 5P
# =====================================================================
def classify_5p_pattern(results):
    if len(results) < 5: return ("Chưa đủ", None, 0)
    last5 = results[:5]
    alt_count = sum(1 for i in range(4) if last5[i] != last5[i+1])
    t_count = sum(1 for r in last5 if r == "Tài")
    x_count = 5 - t_count
    if alt_count == 4: return ("ĐẢO", _opp(last5[0]), 88)
    if alt_count == 0: return ("THUẬN", last5[0], 85)
    if alt_count == 3: return ("NGHỊCH", _opp(last5[0]), 70)
    if alt_count in (1, 2):
        pred = "Tài" if t_count > x_count else ("Xỉu" if x_count > t_count else _opp(last5[0]))
        return ("1-1", pred, 65)
    return ("1-1", _opp(last5[0]), 60)

# =====================================================================
# MULTI-WINDOW MD5 ENGINE
# =====================================================================
MD5_WINDOWS = (3, 4, 5, 6, 7, 8)

def learn_md5_deep_5p(valid):
    if not valid: return {}
    cache_key = f"{valid[-1]['phien']}_{len(valid)}_{RESET_ID}"
    now = time.time()
    if (_MD5_DB_CACHE["key"] == cache_key and
        _MD5_DB_CACHE["value"] is not None and
        now - _MD5_DB_CACHE["ts"] < _CACHE_TTL):
        return _MD5_DB_CACHE["value"]

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
    _MD5_DB_CACHE.update({"key": cache_key, "value": dbs, "ts": now})
    return dbs

def lookup_md5_deep_5p(results, dbs):
    if not isinstance(dbs, dict) or not dbs: return (None, 0, None)
    weighted_tai = 0.0; weighted_xiu = 0.0
    active_windows = 0; max_window_hit = 0
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
    if active_windows == 0: return (None, 0, None)
    total_w = weighted_tai + weighted_xiu
    p_tai_agg = weighted_tai / total_w if total_w > 0 else 0.5
    extremity = abs(p_tai_agg - 0.5) * 2
    conf = 55 + extremity * 28 + min(active_windows, 4) * 1.5 + max_window_hit * 0.5
    if p_tai_agg >= 0.62: return ("Tài", int(min(MAX_CONFIDENCE, conf)), p_tai_agg)
    if p_tai_agg <= 0.38: return ("Xỉu", int(min(MAX_CONFIDENCE, conf)), p_tai_agg)
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
    b = [_b(r) for r in results[:8]]
    weights = [1.5, 1.3, 1.1, 0.9, 0.7, 0.5, 0.4, 0.3]
    momentum = sum(b[i] * weights[i] for i in range(8)) / sum(weights)
    last_2 = b[:2]; last_3 = b[:3]
    if all(x == 1 for x in last_3) and momentum < 0.7: return ("Xỉu", 70, "momentum_reversal_down")
    if all(x == 0 for x in last_3) and momentum > 0.3: return ("Tài", 70, "momentum_reversal_up")
    if momentum >= 0.75 and sum(last_2) == 2: return ("Tài", 66, "momentum_strong_up")
    if momentum <= 0.25 and sum(last_2) == 0: return ("Xỉu", 66, "momentum_strong_down")
    return None

# =====================================================================
# THUẬT TOÁN NÂNG CAO v3
# =====================================================================
def algo_sequence_match(results, min_len=4, max_len=10):
    n = len(results)
    if n < min_len + 3: return None
    best_len = 0; tally = {"Tài": 0, "Xỉu": 0}
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
    if p_tai == 0 or p_xiu == 0: entropy = 0.0
    else: entropy = -(p_tai * math.log2(p_tai) + p_xiu * math.log2(p_xiu))
    return {"entropy": round(entropy, 3), "p_tai": round(p_tai, 3)}

# =====================================================================
# v4 ALGOS
# =====================================================================
def algo_fourier_periodicity(results, max_period=12):
    n = len(results)
    if n < 20: return None
    b = [_b(r) for r in results[:min(n, 64)]][::-1]
    N = len(b)
    mean = sum(b) / N
    centered = [x - mean for x in b]
    best_period = 0; best_power = 0
    for p in range(2, min(max_period, N // 2) + 1):
        re = sum(centered[t] * math.cos(2 * math.pi * t / p) for t in range(N))
        im = sum(centered[t] * math.sin(2 * math.pi * t / p) for t in range(N))
        power = (re * re + im * im) / N
        if power > best_power:
            best_power = power; best_period = p
    if best_period == 0 or best_power < 0.5: return None
    pred_idx = N - best_period
    if pred_idx < 0 or pred_idx >= N: return None
    pred = "Tài" if b[pred_idx] == 1 else "Xỉu"
    conf = int(min(82, 58 + best_power * 8))
    return (pred, conf, f"fourier_p{best_period}")

def algo_ngram_ensemble(results, max_n=6):
    n = len(results)
    if n < 25: return None
    total_tai = 0.0; total_w = 0.0
    for L in (4, 5, 6):
        if n < L + 3: continue
        suffix = tuple(results[:L])
        counts = {"Tài": 0, "Xỉu": 0}
        for i in range(L, min(n, 150)):
            if tuple(results[i:i+L]) == suffix:
                counts[results[i-L]] += 1
        total = counts["Tài"] + counts["Xỉu"]
        if total < 2: continue
        p_tai = (counts["Tài"] + 1) / (total + 2)
        w = L * math.log(total + 1)
        total_tai += p_tai * w
        total_w += w
    if total_w == 0: return None
    p_tai = total_tai / total_w
    if p_tai >= 0.65: return ("Tài", int(60 + (p_tai - 0.65) * 100), "ngram_ens_tai")
    if p_tai <= 0.35: return ("Xỉu", int(60 + (0.35 - p_tai) * 100), "ngram_ens_xiu")
    return None

def algo_runs_test(results, window=40):
    n = min(len(results), window)
    if n < 20: return None
    sub = results[:n]
    n1 = sum(1 for r in sub if r == "Tài")
    n2 = n - n1
    if n1 < 4 or n2 < 4: return None
    runs = 1
    for i in range(1, n):
        if sub[i] != sub[i-1]: runs += 1
    expected = 1 + (2 * n1 * n2) / n
    var = (2 * n1 * n2 * (2 * n1 * n2 - n)) / (n * n * (n - 1) + 1e-9)
    if var <= 0: return None
    z = (runs - expected) / math.sqrt(var)
    last = sub[0]
    if z < -1.5:
        conf = int(min(78, 62 + abs(z) * 5))
        return (last, conf, f"runs_cluster_z{z:.1f}")
    if z > 1.5:
        conf = int(min(78, 62 + z * 5))
        return (_opp(last), conf, f"runs_alt_z{z:.1f}")
    return None

def algo_bayesian_smoothing(results, alpha=1.0, beta=1.0):
    n = len(results)
    if n < 15: return None
    recent = results[:15]
    t = sum(1 for r in recent if r == "Tài")
    post_tai = (t + alpha) / (15 + alpha + beta)
    last3 = results[:3]
    t3 = sum(1 for r in last3 if r == "Tài")
    if t3 == 3 and post_tai < 0.45:
        return ("Xỉu", 68, "bayes_reversal_down")
    if t3 == 0 and post_tai > 0.55:
        return ("Tài", 68, "bayes_reversal_up")
    if post_tai >= 0.65: return ("Tài", int(58 + (post_tai - 0.5) * 60), "bayes_tai")
    if post_tai <= 0.35: return ("Xỉu", int(58 + (0.5 - post_tai) * 60), "bayes_xiu")
    return None

def algo_conditional_entropy(results, cond_len=3):
    n = len(results)
    if n < 30: return None
    cond = tuple(results[:cond_len])
    counts = {"Tài": 0, "Xỉu": 0}
    for i in range(cond_len, min(n, 120)):
        if tuple(results[i:i+cond_len]) == cond:
            counts[results[i-cond_len]] += 1
    total = counts["Tài"] + counts["Xỉu"]
    if total < 4: return None
    p_tai = counts["Tài"] / total
    if p_tai in (0, 1): H = 0
    else: H = -(p_tai * math.log2(p_tai) + (1-p_tai) * math.log2(1-p_tai))
    if H > 0.9: return None
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    conf = int(min(80, 60 + (1 - H) * 20))
    return (pred, conf, f"cond_H{H:.2f}")

def algo_gradient_boost_simple(results, window=10):
    n = len(results)
    if n < window + 5: return None
    b = [_b(r) for r in results[:window]]
    features = []
    features.append(("last", b[0]))
    s3 = sum(b[:3])
    features.append(("sum3_high", 1 if s3 >= 2 else 0))
    alt = sum(1 for i in range(4) if b[i] != b[i+1])
    features.append(("alt", 1 if alt >= 3 else 0))
    majority = 1 if sum(b[:5]) >= 3 else 0
    weights = {"last": 0.3, "sum3_high": 0.25, "alt": 0.2, "majority": 0.25}
    score_tai = 0.0
    for name, val in features:
        score_tai += weights[name] * (val if name != "alt" else (1 - val))
    score_tai += weights["majority"] * majority
    p_tai = score_tai
    if p_tai >= 0.68: return ("Tài", int(60 + (p_tai - 0.5) * 50), "gb_tai")
    if p_tai <= 0.32: return ("Xỉu", int(60 + (0.5 - p_tai) * 50), "gb_xiu")
    return None

def algo_pattern_periodicity(results):
    n = len(results)
    if n < 25: return None
    best_score = 0; best_p = 0
    for p in range(2, 9):
        match = 0; total = 0
        for i in range(p, min(n, 60)):
            total += 1
            if results[i] == results[i-p]: match += 1
        if total < 10: continue
        score = match / total
        if score > best_score: best_score = score; best_p = p
    if best_score >= 0.72 and best_p > 0:
        pred = results[best_p - 1] if best_p - 1 < len(results) else None
        if pred:
            conf = int(min(80, 58 + (best_score - 0.5) * 60))
            return (pred, conf, f"periodic_p{best_p}")
    return None

def algo_knn_sequence(results, k=5):
    n = len(results)
    L = 4
    if n < L + 8: return None
    suffix = results[:L]
    candidates = []
    for i in range(L, min(n, 150)):
        window = results[i-L:i]
        dist = sum(1 for a, b in zip(suffix, window) if a != b)
        candidates.append((dist, results[i-L]))
    if len(candidates) < k: return None
    candidates.sort(key=lambda x: x[0])
    top_k = candidates[:k]
    tally = {"Tài": 0.0, "Xỉu": 0.0}
    for dist, r in top_k:
        w = 1.0 / (dist + 1)
        tally[r] += w
    total = tally["Tài"] + tally["Xỉu"]
    if total == 0: return None
    p_tai = tally["Tài"] / total
    if p_tai >= 0.7: return ("Tài", int(60 + (p_tai - 0.5) * 40), "knn_tai")
    if p_tai <= 0.3: return ("Xỉu", int(60 + (0.5 - p_tai) * 40), "knn_xiu")
    return None

# =====================================================================
# ⭐ 3 THUẬT TOÁN MỚI v5
# =====================================================================
def algo_hurst_exponent(results, window=50):
    """Hurst exponent: H > 0.5 → trending, H < 0.5 → mean-reverting."""
    n = min(len(results), window)
    if n < 24: return None
    b = [_b(r) for r in results[:n]][::-1]
    rs_values = []
    for size in (8, 12, 16, 24):
        if n < size * 2: continue
        chunks = n // size
        rs_chunk = []
        for c in range(chunks):
            seg = b[c*size:(c+1)*size]
            m = sum(seg) / size
            dev = [x - m for x in seg]
            cum = []
            s = 0
            for d in dev:
                s += d
                cum.append(s)
            R = max(cum) - min(cum)
            S = math.sqrt(sum((x - m) ** 2 for x in seg) / size) + 1e-9
            rs_chunk.append(R / S)
        if rs_chunk:
            rs_values.append((math.log(size), math.log(sum(rs_chunk) / len(rs_chunk) + 1e-9)))
    if len(rs_values) < 2: return None
    xs = [v[0] for v in rs_values]; ys = [v[1] for v in rs_values]
    xm = sum(xs) / len(xs); ym = sum(ys) / len(ys)
    num = sum((xs[i] - xm) * (ys[i] - ym) for i in range(len(xs)))
    den = sum((xs[i] - xm) ** 2 for i in range(len(xs)))
    if den == 0: return None
    H = num / den
    last = results[0]
    if H > 0.62:
        return (last, int(min(78, 60 + (H - 0.5) * 40)), f"hurst_trend_H{H:.2f}")
    if H < 0.38:
        return (_opp(last), int(min(78, 60 + (0.5 - H) * 40)), f"hurst_revert_H{H:.2f}")
    return None

def algo_markov_high_order(results, max_order=8, min_samples=3):
    """Markov bậc cao (4..8) — chọn bậc cao nhất có đủ mẫu."""
    n = len(results)
    if n < 30: return None
    best = None
    for order in range(4, max_order + 1):
        if n < order + min_samples: continue
        suffix = tuple(results[:order])
        counts = {"Tài": 0, "Xỉu": 0}
        for i in range(order, n):
            if tuple(results[i:i+order]) == suffix:
                counts[results[i-order]] += 1
        total = counts["Tài"] + counts["Xỉu"]
        if total < min_samples: continue
        p_tai = (counts["Tài"] + 1) / (total + 2)
        extremity = abs(p_tai - 0.5) * 2
        if extremity < 0.3: continue
        pred = "Tài" if p_tai > 0.5 else "Xỉu"
        conf = int(min(82, 58 + extremity * 30 + order * 1.5))
        score = extremity * math.log(total + 1)
        if best is None or score > best[0]:
            best = (score, pred, conf, f"mkov{order}_n{total}")
    if best: return (best[1], best[2], best[3])
    return None

def algo_volatility_regime(results, window=20):
    """Volatility cao đột biến → sắp đảo; thấp đột biến → sắp breakout."""
    n = len(results)
    if n < window + 10: return None
    def _changes(sub):
        return sum(1 for i in range(1, len(sub)) if sub[i] != sub[i-1]) / max(1, len(sub) - 1)
    recent = _changes(results[:window])
    long_term = _changes(results[:min(n, 80)])
    if long_term == 0: return None
    ratio = recent / long_term
    last = results[0]
    if ratio >= 1.4:
        return (_opp(last), int(min(74, 60 + (ratio - 1) * 25)), f"vol_high_{ratio:.2f}")
    if ratio <= 0.6:
        return (last, int(min(74, 60 + (1 - ratio) * 25)), f"vol_low_{ratio:.2f}")
    return None

# =====================================================================
# ADAPTIVE WEIGHT + CALIBRATION
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
    if not results: return
    fp = (tuple(results[:10]), len(results))
    if _update_recent_stats.__dict__.get("_fp") == fp:
        return
    _update_recent_stats.__dict__["_fp"] = fp

    ALGO_RECENT_STATS.clear()
    if len(results) < 20: return
    limit = min(ADAPTIVE_WINDOW, len(results) - 6)
    algo_fns = [
        ("streak", algo_streak_break),
        ("bigram", algo_bigram_markov),
        ("momentum", algo_momentum_reversal),
        ("trigram", algo_trigram_markov),
        ("sequence", algo_sequence_match),
        ("fourier", algo_fourier_periodicity),
        ("ngram_ens", algo_ngram_ensemble),
        ("runs", algo_runs_test),
        ("bayes", algo_bayesian_smoothing),
        ("cond", algo_conditional_entropy),
        ("gb", algo_gradient_boost_simple),
        ("periodic", algo_pattern_periodicity),
        ("knn", algo_knn_sequence),
        ("hurst", algo_hurst_exponent),
        ("markov_ho", algo_markov_high_order),
        ("volatility", algo_volatility_regime),
    ]
    for i in range(1, limit):
        hist = results[i:]
        actual = results[i - 1]
        try:
            label, pred, _ = classify_5p_pattern(hist)
            if pred:
                k = f"pattern:{label}"
                ALGO_RECENT_STATS[k]["win" if pred == actual else "lose"] += 1
        except Exception: pass
        for label_name, fn in algo_fns:
            try:
                s = fn(hist)
                if s:
                    k = f"{label_name}:{s[2]}"
                    ALGO_RECENT_STATS[k]["win" if s[0] == actual else "lose"] += 1
            except Exception: pass

def _update_calibration(valid, md5_dbs):
    global CALIBRATION_BUCKETS, CALIBRATION_READY
    if not valid: return
    cache_key = f"{len(valid)}_{valid[-1]['phien']}_{RESET_ID}"
    now = time.time()
    if (_CALIB_CACHE["key"] == cache_key and
        _CALIB_CACHE["value"] is not None and
        now - _CALIB_CACHE["ts"] < _CACHE_TTL):
        CALIBRATION_BUCKETS.clear()
        CALIBRATION_BUCKETS.update(_CALIB_CACHE["value"]["buckets"])
        CALIBRATION_READY = _CALIB_CACHE["value"]["ready"]
        return

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
    _CALIB_CACHE.update({
        "key": cache_key,
        "value": {"buckets": dict(CALIBRATION_BUCKETS), "ready": True},
        "ts": now
    })

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
# DỰ ĐOÁN CHÍNH v5
# =====================================================================
ALGO_REGISTRY = [
    ("streak", algo_streak_break, 1.5),
    ("bigram", algo_bigram_markov, 1.8),
    ("momentum", algo_momentum_reversal, 1.6),
    ("trigram", algo_trigram_markov, 1.7),
    ("sequence", algo_sequence_match, 1.9),
    ("fourier", algo_fourier_periodicity, 1.4),
    ("ngram_ens", algo_ngram_ensemble, 1.8),
    ("runs", algo_runs_test, 1.5),
    ("bayes", algo_bayesian_smoothing, 1.3),
    ("cond", algo_conditional_entropy, 1.5),
    ("gb", algo_gradient_boost_simple, 1.2),
    ("periodic", algo_pattern_periodicity, 1.4),
    ("knn", algo_knn_sequence, 1.6),
    ("hurst", algo_hurst_exponent, 1.7),
    ("markov_ho", algo_markov_high_order, 1.9),
    ("volatility", algo_volatility_regime, 1.4),
]

def compute_prediction(results, md5_dbs, _skip_calibration=False):
    if not results: return ("Tài", 52)
    if len(results) < 5: return (_opp(results[0]), 55)

    _update_recent_stats(results, md5_dbs)
    overfit = _detect_overfit_guard(results)
    ent_info = algo_entropy_regime(results, 12)
    high_entropy = ent_info is not None and ent_info["entropy"] > 0.92

    pattern_label, pattern_pred, pattern_conf = classify_5p_pattern(results)
    md5_pred, md5_conf, md5_p_tai = lookup_md5_deep_5p(results, md5_dbs)

    signals = {}
    for name, fn, _ in ALGO_REGISTRY:
        try: signals[name] = fn(results)
        except Exception: signals[name] = None

    # TẦNG 1: Siêu tín hiệu MD5
    if md5_pred and md5_conf >= 80:
        if pattern_pred == md5_pred:
            return (md5_pred, min(MAX_CONFIDENCE, md5_conf + 4))
        trig = signals.get("trigram")
        if trig and trig[0] == md5_pred:
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

    for name, fn, base_mult in ALGO_REGISTRY:
        sig = signals.get(name)
        if sig:
            pred, conf, algo_name = sig
            w = _get_adaptive_weight(f"{name}:{algo_name}", conf / 100 * base_mult)
            votes[pred] += w
            active.append((algo_name, pred, w))

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
    if agree >= 8 and disagree == 0:
        conf = min(MAX_CONFIDENCE, conf + 8)
    elif agree >= 6 and disagree <= 1:
        conf = min(MAX_CONFIDENCE, conf + 5)
    elif agree >= 4 and disagree <= 2:
        conf = min(MAX_CONFIDENCE, conf + 2)
    elif disagree >= 4:
        conf = max(55, conf - 12)
    elif disagree >= 2:
        conf = max(55, conf - 5)

    if overfit: conf = max(55, conf - 8)
    if high_entropy: conf = max(55, conf - 6)

    if md5_pred == pred and md5_conf >= 70 and conf < 78:
        conf = min(80, conf + 4)

    if not _skip_calibration:
        conf = _calibrate_confidence(conf)

    return (pred, conf)

# =====================================================================
# RECOVERY v5
# =====================================================================
def apply_recovery(base_pred, conf, loss_streak, results):
    if loss_streak < 2:
        return (base_pred, conf, False)
    if _detect_overfit_guard(results):
        return (base_pred, max(55, conf - 5), False)
    if FLIP_STATS["consecutive_loss"] >= 2:
        return (base_pred, max(55, conf - 3), False)
    ent = algo_entropy_regime(results, 12)
    high_ent = ent is not None and ent["entropy"] > 0.90
    if loss_streak == 2:
        new_conf = max(62, conf - (2 if high_ent else 5))
        return (_opp(base_pred), new_conf, True)
    new_conf = min(MAX_CONFIDENCE, max(conf, 78 if not high_ent else 72))
    return (_opp(base_pred), new_conf, True)

def compute_loss_streak(valid, md5_dbs):
    if len(valid) < 5: return 0
    cache_key = f"{len(valid)}_{valid[-1]['phien']}_{RESET_ID}"
    now = time.time()
    if (_LOSS_STREAK_CACHE["key"] == cache_key and
        now - _LOSS_STREAK_CACHE["ts"] < _CACHE_TTL):
        return _LOSS_STREAK_CACHE["value"]

    streak = 0
    for i in range(len(valid) - 1, max(4, len(valid) - 10), -1):
        hist = [v['result'] for v in valid[:i]][::-1]
        pred, _ = compute_prediction(hist, md5_dbs)
        if pred == valid[i]['result']: break
        streak += 1
    _LOSS_STREAK_CACHE.update({"key": cache_key, "value": streak, "ts": now})
    return streak

# =====================================================================
# FETCH SESSIONS + API
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
        raw_rows, _ = fetch_sessions()
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
            'version': 'v5',
            'calibration': {str(k): v for k, v in CALIBRATION_BUCKETS.items()} if CALIBRATION_READY else {}
        })
    except Exception as e:
        traceback.print_exc()
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
        all_signals = {}
        for name, fn, _ in ALGO_REGISTRY:
            try:
                sig = fn(results)
                all_signals[name] = {
                    'pred': sig[0] if sig else None,
                    'conf': sig[1] if sig else 0,
                    'tag': sig[2] if sig else None,
                }
            except Exception:
                all_signals[name] = {'pred': None, 'conf': 0, 'tag': None}

        ent = algo_entropy_regime(results, 12)

        return jsonify({
            'version': 'v5',
            'last_phien': valid[-1]['phien'],
            'next_phien': valid[-1]['phien'] + 1,
            'prediction': pred, 'confidence': conf, 'recovery_flipped': flipped,
            'loss_streak': loss_streak,
            'overfit_guard': _detect_overfit_guard(results),
            'entropy': ent,
            'ls_5p': format_tx(results, 5),
            'signals': {
                'pattern': {'label': pattern_label, 'pred': pattern_pred, 'conf': pattern_conf},
                'md5': {'pred': md5_pred, 'conf': md5_conf,
                        'p_tai': round(md5_p_tai, 3) if md5_p_tai is not None else None},
                **all_signals,
            },
            'algorithm_count': len(ALGO_REGISTRY) + 2,
            'adaptive_stats': dict(ALGO_RECENT_STATS),
            'calibration': {str(k): v for k, v in CALIBRATION_BUCKETS.items()} if CALIBRATION_READY else {},
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        traceback.print_exc()
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
        pred, conf, _ = apply_recovery(base_pred, base_conf, loss_streak, results)

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
    global RESET_ID, HISTORY_CACHE, ALGO_RECENT_STATS, CALIBRATION_BUCKETS, CALIBRATION_READY, FLIP_STATS, _MD5_DB_CACHE
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
                _MD5_DB_CACHE.update({"key": None, "value": None, "ts": 0})
                _CALIB_CACHE.update({"key": None, "value": None, "ts": 0})
                _PRED_CACHE.update({"key": None, "value": None, "ts": 0})
                _LOSS_STREAK_CACHE.update({"key": None, "value": 0, "ts": 0})
                _update_recent_stats.__dict__.pop("_fp", None)
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/health')
def health():
    return jsonify({
        'status': 'ok', 'version': 'v5',
        'cached_sessions': len(HISTORY_CACHE),
        'reset_id': RESET_ID,
        'algo_count': len(ALGO_REGISTRY) + 2,
        'calibration_ready': CALIBRATION_READY,
        'md5_cache_age': round(time.time() - _MD5_DB_CACHE['ts'], 2),
        'loss_streak_cache_age': round(time.time() - _LOSS_STREAK_CACHE['ts'], 2),
        'timestamp': datetime.now().isoformat()
    })

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

        all_sigs = {}
        for name, fn, _ in ALGO_REGISTRY:
            try:
                sig = fn(results)
                all_sigs[name] = {'pred': sig[0] if sig else None,
                                  'conf': sig[1] if sig else 0,
                                  'tag': sig[2] if sig else None}
            except Exception as e:
                all_sigs[name] = {'error': str(e)}

        return jsonify({
            'version': 'v5',
            'last_5p': format_tx(results, 5),
            'pattern': {'label': pattern_label, 'pred': pattern_pred, 'conf': pattern_conf},
            'md5': {'pred': md5_pred, 'conf': md5_conf,
                    'p_tai': round(md5_p_tai, 3) if md5_p_tai is not None else None},
            'signals': all_sigs,
            'entropy': algo_entropy_regime(results, 12),
            'overfit_guard': _detect_overfit_guard(results),
            'adaptive_stats': dict(ALGO_RECENT_STATS),
            'calibration': {str(k): v for k, v in CALIBRATION_BUCKETS.items()} if CALIBRATION_READY else {},
            'md5_windows': list(MD5_WINDOWS),
            'md5_db_sizes': {w: len(db) for w, db in md5_dbs.items()},
            'algorithm_count': len(ALGO_REGISTRY) + 2
        })
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
