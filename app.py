import os
import math
import hashlib
import traceback
import threading
from datetime import datetime
from collections import defaultdict
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
MAX_CONFIDENCE = 88

LEARNED_PHIEN = 0
LEARN_LOCK = threading.Lock()

# ===== DATABASE ĐA TẦNG =====
HASH_DEEP_DB = {
    5: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
}
MD5_BIT_DB = {bit: {"Tài": 0, "Xỉu": 0} for bit in range(128)}
MD5_NGRAM_DB = {
    2: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    3: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
    4: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
}
MD5_HAMMING_DB = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 V16</title>
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
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: var(--text-main); min-height: 100vh; padding-bottom: 40px; }
    .header { background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-color); padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
    .header-title { font-size: 22px; font-weight: 800; color: #38bdf8; display: flex; align-items: center; gap: 10px; text-shadow: 0 0 20px rgba(56, 189, 248, 0.4); }
    .header-title span { font-size: 11px; background: linear-gradient(135deg, #38bdf8, #ec4899); color: #fff; padding: 4px 12px; border-radius: 20px; font-weight: 800; letter-spacing: 1px; }
    .header-actions { display: flex; gap: 12px; align-items: center; }
    .time-update { font-size: 12px; color: var(--text-muted); font-weight: 600; }
    .btn-refresh { background: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); width: 38px; height: 38px; border-radius: 10px; font-weight: 700; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: 0.2s; }
    .btn-refresh:hover { background: var(--border-color); transform: rotate(180deg); }
    .btn-reset { background: rgba(248, 113, 113, 0.2); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 8px 16px; border-radius: 10px; font-weight: 700; font-size: 13px; cursor: pointer; transition: 0.2s; }
    .btn-reset:hover { background: var(--lose-color); color: #fff; }
    .stats-bar { max-width: 800px; margin: 24px auto 16px; padding: 0 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .stat-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 16px 10px; text-align: center; }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px; }
    .stat-value { font-size: 22px; font-weight: 800; }
    .stat-value.win { color: var(--win-color); }
    .stat-value.loss { color: var(--lose-color); }
    .stat-value.rate { color: var(--tai-color); }
    .table-wrapper { max-width: 800px; margin: 0 auto; padding: 0 16px; }
    .table-container { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 16px; max-height: 70vh; overflow-y: auto; }
    .data-table { width: 100%; border-collapse: separate; border-spacing: 0; }
    .data-table th { background: #111827; color: var(--text-muted); font-size: 11px; font-weight: 700; text-transform: uppercase; padding: 16px 12px; text-align: center; border-bottom: 1px solid var(--border-color); position: sticky; top: 0; z-index: 10; }
    .data-table td { padding: 14px 12px; text-align: center; border-bottom: 1px solid var(--border-color); font-size: 14px; font-weight: 600; }
    .row-next { background: rgba(14, 165, 233, 0.08); border-left: 4px solid var(--tai-color); }
    .badge { display: inline-block; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; min-width: 70px; text-align: center; }
    .badge-tai { background: var(--tai-bg); color: var(--tai-color); border: 1px solid rgba(56, 189, 248, 0.3); }
    .badge-xiu { background: var(--xiu-bg); color: var(--xiu-color); border: 1px solid rgba(244, 114, 182, 0.3); }
    .badge-empty { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); }
    .status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; padding: 6px 14px; border-radius: 20px; }
    .st-win { background: var(--win-bg); color: var(--win-color); }
    .st-lose { background: var(--lose-bg); color: var(--lose-color); }
    .st-wait { background: var(--wait-bg); color: var(--wait-color); animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .dice-text { font-size: 11px; color: var(--text-muted); display: block; margin-top: 4px; }
    .conf-badge { font-size: 11px; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 2px 8px; border-radius: 10px; margin-top: 4px; display: inline-block; font-weight: 700; }
    .conf-badge.high { color: #34d399; background: rgba(52, 211, 153, 0.15); }
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
    <div class="header-title">LE MINH <span>V16</span></div>
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
    <div class="stat-item"><div class="stat-label">Tỷ lệ</div><div class="stat-value rate" id="stat-rate">0%</div></div>
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
    } catch (e) { console.error(e); }
}
function renderTable(rows, stats) {
    const tbody = document.getElementById('table-body');
    const total = stats.total || 0;
    const correct = stats.correct || 0;
    animateNumber(document.getElementById('stat-total'), total);
    animateNumber(document.getElementById('stat-win'), correct);
    animateNumber(document.getElementById('stat-lose'), total - correct);
    const rate = total > 0 ? (correct / total) * 100 : 0;
    animateNumber(document.getElementById('stat-rate'), Math.round(rate), '%');
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="4" class="loading">Không có dữ liệu.</td></tr>'; return; }
    let html = '';
    rows.forEach((row) => {
        let trClass = row.is_next ? 'class="row-next"' : '';
        let predHtml = `<span class="badge badge-empty">-</span>`;
        if (row.prediction === "Tài") predHtml = `<span class="badge badge-tai">TÀI</span>`;
        if (row.prediction === "Xỉu") predHtml = `<span class="badge badge-xiu">XỈU</span>`;
        let confHtml = "";
        if (row.conf && row.prediction !== "-") {
            const cls = row.conf >= 70 ? 'conf-badge high' : 'conf-badge';
            confHtml = `<div class="${cls}">${row.conf}%</div>`;
        }
        let predFull = `<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">${predHtml}${confHtml}</div>`;
        let resultHtml = `<span class="badge badge-empty">-</span>`;
        if (row.result === "Tài") resultHtml = `<span class="badge badge-tai">TÀI</span>`;
        if (row.result === "Xỉu") resultHtml = `<span class="badge badge-xiu">XỈU</span>`;
        let diceDisplay = "";
        if (row.dice && row.dice !== "? + ? + ?") {
            const p = row.dice.split(" + ");
            const sum = parseInt(p[0]) + parseInt(p[1]) + parseInt(p[2]);
            diceDisplay = `<span class="dice-text">${row.dice} (${sum})</span>`;
        }
        let resultFull = `<div style="display:flex;flex-direction:column;align-items:center;">${resultHtml}${diceDisplay}</div>`;
        let statusHtml = '';
        if (row.is_next) statusHtml = `<span class="status st-wait">Chờ kết quả</span>`;
        else if (row.is_correct === true) statusHtml = `<span class="status st-win">✔ THẮNG</span>`;
        else if (row.is_correct === false) statusHtml = `<span class="status st-lose">✖ THUA</span>`;
        else statusHtml = `<span class="status" style="color:var(--text-muted)">-</span>`;
        html += `<tr ${trClass}><td>#${row.phien}</td><td>${predFull}</td><td>${resultFull}</td><td>${statusHtml}</td></tr>`;
    });
    tbody.innerHTML = html;
}
async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', text: "Xoá toàn bộ lịch sử và bắt đầu lại!",
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
                    Swal.fire({ title: 'Thành công!', icon: 'success', background: '#1e293b', color: '#f8fafc', confirmButtonColor: '#0ea5e9' });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire({title: 'Lỗi!', text: error.message, icon: 'error', background: '#1e293b', color: '#f8fafc'});
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
# HÀM CƠ BẢN
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
        if n <= 5:
            LEARNED_PHIEN = valid[-1]['phien']
            return

        db = HASH_DEEP_DB[5]
        for idx in new_indices:
            if idx < 5: continue
            history = [v['result'] for v in valid[idx-5:idx]][::-1]
            tx = encode_tx(history, 5)
            if not tx: continue
            h = hash_deep_md5(tx, depth_level=3)
            if not h: continue
            db[h][valid[idx]['result']] += 1

        hash_cache = {}
        for idx in new_indices:
            if idx < 5: continue
            history = [v['result'] for v in valid[idx-5:idx]][::-1]
            tx = encode_tx(history, 5)
            if not tx: continue
            h = hash_deep_md5(tx, depth_level=3)
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
            if idx < 6 or idx not in hash_cache: continue
            prev_idx = idx - 1
            if prev_idx in hash_cache:
                h_prev = hash_cache[prev_idx]
            else:
                if prev_idx < 5: continue
                ph = [v['result'] for v in valid[prev_idx-5:prev_idx]][::-1]
                ptx = encode_tx(ph, 5)
                if not ptx: continue
                h_prev = hash_deep_md5(ptx, depth_level=3)
                if not h_prev: continue
            hd = hamming_distance(hash_cache[idx], h_prev)
            MD5_HAMMING_DB[hd // 8][valid[idx]['result']] += 1

        LEARNED_PHIEN = valid[-1]['phien']

# =====================================================================
# PATTERN + ĐA TẦNG MD5
# =====================================================================
def classify_5p_pattern(last5):
    if len(last5) < 5:
        return None
    groups = get_groups(last5)
    alt_count = sum(1 for i in range(4) if last5[i] != last5[i+1])

    if alt_count == 4:
        return {'type': 'ĐẢO', 'groups': groups, 'alt': alt_count}
    if len(groups) == 1 and groups[0] == 5:
        return {'type': 'THUẬN', 'groups': groups, 'alt': alt_count}
    if len(groups) == 2 and (groups[0] == 4 or groups[1] == 4):
        return {'type': 'THUẬN', 'groups': groups, 'alt': alt_count}
    if len(groups) == 3 and (
        (groups[0] == 3 and groups[1] == 1 and groups[2] == 1) or
        (groups[0] == 1 and groups[1] == 1 and groups[2] == 3)
    ):
        return {'type': 'NGHỊCH', 'groups': groups, 'alt': alt_count}
    if len(groups) == 2 and (
        (groups[0] == 3 and groups[1] == 2) or
        (groups[0] == 2 and groups[1] == 3)
    ):
        return {'type': 'NGHỊCH', 'groups': groups, 'alt': alt_count}
    if len(groups) == 3 and (
        (groups[0] == 2 and groups[1] == 2 and groups[2] == 1) or
        (groups[0] == 1 and groups[1] == 2 and groups[2] == 2) or
        (groups[0] == 2 and groups[1] == 1 and groups[2] == 2)
    ):
        return {'type': '1-1', 'groups': groups, 'alt': alt_count}
    if len(groups) == 4 and (groups[0] == 2 or groups[3] == 2):
        return {'type': '1-1', 'groups': groups, 'alt': alt_count}
    if len(groups) == 2 and groups[0] == 2 and groups[1] == 2:
        return {'type': '1-1', 'groups': groups, 'alt': alt_count}
    return {'type': 'KHÁC', 'groups': groups, 'alt': alt_count}


def lookup_pattern_stats(results, key_len, key_tuple, max_scan=80):
    n = len(results)
    tai_next = xiu_next = 0
    for i in range(min(n - key_len, max_scan)):
        if tuple(results[i:i+key_len]) == key_tuple:
            if results[i+key_len] == "Tài": tai_next += 1
            else: xiu_next += 1
    total = tai_next + xiu_next
    if total == 0:
        return 0.5, 0, 0.0
    p_tai = (tai_next + 1) / (total + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
    return p_tai, total, z


def lookup_hash_deep_5p(results):
    tx = encode_tx(results, 5)
    if not tx: return None
    h = hash_deep_md5(tx, depth_level=3)
    if not h or h not in HASH_DEEP_DB[5]: return None
    counts = HASH_DEEP_DB[5][h]
    total = counts["Tài"] + counts["Xỉu"]
    if total < 3: return None
    p_tai = (counts["Tài"] + 1) / (total + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    return pred, total, z, p_tai


def lookup_md5_bit(results):
    tx = encode_tx(results, 5)
    if not tx: return None
    h = hash_deep_md5(tx, depth_level=3)
    if not h: return None
    bits = hash_to_bits(h)
    tai_votes = xiu_votes = 0
    total_seen = 0
    for bit_idx in range(min(128, len(bits))):
        if bits[bit_idx] == 1:
            counts = MD5_BIT_DB[bit_idx]
            t = counts["Tài"] + counts["Xỉu"]
            if t > 0:
                tai_votes += counts["Tài"]
                xiu_votes += counts["Xỉu"]
                total_seen += t
    if total_seen < 10: return None
    p_tai = (tai_votes + 1) / (total_seen + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total_seen + 2))
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    return pred, total_seen, z, p_tai


def lookup_md5_ngram(results):
    tx = encode_tx(results, 5)
    if not tx: return None
    h = hash_deep_md5(tx, depth_level=3)
    if not h: return None
    tai_votes = xiu_votes = 0
    total_seen = 0
    for ng_size in (2, 3, 4):
        weight = 1.0 + (ng_size - 2) * 0.5
        for start in range(0, len(h) - ng_size + 1):
            gram = h[start:start + ng_size]
            counts = MD5_NGRAM_DB[ng_size].get(gram)
            if not counts: continue
            t = counts["Tài"] + counts["Xỉu"]
            if t < 2: continue
            tai_votes += counts["Tài"] * weight
            xiu_votes += counts["Xỉu"] * weight
            total_seen += t * weight
    if total_seen < 20: return None
    p_tai = (tai_votes + 1) / (total_seen + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total_seen + 2))
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    return pred, total_seen, z, p_tai


def lookup_md5_hamming(results, prev_results):
    tx = encode_tx(results, 5)
    tx_prev = encode_tx(prev_results, 5)
    if not tx or not tx_prev: return None
    h = hash_deep_md5(tx, depth_level=3)
    h_prev = hash_deep_md5(tx_prev, depth_level=3)
    if not h or not h_prev: return None
    hd = hamming_distance(h, h_prev)
    bucket = hd // 8
    counts = MD5_HAMMING_DB.get(bucket)
    if not counts: return None
    total = counts["Tài"] + counts["Xỉu"]
    if total < 5: return None
    p_tai = (counts["Tài"] + 1) / (total + 2)
    z = (p_tai - 0.5) / math.sqrt(0.25 / (total + 2))
    pred = "Tài" if p_tai > 0.5 else "Xỉu"
    return pred, total, z, p_tai


def _count_streak_break_stats(results, current, streak_len, max_scan=80):
    n = len(results)
    cont = brk = 0
    for i in range(min(n - streak_len, max_scan)):
        if all(results[i+j] == current for j in range(streak_len)):
            if i + streak_len < n:
                if results[i+streak_len] == current: cont += 1
                else: brk += 1
    return cont, brk


def compute_stability_score(total_pat, z_pat, hash_agree, bit_agree, ngram_agree, hamming_agree, cau_type):
    score = 40.0
    if total_pat >= 20: score += 20
    elif total_pat >= 15: score += 16
    elif total_pat >= 10: score += 12
    elif total_pat >= 7: score += 8
    elif total_pat >= 5: score += 4

    abs_z = abs(z_pat)
    if abs_z >= 2.0: score += 15
    elif abs_z >= 1.5: score += 11
    elif abs_z >= 1.0: score += 7
    elif abs_z >= 0.8: score += 3

    agrees = [x for x in (hash_agree, bit_agree, ngram_agree, hamming_agree) if x is not None]
    if agrees:
        ratio = sum(agrees) / len(agrees)
        score += ratio * 20
        if len(agrees) >= 3 and all(agrees):
            score += 5

    stable_cau = {'ĐẢO': 5, 'THUẬN': 4, 'NGHỊCH': 3, '1-1': 3, 'KHÁC': 0}
    score += stable_cau.get(cau_type, 0)
    return max(0, min(100, round(score, 1)))


def _recommendation_from_stability(stability, conf):
    if stability >= 75 and conf >= 70: return "STRONG"
    if stability >= 60 and conf >= 62: return "NORMAL"
    if stability >= 45: return "CAUTION"
    return "SKIP"


def predict_5p_pattern(results):
    """Core prediction — V15 giữ nguyên."""
    n = len(results)
    if n < 5:
        if n == 0: return "Tài", 50, "KHÁC", _empty_detail(50)
        if n == 1: return _opp(results[0]), 52, "KHÁC", _empty_detail(52)
        if n == 2:
            if results[0] == results[1]: return _opp(results[0]), 54, "KHÁC", _empty_detail(54)
            return results[1], 52, "KHÁC", _empty_detail(52)
        if n == 3:
            if results[0] == results[1] == results[2]:
                return _opp(results[0]), 55, "KHÁC", _empty_detail(55)
            return results[0], 52, "KHÁC", _empty_detail(52)
        if n == 4:
            g = get_groups(results)
            if len(g) == 1: return _opp(results[0]), 56, "KHÁC", _empty_detail(56)
            if len(g) == 4: return _opp(results[0]), 55, "KHÁC", _empty_detail(55)
            return results[0], 52, "KHÁC", _empty_detail(52)

    last5 = results[:5]
    pattern = classify_5p_pattern(last5)
    cau_type = pattern['type']
    groups = pattern['groups']

    key_tuple = tuple(last5)
    p_tai_pat, total_pat, z_pat = lookup_pattern_stats(results, 5, key_tuple)

    hash_result = lookup_hash_deep_5p(results)
    bit_result = lookup_md5_bit(results)
    ngram_result = lookup_md5_ngram(results)
    hamming_result = None
    if n >= 6:
        hamming_result = lookup_md5_hamming(results, results[1:])

    if total_pat >= 15: z_threshold = 0.7
    elif total_pat >= 10: z_threshold = 0.85
    elif total_pat >= 6: z_threshold = 1.0
    else: z_threshold = 1.3

    pred = None; conf = 50; reason = ""; extra = {}

    if cau_type == 'ĐẢO':
        theory_pred = _opp(last5[0])
        if total_pat >= 5 and abs(z_pat) >= z_threshold:
            data_pred = "Tài" if p_tai_pat > 0.5 else "Xỉu"
            if data_pred == theory_pred:
                pred = data_pred; conf = 60 + min(20, abs(z_pat) * 10)
                reason = f"dao_data_{total_pat}"
            else:
                pred = data_pred; conf = 55 + min(10, abs(z_pat) * 6)
                reason = f"dao_data_conflict_{total_pat}"
        else:
            pred = theory_pred; conf = 58; reason = "dao_theory"
        extra = {'theory_pred': theory_pred}

    elif cau_type == 'THUẬN':
        current = last5[0]
        if len(groups) == 1:
            cont, brk = _count_streak_break_stats(results, current, 5)
            total_streak = cont + brk
            if total_streak >= 5:
                p_cont = (cont + 1) / (total_streak + 2)
                z_cont = (p_cont - 0.5) / math.sqrt(0.25 / (total_streak + 2))
                if abs(z_cont) >= z_threshold:
                    if p_cont >= 0.55:
                        pred = current; conf = 58 + min(18, abs(z_cont) * 8)
                        reason = f"thuan_cont_{total_streak}"
                    else:
                        pred = _opp(current); conf = 56 + min(15, abs(z_cont) * 7)
                        reason = f"thuan_break_{total_streak}"
                else:
                    pred = current; conf = 55; reason = "thuan_theory"
            else:
                pred = current; conf = 55; reason = "thuan_theory"
            extra = {'cont': cont, 'brk': brk, 'total_streak': total_streak}
        else:
            if groups[0] == 4:
                pred = last5[0]; conf = 56; reason = "thuan_4_1_head"
            else:
                pred = last5[0]; conf = 55; reason = "thuan_4_1_tail"
            extra = {'groups_mode': '4-1'}

    elif cau_type == 'NGHỊCH':
        theory_pred = _opp(last5[0])
        if total_pat >= 5 and abs(z_pat) >= z_threshold:
            data_pred = "Tài" if p_tai_pat > 0.5 else "Xỉu"
            if data_pred == theory_pred:
                pred = data_pred; conf = 58 + min(18, abs(z_pat) * 9)
                reason = f"nghich_data_{total_pat}"
            else:
                pred = data_pred; conf = 54 + min(10, abs(z_pat) * 6)
                reason = f"nghich_data_conflict_{total_pat}"
        else:
            pred = theory_pred; conf = 56; reason = "nghich_theory"
        extra = {'theory_pred': theory_pred}

    elif cau_type == '1-1':
        theory_pred = _opp(last5[0])
        if total_pat >= 5 and abs(z_pat) >= z_threshold:
            data_pred = "Tài" if p_tai_pat > 0.5 else "Xỉu"
            if data_pred == theory_pred:
                pred = data_pred; conf = 57 + min(17, abs(z_pat) * 8)
                reason = f"11_data_{total_pat}"
            else:
                pred = data_pred; conf = 54 + min(10, abs(z_pat) * 6)
                reason = f"11_data_conflict_{total_pat}"
        else:
            pred = theory_pred; conf = 55; reason = "11_theory"
        extra = {'theory_pred': theory_pred}

    else:
        if total_pat >= 5 and abs(z_pat) >= z_threshold:
            pred = "Tài" if p_tai_pat > 0.5 else "Xỉu"
            conf = 55 + min(15, abs(z_pat) * 8)
            reason = f"khac_data_{total_pat}"
        else:
            if n >= 2 and results[0] == results[1]:
                pred = _opp(results[0]); conf = 53; reason = "khac_fallback_streak"
            else:
                pred = results[0]; conf = 51; reason = "khac_fallback_follow"

    hash_info = {}; bit_info = {}; ngram_info = {}; hamming_info = {}
    hash_agree = bit_agree = ngram_agree = hamming_agree = None

    if hash_result:
        h_pred, h_total, h_z, h_p_tai = hash_result
        hash_info = {'pred': h_pred, 'total': h_total, 'z': round(h_z, 2), 'p_tai': round(h_p_tai, 3)}
        if h_total >= 5 and abs(h_z) >= 1.0:
            hash_agree = (h_pred == pred)
            if hash_agree:
                conf += min(6, abs(h_z) * 2.5); reason += "+hash_ok"
            else:
                conf -= min(8, abs(h_z) * 3); reason += "+hash_no"

    if bit_result:
        b_pred, b_total, b_z, b_p_tai = bit_result
        bit_info = {'pred': b_pred, 'total': b_total, 'z': round(b_z, 2)}
        if abs(b_z) >= 1.0:
            bit_agree = (b_pred == pred)
            if bit_agree:
                conf += min(5, abs(b_z) * 2); reason += "+bit_ok"
            else:
                conf -= min(6, abs(b_z) * 2.5); reason += "+bit_no"

    if ngram_result:
        n_pred, n_total, n_z, n_p_tai = ngram_result
        ngram_info = {'pred': n_pred, 'total': n_total, 'z': round(n_z, 2)}
        if abs(n_z) >= 1.0:
            ngram_agree = (n_pred == pred)
            if ngram_agree:
                conf += min(5, abs(n_z) * 2); reason += "+ngram_ok"
            else:
                conf -= min(6, abs(n_z) * 2.5); reason += "+ngram_no"

    if hamming_result:
        hm_pred, hm_total, hm_z, hm_p_tai = hamming_result
        hamming_info = {'pred': hm_pred, 'total': hm_total, 'z': round(hm_z, 2)}
        if abs(hm_z) >= 1.0:
            hamming_agree = (hm_pred == pred)
            if hamming_agree:
                conf += min(4, abs(hm_z) * 1.8); reason += "+ham_ok"
            else:
                conf -= min(5, abs(hm_z) * 2); reason += "+ham_no"

    disagree_count = sum(1 for x in (hash_agree, bit_agree, ngram_agree, hamming_agree) if x is False)
    agree_count = sum(1 for x in (hash_agree, bit_agree, ngram_agree, hamming_agree) if x is True)

    if disagree_count >= 3: conf = min(conf, 56)
    elif disagree_count == 2: conf = min(conf, 62)
    elif disagree_count == 1: conf = min(conf, 72)

    if agree_count >= 3:
        conf = min(conf + 5, MAX_CONFIDENCE)

    if total_pat < 8:
        conf = min(conf, 68)

    conf = int(max(50, min(MAX_CONFIDENCE, round(conf))))

    stability = compute_stability_score(total_pat, z_pat, hash_agree, bit_agree, ngram_agree, hamming_agree, cau_type)
    recommendation = _recommendation_from_stability(stability, conf)

    detail = {
        'cau_type': cau_type, 'groups': groups,
        'pattern_total': total_pat, 'pattern_p_tai': round(p_tai_pat, 3),
        'pattern_z': round(z_pat, 2), 'z_threshold_used': round(z_threshold, 2),
        'hash_info': hash_info, 'bit_info': bit_info,
        'ngram_info': ngram_info, 'hamming_info': hamming_info,
        'agreement': {'hash': hash_agree, 'bit': bit_agree, 'ngram': ngram_agree,
                      'hamming': hamming_agree, 'agree_count': agree_count,
                      'disagree_count': disagree_count},
        'reason': reason, 'extra': extra,
        'stability_score': stability, 'recommendation': recommendation,
    }
    return pred, conf, cau_type, detail


def _empty_detail(conf):
    return {
        'cau_type': 'KHÁC', 'groups': [], 'pattern_total': 0,
        'pattern_p_tai': 0.5, 'pattern_z': 0.0, 'z_threshold_used': 1.3,
        'hash_info': {}, 'bit_info': {}, 'ngram_info': {}, 'hamming_info': {},
        'agreement': {'hash': None, 'bit': None, 'ngram': None, 'hamming': None,
                      'agree_count': 0, 'disagree_count': 0},
        'reason': 'insufficient_data', 'extra': {},
        'stability_score': 40.0,
        'recommendation': _recommendation_from_stability(40.0, conf),
    }


# =====================================================================
# ★★★ V16: AUTO FLIP 2-3 TAY THEO DEEP-HASH 5P ★★★
# =====================================================================
def _get_prev_actual_result(valid, upto_idx):
    """Lấy kết quả thực tế của phiên trước đó."""
    if upto_idx <= 0 or upto_idx > len(valid): return None
    return valid[upto_idx - 1]['result']


def count_loss_streak(valid, max_scan=10):
    """
    Đếm chuỗi thua liên tiếp của thuật toán.
    Dựa trên PREDICTION_CACHE đã có.
    """
    if len(valid) < 6: return 0
    streak = 0
    end = len(valid) - 1
    start = max(0, end - max_scan)
    for i in range(end, start - 1, -1):
        pred, conf, is_correct = get_prediction_for(valid, i)
        if is_correct is None: break
        if is_correct: break
        streak += 1
    return streak


def apply_auto_flip(base_pred, base_conf, loss_streak, results, detail):
    """
    ★ AUTO FLIP 2-3 TAY THEO DEEP-HASH 5P ★
    - loss 0-1: giữ nguyên
    - loss 2: flip CHỈ KHI deep-hash 5P đủ mạnh VÀ ngược base
    - loss 3: flip THEO deep-hash nếu có, không thì flip thường
    - loss 4+: flip mạnh
    
    Trả (final_pred, final_conf, flipped, flip_reason)
    """
    if loss_streak < 2:
        return base_pred, base_conf, False, None

    # Lấy tín hiệu deep-hash 5P (KHÔNG dùng bit/ngram/hamming vì chúng chỉ là xác nhận)
    hash_result = detail.get('hash_info', {})
    hash_pred = hash_result.get('pred')
    hash_total = hash_result.get('total', 0)
    hash_z = abs(hash_result.get('z', 0))

    if loss_streak == 2:
        # Flip nếu deep-hash đủ mạnh VÀ ngược base
        if hash_pred and hash_pred != base_pred and hash_total >= 7 and hash_z >= 1.3:
            return hash_pred, min(MAX_CONFIDENCE, max(base_conf, 70)), True, f"flip2_hash_{hash_total}_{hash_z:.1f}"
        return base_pred, max(50, base_conf - 3), False, "hold_2"

    if loss_streak == 3:
        # Flip theo deep-hash nếu có, không thì đảo thường
        if hash_pred and hash_pred != base_pred and hash_total >= 5 and hash_z >= 1.0:
            return hash_pred, min(MAX_CONFIDENCE, max(base_conf, 72)), True, f"flip3_hash_{hash_total}_{hash_z:.1f}"
        return _opp(base_pred), min(MAX_CONFIDENCE, max(base_conf, 70)), True, "flip3_opp"

    # loss 4+
    if hash_pred and hash_pred != base_pred:
        return hash_pred, min(MAX_CONFIDENCE, max(base_conf, 75)), True, f"flip4_hash_{hash_total}"
    return _opp(base_pred), min(MAX_CONFIDENCE, max(base_conf, 75)), True, "flip4_opp"


# =====================================================================
# CACHE
# =====================================================================
def get_prediction_for(valid, i):
    key = valid[i]['phien']
    if key in PREDICTION_CACHE: return PREDICTION_CACHE[key]
    hist = [v['result'] for v in valid[:i]][::-1]
    if len(hist) < 5:
        result = ("-", 50, None)
    else:
        pred, conf, _, _ = predict_5p_pattern(hist)
        is_correct = (pred == valid[i]['result'])
        result = (pred, conf, is_correct)
    if len(PREDICTION_CACHE) > MAX_PREDICTION_CACHE: PREDICTION_CACHE.clear()
    PREDICTION_CACHE[key] = result
    return result


def get_stable_next_prediction(valid):
    """Trả prediction cuối cùng cho phiên tới (đã áp auto-flip)."""
    if not valid:
        return None, 50, None, False, None
    next_phien = valid[-1]['phien'] + 1
    if next_phien in NEXT_PREDICTION_CACHE:
        return NEXT_PREDICTION_CACHE[next_phien]
    results = [v['result'] for v in valid][::-1]
    base_pred, base_conf, cau_type, detail = predict_5p_pattern(results)
    loss_streak = count_loss_streak(valid)
    final_pred, final_conf, flipped, flip_reason = apply_auto_flip(
        base_pred, base_conf, loss_streak, results, detail
    )
    NEXT_PREDICTION_CACHE[next_phien] = (final_pred, final_conf, cau_type, flipped, flip_reason)
    if len(NEXT_PREDICTION_CACHE) > 200:
        oldest = min(NEXT_PREDICTION_CACHE.keys())
        del NEXT_PREDICTION_CACHE[oldest]
    return NEXT_PREDICTION_CACHE[next_phien]


def reset_all_databases():
    global LEARNED_PHIEN
    with LEARN_LOCK:
        HASH_DEEP_DB[5].clear()
        for bit in range(128):
            MD5_BIT_DB[bit]["Tài"] = 0
            MD5_BIT_DB[bit]["Xỉu"] = 0
        for ng_size in (2, 3, 4):
            MD5_NGRAM_DB[ng_size].clear()
        MD5_HAMMING_DB.clear()
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
        next_pred, next_conf, next_cau, next_flipped, next_reason = get_stable_next_prediction(valid)

        out = []; correct_count = 0; total_past = 0

        out.append({
            'phien': next_phien, 'is_next': True,
            'prediction': next_pred, 'result': 'Chờ...',
            'dice': "? + ? + ?", 'is_correct': None,
            'conf': next_conf, 'flipped': next_flipped,
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
                        'conf': conf, 'flipped': False})

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count},
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

        base_pred, base_conf, cau_type, detail = predict_5p_pattern(results)
        loss_streak = count_loss_streak(valid)
        final_pred, final_conf, flipped, flip_reason = apply_auto_flip(
            base_pred, base_conf, loss_streak, results, detail
        )

        return jsonify({
            'last_phien': valid[-1]['phien'],
            'next_phien': valid[-1]['phien'] + 1,
            'last_result': valid[-1]['result'],
            'last_dice': valid[-1]['dice'],
            'prediction': final_pred,
            'confidence': final_conf,
            'base_prediction': base_pred,
            'base_confidence': base_conf,
            'flipped': flipped,
            'flip_reason': flip_reason,
            'loss_streak': loss_streak,
            'cau_type': cau_type,
            'stability_score': detail.get('stability_score', 50),
            'recommendation': detail.get('recommendation', 'CAUTION'),
            'total_sessions': len(valid),
            'detail': detail,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =====================================================================
# ★★★ /lc79md5 — CHỈ OUTPUT GỌN ★★★
# =====================================================================
@app.route('/lc79md5')
def lc79md5():
    """Format CHÍNH: chỉ id, phien, ket_qua, du_doan, do_tin_cay."""
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

        base_pred, base_conf, cau_type, detail = predict_5p_pattern(results)
        loss_streak = count_loss_streak(valid)
        final_pred, final_conf, flipped, flip_reason = apply_auto_flip(
            base_pred, base_conf, loss_streak, results, detail
        )

        last = valid[-1]
        dice_parts = last['dice'].split(" + ")
        dice_short = "-".join(dice_parts) if len(dice_parts) == 3 else last['dice']
        next_phien = last['phien'] + 1

        return jsonify({
            'id': '@cskhleminh',
            'phien': str(next_phien),
            'ket_qua': f"{last['result'].lower()} {dice_short}",
            'du_doan': final_pred,
            'do_tin_cay': f"{final_conf}%",
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
        return jsonify({'status': 'error', 'message': 'Lỗi mạng'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
