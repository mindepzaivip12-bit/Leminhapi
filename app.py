import os
import time
import traceback
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

from thuat_toan import (
    learn_hash_deep_from_history,
    full_bridge_predict_adaptive,
    apply_recovery,
    reset_all_databases,
    get_groups,
    encode_tx,
    hash_deep_md5,
    MAX_CONFIDENCE,
)

app = Flask(__name__)
CORS(app)

# =====================================================================
# API CONFIG — ổn định với retry + timeout
# =====================================================================
API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

API_TIMEOUT = 8           # Timeout mỗi request
API_MAX_RETRY = 3         # Số lần retry tối đa
API_BACKOFF = 0.5         # Backoff factor
CACHE_TTL = 4             # Cache API 4 giây (tránh gọi liên tục)
LAST_API_CALL = {"ts": 0, "data": None, "ok": False}

# Session với retry tự động
session = requests.Session()
retry_strategy = Retry(
    total=API_MAX_RETRY,
    backoff_factor=API_BACKOFF,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
    'Referer': 'https://tele68.com/',
    'Origin': 'https://tele68.com',
})

# =====================================================================
# STATE
# =====================================================================
HISTORY_CACHE = {}
PREDICTION_CACHE = {}
MAX_PREDICTION_CACHE = 2000
RESET_ID = 0
SCAN_LIMIT = 150
LAST_SUCCESS_TIME = {"ts": 0}

# =====================================================================
# HTML TEMPLATE
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
# API FETCHER — ỔN ĐỊNH với retry + cache
# =====================================================================
def fetch_sessions():
    """
    Gọi API với:
    - Cache TTL 4 giây (tránh spam)
    - Retry 3 lần với exponential backoff
    - Fallback về cache cũ nếu API lỗi
    - Timeout 8s
    """
    now = time.time()

    # Cache hit
    if LAST_API_CALL["ok"] and (now - LAST_API_CALL["ts"]) < CACHE_TTL:
        cached = LAST_API_CALL["data"]
        if cached:
            return cached, True

    try:
        r = session.get(API_URL_MD5, timeout=API_TIMEOUT)
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
                # Cập nhật cache
                LAST_API_CALL["ts"] = now
                LAST_API_CALL["data"] = rows
                LAST_API_CALL["ok"] = True
                LAST_SUCCESS_TIME["ts"] = now
                return rows, True

        # HTTP khác 200 → fallback cache
        print(f"[API WARN] Status {r.status_code}, dùng cache cũ")
        if LAST_API_CALL["ok"] and LAST_API_CALL["data"]:
            return LAST_API_CALL["data"], True

    except requests.exceptions.Timeout:
        print(f"[API TIMEOUT] {API_TIMEOUT}s, dùng cache cũ")
        if LAST_API_CALL["ok"] and LAST_API_CALL["data"]:
            return LAST_API_CALL["data"], True
    except requests.exceptions.ConnectionError:
        print("[API CONN ERROR], dùng cache cũ")
        if LAST_API_CALL["ok"] and LAST_API_CALL["data"]:
            return LAST_API_CALL["data"], True
    except Exception as e:
        print(f"[API ERROR]: {e}")
        if LAST_API_CALL["ok"] and LAST_API_CALL["data"]:
            return LAST_API_CALL["data"], True

    return [], False


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

        # Nếu API fail HOÀN TOÀN và chưa có cache
        if not success and not HISTORY_CACHE:
            return jsonify({
                'error': 'Không thể kết nối API',
                'rows': [],
                'stats': {'total': 0, 'correct': 0},
            }), 200  # 200 để client không bị lỗi

        if raw_rows:
            for row in raw_rows: HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0}})

        # Học hash deep
        try:
            learn_hash_deep_from_history(valid)
        except Exception as e:
            print(f"[LEARN ERROR]: {e}")

        loss_streak = compute_loss_streak(valid)
        out = []; correct_count = 0; total_past = 0
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]

        try:
            base_pred, base_conf, _ = full_bridge_predict_adaptive(history_for_next)
            next_pred, next_conf, flipped, reason = apply_recovery(
                base_pred, base_conf, loss_streak, results=history_for_next
            )
        except Exception as e:
            print(f"[PREDICT ERROR]: {e}")
            base_pred, base_conf = history_for_next[0], 50
            next_pred, next_conf, flipped, reason = base_pred, 50, False, None

        out.append({
            'phien': next_phien, 'is_next': True,
            'prediction': next_pred, 'result': 'Chờ...',
            'dice': "? + ? + ?", 'is_correct': None,
            'conf': next_conf, 'recovery_flipped': flipped,
            'recovery_reason': reason, 'loss_streak': loss_streak,
            'base_prediction': base_pred if flipped else None,
        })

        for i in range(len(valid) - 1, len(valid) - min(len(valid), SCAN_LIMIT) - 1, -1):
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
            'api_status': 'ok' if success else 'cache',
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'rows': [],
            'stats': {'total': 0, 'correct': 0},
        }), 200


