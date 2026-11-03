import os
import math
import traceback
import random
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
        --bg-page: #0f172a;
        --bg-card: #1e293b;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --border-color: #334155;
        --tai-color: #38bdf8;
        --tai-bg: rgba(56, 189, 248, 0.15);
        --xiu-color: #f472b6;
        --xiu-bg: rgba(244, 114, 182, 0.15);
        --win-color: #34d399;
        --win-bg: rgba(52, 211, 153, 0.15);
        --lose-color: #f87171;
        --lose-bg: rgba(248, 113, 113, 0.15);
        --wait-color: #fbbf24;
        --wait-bg: rgba(251, 191, 36, 0.15);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: var(--text-main);
        min-height: 100vh;
        padding-bottom: 40px;
    }
    .header {
        background: rgba(30, 41, 59, 0.85);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid var(--border-color);
        padding: 16px 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .header-title {
        font-size: 22px;
        font-weight: 800;
        color: #38bdf8;
        display: flex;
        align-items: center;
        gap: 10px;
        text-shadow: 0 0 20px rgba(56, 189, 248, 0.4);
    }
    .header-title span {
        font-size: 11px;
        background: linear-gradient(135deg, #38bdf8, #ec4899);
        color: #fff;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 800;
        letter-spacing: 1px;
        box-shadow: 0 0 15px rgba(236, 72, 153, 0.4);
    }
    .header-actions { display: flex; gap: 12px; align-items: center; }
    .time-update { font-size: 12px; color: var(--text-muted); font-weight: 600; }
    .btn-refresh {
        background: var(--bg-card);
        color: var(--text-main);
        border: 1px solid var(--border-color);
        width: 38px;
        height: 38px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 16px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: 0.2s;
    }
    .btn-refresh:hover { background: var(--border-color); transform: rotate(180deg); }
    .btn-reset {
        background: rgba(248, 113, 113, 0.2);
        color: var(--lose-color);
        border: 1px solid var(--lose-color);
        padding: 8px 16px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 13px;
        cursor: pointer;
        transition: 0.2s;
    }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 15px rgba(248, 113, 113, 0.4); }

    .stats-bar {
        max-width: 800px;
        margin: 24px auto 16px;
        padding: 0 16px;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
    }
    .stat-item {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px; letter-spacing: 0.5px; }
    .stat-value { font-size: 24px; font-weight: 800; color: var(--text-main); }
    .stat-value.win { color: var(--tai-color); text-shadow: 0 0 15px rgba(56, 189, 248, 0.3); }

    .table-wrapper { max-width: 800px; margin: 0 auto; padding: 0 16px; }
    .table-container {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        max-height: 70vh;
        overflow-y: auto;
    }
    .data-table { width: 100%; border-collapse: separate; border-spacing: 0; }
    .data-table th {
        background: #111827;
        color: var(--text-muted);
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 16px 12px;
        text-align: center;
        border-bottom: 1px solid var(--border-color);
        position: sticky;
        top: 0;
        z-index: 10;
    }
    .data-table td {
        padding: 14px 12px;
        text-align: center;
        border-bottom: 1px solid var(--border-color);
        font-size: 14px;
        font-weight: 600;
    }
    .data-table tr:last-child td { border-bottom: none; }
    .data-table tr:hover { background: rgba(255, 255, 255, 0.02); }
    .row-next { background: rgba(14, 165, 233, 0.08); border-left: 4px solid var(--tai-color); }

    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        min-width: 70px;
        text-align: center;
    }
    .badge-tai { background: var(--tai-bg); color: var(--tai-color); border: 1px solid rgba(56, 189, 248, 0.3); box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); }
    .badge-xiu { background: var(--xiu-bg); color: var(--xiu-color); border: 1px solid rgba(244, 114, 182, 0.3); box-shadow: 0 0 10px rgba(244, 114, 182, 0.2); }
    .badge-empty { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); }

    .status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; padding: 6px 14px; border-radius: 20px; }
    .st-win { background: var(--win-bg); color: var(--win-color); border: 1px solid rgba(52, 211, 153, 0.3); }
    .st-lose { background: var(--lose-bg); color: var(--lose-color); border: 1px solid rgba(248, 113, 113, 0.3); }
    .st-wait { background: var(--wait-bg); color: var(--wait-color); border: 1px solid rgba(251, 191, 36, 0.3); animation: pulse 1.5s infinite; }
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
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-title">LE MINH <span>MD5 v21</span></div>
    <div class="header-actions">
        <div class="time-update" id="time-update">--:--:--</div>
        <button class="btn-refresh" onclick="fetchData()">↻</button>
        <button class="btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>

