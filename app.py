import os
import math
import hashlib
import traceback
from datetime import datetime
from collections import defaultdict, deque
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
PREDICTION_CACHE = {}
MAX_PREDICTION_CACHE = 2000
RESET_ID = 0
MAX_CONFIDENCE = 90

# =====================================================================
# HASH DEEP MD5 DATABASE — 4 độ sâu
# =====================================================================
HASH_DEEP_DB = {
    13: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    10: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    7:  defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    5:  defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
}

# =====================================================================
# LOSS TRACKER — theo dõi lịch sử thua để fix gãy
# =====================================================================
LOSS_HISTORY = deque(maxlen=20)  # [(phien, pred, actual), ...]


# =====================================================================
# HTML TEMPLATE (GIỮ NGUYÊN 100%)
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 </title>
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
    <div class="header-title">LE MINH <span>MD5 </span></div>
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
            recBadge = `<span class="recovery-badge" title="Auto-flip do thua ${row.loss_streak || 0} lần">⚡ </span>`;
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
# DATA FETCHER
# =====================================================================
def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(API_URL_MD5, timeout=5, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']:
                rows = []
                for item in data['list']:
                    res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
                    total = item.get('point', sum(dices))
                    rows.append({'phien': int(item['id']), 'result': res,
                                 'dice': dice_str, 'total': total})
                return rows, True
    except Exception as e:
        print(f"[API ERROR]: {e}")
    return [], False


# =====================================================================
# UTILS
# =====================================================================
def _opp(v): return "Xỉu" if v == "Tài" else "Tài"


def _count_streak(results):
    if not results: return 0
    r0 = results[0]; c = 1
    for r in results[1:]:
        if r == r0: c += 1
        else: break
    return c


def _count_alternations(results, max_len=15):
    count = 0
    for i in range(min(len(results) - 1, max_len)):
        if results[i] != results[i+1]: count += 1
        else: break
    return count


def get_groups(results):
    if not results: return []
    groups = []
    current_val = results[0]; count = 1
    for r in results[1:]:
        if r == current_val: count += 1
        else:
            groups.append(count); current_val = r; count = 1
    groups.append(count)
    return groups


def _regime(results):
    if len(results) < 5: return "balanced"
    alt = _count_alternations(results, 12)
    streak = _count_streak(results)
    if alt >= 4 and alt > streak: return "alternation"
    if streak >= 3: return "streak"
    return "balanced"


# =====================================================================
# 🧬 HASH DEEP MD5 — 4 TẦNG
# =====================================================================
def encode_tx(results, length):
    if len(results) < length: return None
    return "".join("T" if r == "Tài" else "X" for r in results[:length])


def hash_deep_md5(tx_string, depth_level=2):
    """Băm sâu nhiều tầng MD5."""
    salted = f"leminh_deep_{depth_level}|{tx_string}"
    h = hashlib.md5(salted.encode('utf-8')).hexdigest()
    for _ in range(depth_level - 1):
        h = hashlib.md5(f"{h}|salt_{depth_level}".encode('utf-8')).hexdigest()
    return h


def learn_hash_deep_from_history(valid):
    """Học HASH_DEEP_DB từ lịch sử API ở 4 độ sâu: 5, 7, 10, 13."""
    global HASH_DEEP_DB
    n = len(valid)
    if n < 15: return

    for depth in (5, 7, 10, 13):
        if n <= depth: continue
        db = HASH_DEEP_DB[depth]
        for i in range(depth, n):
            history = [v['result'] for v in valid[i-depth:i]][::-1]
            tx = encode_tx(history, depth)
            if not tx: continue
            h = hash_deep_md5(tx, depth_level=2)
            actual = valid[i]['result']
            db[h][actual] += 1


def algo_hash_deep_lookup(results):
    """Tra cứu 4 độ sâu, ensemble có trọng số."""
    combined_score = {"Tài": 0.0, "Xỉu": 0.0}
    hits = []
    total_samples = 0

    for depth, weight_factor in ((13, 1.0), (10, 0.8), (7, 0.6), (5, 0.4)):
        tx = encode_tx(results, depth)
        if not tx: continue
        h = hash_deep_md5(tx, depth_level=2)
        db = HASH_DEEP_DB[depth]
        if h not in db: continue
        counts = db[h]
        total = counts["Tài"] + counts["Xỉu"]
        if total < 2: continue

        p_tai = (counts["Tài"] + 1) / (total + 2)
        z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))

        pred = "Tài" if p_tai > 0.5 else "Xỉu"
        weight = min(24, 10 + abs(z) * 4) * weight_factor
        combined_score[pred] += weight
        hits.append({'depth': depth, 'pred': pred, 'samples': total,
                     'p_tai': round(p_tai, 3), 'z': round(z, 2)})
        total_samples += total

    if not hits or total_samples < 3:
        return None

    st = combined_score["Tài"]; sx = combined_score["Xỉu"]
    if st == sx: return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    z_total = (ratio - 0.5) * 4

    if abs(z_total) < 1.2: return None

    weight = min(25, 10 + abs(z_total) * 5)
    return (pred, weight, f"hash_deep_multi_{total_samples}")


