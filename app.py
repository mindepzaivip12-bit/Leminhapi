import os
import math
import hashlib
import traceback
import threading
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
NEXT_PREDICTION_CACHE = {}
MAX_PREDICTION_CACHE = 2000
RESET_ID = 0
MAX_CONFIDENCE = 90

LEARNED_PHIEN = 0
LEARN_LOCK = threading.Lock()

HASH_DEEP_DB = {
    13: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    10: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    7:  defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    5:  defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
}
MD5_BIT_DB = {bit: {"Tài": 0, "Xỉu": 0} for bit in range(128)}
MD5_NGRAM_DB = {
    2: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    3: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    4: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
}
MD5_HAMMING_DB = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
LOSS_HISTORY = deque(maxlen=20)

# ==== HTML + CSS (GIỮ NGUYÊN) ====
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
    <div class="header-title">LE MINH <span>MD5</span></div>
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
            <thead><tr><th>Phiên</th><th>Dự đoán</th><th>Kết quả</th><th>Trạng thái</th></tr></thead>
            <tbody id="table-body"><tr><td colspan="4" class="loading">Đang kết nối Server...</td></tr></tbody>
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
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="4" class="loading">Không có dữ liệu. Hãy đợi phiên mới.</td></tr>'; return; }
    let html = '';
    rows.forEach((row) => {
        let trClass = '';
        if (row.is_next) trClass = row.recovery_flipped ? 'class="row-next recovery"' : 'class="row-next"';
        let predHtml = `<span class="badge badge-empty">-</span>`;
        if (row.prediction === "Tài") predHtml = `<span class="badge badge-tai">TÀI</span>`;
        if (row.prediction === "Xỉu") predHtml = `<span class="badge badge-xiu">XỈU</span>`;
        let recBadge = "";
        if (row.recovery_flipped) { recBadge = `<span class="recovery-badge" title="Auto-flip do thua ${row.loss_streak || 0} lần">⚡</span>`; }
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
            statusHtml = row.recovery_flipped ? `<span class="status st-recover">⚡ Đảo chiều</span>` : `<span class="status st-wait">Chờ kết quả</span>`;
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
# CÁC HÀM XỬ LÝ CƠ BẢN
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

def encode_tx(results, length):
    if not results or len(results) < length: return None
    return "".join("T" if r == "Tài" else "X" for r in results[:length])

def hash_deep_md5(tx_string, depth_level=2):
    if not tx_string: return None
    salted = f"leminh_deep_{depth_level}|{tx_string}"
    h = hashlib.md5(salted.encode('utf-8')).hexdigest()
    for _ in range(depth_level - 1):
        h = hashlib.md5(f"{h}|salt_{depth_level}".encode('utf-8')).hexdigest()
    return h

def hash_to_bits(hash_hex):
    if not hash_hex: return []
    bits = []
    for c in hash_hex:
        v = int(c, 16)
        for shift in (3, 2, 1, 0):
            bits.append((v >> shift) & 1)
    return bits

def hamming_distance(h1, h2):
    if not h1 or not h2 or len(h1) != len(h2): return 0
    return sum(a != b for a, b in zip(hash_to_bits(h1), hash_to_bits(h2)))

def learn_incremental(valid):
    global LEARNED_PHIEN
    if not valid: return
    with LEARN_LOCK:
        new_indices = [idx for idx, v in enumerate(valid) if v['phien'] > LEARNED_PHIEN]
        if not new_indices: return
        n = len(valid)
        for depth in (5, 7, 10, 13):
            if n <= depth: continue
            db = HASH_DEEP_DB[depth]
            for idx in new_indices:
                if idx < depth: continue
                history = [v['result'] for v in valid[idx-depth:idx]][::-1]
                tx = encode_tx(history, depth)
                if not tx: continue
                h = hash_deep_md5(tx, depth_level=2)
                if not h: continue
                db[h][valid[idx]['result']] += 1
        if n >= 14:
            hash_cache = {}
            for idx in new_indices:
                if idx < 13: continue
                history = [v['result'] for v in valid[idx-13:idx]][::-1]
                tx = encode_tx(history, 13)
                if not tx: continue
                h = hash_deep_md5(tx, depth_level=2)
                if not h: continue
                hash_cache[idx] = h
                bits = hash_to_bits(h)
                for bit_idx in range(128):
                    if bit_idx < len(bits) and bits[bit_idx] == 1:
                        MD5_BIT_DB[bit_idx][valid[idx]['result']] += 1
                for ng_size in (2, 3, 4):
                    for start in range(0, len(h) - ng_size + 1):
                        gram = h[start:start + ng_size]
                        MD5_NGRAM_DB[ng_size][gram][valid[idx]['result']] += 1
            for idx in new_indices:
                if idx < 14 or idx not in hash_cache: continue
                prev_idx = idx - 1
                if prev_idx in hash_cache:
                    h_prev = hash_cache[prev_idx]
                else:
                    if prev_idx < 13: continue
                    ph = [v['result'] for v in valid[prev_idx-13:prev_idx]][::-1]
                    ptx = encode_tx(ph, 13)
                    if not ptx: continue
                    h_prev = hash_deep_md5(ptx, depth_level=2)
                    if not h_prev: continue
                hd = hamming_distance(hash_cache[idx], h_prev)
                MD5_HAMMING_DB[hd // 8][valid[idx]['result']] += 1
        LEARNED_PHIEN = valid[-1]['phien']

# =====================================================================
# MODULE 6P
# =====================================================================
def classify_6p_pattern(results):
    n = len(results)
    if n < 6: return None
    last6 = results[:6]
    last5 = results[:5]
    alt_count = sum(1 for i in range(5) if last6[i] != last6[i+1])

    if alt_count == 5:
        tai_next = xiu_next = 0
        key6 = tuple(last6)
        for i in range(min(n - 6, 60)):
            if tuple(results[i:i+6]) == key6:
                if results[i+6] == "Tài": tai_next += 1
                else: xiu_next += 1
        total_seen = tai_next + xiu_next
        if total_seen >= 3:
            p_tai = (tai_next + 1) / (total_seen + 2)
            if p_tai >= 0.68:
                return {'type': 'Đảo', 'pred': 'Tài',
                        'weight': min(18, 12 + (p_tai - 0.5) * 20),
                        'reason': f'dao_6p_dataT_{total_seen}'}
            elif p_tai <= 0.32:
                return {'type': 'Đảo', 'pred': 'Xỉu',
                        'weight': min(18, 12 + (0.5 - p_tai) * 20),
                        'reason': f'dao_6p_dataX_{total_seen}'}
        return {'type': 'Đảo', 'pred': _opp(last6[0]), 'weight': 13,
                'reason': 'dao_6p_lythuyet'}

    if alt_count == 0:
        current = last6[0]
        cont = brk = 0
        for i in range(min(n - 6, 60)):
            if all(results[i+j] == current for j in range(6)):
                if i + 6 < n:
                    if results[i+6] == current: cont += 1
                    else: brk += 1
        total = cont + brk
        if total >= 3:
            p_cont = (cont + 1) / (total + 2)
            if p_cont >= 0.60:
                return {'type': 'Thuận', 'pred': current,
                        'weight': min(17, 12 + (p_cont - 0.5) * 18),
                        'reason': f'thuan_6p_cont_{total}'}
            elif p_cont <= 0.40:
                return {'type': 'Thuận_break', 'pred': _opp(current),
                        'weight': min(17, 12 + (0.5 - p_cont) * 18),
                        'reason': f'thuan_6p_break_{total}'}
        return {'type': 'Thuận', 'pred': current, 'weight': 12,
                'reason': 'thuan_6p_lythuyet'}

    groups = get_groups(last6)
    if len(groups) == 3 and all(g == 2 for g in groups):
        return {'type': '1-1', 'pred': last6[0], 'weight': 15,
                'reason': 'zigzag_2_2_2'}
    if len(groups) == 2 and groups[0] == 2 and groups[1] == 4:
        return {'type': '1-1', 'pred': _opp(last6[0]), 'weight': 14,
                'reason': 'zigzag_2_4'}
    if len(groups) == 2 and groups[0] == 4 and groups[1] == 2:
        return {'type': '1-1', 'pred': _opp(last6[0]), 'weight': 13,
                'reason': 'zigzag_4_2'}
    if len(groups) == 2 and groups[0] == 3 and groups[1] == 3:
        return {'type': '1-1', 'pred': _opp(last6[0]), 'weight': 14,
                'reason': 'zigzag_3_3'}

    alt5 = sum(1 for i in range(4) if last5[i] != last5[i+1])
    if alt5 == 4:
        key5 = tuple(last5)
        tai_next = xiu_next = 0
        for i in range(min(n - 5, 50)):
            if tuple(results[i:i+5]) == key5:
                if results[i+5] == "Tài": tai_next += 1
                else: xiu_next += 1
        total_seen = tai_next + xiu_next
        if total_seen >= 3:
            p_tai = (tai_next + 1) / (total_seen + 2)
            if p_tai >= 0.65:
                return {'type': 'Nghịch', 'pred': 'Tài',
                        'weight': min(18, 12 + (p_tai - 0.5) * 20),
                        'reason': f'nghich_dataT_{total_seen}'}
            elif p_tai <= 0.35:
                return {'type': 'Nghịch', 'pred': 'Xỉu',
                        'weight': min(18, 12 + (0.5 - p_tai) * 20),
                        'reason': f'nghich_dataX_{total_seen}'}
        return {'type': 'Nghịch', 'pred': _opp(last5[0]), 'weight': 14,
                'reason': 'nghich_5p_lythuyet'}

    streak = _count_streak(results)
    if 3 <= streak <= 4 and len(results) > streak:
        current = results[0]
        breaks = totals = 0
        i = 0
        while i < n - 1 and totals < 30:
            j = i; cnt = 1
            while j + 1 < n and results[j] == results[j+1]:
                cnt += 1; j += 1
            if cnt >= streak:
                totals += 1
                if j + 1 < n and results[j+1] != results[i]:
                    breaks += 1
            i = j + 1
        if totals >= 4:
            p_break = (breaks + 1) / (totals + 2)
            if p_break >= 0.62:
                return {'type': 'Nghịch', 'pred': _opp(current),
                        'weight': min(16, 12 + (p_break - 0.5) * 18),
                        'reason': f'nghich_streak{streak}_break'}
            elif p_break <= 0.38:
                return {'type': 'Thuận', 'pred': current, 'weight': 14,
                        'reason': f'thuan_streak{streak}_cont'}
    return None


def algo_6p_balanced(results):
    info = classify_6p_pattern(results)
    if not info: return None
    return (info['pred'], info['weight'], info['reason'])

# =====================================================================
# CÁC THUẬT TOÁN KHÁC (giữ nguyên)
# =====================================================================
def algo_lc79_specialist(results):
    n = len(results)
    if n < 20: return None
    if n >= 9:
        block1 = results[0:3]; block2 = results[3:6]; block3 = results[6:9]
        t1 = block1.count("Tài"); t2 = block2.count("Tài"); t3 = block3.count("Tài")
        pattern = (t1, t2, t3)
        matches_tai = matches_xiu = 0
        for i in range(min(n - 9, 50)):
            b1 = results[i:i+3].count("Tài")
            b2 = results[i+3:i+6].count("Tài")
            b3 = results[i+6:i+9].count("Tài")
            if (b1, b2, b3) == pattern:
                if results[i+9] == "Tài": matches_tai += 1
                else: matches_xiu += 1
        total_match = matches_tai + matches_xiu
        if total_match >= 3:
            p_tai = (matches_tai + 1) / (total_match + 2)
            z = (p_tai - 0.5) / math.sqrt(0.25 / (total_match + 2))
            if abs(z) >= 1.2:
                pred = "Tài" if p_tai > 0.5 else "Xỉu"
                weight = min(27, 16 + abs(z) * 4)
                return (pred, weight, f"lc79_matrix_3x3_{t1}{t2}{t3}")
    groups = get_groups(results[:10])
    if len(groups) >= 2:
        if groups[0] == 1 and groups[1] >= 3:
            hist_count = 0; tai_next = xiu_next = 0
            for i in range(min(n - groups[1] - 1, 60)):
                if results[i] != results[i+1]:
                    seg_start = i + 1; seg_len = 1
                    while seg_start + seg_len < n and results[seg_start] == results[seg_start + seg_len]:
                        seg_len += 1
                    if seg_len >= 3 and seg_start + seg_len < n:
                        hist_count += 1
                        if results[seg_start + seg_len] == "Tài": tai_next += 1
                        else: xiu_next += 1
            if hist_count >= 3:
                p_tai = (tai_next + 1) / (tai_next + xiu_next + 2)
                pred = "Tài" if p_tai > 0.5 else "Xỉu"
                return (pred, 22, "lc79_break_pattern")
    groups5 = get_groups(results[:5])
    if len(groups5) == 3 and (groups5[0] == 1 and groups5[1] == 2 and groups5[2] == 1) or \
       (len(groups5) == 3 and groups5[0] == 2 and groups5[1] == 1 and groups5[2] == 2):
        return (results[0], 20, "lc79_zigzag_121")
    return None

def algo_7p_pattern_radar(results):
    n = len(results)
    if n < 15: return None
    last7 = results[:7]; groups = get_groups(last7)
    alt = sum(1 for i in range(6) if last7[i] != last7[i+1])
    if alt >= 5:
        key7 = tuple(last7); tai_next = xiu_next = 0
        for i in range(min(n - 7, 60)):
            if tuple(results[i:i+7]) == key7:
                if results[i+7] == "Tài": tai_next += 1
                else: xiu_next += 1
        if (tai_next + xiu_next) >= 2:
            p_tai = (tai_next + 1) / (tai_next + xiu_next + 2)
            pred = "Tài" if p_tai > 0.5 else "Xỉu"
            return (pred, 22, "7p_radar_dao_1_1")
    if len(groups) == 1 and groups[0] >= 6:
        streak = groups[0]; current = last7[0]; breaks = totals = 0
        for i in range(min(n - streak, 60)):
            if all(results[i+j] == current for j in range(streak)):
                totals += 1
                if i + streak < n and results[i+streak] != current: breaks += 1
        if totals >= 3:
            p_break = (breaks + 1) / (totals + 2)
            if p_break >= 0.60: return (_opp(current), 22, f"7p_radar_thuan_break_{streak}")
            else: return (current, 18, f"7p_radar_thuan_{streak}")
    if len(groups) >= 2 and groups[0] == 1 and groups[1] >= 3: return (last7[0], 20, "7p_radar_nghich")
    if len(groups) >= 3 and groups[0] == 2 and groups[1] == 2 and groups[2] == 2: return (last7[0], 20, "7p_radar_2_2")
    return None

def algo_7p_no_reverse(results):
    n = len(results)
    if n < 15: return None
    last7 = results[:7]
    alternations = sum(1 for i in range(6) if last7[i] != last7[i+1])
    if alternations <= 3:
        key7 = tuple(last7); tai_next = xiu_next = 0
        for i in range(min(n - 7, 60)):
            if tuple(results[i:i+7]) == key7:
                if results[i+7] == "Tài": tai_next += 1
                else: xiu_next += 1
        total_seen = tai_next + xiu_next
        if total_seen >= 3:
            p_tai = (tai_next + 1) / (total_seen + 2)
            z = (p_tai - 0.5) / math.sqrt(0.25 / (total_seen + 2))
            if abs(z) >= 1.0:
                pred = "Tài" if p_tai > 0.5 else "Xỉu"
                return (pred, min(22, 13 + abs(z) * 4), f"7p_no_reverse_{alternations}alt")
        groups = get_groups(results[:7])
        if len(groups) >= 2:
            if groups[0] < groups[1]: return (last7[0], 15, "7p_no_reverse_extend")
            else: return (_opp(last7[0]), 13, "7p_no_reverse_wait")
    return None

def algo_7p_hash_deep(results):
    n = len(results)
    if n < 15: return None
    tx = encode_tx(results, 7)
    if not tx: return None
    h = hash_deep_md5(tx, depth_level=3)
    if not h or h not in HASH_DEEP_DB[7]: return None
    counts = HASH_DEEP_DB[7][h]; total = counts["Tài"] + counts["Xỉu"]
    if total < 3: return None
    p_tai = (counts["Tài"] + 1) / (total + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
    if abs(z) < 1.1: return None
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    return (pred, min(22, 12 + abs(z) * 4), f"7p_hash_deep_{total}")

def algo_stable_zone_10p(results):
    n = len(results)
    if n < 20: return None
    last10 = results[:10]
    noise = sum(1 for i in range(9) if last10[i] != last10[i+1])
    if noise < 2 or noise > 6: return None
    key10 = tuple(last10); tai_next = xiu_next = 0
    for i in range(min(n - 10, 80)):
        if tuple(results[i:i+10]) == key10:
            if results[i+10] == "Tài": tai_next += 1
            else: xiu_next += 1
    total_seen = tai_next + xiu_next
    if total_seen >= 2:
        p_tai = (tai_next + 1) / (total_seen + 2)
        z = (p_tai - 0.5) / math.sqrt(0.25 / (total_seen + 2))
        if abs(z) >= 0.9:
            pred = "Tài" if p_tai > 0.5 else "Xỉu"
            return (pred, min(24, 14 + abs(z) * 4), "stable_zone_10p")
    groups = get_groups(last10)
    if len(groups) >= 2:
        if groups[0] < groups[1]: return (last10[0], 15, "stable_zone_extend")
        else: return (_opp(last10[0]), 14, "stable_zone_break")
    return None

def algo_consensus_filter(results, current_signals):
    if not current_signals: return None
    tai_score = sum(w for p, w, n in current_signals if p == "Tài")
    xiu_score = sum(w for p, w, n in current_signals if p == "Xỉu")
    total = tai_score + xiu_score
    if total == 0: return None
    ratio = max(tai_score, xiu_score) / total
    if ratio < 0.55: return None
    pred = "Tài" if tai_score > xiu_score else "Xỉu"
    return (pred, min(14, 9 + (ratio - 0.5) * 28), f"consensus_{int(ratio*100)}pct")

def algo_hash_deep_5p(results):
    tx = encode_tx(results, 5)
    if not tx: return None
    h = hash_deep_md5(tx, depth_level=3)
    if not h or h not in HASH_DEEP_DB[5]: return None
    counts = HASH_DEEP_DB[5][h]; total = counts["Tài"] + counts["Xỉu"]
    if total < 3: return None
    p_tai = (counts["Tài"] + 1) / (total + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
    if abs(z) < 0.9: return None
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    return (pred, min(24, 13 + abs(z) * 4), f"hash_deep_5p_{total}")

def algo_hash_deep_10p(results):
    tx = encode_tx(results, 10)
    if not tx: return None
    h = hash_deep_md5(tx, depth_level=3)
    if not h or h not in HASH_DEEP_DB[10]: return None
    counts = HASH_DEEP_DB[10][h]; total = counts["Tài"] + counts["Xỉu"]
    if total < 3: return None
    p_tai = (counts["Tài"] + 1) / (total + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
    if abs(z) < 1.0: return None
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    return (pred, min(23, 13 + abs(z) * 4), f"hash_deep_10p_{total}")

def algo_hash_deep_13p(results):
    tx = encode_tx(results, 13)
    if not tx: return None
    h = hash_deep_md5(tx, depth_level=2)
    if not h or h not in HASH_DEEP_DB[13]: return None
    counts = HASH_DEEP_DB[13][h]; total = counts["Tài"] + counts["Xỉu"]
    if total < 3: return None
    p_tai = (counts["Tài"] + 1) / (total + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
    if abs(z) < 1.0: return None
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    return (pred, min(22, 12 + abs(z) * 4), f"hash_deep_13p_{total}")

def algo_hash_deep_multi(results):
    combined = {"Tài": 0.0, "Xỉu": 0.0}; total_samples = 0
    for depth, wf in ((13, 1.0), (10, 0.75), (7, 0.55), (5, 0.9)):
        tx = encode_tx(results, depth)
        if not tx: continue
        h = hash_deep_md5(tx, depth_level=2 if depth >= 7 else 3)
        if not h or h not in HASH_DEEP_DB[depth]: continue
        counts = HASH_DEEP_DB[depth][h]; total = counts["Tài"] + counts["Xỉu"]
        if total < 2: continue
        p_tai = (counts["Tài"] + 1) / (total + 2)
        z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
        pred = "Tài" if p_tai > 0.5 else "Xỉu"
        combined[pred] += min(18, 8 + abs(z) * 3.5) * wf; total_samples += total
    if total_samples < 4: return None
    st, sx = combined["Tài"], combined["Xỉu"]
    if st == sx: return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    if ratio < 0.56: return None
    return (pred, min(20, 10 + (ratio - 0.5) * 30), f"hash_deep_multi_{total_samples}")

def algo_md5_bit_analysis(results):
    if len(results) < 13: return None
    tx = encode_tx(results, 13)
    if not tx: return None
    h = hash_deep_md5(tx, depth_level=2)
    if not h: return None
    bits = hash_to_bits(h)
    if len(bits) < 128: return None
    st = sx = 0.0; total_active = 0
    for bit_idx in range(128):
        if bits[bit_idx] != 1: continue
        cnt = MD5_BIT_DB[bit_idx]; total = cnt["Tài"] + cnt["Xỉu"]
        if total < 5: continue
        p_tai = (cnt["Tài"] + 1) / (total + 2)
        z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
        if abs(z) < 0.8: continue
        w = abs(z) * 2
        if p_tai > 0.5: st += w
        else: sx += w
        total_active += 1
    if total_active < 5 or st == sx: return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    if ratio < 0.58: return None
    return (pred, min(20, 10 + (ratio - 0.5) * 35), f"md5_bit_{total_active}")

def algo_md5_ngram(results):
    if len(results) < 13: return None
    tx = encode_tx(results, 13)
    if not tx: return None
    h = hash_deep_md5(tx, depth_level=2)
    if not h: return None
    st = sx = 0.0; total_grams = 0
    for ng_size, wf in ((2, 0.5), (3, 1.0), (4, 1.5)):
        db = MD5_NGRAM_DB[ng_size]
        for start in range(0, len(h) - ng_size + 1):
            gram = h[start:start + ng_size]
            if gram not in db: continue
            cnt = db[gram]; total = cnt["Tài"] + cnt["Xỉu"]
            if total < 3: continue
            p_tai = (cnt["Tài"] + 1) / (total + 2)
            z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
            if abs(z) < 1.0: continue
            w = abs(z) * 2 * wf
            if p_tai > 0.5: st += w
            else: sx += w
            total_grams += 1
    if total_grams < 8 or st == sx: return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    if ratio < 0.58: return None
    return (pred, min(19, 10 + (ratio - 0.5) * 30), f"md5_ngram_{total_grams}")

def algo_md5_hamming(results):
    if len(results) < 15: return None
    tx_now = encode_tx(results, 13)
    tx_prev = encode_tx(results[1:], 13) if len(results) > 14 else None
    if not tx_now or not tx_prev: return None
    h_now = hash_deep_md5(tx_now, depth_level=2)
    h_prev = hash_deep_md5(tx_prev, depth_level=2)
    if not h_now or not h_prev: return None
    hd = hamming_distance(h_now, h_prev); bin_key = hd // 8
    if bin_key not in MD5_HAMMING_DB: return None
    cnt = MD5_HAMMING_DB[bin_key]; total = cnt["Tài"] + cnt["Xỉu"]
    if total < 4: return None
    p_tai = (cnt["Tài"] + 1) / (total + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
    if abs(z) < 1.2: return None
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    return (pred, min(18, 10 + abs(z) * 3), f"md5_hamming_{hd}")

def algo_5p_alternation(results):
    n = len(results)
    if n < 10: return None
    last5 = results[:5]
    alt_count = sum(1 for i in range(4) if last5[i] != last5[i+1])
    if alt_count == 4:
        tai_next = xiu_next = 0; key5 = tuple(last5)
        for i in range(min(n - 5, 50)):
            if tuple(results[i:i+5]) == key5:
                if results[i+5] == "Tài": tai_next += 1
                else: xiu_next += 1
        total_seen = tai_next + xiu_next
        if total_seen >= 3:
            p_tai = (tai_next + 1) / (total_seen + 2)
            if p_tai >= 0.62: return ("Tài", min(20, 12 + (p_tai - 0.5) * 22), "5p_alt_data_T")
            elif p_tai <= 0.38: return ("Xỉu", min(20, 12 + (0.5 - p_tai) * 22), "5p_alt_data_X")
        return (_opp(last5[0]), 16, "5p_alt_continue")
    if alt_count == 3:
        tai_next = xiu_next = 0; key5 = tuple(last5)
        for i in range(min(n - 5, 50)):
            if tuple(results[i:i+5]) == key5:
                if results[i+5] == "Tài": tai_next += 1
                else: xiu_next += 1
        total_seen = tai_next + xiu_next
        if total_seen >= 3:
            p_tai = (tai_next + 1) / (total_seen + 2)
            if p_tai >= 0.62: return ("Tài", min(18, 11 + (p_tai - 0.5) * 20), "5p_alt_reverse_data_T")
            elif p_tai <= 0.38: return ("Xỉu", min(18, 11 + (0.5 - p_tai) * 20), "5p_alt_reverse_data_X")
        return (_opp(last5[0]), 13, "5p_alt_reverse")
    return None

def algo_trend_break(results):
    n = len(results)
    if n < 20: return None
    window = list(reversed(results[:20]))
    b = [1 if r == "Tài" else 0 for r in window]
    x_mean = 9.5; y_mean = sum(b) / 20
    num = sum((i - x_mean) * (b[i] - y_mean) for i in range(20))
    den = sum((i - x_mean) ** 2 for i in range(20))
    slope = num / den if den else 0; last3 = b[-3:]
    if slope > 0.04:
        if sum(last3) <= 1: return ("Tài", min(18, 11 + abs(slope) * 28), "trend_bounce_T")
    elif slope < -0.04:
        if sum(last3) >= 2: return ("Xỉu", min(18, 11 + abs(slope) * 28), "trend_bounce_X")
    if abs(slope) > 0.08:
        last_dir = "Tài" if sum(last3) >= 2 else "Xỉu"
        if (slope > 0 and last_dir == "Tài") or (slope < 0 and last_dir == "Xỉu"):
            return (last_dir, min(16, 11 + abs(slope) * 22), "trend_continue")
    return None

def algo_break_rhythm(results):
    n = len(results)
    if n < 12: return None
    last8 = results[:8]
    alt_count = sum(1 for i in range(7) if last8[i] != last8[i+1])
    if 5 <= alt_count <= 6: return (_opp(last8[0]), 14, "break_rhythm_alt")
    if alt_count <= 2: return (last8[0], 13, "break_rhythm_streak")
    return None

def data_markov2(results):
    n = len(results)
    if n < 20: return None
    key = (results[1], results[0]); counts = {"Tài": 1, "Xỉu": 1}
    for i in range(min(n - 2, 60)):
        if (results[i+2], results[i+1]) == key: counts[results[i]] += 1
    total = counts["Tài"] + counts["Xỉu"]
    if total < 6: return None
    p_tai = counts["Tài"] / total
    z = (p_tai - 0.5) / math.sqrt(0.25 / total)
    if abs(z) < 1.2: return None
    return ("Tài" if p_tai > 0.5 else "Xỉu", min(18, 9 + abs(z) * 3), "markov2_data")

def data_markov3(results):
    n = len(results)
    if n < 30: return None
    key = (results[2], results[1], results[0]); counts = {"Tài": 1, "Xỉu": 1}
    for i in range(min(n - 3, 80)):
        if (results[i+3], results[i+2], results[i+1]) == key: counts[results[i]] += 1
    total = counts["Tài"] + counts["Xỉu"]
    if total < 5: return None
    p_tai = counts["Tài"] / total
    z = (p_tai - 0.5) / math.sqrt(0.25 / total)
    if abs(z) < 1.3: return None
    return ("Tài" if p_tai > 0.5 else "Xỉu", min(20, 10 + abs(z) * 3), "markov3_data")

def data_pattern3(results):
    n = len(results)
    if n < 25: return None
    key = tuple(results[:3]); tai_next = xiu_next = 0
    for i in range(min(n - 3, 60)):
        if tuple(results[i:i+3]) == key:
            if results[i+3] == "Tài": tai_next += 1
            else: xiu_next += 1
    tot = tai_next + xiu_next
    if tot < 4: return None
    p = (tai_next + 1) / (tot + 2)
    if p >= 0.68: return ("Tài", min(17, 10 + (p - 0.5) * 20), "pattern3_data")
    if p <= 0.32: return ("Xỉu", min(17, 10 + (0.5 - p) * 20), "pattern3_data")
    return None

def data_alternation(results):
    n = len(results)
    if n < 4: return None
    alt = _count_alternations(results)
    if alt >= 8: return (_opp(results[0]), 20, "alt_8plus")
    if alt >= 6: return (_opp(results[0]), 17, "alt_6_7")
    if alt >= 4: return (_opp(results[0]), 13, "alt_4_5")
    if alt >= 3: return (_opp(results[0]), 9, "alt_3")
    return None

def data_streak_break(results):
    n = len(results)
    if n < 25: return None
    streak = _count_streak(results)
    if streak < 3: return None
    current = results[0]; breaks = totals = 0; i = 0
    while i < n - 1:
        j = i; cnt = 1
        while j + 1 < n and results[j] == results[j+1]: cnt += 1; j += 1
        if cnt >= streak and results[i] == current:
            totals += 1
            if j + 1 < n and results[j+1] != current: breaks += 1
        i = j + 1
    if totals < 4: return None
    p_break = (breaks + 1) / (totals + 2)
    if p_break >= 0.65: return (_opp(current), min(17, 10 + (p_break - 0.5) * 20), "streak_break_data")
    if p_break <= 0.35: return (current, min(14, 9 + (0.5 - p_break) * 15), "streak_continue_data")
    return None

def data_bayes_ratio(results):
    n = len(results)
    if n < 15: return None
    window = results[:min(30, n)]
    tai = window.count("Tài"); xiu = len(window) - tai
    alpha = 10 + tai; beta = 10 + xiu
    p_tai = alpha / (alpha + beta)
    var = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
    std = math.sqrt(var) if var > 0 else 0
    z = abs((p_tai - 0.5) / std) if std else 0
    if z < 1.5: return None
    return ("Tài" if p_tai > 0.5 else "Xỉu", min(15, 9 + z * 2), "bayes_data")

def data_tilt(results):
    n = len(results)
    if n < 12: return None
    for w, hi, lo, wgt in ((8, 7, 1, 14), (12, 10, 2, 12)):
        if n < w: continue
        tc = results[:w].count("Tài")
        if tc >= hi: return ("Xỉu", wgt, f"tilt_tai_{w}")
        if tc <= lo: return ("Tài", wgt, f"tilt_xiu_{w}")
    return None

def data_periodicity(results):
    n = len(results)
    if n < 24: return None
    best_period, best_score = 0, 0.0
    for period in range(2, min(12, n // 2)):
        matches = total = 0
        for i in range(period, min(n, period + 20)):
            total += 1
            if results[i] == results[i - period]: matches += 1
        if total >= 10:
            score = matches / total
            if score > best_score: best_score, best_period = score, period
    if best_period and best_score >= 0.72:
        pred = results[best_period - 1]
        return (pred, min(20, 12 + (best_score - 0.5) * 22), f"periodicity_p{best_period}")
    return None

def data_volatility_break(results):
    n = len(results)
    if n < 15: return None
    window = results[:12]
    changes = sum(1 for i in range(11) if window[i] != window[i+1])
    if changes <= 2: return (_opp(results[0]), 16, "volatility_low_break")
    if changes >= 9: return (results[0], 14, "volatility_high_continue")
    return None

def data_entropy_bias(results):
    n = len(results)
    if n < 15: return None
    window = results[:20]
    p_tai = (window.count("Tài") + 1) / (len(window) + 2); p_xiu = 1 - p_tai
    if p_tai <= 0 or p_xiu <= 0: return None
    entropy = -(p_tai * math.log2(p_tai) + p_xiu * math.log2(p_xiu))
    if entropy < 0.75: return ("Tài" if p_tai > 0.5 else "Xỉu", 14, f"entropy_{entropy:.2f}")
    return None

def data_cusum(results):
    n = len(results)
    if n < 20: return None
    window = list(reversed(results[:20])); s_pos = s_neg = 0.0; target = 0.5
    for r in window:
        x = 1 if r == "Tài" else 0
        s_pos = max(0, s_pos + (x - target))
        s_neg = max(0, s_neg + (target - x))
    if s_pos > 3.5: return ("Xỉu", 15, "cusum_T_bias")
    if s_neg > 3.5: return ("Tài", 15, "cusum_X_bias")
    return None

def algo_pair_pattern(results):
    n = len(results)
    if n < 8: return None
    groups = get_groups(results)
    if len(groups) < 3: return None
    last3 = groups[:3]
    if last3 == [2, 2, 2]: return (results[0], 16, "pattern_2_2_2")
    if last3 == [3, 3, 3]: return (results[0], 18, "pattern_3_3_3")
    if groups[0] == groups[1] and groups[0] <= 3 and len(groups) >= 2:
        return (_opp(results[0]), 14, f"pattern_{groups[0]}_{groups[1]}_break")
    return None

def algo_regime_predictor(results):
    n = len(results)
    if n < 30: return None
    regime_seq = []
    for i in range(min(n - 10, 50)):
        window = results[i:i+10]
        alt = sum(1 for j in range(9) if window[j] != window[j+1])
        streak = _count_streak(window)
        if alt >= 5: regime_seq.append("alt")
        elif streak >= 3: regime_seq.append("streak")
        else: regime_seq.append("balanced")
    if len(regime_seq) < 10: return None
    current_regime = regime_seq[0]
    transitions = defaultdict(int)
    for i in range(len(regime_seq) - 1):
        if regime_seq[i] == current_regime:
            transitions[regime_seq[i+1]] += 1
    if not transitions: return None
    total = sum(transitions.values())
    most_likely_next = max(transitions, key=transitions.get)
    prob = transitions[most_likely_next] / total
    if prob < 0.55: return None
    if most_likely_next == "streak":
        return (results[0], min(20, 12 + prob * 14), f"regime_pred_streak_{prob:.2f}")
    elif most_likely_next == "alt":
        return (_opp(results[0]), min(20, 12 + prob * 14), f"regime_pred_alt_{prob:.2f}")
    return None

def analyze_5phien(results):
    if len(results) < 5: return None
    last5 = results[:5]
    alt = sum(1 for i in range(4) if last5[i] != last5[i+1])
    if alt == 4: return ("Đảo", _opp(last5[0]), 20)
    if alt == 0:
        n = len(results); same_streak_cont = same_streak_break = 0
        for i in range(min(n - 5, 40)):
            if results[i:i+5] == last5:
                if results[i+5] == last5[0]: same_streak_cont += 1
                else: same_streak_break += 1
        total = same_streak_cont + same_streak_break
        if total >= 3:
            p_cont = (same_streak_cont + 1) / (total + 2)
            if p_cont >= 0.55: return ("Thuận", last5[0], 17)
            else: return ("Thuận_break", _opp(last5[0]), 16)
        return ("Thuận", last5[0], 15)
    last4 = results[:4]
    alt4 = sum(1 for i in range(3) if last4[i] != last4[i+1])
    if alt4 == 3: return ("1-1", _opp(last4[0]), 18)
    streak = _count_streak(results)
    if streak >= 3 and streak <= 4 and len(results) > streak:
        return ("Nghịch", _opp(results[0]), 17)
    return None

# =====================================================================
# ★ V9 ENGINE — META-PREDICTOR MỚI
# =====================================================================
SIGNAL_FAMILIES = {
    'lc79':      ('lc79_',),
    '6p':        ('dao_6p', 'thuan_6p', 'nghich_6p', 'zigzag'),
    '7p':        ('7p_radar', '7p_no_reverse', '7p_hash_deep'),
    '10p':       ('stable_zone', 'hash_deep_10p'),
    'hash13':    ('hash_deep_13p', 'hash_deep_multi'),
    'bit':       ('md5_bit_',),
    'ngram':     ('md5_ngram_',),
    'hamming':   ('md5_hamming_',),
    'alt':       ('5p_alt', 'alt_'),
    'streak':    ('streak_', 'break_rhythm', 'volatility_'),
    'trend':     ('trend_',),
    'markov':    ('markov',),
    'pattern':   ('pattern_', 'pattern3'),
    'bayes':     ('bayes_', 'tilt_', 'entropy_', 'cusum_'),
    'periodic':  ('periodicity_',),
    'regime':    ('regime_pred',),
    'consensus': ('consensus_',),
}

_FAMILY_BASE_CAP = {
    'lc79': 30, '6p': 34, '7p': 26, '10p': 22, 'hash13': 20,
    'bit': 18, 'ngram': 16, 'hamming': 14, 'alt': 18, 'streak': 16,
    'trend': 14, 'markov': 16, 'pattern': 18, 'bayes': 14,
    'periodic': 16, 'regime': 20, 'consensus': 12, 'other': 12,
}

def _signal_family(name):
    for fam, prefixes in SIGNAL_FAMILIES.items():
        for p in prefixes:
            if p in name:
                return fam
    return 'other'

def _family_cap(family, regime):
    cap = _FAMILY_BASE_CAP.get(family, 12)
    if regime == 'alternation':
        if family in ('alt', '6p', '7p'): cap *= 1.30
        if family in ('streak', 'trend'):  cap *= 0.70
    elif regime == 'streak':
        if family in ('streak', 'trend'):  cap *= 1.30
        if family in ('alt', '6p'):        cap *= 0.75
    return cap

def _bayes_accuracy(wins, total, prior=0.5, prior_strength=2.5):
    return (wins + prior * prior_strength) / (total + prior_strength)

def meta_predictor(all_signals, signal_stats, regime="balanced"):
    adjusted = []
    for pred, weight, name in all_signals:
        stats = signal_stats.get(name, {})
        wins = stats.get('wins', 0.0)
        total = stats.get('total', 0.0)
        recent = stats.get('recent_hits', [])

        if total >= 3.0:
            acc = _bayes_accuracy(wins, total, prior=0.5, prior_strength=2.5)
        else:
            acc = 0.5

        accuracy_mult = 0.55 + max(0.0, min(0.80, (acc - 0.40) * 2.0))

        win_streak = 0; loss_streak = 0
        for h in recent[:5]:
            if h: win_streak += 1
            else: break
        for h in recent[:5]:
            if not h: loss_streak += 1
            else: break
        if   loss_streak >= 4: streak_mult = 0.45
        elif loss_streak == 3: streak_mult = 0.60
        elif loss_streak == 2: streak_mult = 0.80
        elif win_streak >= 4:  streak_mult = 1.20
        elif win_streak == 3:  streak_mult = 1.12
        elif win_streak == 2:  streak_mult = 1.05
        else:                  streak_mult = 1.00

        if recent:
            n_use = min(5, len(recent))
            w_sum = sum(0.85 ** i for i in range(n_use))
            m = sum((1.0 if recent[i] else 0.0) * (0.85 ** i) for i in range(n_use)) / w_sum
        else:
            m = 0.5
        momentum_mult = 0.85 + m * 0.30

        fam = _signal_family(name)
        reg_mult = 1.0
        if regime == 'alternation':
            if fam in ('alt', '6p', '7p'): reg_mult = 1.15
            elif fam in ('streak', 'trend'): reg_mult = 0.85
        elif regime == 'streak':
            if fam in ('streak', 'trend'): reg_mult = 1.15
            elif fam in ('alt', '6p'):     reg_mult = 0.85

        final_w = weight * accuracy_mult * streak_mult * momentum_mult * reg_mult
        adjusted.append({
            'name': name, 'pred': pred, 'family': fam,
            'base_weight': weight, 'final_weight': final_w,
            'accuracy': round(acc, 3), 'streak_mult': streak_mult,
            'momentum': round(m, 2), 'regime_mult': reg_mult,
            'win_streak': win_streak, 'loss_streak': loss_streak,
        })
    return adjusted

def apply_family_cap(signals, regime):
    fam_sum = defaultdict(float)
    for s in signals:
        fam_sum[s['family']] += s['final_weight']
    for s in signals:
        cap = _family_cap(s['family'], regime)
        if fam_sum[s['family']] > cap and fam_sum[s['family']] > 0:
            ratio = cap / fam_sum[s['family']]
            s['final_weight'] *= ratio
    return signals

# =====================================================================
# ANALYZER
# =====================================================================
def analyze_full_bridge(results):
    if len(results) < 3: return []
    signals = []
    for fn in (
        algo_lc79_specialist,
        algo_6p_balanced,
        algo_stable_zone_10p,
        algo_7p_no_reverse,
        algo_7p_hash_deep,
        algo_7p_pattern_radar,
        algo_hash_deep_5p,
        algo_hash_deep_10p,
        algo_hash_deep_13p,
        algo_hash_deep_multi,
        algo_md5_bit_analysis,
        algo_md5_ngram,
        algo_md5_hamming,
        algo_5p_alternation,
        algo_trend_break,
        algo_break_rhythm,
        data_markov2,
        data_markov3,
        data_pattern3,
        data_alternation,
        data_streak_break,
        data_bayes_ratio,
        data_tilt,
        data_periodicity,
        data_volatility_break,
        data_entropy_bias,
        data_cusum,
        algo_pair_pattern,
        algo_regime_predictor,
    ):
        try:
            s = fn(results)
            if s: signals.append(s)
        except Exception:
            pass
    try:
        consensus = algo_consensus_filter(results, signals)
        if consensus:
            signals.append(consensus)
    except Exception:
        pass
    return signals

def full_bridge_predict_adaptive(results, replay_n=120):
    n = len(results)
    if n == 0: return "Tài", 50, []
    if n == 1: return _opp(results[0]), 52, []
    if n == 2:
        if results[0] == results[1]: return _opp(results[0]), 55, []
        return results[1], 52, []

    signal_stats = defaultdict(lambda: {'wins': 0.0, 'total': 0.0, 'recent_hits': []})
    replay_count = min(replay_n, n - 3)
    for j in range(replay_count):
        history = results[j + 1:]
        actual = results[j]
        decay = math.exp(-j / 40.0)
        for pred_sig, weight, name in analyze_full_bridge(history):
            signal_stats[name]['total'] += decay
            hit = (pred_sig == actual)
            if hit: signal_stats[name]['wins'] += decay
            if j < 6:
                signal_stats[name]['recent_hits'].append(hit)

    signals = analyze_full_bridge(results)
    if not signals: return results[0], 52, []

    regime = _regime(results)
    adjusted = meta_predictor(signals, signal_stats, regime)
    adjusted = apply_family_cap(adjusted, regime)

    st = sx = 0.0
    detail = []
    for a in adjusted:
        w = a['final_weight']
        if a['pred'] == "Tài": st += w
        else:                  sx += w
        detail.append({
            'name': a['name'], 'pred': a['pred'],
            'base_weight': a['base_weight'],
            'accuracy': a['accuracy'],
            'adjusted_weight': round(w, 2),
            'family': a['family'],
            'streak_mult': a['streak_mult'],
            'momentum': a['momentum'],
            'regime_mult': a['regime_mult'],
        })

    total = st + sx
    if total <= 0:
        return results[0], 50, detail

    if st > sx: pred = "Tài"
    elif sx > st: pred = "Xỉu"
    else: return _opp(results[0]), 50, detail

    lean = max(st, sx) / total

    agree_w = sum(a['final_weight'] for a in adjusted if a['pred'] == pred)
    disagree_w = total - agree_w
    conflict_ratio = disagree_w / total if total > 0 else 0

    if len(signals) <= 2 and lean > 0.88:
        return _opp(pred), 51, detail

    raw_conf = 50.0 + (lean - 0.5) * 100.0
    evidence = total / (total + 80.0)
    sig_evidence = min(1.0, len(adjusted) / 8.0)
    if total > 0:
        wacc = sum(a['final_weight'] * a['accuracy'] for a in adjusted) / total
    else:
        wacc = 0.5
    acc_factor = 0.85 + (wacc - 0.5) * 0.6

    conf = 50.0 + (raw_conf - 50.0) * evidence * sig_evidence * acc_factor

    if conflict_ratio > 0.60: conf -= 15
    elif conflict_ratio > 0.50: conf -= 8
    elif conflict_ratio > 0.40: conf -= 4

    if conflict_ratio > 0.58:
        conf = min(conf, 52)

    if lean >= 0.75: conf += 4
    if lean >= 0.82 and conflict_ratio < 0.30: conf += 2

    fam_set = set(a['family'] for a in adjusted)
    if len(fam_set) <= 2 and len(adjusted) >= 3:
        conf = min(conf, 68)

    conf = int(max(50, min(MAX_CONFIDENCE, round(conf))))
    return pred, conf, detail

# =====================================================================
# RECOVERY V9
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

def apply_recovery(base_pred, conf, loss_streak, results=None):
    if loss_streak < 1:
        return base_pred, conf, False, None

    regime = _regime(results) if results else "balanced"

    if loss_streak == 1:
        return base_pred, max(50, conf - 3), False, "hold_1"

    if loss_streak == 2:
        if regime == "streak":
            return base_pred, min(MAX_CONFIDENCE, conf + 3), False, "hold_streak_2"
        if regime == "alternation":
            return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 72)), True, "flip_alt_2"
        return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 68)), True, "flip_2"

    if loss_streak == 3:
        if regime == "streak":
            if results and len(results) >= 1:
                return results[0], min(MAX_CONFIDENCE, max(conf, 72)), False, "follow_3"
        return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 78)), True, "flip_3"

    if loss_streak == 4:
        return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 80)), True, "flip_4"

    return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 82)), True, "flip_5plus"

