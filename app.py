import os
import math
import traceback
import hashlib
from datetime import datetime
from collections import defaultdict, Counter
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
PREDICTION_CACHE = {}
MAX_PREDICTION_CACHE = 2000
RESET_ID = 0

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
    .stats-bar { max-width: 800px; margin: 24px auto 16px; padding: 0 16px; display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
    .stat-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 14px 8px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
    .stat-label { font-size: 9px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px; letter-spacing: 0.3px; }
    .stat-value { font-size: 19px; font-weight: 800; color: var(--text-main); }
    .stat-value.win { color: var(--tai-color); text-shadow: 0 0 15px rgba(56, 189, 248, 0.3); }
    .stat-value.win.streak { color: var(--win-color); text-shadow: 0 0 15px rgba(52, 211, 153, 0.4); }
    .stat-value.loss { color: var(--lose-color); }
    .stat-value.win.streak.hot { animation: pulse 1.5s infinite; text-shadow: 0 0 15px rgba(52, 211, 153, 0.6); }
    .stat-value.loss.hot { color: var(--recovery-color); text-shadow: 0 0 15px rgba(251, 146, 60, 0.5); animation: pulse 1.5s infinite; }
    .stat-value.regime { font-size: 12px; color: #fbbf24; text-shadow: 0 0 12px rgba(251, 191, 36, 0.4); letter-spacing: 0.3px; }
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
        .stats-bar { grid-template-columns: repeat(3, 1fr); }
        .stat-value { font-size: 15px; }
        .stat-value.regime { font-size: 10px; }
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-title">LE MINH <span>CTEW</span></div>
    <div class="header-actions">
        <div class="time-update" id="time-update">--:--:--</div>
        <button class="btn-refresh" onclick="fetchData()">↻</button>
        <button class="btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>

<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ</div><div class="stat-value win" id="stat-rate">0%</div></div>
    <div class="stat-item"><div class="stat-label">Chuỗi thắng</div><div class="stat-value win streak" id="stat-wstreak">0</div></div>
    <div class="stat-item"><div class="stat-label">Chuỗi thua</div><div class="stat-value loss" id="stat-streak">0</div></div>
    <div class="stat-item"><div class="stat-label">MINHDZ</div><div class="stat-value regime" id="stat-regime">-</div></div>
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
        renderTable(data.rows || [], data.stats || {}, data.regime || '-', data.loss_streak || 0, data.win_streak || 0);
    } catch (e) { console.error("Lỗi tải dữ liệu:", e); }
}