# =====================================================================
# 🔥 5P ALTERNATION — Đảo thuận nghịch 1-1
# =====================================================================
def algo_5p_alternation(results):
    n = len(results)
    if n < 10: return None

    last5 = results[:5]
    alt_count = sum(1 for i in range(4) if last5[i] != last5[i+1])

    if alt_count == 4:
        tai_next = xiu_next = 0
        key5 = tuple(last5)
        for i in range(min(n - 5, 50)):
            if tuple(results[i:i+5]) == key5:
                if results[i+5] == "Tài": tai_next += 1
                else: xiu_next += 1
        total_seen = tai_next + xiu_next
        if total_seen >= 3:
            p_tai = (tai_next + 1) / (total_seen + 2)
            if p_tai >= 0.62:
                return ("Tài", min(24, 13 + (p_tai - 0.5) * 25), "5p_alt_data_T")
            elif p_tai <= 0.38:
                return ("Xỉu", min(24, 13 + (0.5 - p_tai) * 25), "5p_alt_data_X")
        return (_opp(last5[0]), 18, "5p_alt_continue")

    if alt_count == 3:
        tai_next = xiu_next = 0
        key5 = tuple(last5)
        for i in range(min(n - 5, 50)):
            if tuple(results[i:i+5]) == key5:
                if results[i+5] == "Tài": tai_next += 1
                else: xiu_next += 1
        total_seen = tai_next + xiu_next
        if total_seen >= 3:
            p_tai = (tai_next + 1) / (total_seen + 2)
            if p_tai >= 0.62:
                return ("Tài", min(22, 12 + (p_tai - 0.5) * 22), "5p_alt_reverse_data_T")
            elif p_tai <= 0.38:
                return ("Xỉu", min(22, 12 + (0.5 - p_tai) * 22), "5p_alt_reverse_data_X")
        return (_opp(last5[0]), 15, "5p_alt_reverse")

    return None


# =====================================================================
# 🔥 TREND DETECTOR — BẺ CẦU XU HƯỚNG
# =====================================================================
def algo_trend_break(results):
    """
    Phát hiện xu hướng bằng linear regression trên 20 phiên.
    Nếu slope mạnh + đổi chiều → bẻ cầu.
    """
    n = len(results)
    if n < 20: return None

    # Chuyển T/X → 1/0 (gần nhất = cuối mảng)
    window = list(reversed(results[:20]))  # cũ → mới
    b = [1 if r == "Tài" else 0 for r in window]

    # Linear regression: y = a + b*x
    x_mean = 9.5  # (0+...+19)/20
    y_mean = sum(b) / 20
    num = sum((i - x_mean) * (b[i] - y_mean) for i in range(20))
    den = sum((i - x_mean) ** 2 for i in range(20))
    slope = num / den if den else 0

    # Slope > 0: xu hướng Tài tăng; slope < 0: Xỉu tăng
    # Kiểm tra 3 phiên gần nhất có đi ngược xu hướng không
    last3 = b[-3:]
    if slope > 0.04:
        # Xu hướng Tài tăng → nếu 3 phiên gần nhất đang giảm → bẻ về Tài
        if sum(last3) <= 1:
            return ("Tài", min(20, 12 + abs(slope) * 30), "trend_bounce_T")
    elif slope < -0.04:
        if sum(last3) >= 2:
            return ("Xỉu", min(20, 12 + abs(slope) * 30), "trend_bounce_X")

    # Slope cực mạnh + 3 phiên cuối cùng hướng → tiếp tục
    if abs(slope) > 0.08:
        last_dir = "Tài" if sum(last3) >= 2 else "Xỉu"
        if (slope > 0 and last_dir == "Tài") or (slope < 0 and last_dir == "Xỉu"):
            return (last_dir, min(18, 12 + abs(slope) * 25), f"trend_continue_{last_dir[0]}")

    return None