<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng phiên</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ</div><div class="stat-value win" id="stat-rate">0%</div></div>
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
    } catch (e) {
        console.error("Lỗi tải dữ liệu:", e);
    }
}

function renderTable(rows, stats) {
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
        const trClass = row.is_next ? 'class="row-next"' : '';

        let predHtml = `<span class="badge badge-empty">-</span>`;
        if (row.prediction === "Tài") predHtml = `<span class="badge badge-tai">TÀI</span>`;
        if (row.prediction === "Xỉu") predHtml = `<span class="badge badge-xiu">XỈU</span>`;

        let confHtml = "";
        if (row.conf && row.prediction !== "-") {
            const cls = row.conf >= 70 ? 'conf-badge high' : 'conf-badge';
            confHtml = `<div class="${cls}">${row.conf}%</div>`;
        }
        let predFull = `<div style="display:flex; flex-direction:column; align-items:center;">${predHtml}${confHtml}</div>`;

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
            statusHtml = `<span class="status st-wait">Chờ kết quả</span>`;
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
        title: 'Xác nhận Reset?',
        text: "Toàn bộ lịch sử hiển thị sẽ bị xoá và bắt đầu lại từ đầu!",
        icon: 'warning',
        background: '#1e293b',
        color: '#f8fafc',
        showCancelButton: true,
        confirmButtonColor: '#0ea5e9',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Đồng ý',
        cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, background: '#1e293b', color: '#f8fafc', didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Thành công!', text: 'Đã xoá lịch sử và bắt đầu lại.', icon: 'success', background: '#1e293b', color: '#f8fafc', confirmButtonColor: '#0ea5e9' });
                    isResetting = false;
                    fetchData();
                } else {
                    throw new Error(data.message);
                }
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
                    rows.append({
                        'phien': int(item['id']),
                        'result': res,
                        'dice': dice_str,
                        'total': total
                    })
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


def _detect_group_pattern(groups, results):
    if len(groups) < 3 or len(results) < 20:
        return None
    for plen in range(min(5, len(groups) - 1), 1, -1):
        current = tuple(groups[:plen])
        if sum(current) > len(results): continue
        matches = []
        for i in range(1, len(groups) - plen):
            if tuple(groups[i:i+plen]) == current:
                pos = sum(groups[:i])
                if pos < len(results):
                    matches.append(results[pos])
        if len(matches) >= 2:
            total = len(matches)
            t = matches.count("Tài"); x = total - t
            if t / total >= 0.7: return ("Tài", 14 if total >= 3 else 10, f"hist_{plen}")
            if x / total >= 0.7: return ("Xỉu", 14 if total >= 3 else 10, f"hist_{plen}")
    return None


def _stable_hash(s):
    return int(hashlib.md5(s.encode('utf-8')).hexdigest()[:8], 16)


# =====================================================================
# THUẬT TOÁN PHỤ #1 — RANDOM CÓ TRỌNG SỐ
# =====================================================================
def algo_random_weighted(results):
    if len(results) < 3:
        return None
    window = results[:12]
    p_tai = window.count("Tài") / len(window)
    seed = _stable_hash(",".join(results[:20]))
    rng = random.Random(seed)
    r = rng.random()

    if p_tai >= 0.65:
        pred = "Tài" if r < 0.70 else "Xỉu"
        weight = 9
    elif p_tai <= 0.35:
        pred = "Xỉu" if r < 0.70 else "Tài"
        weight = 9
    else:
        pred = "Tài" if r < 0.50 else "Xỉu"
        weight = 6

    return (pred, weight, "random_weighted")