function renderTable(rows, stats, regime, lossStreak, winStreak) {
    document.getElementById('stat-regime').innerText = regime || '-';
    const stkEl = document.getElementById('stat-streak');
    stkEl.innerText = lossStreak;
    if (lossStreak >= 2) { stkEl.classList.add('hot'); } else { stkEl.classList.remove('hot'); }
    const wstkEl = document.getElementById('stat-wstreak');
    wstkEl.innerText = winStreak;
    if (winStreak >= 2) { wstkEl.classList.add('hot'); } else { wstkEl.classList.remove('hot'); }

    const tbody = document.getElementById('table-body');
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
            recBadge = `<span class="recovery-badge" title="Auto-flip do thua ${row.loss_streak || 0} lần">⚡ RECOVERY</span>`;
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
                    rows.append({'phien': int(item['id']), 'result': res, 'dice': dice_str, 'total': total})
                return rows, True
    except Exception as e:
        print(f"[API ERROR]: {e}")
    return [], False


# =====================================================================
# UTILS
# =====================================================================
def get_groups(results):
    if not results: return []
    groups = []
    current_val = results[0]
    count = 1
    for r in results[1:]:
        if r == current_val:
            count += 1
        else:
            groups.append(count)
            current_val = r
            count = 1
    groups.append(count)
    return groups


def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"


def _count_alternations(results, max_len=15):
    count = 0
    for i in range(min(len(results) - 1, max_len)):
        if results[i] != results[i+1]:
            count += 1
        else:
            break
    return count


# =====================================================================
# ALGOS (deterministic, no randomness, no pattern-matching)
# =====================================================================
def algo_recency_momentum(results):
    n = len(results)
    if n < 8: return None
    st = sx = 0
    for i in range(min(n, 20)):
        w = 20 - i
        if results[i] == "Tài": st += w
        else: sx += w
    total = st + sx
    if total == 0: return None
    if max(st, sx) / total < 0.68: return None
    return ("Tài", 9, "recency_tai") if st > sx else ("Xỉu", 9, "recency_xiu")


def algo_non_random_deterministic(results):
    if len(results) < 5: return None
    groups = get_groups(results); r0 = results[0]
    if len(groups) >= 5:
        common_len, freq = Counter(groups[:10]).most_common(1)[0]
        if freq >= 3:
            if groups[0] < common_len: return (r0, 11, "nonrand_cycle_continue")
            return (_opp(r0), 12, "nonrand_cycle_break")
    if len(groups) >= 4:
        avg = sum(groups[:6]) / len(groups[:6]); cur = groups[0]
        if cur > avg + 0.5: return (_opp(r0), 10, "nonrand_streak_break")
        if cur < avg - 0.3: return (r0, 9, "nonrand_streak_continue")
    return None


def algo_simple_enhanced(results):
    if len(results) < 3: return None
    r0 = results[0]; streak = 1
    for r in results[1:]:
        if r == r0: streak += 1
        else: break
    if streak == 1:
        if len(results) >= 3 and results[1] == results[2]:
            return (_opp(r0), 8, "simple_break_after_pair")
        return (r0, 8, "simple_continue")
    if streak == 2: return (r0, 9, "simple_momentum")
    if streak == 3: return (_opp(r0), 10, "simple_break_3")
    if streak >= 4: return (_opp(r0), 11, "simple_break_4plus")
    return None


def algo_runlength_compare(results):
    n = len(results)
    if n < 20: return None
    groups = get_groups(results)
    if len(groups) < 4: return None
    cur = groups[0]; past = groups[1:min(20, len(groups))]
    if not past: return None
    avg = sum(past) / len(past)
    if cur > avg * 1.6 and cur >= 3: return (_opp(results[0]), 11, "runlength_break")
    if cur < 1.5 and avg >= 2.5: return (results[0], 8, "runlength_continue")
    return None


def algo_weighted_trend(results):
    """Trend có trọng số giảm dần — tất định, không pattern."""
    n = len(results)
    if n < 10: return None
    weights = [10.0, 8.0, 6.0, 4.0, 3.0, 2.0, 1.5, 1.0, 0.8, 0.5]
    tw = sw = 0.0
    for i, r in enumerate(results[:10]):
        w = weights[i]
        tw += w
        if r == "Tài": sw += w
    if tw == 0: return None
    ratio = sw / tw
    if ratio >= 0.72: return ("Tài", 10, "wt_trend_tai")
    if ratio <= 0.28: return ("Xỉu", 10, "wt_trend_xiu")
    return None


# =====================================================================
# HELPERS
# =====================================================================
def analyze_bet_advanced(results, groups):
    signals = []
    if not groups or len(results) < 3: return signals
    r0 = results[0]; g0 = groups[0]; n = len(results)
    if   g0 >= 12: signals.append((_opp(r0), 42, "bet_12plus_break"))
    elif g0 >= 10: signals.append((_opp(r0), 38, "bet_10plus_break"))
    elif g0 >= 8:  signals.append((_opp(r0), 32, "bet_8_9_break"))
    elif g0 >= 6:  signals.append((_opp(r0), 25, "bet_6_7_break"))
    elif g0 == 5:  signals.append((_opp(r0), 18, "bet_5_break"))
    elif g0 == 4:  signals.append((_opp(r0), 12, "bet_4_break"))
    elif g0 == 3:
        if len(groups) >= 5:
            avg_g = sum(groups[1:min(12, len(groups))]) / len(groups[1:min(12, len(groups))])
            if   avg_g < 2.3: signals.append((_opp(r0), 13, "bet_3_break_adaptive"))
            elif avg_g >= 3.5: signals.append((r0, 11, "bet_3_continue_adaptive"))
            else:              signals.append((_opp(r0), 9, "bet_3_break_default"))
        else: signals.append((_opp(r0), 9, "bet_3_break_default"))
    if n >= 15:
        tai15 = results[:15].count("Tài")
        if tai15 >= 12 and r0 == "Tài" and g0 <= 5: signals.append(("Tài", 9, "bet_hot_continue_tai"))
        elif tai15 <= 3 and r0 == "Xỉu" and g0 <= 5: signals.append(("Xỉu", 9, "bet_hot_continue_xiu"))
    return signals


def analyze_sandwich(groups, results):
    signals = []
    if len(groups) < 3 or len(results) < 5: return signals
    r0 = results[0]
    if groups[0] == 1 and groups[2] == 1 and 1 <= groups[1] <= 6:
        signals.append((_opp(r0), 10 + min(groups[1], 5), f"sandwich_1_{groups[1]}_1"))
    if groups[0] == 2 and groups[2] == 2 and 1 <= groups[1] <= 5:
        signals.append((_opp(r0), 13, f"sandwich_2_{groups[1]}_2"))
    if groups[0] == 3 and groups[2] == 3 and 1 <= groups[1] <= 4:
        signals.append((_opp(r0), 14, f"sandwich_3_{groups[1]}_3"))
    if len(groups) >= 4 and groups[0] == 1 and groups[2] == 1 and groups[3] >= 2:
        signals.append((r0, 8, "sandwich_chain"))
    return signals


def analyze_cycle(results):
    signals = []
    n = len(results)
    if n < 10: return signals
    for cl in range(2, 6):
        if n < cl * 3: continue
        seq = results[:cl]; matches = 0
        for i in range(cl, min(n, cl * 5)):
            if results[i] == seq[matches % cl]: matches += 1
            else: break
        if matches >= cl * 2.5:
            signals.append((seq[matches % cl], 8 + min(int(matches * 0.8), 12), f"cycle_{cl}"))
            break
    return signals


# =====================================================================
# MASTER ANALYZER — deterministic, no random, no pattern-matching
# =====================================================================
def analyze_full_bridge(results):
    if len(results) < 3: return []
    signals = []
    groups = get_groups(results)
    n = len(results); r0 = results[0]

    signals.extend(analyze_bet_advanced(results, groups))

    alt = _count_alternations(results)
    if   alt >= 8: signals.append((_opp(r0), 26, "1_1_extreme"))
    elif alt >= 6: signals.append((_opp(r0), 22, "1_1_strong"))
    elif alt >= 4: signals.append((_opp(r0), 16, "1_1"))
    elif alt >= 3: signals.append((_opp(r0), 10, "1_1_weak"))

    if   len(groups) >= 6 and all(g == 2 for g in groups[:6]): signals.append((_opp(r0), 22, "2_2_extreme"))
    elif len(groups) >= 5 and all(g == 2 for g in groups[:5]): signals.append((_opp(r0), 18, "2_2_strong"))
    elif len(groups) >= 4 and all(g == 2 for g in groups[:4]): signals.append((_opp(r0), 14, "2_2"))
    elif len(groups) >= 3 and all(g == 2 for g in groups[:3]): signals.append((_opp(r0), 9, "2_2_weak"))

    if   len(groups) >= 5 and all(g == 3 for g in groups[:5]): signals.append((_opp(r0), 18, "3_3_strong"))
    elif len(groups) >= 4 and all(g == 3 for g in groups[:4]): signals.append((_opp(r0), 15, "3_3"))
    elif len(groups) >= 3 and all(g == 3 for g in groups[:3]): signals.append((_opp(r0), 10, "3_3_weak"))

    for L in (6, 5, 4):
        if len(groups) >= 3 and all(g == L for g in groups[:3]):
            signals.append((_opp(r0), max(8, 15 - L), f"{L}_{L}")); break

    signals.extend(analyze_sandwich(groups, results))

    if len(groups) >= 5:
        if groups[:5] == [1,2,3,2,1]: signals.append((results[1], 13, "pyramid_12321"))
        elif groups[:5] == [2,3,4,3,2]: signals.append((results[1], 12, "pyramid_23432"))
        elif groups[:5] == [1,2,1,2,1]: signals.append((results[0], 11, "zigzag_12121"))

    if len(groups) >= 3:
        if groups[:3] == [1,2,3]: signals.append((r0, 10, "inc_123"))
        if groups[:3] == [3,2,1]: signals.append((r0, 10, "dec_321"))
        if groups[:3] == [1,3,5]: signals.append((r0, 9, "inc_135"))
        if groups[:3] == [2,4,6]: signals.append((r0, 9, "inc_246"))

    if len(groups) >= 3 and groups[:3] == [1,2,1] and n >= 4: signals.append((results[1], 13, "1_2_1"))
    if len(groups) >= 3 and groups[:3] == [2,1,2] and n >= 5: signals.append((results[2], 13, "2_1_2"))
    if len(groups) >= 3 and groups[:3] == [1,3,1] and n >= 5: signals.append((results[1], 11, "1_3_1"))
    if len(groups) >= 3 and groups[:3] == [1,1,2] and n >= 5: signals.append((_opp(results[0]), 12, "1_1_2"))
    if len(groups) >= 3 and groups[:3] == [2,2,1] and n >= 6: signals.append((_opp(results[0]), 11, "2_2_1"))

    signals.extend(analyze_cycle(results))

    if n >= 15:
        for window in (15, 20, 30):
            if n < window: continue
            tr = results[:window].count("Tài") / window
            if   tr >= 0.73: signals.append(("Xỉu", 10, f"tilt_tai_{window}")); break
            elif tr <= 0.27: signals.append(("Tài", 10, f"tilt_xiu_{window}")); break

    if n >= 15:
        tr = {"Tài": {"Tài":0,"Xỉu":0}, "Xỉu": {"Tài":0,"Xỉu":0}}
        for i in range(len(results[:45]) - 1):
            tr[results[i+1]][results[i]] += 1
        last = results[0]; tot = sum(tr[last].values())
        if tot >= 5:
            p = tr[last]["Tài"] / tot
            if   p >= 0.65: signals.append(("Tài", 10, "markov1"))
            elif p <= 0.35: signals.append(("Xỉu", 10, "markov1"))

    if n >= 20:
        target = tuple(results[:2]); nt = nx = 0
        for i in range(2, min(n, 50)):
            if tuple(results[i:i+2]) == target:
                if results[i-1] == "Tài": nt += 1
                else: nx += 1
        tot = nt + nx
        if tot >= 3:
            if   nt/tot >= 0.68: signals.append(("Tài", 11, "markov2"))
            elif nx/tot >= 0.68: signals.append(("Xỉu", 11, "markov2"))

    if n >= 12:
        for w, hi, lo in ((8, 7, 1), (12, 10, 2)):
            if n < w: continue
            tc = results[:w].count("Tài")
            if tc >= hi: signals.append(("Xỉu", 14 if w == 8 else 12, f"hot_tai_{w}"))
            elif tc <= lo: signals.append(("Tài", 14 if w == 8 else 12, f"hot_xiu_{w}"))

    if n >= 15:
        w5 = results[:5].count("Tài"); w10 = results[:10].count("Tài"); w15 = results[:15].count("Tài")
        vt = sum([w5 >= 4, w10 >= 7, w15 >= 10]); vx = sum([w5 <= 1, w10 <= 3, w15 <= 5])
        if   vt >= 2: signals.append(("Tài", 11, "multi_window"))
        elif vx >= 2: signals.append(("Xỉu", 11, "multi_window"))

    if n >= 15:
        trans = sum(1 for i in range(14) if results[i] != results[i+1])
        if trans >= 12: signals.append((_opp(results[0]), 13, "chaos_alt"))

    if n >= 20:
        p_tai = results[:20].count("Tài") / 20
        entropy = 0 if p_tai in (0,1) else -(p_tai * math.log2(p_tai) + (1-p_tai) * math.log2(1-p_tai))
        if entropy < 0.6: signals.append(("Tài" if p_tai > 0.5 else "Xỉu", 9, "low_entropy"))

    if n >= 10:
        trans = sum(1 for i in range(9) if results[i] != results[i+1])
        if 4 <= trans <= 6: signals.append((_opp(results[0]), 7, "balanced_osc"))

    if n >= 8 and groups[0] >= 2:
        w8 = results[:8].count("Tài")
        if   w8 >= 6: signals.append(("Tài", 8, "momentum"))
        elif w8 <= 2: signals.append(("Xỉu", 8, "momentum"))

    if len(groups) >= 5 and tuple(groups[:5]) in ((1,2,3,2,1),(1,2,3,2),(1,1,2,1,1),(2,1,1,2,2)):
        signals.append((results[1], 10, "zigzag_ext"))

    recency = algo_recency_momentum(results)
    if recency: signals.append(recency)

    weighted = algo_weighted_trend(results)
    if weighted: signals.append(weighted)

    if len(groups) >= 4:
        if groups[:4] in ([1,1,2,2],[2,2,1,1]): signals.append((_opp(r0), 14, "double_bridge_1122"))
        if groups[:4] in ([2,2,3,3],[3,3,2,2]): signals.append((_opp(r0), 12, "double_bridge_2233"))
        if groups[:4] in ([1,2,2,1],[2,1,1,2]): signals.append((_opp(r0), 13, "double_bridge_mirror"))
        par = [g % 2 for g in groups[:4]]
        if par in ([0,1,0,1],[1,0,1,0]): signals.append((_opp(r0), 11, "parity_alt"))
        elif par in ([0,0,1,1],[1,1,0,0]): signals.append((_opp(r0), 10, "parity_pair"))
        sample = groups[:4]; mean = sum(sample)/4
        var = sum((g-mean)**2 for g in sample)/4
        if var <= 0.25 and mean >= 2: signals.append((_opp(r0), 12, "consistent_groups"))

    if len(groups) >= 7 and groups[:7] == [1,2,3,4,3,2,1]: signals.append((r0, 12, "pyramid_1234321"))
    if len(groups) >= 6 and groups[:6] == [1,2,3,4,3,2]: signals.append((results[0], 11, "pyramid_123432"))
    if len(groups) >= 4 and groups[:4] == [1,2,3,4]: signals.append((r0, 10, "prog_inc_1234"))
    if len(groups) >= 5 and groups[:5] == [1,2,3,4,5]: signals.append((r0, 10, "prog_inc_12345"))
    if len(groups) >= 4 and groups[:4] == [4,3,2,1]: signals.append((_opp(r0), 11, "prog_dec_4321"))
    if len(groups) >= 5 and groups[:5] == [5,4,3,2,1]: signals.append((_opp(r0), 11, "prog_dec_54321"))
    if len(groups) >= 3 and groups[:3] == [2,3,2]: signals.append((_opp(r0), 13, "sym_232"))
    if len(groups) >= 3 and groups[:3] == [1,4,1]: signals.append((_opp(r0), 13, "sym_141"))
    for c in (2, 3, 4):
        if len(groups) >= 3 and groups[:3] == [c, c+2, c]:
            signals.append((_opp(r0), 12, f"sym_{c}_{c+2}_{c}")); break

    nrnd = algo_non_random_deterministic(results)
    if nrnd: signals.append(nrnd)
    simple = algo_simple_enhanced(results)
    if simple: signals.append(simple)

    runlen = algo_runlength_compare(results)
    if runlen: signals.append(runlen)

    return signals


# =====================================================================
# REGIME DETECTION (NEUTRAL removed)
# =====================================================================
def detect_regime(results):
    n = len(results)
    if n < 8: return {"regime": "TREND", "trans_rate": 0.5, "max_streak": 1}
    sample = results[:min(n, 20)]
    trans = sum(1 for i in range(len(sample) - 1) if sample[i] != sample[i + 1])
    trans_rate = trans / (len(sample) - 1) if len(sample) > 1 else 0.5
    max_streak = max(get_groups(sample)) if sample else 1
    if   trans_rate >= 0.80: regime = "STRONG_ALT"
    elif trans_rate >= 0.65: regime = "ALT"
    elif max_streak >= 5:    regime = "STRONG_TREND"
    elif max_streak >= 3:    regime = "TREND"
    elif trans_rate >= 0.55: regime = "ALT"
    elif max_streak >= 2:    regime = "TREND"
    else:                    regime = "CHAOS"
    return {"regime": regime, "trans_rate": round(trans_rate, 3), "max_streak": max_streak}


REGIME_PREFERENCES = {
    "STRONG_ALT":   {"1_1": 1.5, "cycle": 1.4, "seq": 1.2, "bet": 0.5, "simple": 0.6, "momentum": 0.4},
    "ALT":          {"1_1": 1.3, "cycle": 1.2, "seq": 1.1, "bet": 0.7, "simple": 0.8},
    "TREND":        {"bet": 1.4, "simple": 1.3, "momentum": 1.2, "nonrand": 1.2, "1_1": 0.6},
    "STRONG_TREND": {"bet": 1.5, "simple": 1.4, "momentum": 1.3, "nonrand": 1.3, "1_1": 0.4},
    "CHAOS":        {"1_1": 1.2, "2_2": 1.1, "sandwich": 1.1, "simple": 0.8, "bet": 0.9},
}

def get_signal_multiplier(name, regime):
    for prefix, mult in REGIME_PREFERENCES.get(regime, {}).items():
        if name.startswith(prefix): return mult
    return 1.0


# =====================================================================
# BASE PREDICTOR
# =====================================================================
def full_bridge_predict(results):
    if not results: return "Tài", 50
    if len(results) == 1: return _opp(results[0]), 52
    if len(results) == 2:
        if results[0] == results[1]: return _opp(results[0]), 55
        return results[1], 52
    signals = analyze_full_bridge(results)
    if not signals: return results[0], 52
    regime = detect_regime(results)["regime"]
    st = sx = 0.0
    for p, w, name in signals:
        w_adj = w * get_signal_multiplier(name, regime)
        if p == "Tài": st += w_adj
        else: sx += w_adj
    total = st + sx
    if total == 0: return results[0], 50
    ratio = max(st, sx) / total
    evidence = min(1.0, total / 40.0)
    conf = int(max(50, min(92, 50 + ((ratio - 0.5) * 100) * evidence)))
    if st > sx: return "Tài", conf
    if sx > st: return "Xỉu", conf
    return _opp(results[0]), 50


# =====================================================================
# ADAPTIVE PREDICTOR (deterministic)
# =====================================================================
def full_bridge_predict_adaptive(results, replay_n=80):
    n = len(results)
    default_regime = {"regime": "TREND", "trans_rate": 0.5, "max_streak": 1}
    if n == 0:
        return "Tài", 50, [], default_regime
    if n == 1:
        return _opp(results[0]), 52, [], default_regime
    if n == 2:
        if results[0] == results[1]:
            return _opp(results[0]), 55, [], default_regime
        return results[1], 52, [], default_regime

    regime_info = detect_regime(results)
    regime = regime_info["regime"]
    signal_stats = defaultdict(lambda: {
        'wins': 0.0, 'total': 0.0,
        'regime_wins':  defaultdict(float),
        'regime_total': defaultdict(float),
    })
    replay_count = min(replay_n, n - 3)
    for j in range(replay_count):
        history = results[j + 1:]; actual = results[j]
        decay = math.exp(-j / max(replay_count / 2.0, 1.0))
        hist_regime = detect_regime(history)["regime"]
        for pred_sig, weight, name in analyze_full_bridge(history):
            signal_stats[name]['total'] += decay
            signal_stats[name]['regime_total'][hist_regime] += decay
            if pred_sig == actual:
                signal_stats[name]['wins'] += decay
                signal_stats[name]['regime_wins'][hist_regime] += decay

    signals = analyze_full_bridge(results)
    if not signals:
        return results[0], 52, [], regime_info

    st = sx = 0.0; detail = []
    for pred_sig, weight, name in signals:
        s = signal_stats[name]
        if s['total'] >= 3:
            alpha = 2.0
            acc = (s['wins'] + alpha * 0.5) / (s['total'] + alpha)
            samples = int(s['total'])
        else:
            acc, samples = 0.5, int(s['total'])
        rt = s['regime_total'][regime]; rw = s['regime_wins'][regime]
        if rt >= 2:
            regime_acc = (rw + 1.0) / (rt + 2.0)
            acc = 0.70 * regime_acc + 0.30 * acc
        accuracy_mult = 0.4 + max(0.0, min(1.8, (acc - 0.3) * 3.0))
        regime_mult = get_signal_multiplier(name, regime)
        adjusted = weight * accuracy_mult * regime_mult
        if pred_sig == "Tài": st += adjusted
        else: sx += adjusted
        detail.append({'name': name, 'pred': pred_sig, 'base_weight': weight,
                       'accuracy': round(acc, 3), 'samples': samples,
                       'regime_mult': round(regime_mult, 2),
                       'adjusted_weight': round(adjusted, 2)})

    total = st + sx
    if total == 0:
        return results[0], 50, detail, regime_info
    if st > sx: pred, ratio = "Tài", st / total
    elif sx > st: pred, ratio = "Xỉu", sx / total
    else: return _opp(results[0]), 50, detail, regime_info

    base_conf = 50 + (ratio - 0.5) * 100
    evidence = min(1.0, total / 50.0)
    conf = 50 + (base_conf - 50) * evidence
    if ratio >= 0.72: conf += 6
    if ratio >= 0.80 and len(signals) >= 5: conf += 6
    if len(signals) >= 10 and ratio >= 0.65: conf += 3
    if regime in ("STRONG_ALT", "STRONG_TREND"): conf += 2
    if len(signals) < 4: conf -= 5
    if regime == "CHAOS": conf -= 3
    return pred, int(max(50, min(95, conf))), detail, regime_info


# =====================================================================
# PREDICTION CACHE
# =====================================================================
def get_prediction_for(valid, i):
    key = valid[i]['phien']
    if key in PREDICTION_CACHE:
        return PREDICTION_CACHE[key]
    hist = [v['result'] for v in valid[:i]][::-1]
    if len(hist) < 3:
        result = ("-", 50, None)
    else:
        pred, conf = full_bridge_predict(hist)
        is_correct = (pred == valid[i]['result'])
        result = (pred, conf, is_correct)
    if len(PREDICTION_CACHE) > MAX_PREDICTION_CACHE:
        PREDICTION_CACHE.clear()
    PREDICTION_CACHE[key] = result
    return result


# =====================================================================
# STREAKS (both win & loss)
# =====================================================================
def compute_streaks(valid, max_scan=20):
    if len(valid) < 5: return 0, 0
    win_streak = loss_streak = 0
    current_type = None
    end = len(valid) - 1
    start = max(0, end - max_scan)
    for i in range(end, start - 1, -1):
        pred, conf, is_correct = get_prediction_for(valid, i)
        if is_correct is None: break
        if current_type is None:
            current_type = 'win' if is_correct else 'loss'
        if current_type == 'win' and is_correct:
            win_streak += 1
        elif current_type == 'loss' and not is_correct:
            loss_streak += 1
        else:
            break
    return win_streak, loss_streak


# =====================================================================
# AUTO-RECOVERY (deterministic)
# =====================================================================
def apply_recovery(base_pred, conf, loss_streak):
    if loss_streak < 2:
        return base_pred, conf, False, None
    if loss_streak >= 5:
        return _opp(base_pred), min(96, conf + 15), True, "flip_5plus"
    if loss_streak == 4:
        return _opp(base_pred), min(95, conf + 12), True, "flip_4"
    if loss_streak == 3:
        return _opp(base_pred), min(94, conf + 10), True, "flip_3"
    if conf < 75:
        return _opp(base_pred), min(93, conf + 6), True, "flip_2"
    return base_pred, max(50, conf - 12), False, "penalty_2"


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
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0},
                            'regime': '-', 'loss_streak': 0, 'win_streak': 0})

        win_streak, loss_streak = compute_streaks(valid)

        out = []; correct_count = 0; total_past = 0
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]

        base_pred, base_conf, _, next_regime = full_bridge_predict_adaptive(history_for_next)
        next_pred, next_conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak)

        out.append({
            'phien': next_phien, 'is_next': True,
            'prediction': next_pred, 'result': 'Chờ...',
            'dice': "? + ? + ?", 'is_correct': None,
            'conf': next_conf,
            'recovery_flipped': flipped,
            'recovery_reason': reason,
            'loss_streak': loss_streak,
            'win_streak': win_streak,
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
            'regime': next_regime['regime'],
            'loss_streak': loss_streak,
            'win_streak': win_streak,
            'recovery_active': flipped,
            'recovery_reason': reason,
            'base_prediction': base_pred,
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
        results = [v['result'] for v in valid][::-1]

        win_streak, loss_streak = compute_streaks(valid)
        base_pred, base_conf, detail, regime_info = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak)

        return jsonify({
            'last_phien': valid[-1]['phien'], 'next_phien': valid[-1]['phien'] + 1,
            'last_result': valid[-1]['result'], 'last_dice': valid[-1]['dice'],
            'prediction': pred, 'confidence': conf,
            'base_prediction': base_pred, 'base_confidence': base_conf,
            'recovery_flipped': flipped, 'recovery_reason': reason,
            'loss_streak': loss_streak, 'win_streak': win_streak,
            'total_sessions': len(valid),
            'signals': detail,
            'tai_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài'), 2),
            'xiu_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu'), 2),
            'signal_count': len(detail),
            'regime': regime_info['regime'],
            'trans_rate': regime_info['trans_rate'],
            'max_streak': regime_info['max_streak'],
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
        results = [v['result'] for v in valid][::-1]

        win_streak, loss_streak = compute_streaks(valid)
        base_pred, base_conf, detail, regime_info = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak)

        tai_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài')
        xiu_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu')
        total_sig = tai_score + xiu_score
        if total_sig > 0:
            ratio = max(tai_score, xiu_score) / total_sig
            base_conf_f = 50 + (ratio - 0.5) * 100
            evidence = min(1.0, total_sig / 50.0)
            conf_float = max(50.0, min(95.0, 50 + (base_conf_f - 50) * evidence))
        else:
            conf_float = 50.0
        conf_str = f"{conf_float:.1f}".replace(".", ",") + "%"
        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])
        last = valid[-1]; next_phien = last['phien'] + 1

        return jsonify({
            'Id': 'le minh v24', 'Phien': str(next_phien),
            'Ket_qua': last['result'].lower(), 'Lich_su': lich_su,
            'Du_doan': pred, 'Do_tin_cay': conf_str,
            'Regime': regime_info['regime'],
            'Base_du_doan': base_pred if flipped else None,
            'Auto_flip': flipped,
            'Chuoi_thua': loss_streak,
            'Chuoi_thang': win_streak,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng, không thể xác nhận mốc Reset'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