# =====================================================================
# 🔥 GÃY NHỊP 5P — PHÁT HIỆN VÀ BẺ
# =====================================================================
def algo_break_rhythm(results):
    """
    Phát hiện gãy nhịp trong 8 phiên gần nhất.
    - Gãy nhịp: pattern có 1-2 chỗ đột ngột không theo quy luật
    - Bẻ: dự đoán theo nhịp chính (bỏ qua ngoại lệ)
    """
    n = len(results)
    if n < 12: return None

    last8 = results[:8]
    alt_count = sum(1 for i in range(7) if last8[i] != last8[i+1])

    # Gãy nhịp rõ: 5-6 lần đảo trong 7 phiên (nhịp chính là đảo)
    if 5 <= alt_count <= 6:
        # Tìm vị trí gãy nhịp
        for i in range(7):
            if last8[i] == last8[i+1]:
                # Gãy tại vị trí i → phiên i+1 là ngoại lệ
                # Nhịp chính là đảo → phiên tiếp theo phải đảo từ last8[0]
                return (_opp(last8[0]), 16, "break_rhythm_alt")

    # Gãy nhịp bệt: 1-2 lần đảo trong 7 (nhịp chính là bệt)
    if alt_count <= 2:
        # Đang bệt → tiếp tục bệt
        return (last8[0], 14, "break_rhythm_streak")

    return None


# =====================================================================
# DATA-DRIVEN ALGORITHMS
# =====================================================================
def data_markov2(results):
    n = len(results)
    if n < 20: return None
    key = (results[1], results[0])
    counts = {"Tài": 1, "Xỉu": 1}
    for i in range(min(n - 2, 60)):
        if (results[i+2], results[i+1]) == key:
            counts[results[i]] += 1
    total = counts["Tài"] + counts["Xỉu"]
    if total < 6: return None
    p_tai = counts["Tài"] / total
    z = (p_tai - 0.5) / math.sqrt(0.25 / total)
    if abs(z) < 1.2: return None
    weight = min(20, 9 + abs(z) * 3)
    return ("Tài" if p_tai > 0.5 else "Xỉu", weight, "markov2_data")


def data_pattern3(results):
    n = len(results)
    if n < 25: return None
    key = tuple(results[:3])
    tai_next = xiu_next = 0
    for i in range(min(n - 3, 60)):
        if tuple(results[i:i+3]) == key:
            if results[i+3] == "Tài": tai_next += 1
            else: xiu_next += 1
    tot = tai_next + xiu_next
    if tot < 4: return None
    p = (tai_next + 1) / (tot + 2)
    if p >= 0.68: return ("Tài", min(18, 10 + (p - 0.5) * 20), "pattern3_data")
    if p <= 0.32: return ("Xỉu", min(18, 10 + (0.5 - p) * 20), "pattern3_data")
    return None


def data_alternation(results):
    n = len(results)
    if n < 4: return None
    alt = _count_alternations(results)
    if alt >= 8: return (_opp(results[0]), 28, "alt_8plus")
    if alt >= 6: return (_opp(results[0]), 24, "alt_6_7")
    if alt >= 4: return (_opp(results[0]), 17, "alt_4_5")
    if alt >= 3: return (_opp(results[0]), 11, "alt_3")
    return None


