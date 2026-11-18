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
MAX_CONFIDENCE = 92

LEARNED_PHIEN = 0
LEARN_LOCK = threading.Lock()

# ==================== DB CHIA PHIÊN CŨ (6 TẦNG) ====================
# Tầng 1: Pattern đầy đủ (nhiều độ dài)
PATTERN_DB = {
    L: defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
    for L in (3, 4, 5, 6, 7)
}
# Tầng 2: Hash MD5 salted (nhiều depth)
HASH_DB = {
    d: defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
    for d in (2, 3, 4)
}
# Tầng 3: Cầu type thuần
CAU_DB = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
# Tầng 4: Cầu + hướng phiên đầu
CAU_DIR_DB = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
# Tầng 5: N-gram con (2, 3, 4)
NGRAM_DB = {
    L: defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
    for L in (2, 3, 4)
}
# Tầng 6: Vị trí + giá trị
POS_VAL_DB = {
    pos: defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
    for pos in (0, 1, 2, 3, 4)
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 V22 — CHIA PHIÊN THÔNG MINH</title>
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
    .conf-badge.vip { color: #fbbf24; background: rgba(251, 191, 36, 0.18); box-shadow: 0 0 8px rgba(251,191,36,0.4); }
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
    <div class="header-title">LE MINH <span>V22 SMART</span></div>
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
            let cls = 'conf-badge';
            if (row.conf >= 80) cls = 'conf-badge vip';
            else if (row.conf >= 70) cls = 'conf-badge high';
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

def hash_pattern(tx_string, depth=2):
    """Hash MD5 salted để phân biệt pattern"""
    if not tx_string: return None
    h = hashlib.md5(f"v22_smart_d{depth}|{tx_string}".encode('utf-8')).hexdigest()
    for _ in range(depth - 1):
        h = hashlib.md5(f"{h}|salt{depth}".encode('utf-8')).hexdigest()
    return h[:16]

# =====================================================================
# PHÂN LOẠI CẦU 5P
# =====================================================================
def classify_5p(last5):
    if len(last5) < 5: return None
    groups = get_groups(last5)
    alt = sum(1 for i in range(4) if last5[i] != last5[i+1])

    if alt == 4:
        return {'type': 'ĐẢO', 'groups': groups}
    if len(groups) == 1 and groups[0] == 5:
        return {'type': 'THUẬN', 'groups': groups}
    if len(groups) == 2 and (groups[0] == 4 or groups[1] == 4):
        return {'type': 'THUẬN', 'groups': groups}
    if len(groups) == 3 and (
        (groups[0] == 3 and groups[1] == 1 and groups[2] == 1) or
        (groups[0] == 1 and groups[1] == 1 and groups[2] == 3)
    ):
        return {'type': 'NGHỊCH', 'groups': groups}
    if len(groups) == 2 and (
        (groups[0] == 3 and groups[1] == 2) or
        (groups[0] == 2 and groups[1] == 3)
    ):
        return {'type': 'NGHỊCH', 'groups': groups}
    if len(groups) == 3 and (
        (groups[0] == 2 and groups[1] == 2 and groups[2] == 1) or
        (groups[0] == 1 and groups[1] == 2 and groups[2] == 2) or
        (groups[0] == 2 and groups[1] == 1 and groups[2] == 2)
    ):
        return {'type': '1-1', 'groups': groups}
    if len(groups) == 4 and (groups[0] == 2 or groups[3] == 2):
        return {'type': '1-1', 'groups': groups}
    if len(groups) == 2 and groups[0] == 2 and groups[1] == 2:
        return {'type': '1-1', 'groups': groups}
    return {'type': 'KHÁC', 'groups': groups}


# =====================================================================
# HỌC: CHIA PHIÊN CŨ THEO 6 TẦNG
# =====================================================================
def learn_incremental(valid):
    global LEARNED_PHIEN
    if not valid: return
    with LEARN_LOCK:
        new_indices = [idx for idx, v in enumerate(valid) if v['phien'] > LEARNED_PHIEN]
        if not new_indices: return
        n = len(valid)
        if n <= 7:
            LEARNED_PHIEN = valid[-1]['phien']
            return

        for idx in new_indices:
            if idx < 7: continue

            next_result = valid[idx]['result']

            # ===== TẦNG 1: Pattern đầy đủ nhiều độ dài =====
            for L in (3, 4, 5, 6, 7):
                if idx < L: continue
                history = [v['result'] for v in valid[idx-L:idx]][::-1]
                tx = encode_tx(history, L)
                if tx:
                    PATTERN_DB[L][tx][next_result] += 1

            # ===== TẦNG 2: Hash MD5 salted nhiều depth =====
            for L in (5, 7):
                if idx < L: continue
                history = [v['result'] for v in valid[idx-L:idx]][::-1]
                tx = encode_tx(history, L)
                if not tx: continue
                for depth in (2, 3, 4):
                    h = hash_pattern(tx, depth)
                    if h:
                        HASH_DB[depth][h][next_result] += 1

            # ===== TẦNG 3 + 4: Cầu type + Cầu+hướng =====
            if idx >= 5:
                last5 = [v['result'] for v in valid[idx-5:idx]][::-1]
                cau = classify_5p(last5)
                if cau:
                    CAU_DB[cau['type']][next_result] += 1
                    key_dir = f"{cau['type']}|{last5[0]}"
                    CAU_DIR_DB[key_dir][next_result] += 1

            # ===== TẦNG 5: N-gram con (2, 3, 4) =====
            for L in (2, 3, 4):
                if idx < L: continue
                history = [v['result'] for v in valid[idx-L:idx]][::-1]
                tx = encode_tx(history, L)
                if tx:
                    NGRAM_DB[L][tx][next_result] += 1

            # ===== TẦNG 6: Vị trí + giá trị =====
            for pos in (0, 1, 2, 3, 4):
                if idx < pos + 1: continue
                val = valid[idx-1-pos]['result']  # phiên pos trước đó
                key = f"{val}"
                POS_VAL_DB[pos][key][next_result] += 1

        LEARNED_PHIEN = valid[-1]['phien']


# =====================================================================
# DỰ ĐOÁN — CHIA PHIÊN THÔNG MINH 6 TẦNG
# =====================================================================
def _p_tai_from_counts(counts, min_total=3):
    total = counts["Tài"] + counts["Xỉu"]
    if total < min_total: return None, 0
    p_tai = (counts["Tài"] + 1) / (total + 2)
    return p_tai, total


def _collect_sources(results):
    """Thu thập 6 tầng tín hiệu với trọng số"""
    n = len(results)
    last5 = results[:5]
    cau = classify_5p(last5)
    cau_type = cau['type'] if cau else 'KHÁC'
    sources = []

    # ===== TẦNG 1: Pattern đầy đủ =====
    for L in (3, 4, 5, 6, 7):
        if n < L: continue
        tx = encode_tx(results, L)
        if not tx: continue
        counts = PATTERN_DB[L].get(tx)
        if not counts: continue
        p, total = _p_tai_from_counts(counts, min_total=3)
        if p is not None:
            w = math.sqrt(total) * (1.0 + (L - 3) * 0.15)
            sources.append({'name': f'pattern_{L}', 'p_tai': p, 'total': total, 'weight': w})

    # ===== TẦNG 2: Hash MD5 =====
    for L in (5, 7):
        if n < L: continue
        tx = encode_tx(results, L)
        if not tx: continue
        for depth in (2, 3, 4):
            h = hash_pattern(tx, depth)
            if not h: continue
            counts = HASH_DB[depth].get(h)
            if not counts: continue
            p, total = _p_tai_from_counts(counts, min_total=3)
            if p is not None:
                w = math.sqrt(total) * 1.2 * (1.0 + (L - 5) * 0.1)
                sources.append({'name': f'hash_{L}_{depth}', 'p_tai': p,
                                'total': total, 'weight': w})

    # ===== TẦNG 3: Cầu type =====
    counts = CAU_DB.get(cau_type)
    if counts:
        p, total = _p_tai_from_counts(counts, min_total=8)
        if p is not None:
            w = math.sqrt(total) * 0.8
            sources.append({'name': f'cau_{cau_type}', 'p_tai': p,
                            'total': total, 'weight': w})

    # ===== TẦNG 4: Cầu + hướng =====
    if last5:
        key_dir = f"{cau_type}|{last5[0]}"
        counts = CAU_DIR_DB.get(key_dir)
        if counts:
            p, total = _p_tai_from_counts(counts, min_total=3)
            if p is not None:
                w = math.sqrt(total) * 1.0
                sources.append({'name': f'cau_dir', 'p_tai': p,
                                'total': total, 'weight': w})

    # ===== TẦNG 5: N-gram con =====
    for L in (2, 3, 4):
        if n < L: continue
        tx = encode_tx(results, L)
        if not tx: continue
        counts = NGRAM_DB[L].get(tx)
        if not counts: continue
        p, total = _p_tai_from_counts(counts, min_total=5)
        if p is not None:
            w = math.sqrt(total) * 1.5
            sources.append({'name': f'ngram_{L}', 'p_tai': p,
                            'total': total, 'weight': w})

    # ===== TẦNG 6: Vị trí + giá trị =====
    for pos in (0, 1, 2, 3, 4):
        if n < pos + 1: continue
        val = results[pos]
        counts = POS_VAL_DB[pos].get(val)
        if not counts: continue
        p, total = _p_tai_from_counts(counts, min_total=5)
        if p is not None:
            # Vị trí gần hơn → quan trọng hơn
            pos_weight = 1.0 - pos * 0.1
            w = math.sqrt(total) * 1.3 * pos_weight
            sources.append({'name': f'pos_{pos}_{val}', 'p_tai': p,
                            'total': total, 'weight': w})

    return sources, cau_type, cau


def predict_5p(results):
    n = len(results)
    if n < 5:
        if n == 0: return "Tài", 50, "KHÁC", {}
        if n == 1: return _opp(results[0]), 52, "KHÁC", {}
        if n == 2:
            if results[0] == results[1]: return _opp(results[0]), 54, "KHÁC", {}
            return results[1], 52, "KHÁC", {}
        if n == 3:
            if results[0] == results[1] == results[2]:
                return _opp(results[0]), 55, "KHÁC", {}
            return results[0], 52, "KHÁC", {}
        if n == 4:
            g = get_groups(results)
            if len(g) == 1: return _opp(results[0]), 56, "KHÁC", {}
            if len(g) == 4: return _opp(results[0]), 55, "KHÁC", {}
            return results[0], 52, "KHÁC", {}

    sources, cau_type, cau = _collect_sources(results)

    # Fallback nếu chưa đủ nguồn
    if not sources:
        return _fallback_by_cau(cau_type, results, cau)

    # Weighted average
    total_w = sum(s['weight'] for s in sources)
    p_tai_final = sum(s['p_tai'] * s['weight'] for s in sources) / total_w
    total_samples = sum(s['total'] for s in sources)

    # Z-score
    z = (p_tai_final - 0.5) / math.sqrt(0.25 / (total_samples + 2))

    pred = "Tài" if p_tai_final > 0.5 else "Xỉu"

    # Agreement
    layer_preds = ["Tài" if s['p_tai'] > 0.5 else "Xỉu" for s in sources]
    agree = sum(1 for x in layer_preds if x == pred)

    # ===== CONFIDENCE =====
    strength = abs(p_tai_final - 0.5) * 100
    conf = 50 + strength * 0.9

    # Bonus theo số mẫu tổng
    if total_samples >= 200: conf += 16
    elif total_samples >= 100: conf += 13
    elif total_samples >= 50: conf += 10
    elif total_samples >= 25: conf += 7
    elif total_samples >= 10: conf += 4

    # Bonus z-score
    abs_z = abs(z)
    if abs_z >= 2.5: conf += 12
    elif abs_z >= 2.0: conf += 9
    elif abs_z >= 1.5: conf += 6
    elif abs_z >= 1.0: conf += 3

    # Bonus đồng thuận
    n_src = len(sources)
    if n_src >= 8 and agree >= 7: conf += 10
    elif n_src >= 6 and agree >= 5: conf += 8
    elif n_src >= 4 and agree >= n_src - 1: conf += 6
    elif agree == n_src and n_src >= 2: conf += 4

    # Phạt xung đột mạnh
    disagree = n_src - agree
    if disagree >= 5: conf -= 12
    elif disagree >= 4: conf -= 9
    elif disagree >= 3: conf -= 6

    # Veto: nếu quá nửa phản đối
    if disagree > agree and n_src >= 4:
        conf = min(conf, 58)

    conf = int(max(50, min(MAX_CONFIDENCE, round(conf))))

    detail = {
        'cau_type': cau_type,
        'groups': cau['groups'] if cau else [],
        'n_sources': n_src,
        'agree_count': agree,
        'disagree_count': disagree,
        'total_samples': total_samples,
        'p_tai_final': round(p_tai_final, 3),
        'z': round(z, 2),
        'sources': [
            {'name': s['name'], 'p_tai': round(s['p_tai'], 3),
             'total': s['total'], 'weight': round(s['weight'], 2)}
            for s in sorted(sources, key=lambda x: -x['weight'])[:10]
        ],
    }
    return pred, conf, cau_type, detail


def _fallback_by_cau(cau_type, results, cau):
    if not results: return "Tài", 50, "KHÁC", {'reason': 'empty'}
    last0 = results[0]
    if cau_type == 'ĐẢO':
        return _opp(last0), 58, cau_type, {'reason': 'theory_dao'}
    if cau_type == 'THUẬN':
        groups = cau['groups'] if cau else []
        if len(groups) == 1:
            return _opp(last0), 55, cau_type, {'reason': 'theory_thuan_5'}
        return last0, 56, cau_type, {'reason': 'theory_thuan_41'}
    if cau_type == 'NGHỊCH':
        return _opp(last0), 56, cau_type, {'reason': 'theory_nghich'}
    if cau_type == '1-1':
        return _opp(last0), 55, cau_type, {'reason': 'theory_11'}
    if len(results) >= 2 and results[0] == results[1]:
        return _opp(last0), 53, cau_type, {'reason': 'theory_khac_opp'}
    return last0, 52, cau_type, {'reason': 'theory_khac_follow'}


# =====================================================================
# WRAPPER
# =====================================================================
def get_prediction_for(valid, i):
    key = valid[i]['phien']
    if key in PREDICTION_CACHE: return PREDICTION_CACHE[key]

    hist = [v['result'] for v in valid[:i]][::-1]
    if len(hist) < 5:
        result = ("-", 50, None)
    else:
        pred, conf, _, _ = predict_5p(hist)
        is_correct = (pred == valid[i]['result'])
        result = (pred, conf, is_correct)

    if len(PREDICTION_CACHE) > MAX_PREDICTION_CACHE: PREDICTION_CACHE.clear()
    PREDICTION_CACHE[key] = result
    return result


def get_final_prediction(valid):
    if not valid:
        return {'phien': None, 'prediction': None, 'confidence': 50,
                'cau_type': None, 'detail': {}}
    next_phien = valid[-1]['phien'] + 1
    if next_phien in NEXT_PREDICTION_CACHE:
        return NEXT_PREDICTION_CACHE[next_phien]

    results = [v['result'] for v in valid][::-1]
    pred, conf, cau_type, detail = predict_5p(results)

    result = {'phien': next_phien, 'prediction': pred,
              'confidence': conf, 'cau_type': cau_type, 'detail': detail}
    NEXT_PREDICTION_CACHE[next_phien] = result
    if len(NEXT_PREDICTION_CACHE) > 200:
        oldest = min(NEXT_PREDICTION_CACHE.keys())
        del NEXT_PREDICTION_CACHE[oldest]
    return result


def reset_all_databases():
    global LEARNED_PHIEN
    with LEARN_LOCK:
        for L in (3, 4, 5, 6, 7):
            PATTERN_DB[L].clear()
        for d in (2, 3, 4):
            HASH_DB[d].clear()
        CAU_DB.clear()
        CAU_DIR_DB.clear()
        for L in (2, 3, 4):
            NGRAM_DB[L].clear()
        for pos in (0, 1, 2, 3, 4):
            POS_VAL_DB[pos].clear()
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

        final = get_final_prediction(valid)

        out = []; correct_count = 0; total_past = 0

        out.append({
            'phien': final['phien'], 'is_next': True,
            'prediction': final['prediction'], 'result': 'Chờ...',
            'dice': "? + ? + ?", 'is_correct': None,
            'conf': final['confidence'],
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
                        'conf': conf})

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

        final = get_final_prediction(valid)
        detail = final['detail']

        return jsonify({
            'last_phien': valid[-1]['phien'],
            'next_phien': final['phien'],
            'last_result': valid[-1]['result'],
            'last_dice': valid[-1]['dice'],
            'prediction': final['prediction'],
            'confidence': final['confidence'],
            'cau_type': final['cau_type'],
            'total_sessions': len(valid),
            'detail': detail,
            'timestamp': datetime.now().isoformat()
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

        final = get_final_prediction(valid)

        last = valid[-1]
        dice_parts = last['dice'].split(" + ")
        dice_short = "-".join(dice_parts) if len(dice_parts) == 3 else last['dice']

        return jsonify({
            'id': '@cskhleminh',
            'phien': str(final['phien']),
            'ket_qua': f"{last['result'].lower()} {dice_short}",
            'du_doan': final['prediction'],
            'do_tin_cay': f"{final['confidence']}%",
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def stats_api():
    """Xem trạng thái 6 tầng chia phiên"""
    try:
        return jsonify({
            'pattern_db_sizes': {L: len(PATTERN_DB[L]) for L in (3,4,5,6,7)},
            'hash_db_sizes': {d: len(HASH_DB[d]) for d in (2,3,4)},
            'cau_db': dict(CAU_DB),
            'cau_dir_db_size': len(CAU_DIR_DB),
            'ngram_db_sizes': {L: len(NGRAM_DB[L]) for L in (2,3,4)},
            'pos_val_db_sizes': {p: len(POS_VAL_DB[p]) for p in (0,1,2,3,4)},
            'learned_phien': LEARNED_PHIEN,
            'reset_id': RESET_ID,
        })
    except Exception as e:
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