@app.route('/api/predict')
def predict():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if raw_rows:
            for row in raw_rows: HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu', 'prediction': '-', 'confidence': 50}), 200

        try:
            learn_hash_deep_from_history(valid)
        except Exception as e:
            print(f"[LEARN ERROR]: {e}")

        results = [v['result'] for v in valid][::-1]

        try:
            loss_streak = compute_loss_streak(valid)
            base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
            pred, conf, flipped, reason = apply_recovery(
                base_pred, base_conf, loss_streak, results=results
            )
        except Exception as e:
            print(f"[PREDICT ERROR]: {e}")
            base_pred, base_conf, pred, conf = results[0], 50, results[0], 50
            flipped, reason, detail, loss_streak = False, None, [], 0

        last13_tx = encode_tx(results, 13)
        last13_hash = hash_deep_md5(last13_tx, depth_level=2) if last13_tx else None

        return jsonify({
            'last_phien': valid[-1]['phien'], 'next_phien': valid[-1]['phien'] + 1,
            'last_result': valid[-1]['result'], 'last_dice': valid[-1]['dice'],
            'prediction': pred, 'confidence': conf,
            'base_prediction': base_pred, 'base_confidence': base_conf,
            'recovery_flipped': flipped, 'recovery_reason': reason,
            'loss_streak': loss_streak, 'total_sessions': len(valid),
            'last5_pattern': encode_tx(results, 5),
            'last13_hash': last13_hash,
            'signals': detail,
            'tai_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài'), 2),
            'xiu_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu'), 2),
            'signal_count': len(detail),
            'api_status': 'ok' if success else 'cache',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'error': str(e), 'prediction': '-', 'confidence': 50,
        }), 200


@app.route('/lc79')
def lc79():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if raw_rows:
            for row in raw_rows: HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'Id': 'le minh md5 deep v5', 'Phien': '-',
                            'Ket_qua': '-', 'Lich_su': '-', 'Du_doan': '-',
                            'Do_tin_cay': '50%'}), 200

        try:
            learn_hash_deep_from_history(valid)
            results = [v['result'] for v in valid][::-1]
            loss_streak = compute_loss_streak(valid)
            base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
            pred, conf, flipped, reason = apply_recovery(
                base_pred, base_conf, loss_streak, results=results
            )
        except Exception as e:
            print(f"[LC79 ERROR]: {e}")
            results = [v['result'] for v in valid][::-1]
            loss_streak = 0; base_pred = results[0]; pred = results[0]; flipped = False
            detail = []

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
            'Id': 'le minh md5 deep v5', 'Phien': str(next_phien),
            'Ket_qua': last['result'].lower(), 'Lich_su': lich_su,
            'Du_doan': pred, 'Do_tin_cay': conf_str,
            'Base_du_doan': base_pred if flipped else None,
            'Auto_flip': flipped, 'Chuoi_thua': loss_streak,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'Id': 'le minh md5 deep v5', 'Phien': '-',
                        'Ket_qua': '-', 'Lich_su': '-', 'Du_doan': '-',
                        'Do_tin_cay': '50%', 'error': str(e)}), 200


@app.route('/lc79md5')
def lc79md5():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if raw_rows:
            for row in raw_rows: HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'id': '@cskhleminh', 'phien': '-',
                            'ket_qua': '-', 'du_doan': '-',
                            'do_tin_cay': '50%', 'lich_su': '-'}), 200

        try:
            learn_hash_deep_from_history(valid)
            results = [v['result'] for v in valid][::-1]
            loss_streak = compute_loss_streak(valid)
            base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
            pred, conf, flipped, reason = apply_recovery(
                base_pred, base_conf, loss_streak, results=results
            )
        except Exception as e:
            print(f"[LC79MD5 ERROR]: {e}")
            results = [v['result'] for v in valid][::-1]
            loss_streak = 0; base_pred = results[0]; pred = results[0]; flipped = False
            detail = []

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
        return jsonify({'id': '@cskhleminh', 'phien': '-',
                        'ket_qua': '-', 'du_doan': '-',
                        'do_tin_cay': '50%', 'lich_su': '-',
                        'error': str(e)}), 200


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE, PREDICTION_CACHE
    try:
        raw_rows, success = fetch_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                PREDICTION_CACHE = {}
                reset_all_databases()
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Không thể xác nhận mốc Reset'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 200


# =====================================================================
# HEALTH CHECK
# =====================================================================
@app.route('/api/health')
def health():
    now = time.time()
    api_age = now - LAST_SUCCESS_TIME["ts"] if LAST_SUCCESS_TIME["ts"] > 0 else -1
    return jsonify({
        'status': 'ok',
        'api_last_success_sec_ago': round(api_age, 1) if api_age >= 0 else None,
        'history_size': len(HISTORY_CACHE),
        'cache_size': len(PREDICTION_CACHE),
        'reset_id': RESET_ID,
        'timestamp': datetime.now().isoformat(),
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 LE MINH MD5 v5 running on port {port}")
    print(f"📡 API: {API_URL_MD5[:80]}...")
    app.run(host='0.0.0.0', port=port, threaded=True)