def data_streak_break(results):
    n = len(results)
    if n < 25: return None
    streak = _count_streak(results)
    if streak < 3: return None
    current = results[0]
    breaks = totals = 0
    i = 0
    while i < n - 1:
        j = i; cnt = 1
        while j + 1 < n and results[j] == results[j+1]:
            cnt += 1; j += 1
        if cnt >= streak and results[i] == current:
            totals += 1
            if j + 1 < n and results[j+1] != current:
                breaks += 1
        i = j + 1
    if totals < 4: return None
    p_break = (breaks + 1) / (totals + 2)
    if p_break >= 0.65:
        return (_opp(current), min(18, 10 + (p_break - 0.5) * 20), "streak_break_data")
    if p_break <= 0.35:
        return (current, min(15, 10 + (0.5 - p_break) * 15), "streak_continue_data")
    return None


def data_bayes_ratio(results):
    n = len(results)
    if n < 15: return None
    window = results[:min(30, n)]
    tai = window.count("Tài")
    xiu = len(window) - tai
    alpha = 10 + tai; beta = 10 + xiu
    p_tai = alpha / (alpha + beta)
    var = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
    std = math.sqrt(var) if var > 0 else 0
    z = abs((p_tai - 0.5) / std) if std else 0
    if z < 1.5: return None
    weight = min(16, 9 + z * 2)
    return ("Tài" if p_tai > 0.5 else "Xỉu", weight, "bayes_data")


def data_tilt(results):
    n = len(results)
    if n < 12: return None
    for w, hi, lo, wgt in ((8, 7, 1, 15), (12, 10, 2, 13)):
        if n < w: continue
        tc = results[:w].count("Tài")
        if tc >= hi: return ("Xỉu", wgt, f"tilt_tai_{w}")
        if tc <= lo: return ("Tài", wgt, f"tilt_xiu_{w}")
    return None


# =====================================================================
# MASTER ANALYZER
# =====================================================================
def analyze_full_bridge(results):
    if len(results) < 3: return []
    signals = []
    for fn in (
        algo_hash_deep_lookup,
        algo_5p_alternation,
        algo_trend_break,       # 🔥 MỚI: bẻ cầu xu hướng
        algo_break_rhythm,      # 🔥 MỚI: gãy nhịp 5P
        data_markov2,
        data_pattern3,
        data_alternation,
        data_streak_break,
        data_bayes_ratio,
        data_tilt,
    ):
        try:
            s = fn(results)
            if s: signals.append(s)
        except Exception:
            pass
    return signals


# =====================================================================
# PREDICTOR
# =====================================================================
def full_bridge_predict_adaptive(results, replay_n=80):
    n = len(results)
    if n == 0: return "Tài", 50, []
    if n == 1: return _opp(results[0]), 52, []
    if n == 2:
        if results[0] == results[1]: return _opp(results[0]), 55, []
        return results[1], 52, []

    signal_stats = defaultdict(lambda: {'wins': 0.0, 'total': 0.0})
    replay_count = min(replay_n, n - 3)
    for j in range(replay_count):
        history = results[j + 1:]; actual = results[j]
        decay = math.exp(-j / max(replay_count / 2.0, 1.0))
        for pred_sig, weight, name in analyze_full_bridge(history):
            signal_stats[name]['total'] += decay
            if pred_sig == actual:
                signal_stats[name]['wins'] += decay

    signals = analyze_full_bridge(results)
    if not signals: return results[0], 52, []

    regime = _regime(results)
    st = sx = 0.0; detail = []
    for pred_sig, weight, name in signals:
        s = signal_stats[name]
        if s['total'] >= 3:
            acc = (s['wins'] + 1.0) / (s['total'] + 2.0)
        else:
            acc = 0.5
        accuracy_mult = 0.4 + max(0.0, min(1.9, (acc - 0.3) * 3.0))
        if regime == "streak" and "break" in name:
            accuracy_mult *= 1.10
        elif regime == "alternation" and ("alt" in name or "5p" in name):
            accuracy_mult *= 1.15
        # 🔥 Boost trend/rhythm khi có
        if "trend_" in name or "rhythm_" in name:
            accuracy_mult *= 1.12
        adjusted = weight * accuracy_mult
        if pred_sig == "Tài": st += adjusted
        else: sx += adjusted
        detail.append({'name': name, 'pred': pred_sig, 'base_weight': weight,
                       'accuracy': round(acc, 3), 'adjusted_weight': round(adjusted, 2)})

    total = st + sx
    if total == 0: return results[0], 50, detail
    if st > sx: pred, ratio = "Tài", st / total
    elif sx > st: pred, ratio = "Xỉu", sx / total
    else: return _opp(results[0]), 50, detail

    conf = 50 + (ratio - 0.5) * 100
    conf = conf * min(1.0, total / 50.0) + 50 * (1 - min(1.0, total / 50.0))
    if ratio >= 0.72: conf += 5
    if len(signals) < 3: conf -= 5
    conf = int(max(50, min(MAX_CONFIDENCE, conf)))
    return pred, conf, detail