def get_stable_next_prediction(valid):
    if not valid:
        return None, 50, False, None, None
    next_phien = valid[-1]['phien'] + 1
    if next_phien in NEXT_PREDICTION_CACHE:
        return NEXT_PREDICTION_CACHE[next_phien]
    results = [v['result'] for v in valid][::-1]
    loss_streak = compute_loss_streak(valid)
    base_pred, base_conf, _ = full_bridge_predict_adaptive(results)
    pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak, results=results)
    NEXT_PREDICTION_CACHE[next_phien] = (pred, conf, flipped, reason, base_pred)
    if len(NEXT_PREDICTION_CACHE) > 200:
        oldest = min(NEXT_PREDICTION_CACHE.keys())
        del NEXT_PREDICTION_CACHE[oldest]
    return NEXT_PREDICTION_CACHE[next_phien]

def reset_all_databases():
    global LEARNED_PHIEN
    with LEARN_LOCK:
        for depth in (5, 7, 10, 13):
            HASH_DEEP_DB[depth].clear()
        for bit in range(128):
            MD5_BIT_DB[bit]["Tài"] = 0
            MD5_BIT_DB[bit]["Xỉu"] = 0
        for ng_size in (2, 3, 4):
            MD5_NGRAM_DB[ng_size].clear()
        MD5_HAMMING_DB.clear()
        LOSS_HISTORY.clear()
        LEARNED_PHIEN = RESET_ID

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
        learn_incremental(valid)

        next_phien = valid[-1]['phien'] + 1
        cached_next = get_stable_next_prediction(valid)
        if cached_next and cached_next[0] is not None:
            next_pred, next_conf, flipped, reason, base_pred = cached_next
        else:
            results_now = [v['result'] for v in valid][::-1]
            ls_now = compute_loss_streak(valid)
            bp, bc, _ = full_bridge_predict_adaptive(results_now)
            next_pred, next_conf, flipped, reason = apply_recovery(bp, bc, ls_now, results=results_now)
            base_pred = bp
            NEXT_PREDICTION_CACHE[next_phien] = (next_pred, next_conf, flipped, reason, bp)

        loss_streak = compute_loss_streak(valid)
        out = []; correct_count = 0; total_past = 0

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
        learn_incremental(valid)
        results = [v['result'] for v in valid][::-1]

        loss_streak = compute_loss_streak(valid)
        base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak, results=results)

        cau6 = classify_6p_pattern(results)
        cau6_info = None
        if cau6:
            cau6_info = {'type': cau6['type'], 'pred': cau6['pred'],
                         'weight': cau6['weight'], 'reason': cau6['reason']}

        cau5 = analyze_5phien(results)
        cau_info = None
        if cau5:
            cau_info = {'name': cau5[0], 'pred': cau5[1], 'weight': cau5[2]}

        cau7_radar = algo_7p_pattern_radar(results)
        cau7_info = {'name': cau7_radar[2], 'pred': cau7_radar[0], 'weight': cau7_radar[1]} if cau7_radar else None

        cau_lc79 = algo_lc79_specialist(results)
        cau_lc79_info = {'name': cau_lc79[2], 'pred': cau_lc79[0], 'weight': cau_lc79[1]} if cau_lc79 else None

        regime_pred = algo_regime_predictor(results)
        regime_info = {'name': regime_pred[2], 'pred': regime_pred[0], 'weight': regime_pred[1]} if regime_pred else None

        p5_signal = algo_5p_alternation(results)
        hash5_signal = algo_hash_deep_5p(results)
        hash10_signal = algo_hash_deep_10p(results)
        hash13_signal = algo_hash_deep_13p(results)
        bit_signal = algo_md5_bit_analysis(results)
        ngram_signal = algo_md5_ngram(results)
        hamming_signal = algo_md5_hamming(results)
        trend_signal = algo_trend_break(results)
        rhythm_signal = algo_break_rhythm(results)
        last5_tx = encode_tx(results, 5)
        last13_tx = encode_tx(results, 13)
        last13_hash = hash_deep_md5(last13_tx, depth_level=2) if last13_tx else None
        last5_hash = hash_deep_md5(last5_tx, depth_level=3) if last5_tx else None

        return jsonify({
            'last_phien': valid[-1]['phien'], 'next_phien': valid[-1]['phien'] + 1,
            'last_result': valid[-1]['result'], 'last_dice': valid[-1]['dice'],
            'prediction': pred, 'confidence': conf,
            'base_prediction': base_pred, 'base_confidence': base_conf,
            'recovery_flipped': flipped, 'recovery_reason': reason,
            'loss_streak': loss_streak, 'total_sessions': len(valid),
            'cau_6phien': cau6_info,
            'cau_5phien': cau_info,
            'cau_7phien_radar': cau7_info,
            'cau_lc79': cau_lc79_info,
            'regime_prediction': regime_info,
            'meta_confidence': conf,
            'prediction_breakdown': {'tai_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài'), 2),
                                      'xiu_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu'), 2),
                                      'signal_count': len(detail)},
            'last5_pattern': last5_tx, 'last5_hash_deep': last5_hash,
            'last13_hash': last13_hash,
            'pattern_5p': {'pred': p5_signal[0], 'name': p5_signal[2]} if p5_signal else None,
            'hash_deep_5p': {'pred': hash5_signal[0], 'name': hash5_signal[2]} if hash5_signal else None,
            'hash_deep_10p': {'pred': hash10_signal[0], 'name': hash10_signal[2]} if hash10_signal else None,
            'hash_deep_13p': {'pred': hash13_signal[0], 'name': hash13_signal[2]} if hash13_signal else None,
            'md5_bit': {'pred': bit_signal[0], 'name': bit_signal[2]} if bit_signal else None,
            'md5_ngram': {'pred': ngram_signal[0], 'name': ngram_signal[2]} if ngram_signal else None,
            'md5_hamming': {'pred': hamming_signal[0], 'name': hamming_signal[2]} if hamming_signal else None,
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
        learn_incremental(valid)
        results = [v['result'] for v in valid][::-1]
        loss_streak = compute_loss_streak(valid)
        base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak, results=results)

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

        cau7_radar = algo_7p_pattern_radar(results)
        radar_name = cau7_radar[2] if cau7_radar else "none"
        cau_lc79 = algo_lc79_specialist(results)
        lc79_name = cau_lc79[2] if cau_lc79 else "none"
        regime_pred = algo_regime_predictor(results)
        regime_name = regime_pred[2] if regime_pred else "none"
        cau6 = classify_6p_pattern(results)
        cau6_name = cau6['reason'] if cau6 else "none"
        cau6_type = cau6['type'] if cau6 else "none"

        return jsonify({
            'Id': 'le minh md5 deep v9',
            'Phien': str(next_phien),
            'Ket_qua': last['result'].lower(), 'Lich_su': lich_su,
            'Du_doan': pred, 'Do_tin_cay': conf_str,
            'Cau_6p': cau6_type,
            'Cau_6p_Detail': cau6_name,
            'Cau_7p_Radar': radar_name,
            'Cau_LC79': lc79_name,
            'Regime_Predict': regime_name,
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
        learn_incremental(valid)
        results = [v['result'] for v in valid][::-1]
        loss_streak = compute_loss_streak(valid)
        base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak, results=results)

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

        cau7_radar = algo_7p_pattern_radar(results)
        radar_name = cau7_radar[2] if cau7_radar else "none"
        cau_lc79 = algo_lc79_specialist(results)
        lc79_name = cau_lc79[2] if cau_lc79 else "none"
        regime_pred = algo_regime_predictor(results)
        regime_name = regime_pred[2] if regime_pred else "none"
        cau6 = classify_6p_pattern(results)
        cau6_name = cau6['reason'] if cau6 else "none"
        cau6_type = cau6['type'] if cau6 else "none"

        return jsonify({
            'id': '@cskhleminh', 'phien': str(next_phien),
            'ket_qua': ket_qua_str, 'du_doan': pred,
            'do_tin_cay': conf_str, 'lich_su': lich_su,
            'cau_6p': cau6_type,
            'cau_6p_detail': cau6_name,
            'cau_7p_radar': radar_name,
            'cau_lc79': lc79_name,
            'regime_predict': regime_name,
            'base_du_doan': base_pred if flipped else None,
            'auto_flip': flipped, 'chuoi_thua': loss_streak,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE, PREDICTION_CACHE, LEARNED_PHIEN, NEXT_PREDICTION_CACHE
    try:
        raw_rows, success = fetch_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                LEARNED_PHIEN = RESET_ID
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                PREDICTION_CACHE = {}
                NEXT_PREDICTION_CACHE = {}
                reset_all_databases()
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng, không thể xác nhận mốc Reset'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