# =====================================================================
# THUẬT TOÁN PHỤ #2 — TẤT ĐỊNH (CHU KỲ + STREAK)
# =====================================================================
def algo_non_random_deterministic(results):
    if len(results) < 5:
        return None
    groups = get_groups(results)
    r0 = results[0]

    if len(groups) >= 5:
        cnt = Counter(groups[:10])
        common_len, common_freq = cnt.most_common(1)[0]
        if common_freq >= 3:
            if groups[0] < common_len:
                return (r0, 11, "nonrand_cycle_continue")
            elif groups[0] >= common_len:
                return (_opp(r0), 12, "nonrand_cycle_break")

    if len(groups) >= 4:
        sample = groups[:6]
        avg = sum(sample) / len(sample)
        cur = groups[0]
        if cur > avg + 0.5:
            return (_opp(r0), 10, "nonrand_streak_break")
        if cur < avg - 0.3:
            return (r0, 9, "nonrand_streak_continue")
    return None


# =====================================================================
# THUẬT TOÁN PHỤ #3 — RULE NGẮN HẠN
# =====================================================================
def algo_simple_enhanced(results):
    if len(results) < 3:
        return None
    r0 = results[0]
    streak = 1
    for r in results[1:]:
        if r == r0:
            streak += 1
        else:
            break

    if streak == 1:
        if len(results) >= 3 and results[1] == results[2]:
            return (_opp(r0), 8, "simple_break_after_pair")
        return (r0, 8, "simple_continue")
    if streak == 2:
        return (r0, 9, "simple_momentum")
    if streak == 3:
        return (_opp(r0), 10, "simple_break_3")
    if streak >= 4:
        return (_opp(r0), 11, "simple_break_4plus")
    return None


# =====================================================================
# ★ HELPER v21 #1 — PHÂN TÍCH BỆT ĐA TẦNG
# =====================================================================
def analyze_bet_advanced(results, groups):
    signals = []
    if not groups or len(results) < 3:
        return signals
    r0 = results[0]
    g0 = groups[0]
    n = len(results)

    # LAYER 1: Bệt theo độ dài
    if   g0 >= 10: signals.append((_opp(r0), 38, "bet_10plus_break"))
    elif g0 >= 8:  signals.append((_opp(r0), 32, "bet_8_9_break"))
    elif g0 >= 6:  signals.append((_opp(r0), 25, "bet_6_7_break"))
    elif g0 == 5:  signals.append((_opp(r0), 18, "bet_5_break"))
    elif g0 == 4:  signals.append((_opp(r0), 12, "bet_4_break"))
    elif g0 == 3:
        if len(groups) >= 5:
            sample = groups[1:min(12, len(groups))]
            avg_g = sum(sample) / len(sample)
            if   avg_g < 2.3: signals.append((_opp(r0), 13, "bet_3_break_adaptive"))
            elif avg_g >= 3.5: signals.append((r0, 11, "bet_3_continue_adaptive"))
            else:             signals.append((_opp(r0), 9, "bet_3_break_default"))
        else:
            signals.append((_opp(r0), 9, "bet_3_break_default"))

    # LAYER 2: Bệt "nóng" — continuation khi bệt ngắn nhưng dày
    if n >= 15:
        last15 = results[:15]
        tai15 = last15.count("Tài")
        if tai15 >= 12 and r0 == "Tài" and g0 <= 5:
            signals.append(("Tài", 9, "bet_hot_continue_tai"))
        elif tai15 <= 3 and r0 == "Xỉu" and g0 <= 5:
            signals.append(("Xỉu", 9, "bet_hot_continue_xiu"))

    return signals


# =====================================================================
# ★ HELPER v21 #2 — CẦU KẸP (SANDWICH)
# =====================================================================
def analyze_sandwich(groups, results):
    signals = []
    if len(groups) < 3 or len(results) < 5:
        return signals
    r0 = results[0]

    if groups[0] == 1 and groups[2] == 1 and 1 <= groups[1] <= 6:
        w = 10 + min(groups[1], 5)
        signals.append((_opp(r0), w, f"sandwich_1_{groups[1]}_1"))

    if len(groups) >= 3 and groups[0] == 2 and groups[2] == 2 and 1 <= groups[1] <= 5:
        signals.append((_opp(r0), 13, f"sandwich_2_{groups[1]}_2"))

    if len(groups) >= 3 and groups[0] == 3 and groups[2] == 3 and 1 <= groups[1] <= 4:
        signals.append((_opp(r0), 14, f"sandwich_3_{groups[1]}_3"))

    if len(groups) >= 4 and groups[0] == 1 and groups[2] == 1 and groups[3] >= 2:
        signals.append((r0, 8, "sandwich_chain"))

    return signals