# =====================================================================
# PREDICTION CACHE
# =====================================================================
def get_prediction_for(valid, i):
    key = valid[i]['phien']
    if key in PREDICTION_CACHE: return PREDICTION_CACHE[key]
    hist = [v['result'] for v in valid[:i]][::-1]
    if len(hist) < 3:
        result = ("-", 50, None)
    else:
        pred, conf, _ = full_bridge_predict_adaptive(hist)
        is_correct = (pred == valid[i]['result'])
        result = (pred, conf, is_correct)
    if len(PREDICTION_CACHE) > MAX_PREDICTION_CACHE: PREDICTION_CACHE.clear()
    PREDICTION_CACHE[key] = result
    return result


def compute_loss_streak(valid, max_scan=10):
    if len(valid) < 5: return 0
    streak = 0
    end = len(valid) - 1
    start = max(0, end - max_scan)
    for i in range(end, start - 1, -1):
        pred, conf, is_correct = get_prediction_for(valid, i)
        if is_correct is None: break
        if is_correct: break
        streak += 1
    return streak


# =====================================================================
# 🔥 AUTO-FIX GÃY 2-3 TAY + BẺ CẦU XU HƯỚNG
# =====================================================================
def apply_recovery(base_pred, conf, loss_streak, results=None):
    """
    Auto-fix thông minh:
    - Thua 1: fix mềm, giảm conf
    - Thua 2: BẺ CẦU có điều kiện — kiểm tra xu hướng
    - Thua 3: BẺ MẠNH + boost conf + bẻ theo xu hướng
    - Thua ≥4: đảo khẩn
    """
    if loss_streak < 1:
        return base_pred, conf, False, None

    regime = _regime(results) if results else "balanced"

    # === THUA 1 TAY — Fix mềm ===
    if loss_streak == 1:
        if regime == "alternation":
            return base_pred, max(50, conf - 3), False, "hold_alt"
        return base_pred, max(50, conf - 5), False, "soft_hold"

    # === THUA 2 TAY — BẺ CẦU có điều kiện ===
    if loss_streak == 2:
        # Kiểm tra xu hướng để bẻ đúng hướng
        trend_signal = algo_trend_break(results) if results else None
        rhythm_signal = algo_break_rhythm(results) if results else None

        if regime == "alternation":
            # Đang đảo → không bẻ, giữ nguyên
            return base_pred, max(55, conf - 3), False, "hold_alt_2"

        if regime == "streak":
            # Đang bệt → bẻ mạnh (đảo hướng)
            return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 75)), True, "flip_streak_2"

        # Balanced → kiểm tra trend/rhythm
        if trend_signal and trend_signal[0] == _opp(base_pred):
            return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 74)), True, "flip_trend_2"
        if rhythm_signal and rhythm_signal[0] == _opp(base_pred):
            return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 73)), True, "flip_rhythm_2"

        # Mặc định: đảo
        return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 72)), True, "flip_2"

    # === THUA 3 TAY — BẺ MẠNH ===
    if loss_streak == 3:
        if regime == "alternation":
            # Đang đảo mà thua 3 → đổi chiến thuật: follow xu hướng
            if results and len(results) >= 3:
                return results[0], min(MAX_CONFIDENCE, max(conf, 72)), False, "follow_3"
            return base_pred, max(55, conf - 5), False, "hold_alt_3"

        # Đảo + boost mạnh
        return _opp(base_pred), min(MAX_CONFIDENCE, conf + 12), True, "flip_3_strong"

    # === THUA ≥4 — ĐẢO KHẨN ===
    if loss_streak >= 5:
        return _opp(base_pred), min(MAX_CONFIDENCE, conf + 15), True, "flip_5plus"
    if loss_streak == 4:
        return _opp(base_pred), min(MAX_CONFIDENCE, conf + 13), True, "flip_4"

    return base_pred, conf, False, None


# =====================================================================
# ROUTES
# =====================================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if not success and not HISTORY_CACHE:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        for row in raw_rows: HISTORY_CACHE[row['phien']] = row
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]
        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0}})

        learn_hash_deep_from_history(valid)

        loss_streak = compute_loss_streak(valid)
        out = []; correct_count = 0; total_past = 0
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]

        base_pred, base_conf, _ = full_bridge_predict_adaptive(history_for_next)
        next_pred, next_conf, flipped, reason = apply_recovery(
            base_pred, base_conf, loss_streak, results=history_for_next
        )

        out.append({
            'phien': next_phien, 'is_next': True,
            'prediction': next_pred, 'result': 'Chờ...',
            'dice': "? + ? + ?", 'is_correct': None,
            'conf': next_conf, 'recovery_flipped': flipped,
            'recovery_reason': reason, 'loss_streak': loss_streak,
            'base_prediction': base_pred if flipped else None,
        })

        scan_limit = min(len(valid), 200)
        for i in range(len(valid) - 1, len(valid) - scan_limit - 1, -1):
            if i < 0: break
            current_session = valid[i]
            pred, conf, is_correct = get_prediction_for(valid, i)
            if is_correct is not None: total_past += 1
            if is_correct: correct_count += 1
            out.append({'phien': current_session['phien'], 'is_next': False,
                        'prediction': pred, 'result': current_session['result'],
                        'dice': current_session['dice'], 'is_correct': is_correct,
                        'conf': conf, 'recovery_flipped': False})

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count},
            'loss_streak': loss_streak, 'recovery_active': flipped,
            'recovery_reason': reason, 'base_prediction': base_pred,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if not success and not HISTORY_CACHE:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        for row in raw_rows: HISTORY_CACHE[row['phien']] = row
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]
        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid: return jsonify({'error': 'Chưa có dữ liệu'}), 400

        learn_hash_deep_from_history(valid)
        results = [v['result'] for v in valid][::-1]

        loss_streak = compute_loss_streak(valid)
        base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason = apply_recovery(
            base_pred, base_conf, loss_streak, results=results
        )

        p5_signal = algo_5p_alternation(results)
        hash_signal = algo_hash_deep_lookup(results)
        trend_signal = algo_trend_break(results)
        rhythm_signal = algo_break_rhythm(results)
        last5_tx = encode_tx(results, 5)
        last13_tx = encode_tx(results, 13)
        last13_hash = hash_deep_md5(last13_tx, depth_level=2) if last13_tx else None

        return jsonify({
            'last_phien': valid[-1]['phien'], 'next_phien': valid[-1]['phien'] + 1,
            'last_result': valid[-1]['result'], 'last_dice': valid[-1]['dice'],
            'prediction': pred, 'confidence': conf,
            'base_prediction': base_pred, 'base_confidence': base_conf,
            'recovery_flipped': flipped, 'recovery_reason': reason,
            'loss_streak': loss_streak, 'total_sessions': len(valid),
            'last5_pattern': last5_tx,
            'last13_hash': last13_hash,
            'pattern_5p': {'pred': p5_signal[0], 'name': p5_signal[2]} if p5_signal else None,
            'hash_deep': {'pred': hash_signal[0], 'name': hash_signal[2]} if hash_signal else None,
            'trend': {'pred': trend_signal[0], 'name': trend_signal[2]} if trend_signal else None,
            'rhythm': {'pred': rhythm_signal[0], 'name': rhythm_signal[2]} if rhythm_signal else None,
            'signals': detail,
            'tai_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài'), 2),
            'xiu_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu'), 2),
            'signal_count': len(detail),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lc79')