# =====================================================================
# ★ HELPER v21 #3 — CẦU CHU KỲ (CYCLE DETECTION)
# =====================================================================
def analyze_cycle(results):
    signals = []
    n = len(results)
    if n < 10:
        return signals

    for cycle_len in range(2, 6):
        if n < cycle_len * 3:
            continue
        seq = results[:cycle_len]
        matches = 0
        for i in range(cycle_len, min(n, cycle_len * 5)):
            if results[i] == seq[matches % cycle_len]:
                matches += 1
            else:
                break
        if matches >= cycle_len * 2.5:
            next_pred = seq[matches % cycle_len]
            w = 8 + min(int(matches * 0.8), 12)
            signals.append((next_pred, w, f"cycle_{cycle_len}"))
            break

    return signals


# =====================================================================
# ★★★ FULL BRIDGE ANALYZER v21 — 35+ SIGNALS ★★★
# =====================================================================
def analyze_full_bridge(results):
    if len(results) < 3: return []
    signals = []
    groups = get_groups(results)
    n = len(results)
    r0 = results[0]

    # 1. BỆT (nâng cấp)
    signals.extend(analyze_bet_advanced(results, groups))

    # 2. CẦU 1-1 (alternation)
    alt = _count_alternations(results)
    if   alt >= 8: signals.append((_opp(r0), 26, "1_1_extreme"))
    elif alt >= 6: signals.append((_opp(r0), 22, "1_1_strong"))
    elif alt >= 4: signals.append((_opp(r0), 16, "1_1"))
    elif alt >= 3: signals.append((_opp(r0), 10, "1_1_weak"))

    # 3. CẦU 2-2
    if   len(groups) >= 6 and all(g == 2 for g in groups[:6]):
        signals.append((_opp(r0), 22, "2_2_extreme"))
    elif len(groups) >= 5 and all(g == 2 for g in groups[:5]):
        signals.append((_opp(r0), 18, "2_2_strong"))
    elif len(groups) >= 4 and all(g == 2 for g in groups[:4]):
        signals.append((_opp(r0), 14, "2_2"))
    elif len(groups) >= 3 and all(g == 2 for g in groups[:3]):
        signals.append((_opp(r0), 9, "2_2_weak"))

    # 4. CẦU 3-3
    if   len(groups) >= 5 and all(g == 3 for g in groups[:5]):
        signals.append((_opp(r0), 18, "3_3_strong"))
    elif len(groups) >= 4 and all(g == 3 for g in groups[:4]):
        signals.append((_opp(r0), 15, "3_3"))
    elif len(groups) >= 3 and all(g == 3 for g in groups[:3]):
        signals.append((_opp(r0), 10, "3_3_weak"))

    # 5. CẦU 4-4 / 5-5 / 6-6
    for length in (6, 5, 4):
        if len(groups) >= 3 and all(g == length for g in groups[:3]):
            signals.append((_opp(r0), max(8, 15 - length), f"{length}_{length}"))
            break

    # 6. CẦU KẸP (sandwich)
    signals.extend(analyze_sandwich(groups, results))

    # 7. CẦU PYRAMID
    if len(groups) >= 5:
        if groups[:5] == [1, 2, 3, 2, 1]:
            signals.append((results[1], 13, "pyramid_12321"))
        elif groups[:5] == [2, 3, 4, 3, 2]:
            signals.append((results[1], 12, "pyramid_23432"))
        elif groups[:5] == [1, 2, 1, 2, 1]:
            signals.append((results[0], 11, "zigzag_12121"))

    # 8. CẦU TĂNG/GIẢM
    if len(groups) >= 3:
        if groups[:3] == [1, 2, 3]: signals.append((r0, 10, "inc_123"))
        if groups[:3] == [3, 2, 1]: signals.append((r0, 10, "dec_321"))
        if groups[:3] == [1, 3, 5]: signals.append((r0, 9,  "inc_135"))
        if groups[:3] == [2, 4, 6]: signals.append((r0, 9,  "inc_246"))

    # 9. CẦU 1-2-1 / 2-1-2
    if len(groups) >= 3 and groups[:3] == [1, 2, 1] and n >= 4:
        signals.append((results[1], 13, "1_2_1"))
    if len(groups) >= 3 and groups[:3] == [2, 1, 2] and n >= 5:
        signals.append((results[2], 13, "2_1_2"))

    # 10. CẦU 1-3-1 / 1-1-2 / 2-2-1
    if len(groups) >= 3 and groups[:3] == [1, 3, 1] and n >= 5:
        signals.append((results[1], 11, "1_3_1"))
    if len(groups) >= 3 and groups[:3] == [1, 1, 2] and n >= 5:
        signals.append((_opp(results[0]), 12, "1_1_2"))
    if len(groups) >= 3 and groups[:3] == [2, 2, 1] and n >= 6:
        signals.append((_opp(results[0]), 11, "2_2_1"))

    # 11. CẦU CHU KỲ (cycle)
    signals.extend(analyze_cycle(results))

    # 12. CẦU NGHIÊNG (tilt, multi-window)
    if n >= 15:
        for window in (15, 20, 30):
            if n < window: continue
            sample = results[:window]
            tr = sample.count("Tài") / len(sample)
            if   tr >= 0.73: signals.append(("Xỉu", 10, f"tilt_tai_{window}")); break
            elif tr <= 0.27: signals.append(("Tài", 10, f"tilt_xiu_{window}")); break

    # 13. CẦU LẶP (repetition)
    for win in range(3, min(n // 2, 12) + 1):
        if len(results) >= win * 2 and results[:win] == results[win:win*2]:
            if len(results) > win * 2:
                signals.append((results[win*2], 12, f"lap_{win}"))
                break

    # 14. MARKOV order 1
    if n >= 15:
        tr = {"Tài": {"Tài": 0, "Xỉu": 0}, "Xỉu": {"Tài": 0, "Xỉu": 0}}
        sample = results[:45]
        for i in range(len(sample) - 1):
            tr[sample[i+1]][sample[i]] += 1
        last = sample[0]
        tot = sum(tr[last].values())
        if tot >= 5:
            p = tr[last]["Tài"] / tot
            if   p >= 0.65: signals.append(("Tài", 10, "markov1"))
            elif p <= 0.35: signals.append(("Xỉu", 10, "markov1"))

    # 15. MARKOV order 2
    if n >= 20:
        target = tuple(results[:2])
        nt = nx = 0
        for i in range(2, min(n, 50)):
            if tuple(results[i:i+2]) == target:
                if results[i-1] == "Tài": nt += 1
                else: nx += 1
        tot = nt + nx
        if tot >= 3:
            if   nt / tot >= 0.68: signals.append(("Tài", 11, "markov2"))
            elif nx / tot >= 0.68: signals.append(("Xỉu", 11, "markov2"))

    # 16. BAYESIAN sequence
    if n >= 20:
        for slen in (5, 4, 3, 2):
            if n < slen + 3: continue
            target = tuple(results[:slen])
            nt = nx = 0
            for i in range(slen, min(n, 60)):
                if tuple(results[i:i+slen]) == target:
                    if results[i-1] == "Tài": nt += 1
                    else: nx += 1
            tot = nt + nx
            if tot >= 2:
                if nt / tot >= 0.7:
                    signals.append(("Tài", 12, f"bayes_{slen}")); break
                if nx / tot >= 0.7:
                    signals.append(("Xỉu", 12, f"bayes_{slen}")); break

    # 17. HISTORICAL GROUP PATTERN
    h = _detect_group_pattern(groups, results)
    if h: signals.append(h)

    # 18. HOT/COLD (multi-window)
    if n >= 12:
        for w, hi, lo in ((8, 7, 1), (12, 10, 2)):
            if n < w: continue
            sample = results[:w]
            tc = sample.count("Tài")
            if tc >= hi: signals.append(("Xỉu", 14 if w == 8 else 12, f"hot_tai_{w}"))
            elif tc <= lo: signals.append(("Tài", 14 if w == 8 else 12, f"hot_xiu_{w}"))

    # 19. MULTI-WINDOW CONSENSUS
    if n >= 15:
        w5  = results[:5].count("Tài")
        w10 = results[:10].count("Tài")
        w15 = results[:15].count("Tài")
        vt = sum([w5 >= 4, w10 >= 7, w15 >= 10])
        vx = sum([w5 <= 1, w10 <= 3, w15 <= 5])
        if   vt >= 2: signals.append(("Tài", 11, "multi_window"))
        elif vx >= 2: signals.append(("Xỉu", 11, "multi_window"))

    # 20. CHAOS ALTERNATION
    if n >= 15:
        sample = results[:15]
        trans = sum(1 for i in range(14) if sample[i] != sample[i+1])
        if trans >= 12:
            signals.append((_opp(results[0]), 13, "chaos_alt"))

    # 21. LOW ENTROPY
    if n >= 20:
        sample = results[:20]
        p_tai = sample.count("Tài") / len(sample)
        if p_tai in (0, 1):
            entropy = 0
        else:
            entropy = -(p_tai * math.log2(p_tai) + (1 - p_tai) * math.log2(1 - p_tai))
        if entropy < 0.6:
            signals.append(("Tài" if p_tai > 0.5 else "Xỉu", 9, "low_entropy"))

    # 22. OSCILLATION
    if n >= 10:
        window = results[:10]
        trans = sum(1 for i in range(9) if window[i] != window[i+1])
        if 4 <= trans <= 6:
            signals.append((_opp(results[0]), 7, "balanced_osc"))

    # 23. MOMENTUM
    if n >= 8 and groups[0] >= 2:
        w8 = results[:8].count("Tài")
        if   w8 >= 6: signals.append(("Tài", 8, "momentum"))
        elif w8 <= 2: signals.append(("Xỉu", 8, "momentum"))

    # 24. ZIGZAG mở rộng
    if len(groups) >= 5 and tuple(groups[:5]) in (
        (1,2,3,2,1), (1,2,3,2), (1,1,2,1,1), (2,1,1,2,2)
    ):
        signals.append((results[1], 10, "zigzag_ext"))

    # 25-27. BA THUẬT TOÁN PHỤ
    rnd = algo_random_weighted(results)
    if rnd: signals.append(rnd)
    nrnd = algo_non_random_deterministic(results)
    if nrnd: signals.append(nrnd)
    simple = algo_simple_enhanced(results)
    if simple: signals.append(simple)

    return signals


# =====================================================================
# BASE PREDICTOR (dùng cho lịch sử)
# =====================================================================
def full_bridge_predict(results):
    if not results: return "Tài", 50
    if len(results) < 3: return results[0], 50

    signals = analyze_full_bridge(results)
    if not signals:
        return results[0], 52

    score_tai = sum(w for p, w, _ in signals if p == "Tài")
    score_xiu = sum(w for p, w, _ in signals if p == "Xỉu")
    total = score_tai + score_xiu
    if total == 0:
        return results[0], 50

    def _calc(ratio):
        base = 50 + (ratio - 0.5) * 100
        evidence = min(1.0, total / 30.0)
        return int(max(50, min(92, 50 + (base - 50) * evidence)))

    if score_tai > score_xiu:
        return "Tài", _calc(score_tai / total)
    elif score_xiu > score_tai:
        return "Xỉu", _calc(score_xiu / total)
    else:
        return _opp(results[0]), 50


# =====================================================================
# ★★★ ADAPTIVE PREDICTOR v21 — TIME-DECAY + CONSENSUS BOOST ★★★
# =====================================================================
def full_bridge_predict_adaptive(results, replay_n=60):
    n = len(results)
    if n < 3:
        return (results[0] if results else "Tài"), 50, []

    # Replay có TIME-DECAY
    signal_stats = defaultdict(lambda: {'wins': 0.0, 'total': 0.0})
    replay_count = min(replay_n, n - 3)

    for j in range(replay_count):
        history = results[j+1:]
        actual = results[j]
        decay = 1.0 - (j / max(replay_count, 1)) * 0.5
        sigs = analyze_full_bridge(history)
        for pred_sig, weight, name in sigs:
            signal_stats[name]['total'] += decay
            if pred_sig == actual:
                signal_stats[name]['wins'] += decay

    signals = analyze_full_bridge(results)
    if not signals:
        return results[0], 52, []

    score_tai = 0.0
    score_xiu = 0.0
    detail = []

    for pred_sig, weight, name in signals:
        stats = signal_stats[name]
        if stats['total'] >= 3:
            acc = stats['wins'] / stats['total']
            multiplier = 0.3 + acc * 1.4
        else:
            acc = None
            multiplier = 1.0

        adjusted = weight * multiplier
        if pred_sig == "Tài": score_tai += adjusted
        else:                 score_xiu += adjusted

        detail.append({
            'name': name,
            'pred': pred_sig,
            'base_weight': weight,
            'accuracy': round(acc, 3) if acc is not None else None,
            'samples': int(stats['total']),
            'adjusted_weight': round(adjusted, 2),
        })

    total = score_tai + score_xiu
    if total == 0:
        return results[0], 50, detail

    if score_tai > score_xiu:
        pred, ratio = "Tài", score_tai / total
    elif score_xiu > score_tai:
        pred, ratio = "Xỉu", score_xiu / total
    else:
        return _opp(results[0]), 50, detail

    base_conf = 50 + (ratio - 0.5) * 100
    evidence = min(1.0, total / 40.0)
    conf = 50 + (base_conf - 50) * evidence

    # CONSENSUS BOOST
    if ratio >= 0.70:                        conf += 5
    if ratio >= 0.78 and len(signals) >= 6:  conf += 5
    if len(signals) >= 10 and ratio >= 0.65: conf += 3
    if len(signals) < 4:                     conf -= 5

    conf = int(max(50, min(96, conf)))
    return pred, conf, detail


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

        for row in raw_rows:
            HISTORY_CACHE[row['phien']] = row

        keys_to_remove = [k for k in HISTORY_CACHE if k <= RESET_ID]
        for k in keys_to_remove:
            del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])

        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0}})

        out = []
        correct_count = 0
        total_past = 0

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]

        next_pred, next_conf, _ = full_bridge_predict_adaptive(history_for_next)

        out.append({
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None,
            'conf': next_conf
        })

        scan_limit = min(len(valid), 200)

        for i in range(len(valid) - 1, len(valid) - scan_limit - 1, -1):
            if i < 0: break
            current_session = valid[i]
            hist = [v['result'] for v in valid[:i]][::-1]

            if hist and len(hist) >= 3:
                pred, conf = full_bridge_predict(hist)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct:
                    correct_count += 1
            else:
                pred, conf = "-", 50
                is_correct = None

            out.append({
                'phien': current_session['phien'],
                'is_next': False,
                'prediction': pred,
                'result': current_session['result'],
                'dice': current_session['dice'],
                'is_correct': is_correct,
                'conf': conf
            })

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count}
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

        for row in raw_rows:
            HISTORY_CACHE[row['phien']] = row

        keys_to_remove = [k for k in HISTORY_CACHE if k <= RESET_ID]
        for k in keys_to_remove:
            del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'}), 400

        results = [v['result'] for v in valid][::-1]
        pred, conf, detail = full_bridge_predict_adaptive(results)

        return jsonify({
            'last_phien': valid[-1]['phien'],
            'next_phien': valid[-1]['phien'] + 1,
            'last_result': valid[-1]['result'],
            'last_dice': valid[-1]['dice'],
            'prediction': pred,
            'confidence': conf,
            'total_sessions': len(valid),
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

        for row in raw_rows:
            HISTORY_CACHE[row['phien']] = row

        keys_to_remove = [k for k in HISTORY_CACHE if k <= RESET_ID]
        for k in keys_to_remove:
            del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'}), 400

        results = [v['result'] for v in valid][::-1]
        pred, conf, detail = full_bridge_predict_adaptive(results)

        tai_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài')
        xiu_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu')
        total_sig = tai_score + xiu_score
        if total_sig > 0:
            ratio = max(tai_score, xiu_score) / total_sig
            base_conf = 50 + (ratio - 0.5) * 100
            evidence = min(1.0, total_sig / 40.0)
            conf_float = max(50.0, min(96.0, 50 + (base_conf - 50) * evidence))
        else:
            conf_float = 50.0
        conf_str = f"{conf_float:.1f}".replace(".", ",") + "%"

        groups = get_groups(results)
        recent_groups = groups[:4]
        lich_su = "-" + "-".join(str(g) for g in recent_groups)

        last = valid[-1]
        next_phien = last['phien'] + 1

        return jsonify({
            'Id':         'le minh v21',
            'Phien':      str(next_phien),
            'Ket_qua':    last['result'].lower(),
            'Lich_su':    lich_su,
            'Du_doan':    pred,
            'Do_tin_cay': conf_str,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE
    try:
        raw_rows, success = fetch_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {}
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng, không thể xác nhận mốc Reset'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