def lc79():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if not success and not HISTORY_CACHE:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        for row in raw_rows: HISTORY_CACHE[row['phien']] = row
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]
        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid: return jsonify({'error': 'Chưa có dữ liệu'}), 400

        learn_hash_deep_from_history(valid)
        results = [v['result'] for v in valid][::-1]

        loss_streak = compute_loss_streak(valid)
        base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason = apply_recovery(
            base_pred, base_conf, loss_streak, results=results
        )

        tai_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài')
        xiu_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu')
        total_sig = tai_score + xiu_score
        if total_sig > 0:
            ratio = max(tai_score, xiu_score) / total_sig
            base_conf_f = 50 + (ratio - 0.5) * 100
            evidence = min(1.0, total_sig / 50.0)
            conf_float = max(50.0, min(float(MAX_CONFIDENCE), 50 + (base_conf_f - 50) * evidence))
        else:
            conf_float = 50.0
        conf_str = f"{conf_float:.1f}".replace(".", ",") + "%"
        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])
        last = valid[-1]; next_phien = last['phien'] + 1

        return jsonify({
            'Id': 'le minh hashdeep v2', 'Phien': str(next_phien),
            'Ket_qua': last['result'].lower(), 'Lich_su': lich_su,
            'Du_doan': pred, 'Do_tin_cay': conf_str,
            'Base_du_doan': base_pred if flipped else None,
            'Auto_flip': flipped, 'Chuoi_thua': loss_streak,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lc79md5')
def lc79md5():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if not success and not HISTORY_CACHE:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        for row in raw_rows: HISTORY_CACHE[row['phien']] = row
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]
        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid: return jsonify({'error': 'Chưa có dữ liệu'}), 400

        learn_hash_deep_from_history(valid)
        results = [v['result'] for v in valid][::-1]
        loss_streak = compute_loss_streak(valid)
        base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason = apply_recovery(
            base_pred, base_conf, loss_streak, results=results
        )

        tai_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài')
        xiu_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu')
        total_sig = tai_score + xiu_score
        if total_sig > 0:
            ratio = max(tai_score, xiu_score) / total_sig
            base_conf_f = 50 + (ratio - 0.5) * 100
            evidence = min(1.0, total_sig / 50.0)
            conf_float = max(50.0, min(float(MAX_CONFIDENCE), 50 + (base_conf_f - 50) * evidence))
        else:
            conf_float = 50.0
        conf_str = f"{conf_float:.1f}".replace(".", ",") + "%"

        last = valid[-1]
        dice_parts = last['dice'].split(" + ")
        dice_short = "-".join(dice_parts) if len(dice_parts) == 3 else last['dice']
        ket_qua_str = f"{last['result'].lower()} {dice_short}"
        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])
        next_phien = last['phien'] + 1

        return jsonify({
            'id': '@cskhleminh', 'phien': str(next_phien),
            'ket_qua': ket_qua_str, 'du_doan': pred,
            'do_tin_cay': conf_str, 'lich_su': lich_su,
            'base_du_doan': base_pred if flipped else None,
            'auto_flip': flipped, 'chuoi_thua': loss_streak,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE, PREDICTION_CACHE, HASH_DEEP_DB, LOSS_HISTORY
    try:
        raw_rows, success = fetch_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                PREDICTION_CACHE = {}
                HASH_DEEP_DB = {
                    13: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
                    10: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
                    7:  defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
                    5:  defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
                }
                LOSS_HISTORY.clear()
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng, không thể xác nhận mốc Reset'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
