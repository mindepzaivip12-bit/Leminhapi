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
MAX_CONFIDENCE = 90

LEARNED_PHIEN = 0
LEARN_LOCK = threading.Lock()

# ==================== DB 5P THUẦN ====================
# Chia kết quả cũ theo key pattern 5P (dạng chuỗi TX)
PATTERN_DB = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
# Chia kết quả cũ theo hash MD5 salted (deep pattern)
HASH_DB = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
# Chia kết quả cũ theo cầu type (ĐẢO/THUẬN/NGHỊCH/1-1/KHÁC)
CAU_DB = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
# Chia theo (cầu_type + hướng phiên trước) để dự đoán next
CAU_DIR_DB = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 V21 — 5P THUẦN</title>
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
    <div class="header-title">LE MINH <span>V21 5P</span></div>
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
    h = hashlib.md5(f"v21_5p_d{depth}|{tx_string}".encode('utf-8')).hexdigest()
    for _ in range(depth - 1):
        h = hashlib.md5(f"{h}|salt{depth}".encode('utf-8')).hexdigest()
    return h[:16]  # Lấy 16 ký tự đủ phân biệt

# =====================================================================
# PHÂN LOẠI CẦU 5P
# =====================================================================
def classify_5p(last5):
    """Trả về (type, groups, hướng)"""
    if len(last5) < 5: return None
    groups = get_groups(last5)
    alt = sum(1 for i in range(4) if last5[i] != last5[i+1])

    # ĐẢO: T-X-T-X-T hoặc X-T-X-T-X
    if alt == 4:
        return {'type': 'ĐẢO', 'groups': groups}

    # THUẬN: 5 liên tiếp hoặc 4-1 / 1-4
    if len(groups) == 1 and groups[0] == 5:
        return {'type': 'THUẬN', 'groups': groups}
    if len(groups) == 2 and (groups[0] == 4 or groups[1] == 4):
        return {'type': 'THUẬN', 'groups': groups}

    # NGHỊCH: 3-1-1 / 1-1-3 / 3-2 / 2-3
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

    # 1-1: 2-2-1 / 1-2-2 / 2-1-2 / 2-2-... / 2-2
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
# HỌC: CHIA KẾT QUẢ CŨ THEO KEY 5P
# =====================================================================
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

        for idx in new_indices:
            if idx < 5: continue

            # Lấy 5 phiên gần nhất (mới nhất first)
            last5 = [v['result'] for v in valid[idx-5:idx]][::-1]
            tx5 = encode_tx(last5, 5)
            if not tx5: continue

            next_result = valid[idx]['result']

            # 1. Chia theo pattern TX chuỗi
            PATTERN_DB[tx5][next_result] += 1

            # 2. Chia theo hash MD5 salted
            h = hash_pattern(tx5, depth=3)
            if h:
                HASH_DB[h][next_result] += 1

            # 3. Chia theo cầu type
            cau = classify_5p(last5)
            if cau:
                CAU_DB[cau['type']][next_result] += 1
                # 4. Chia theo (cầu_type + kết quả phiên đầu của cầu)
                key_dir = f"{cau['type']}|{last5[0]}"
                CAU_DIR_DB[key_dir][next_result] += 1

        LEARNED_PHIEN = valid[-1]['phien']


# =====================================================================
# DỰ ĐOÁN 5P THUẦN — CHIA KẾT QUẢ CŨ
# =====================================================================
def predict_5p(results):
    n = len(results)
    if n < 5:
        # Fallback cơ bản
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

    last5 = results[:5]
    cau = classify_5p(last5)
    cau_type = cau['type']
    groups = cau['groups']
    tx5 = encode_tx(last5, 5)

    # ==== CHIA KẾT QUẢ CŨ — 3 NGUỒN ====
    pat_counts = PATTERN_DB.get(tx5, {"Tài": 0, "Xỉu": 0})
    h_key = hash_pattern(tx5, depth=3)
    hash_counts = HASH_DB.get(h_key, {"Tài": 0, "Xỉu": 0})
    cau_counts = CAU_DB.get(cau_type, {"Tài": 0, "Xỉu": 0})
    key_dir = f"{cau_type}|{last5[0]}"
    cau_dir_counts = CAU_DIR_DB.get(key_dir, {"Tài": 0, "Xỉu": 0})

    pat_total = pat_counts["Tài"] + pat_counts["Xỉu"]
    hash_total = hash_counts["Tài"] + hash_counts["Xỉu"]
    cau_total = cau_counts["Tài"] + cau_counts["Xỉu"]
    cau_dir_total = cau_dir_counts["Tài"] + cau_dir_counts["Xỉu"]

    # ==== TÍNH P(TÀI) TỪNG NGUỒN (Laplace smoothing) ====
    def _p_tai(counts, total):
        if total == 0: return 0.5, 0
        return (counts["Tài"] + 1) / (total + 2), total

    p_pat, t_pat = _p_tai(pat_counts, pat_total)
    p_hash, t_hash = _p_tai(hash_counts, hash_total)
    p_cau, t_cau = _p_tai(cau_counts, cau_total)
    p_dir, t_dir = _p_tai(cau_dir_counts, cau_dir_total)

    # ==== GOM TRỌNG SỐ THEO SỐ MẪU ====
    # Nguồn nào có nhiều mẫu hơn → tin hơn
    sources = []
    if t_pat >= 3: sources.append((p_pat, t_pat, 'pattern'))
    if t_hash >= 3: sources.append((p_hash, t_hash, 'hash'))
    if t_cau >= 5: sources.append((p_cau, t_cau, 'cau'))
    if t_dir >= 3: sources.append((p_dir, t_dir, 'cau_dir'))

    if not sources:
        # Không đủ mẫu → fallback theo lý thuyết cầu
        return _fallback_by_cau(cau_type, last5, cau, groups)

    # Weighted average theo sqrt(số mẫu)
    total_w = 0.0
    weighted_p_tai = 0.0
    for p, t, name in sources:
        w = math.sqrt(t)
        weighted_p_tai += p * w
        total_w += w
    p_tai_final = weighted_p_tai / total_w

    # ==== Z-SCORE cho độ tin cậy ====
    total_samples = sum(t for _, t, _ in sources)
    z = (p_tai_final - 0.5) / math.sqrt(0.25 / (total_samples + 2))

    pred = "Tài" if p_tai_final > 0.5 else "Xỉu"

    # ==== CONFIDENCE ====
    # Base: 50 + strength
    strength = abs(p_tai_final - 0.5) * 100  # 0-50
    conf = 50 + strength * 0.8

    # Bonus theo số mẫu
    if total_samples >= 50: conf += 15
    elif total_samples >= 30: conf += 12
    elif total_samples >= 20: conf += 9
    elif total_samples >= 10: conf += 6
    elif total_samples >= 5: conf += 3

    # Bonus theo z-score
    abs_z = abs(z)
    if abs_z >= 2.5: conf += 12
    elif abs_z >= 2.0: conf += 9
    elif abs_z >= 1.5: conf += 6
    elif abs_z >= 1.0: conf += 3

    # Bonus khi nhiều nguồn đồng thuận
    preds = []
    for p, t, name in sources:
        preds.append("Tài" if p > 0.5 else "Xỉu")
    agree = sum(1 for x in preds if x == pred)
    if agree >= 3: conf += 6
    elif agree == len(preds) and len(preds) >= 2: conf += 4

    # Phạt khi xung đột
    if agree < len(preds) / 2 + 0.5:
        conf -= 8

    conf = int(max(50, min(MAX_CONFIDENCE, round(conf))))

    detail = {
        'cau_type': cau_type,
        'groups': groups,
        'tx5': tx5,
        'sources': {
            'pattern': {'p_tai': round(p_pat, 3), 'total': t_pat},
            'hash': {'p_tai': round(p_hash, 3), 'total': t_hash},
            'cau': {'p_tai': round(p_cau, 3), 'total': t_cau},
            'cau_dir': {'p_tai': round(p_dir, 3), 'total': t_dir},
        },
        'p_tai_final': round(p_tai_final, 3),
        'z': round(z, 2),
        'total_samples': total_samples,
        'agree_count': agree,
        'n_sources': len(sources),
    }
    return pred, conf, cau_type, detail


def _fallback_by_cau(cau_type, last5, cau, groups):
    """Khi chưa có dữ liệu — dùng lý thuyết cầu"""
    if cau_type == 'ĐẢO':
        return _opp(last5[0]), 58, cau_type, {'reason': 'theory_dao'}
    if cau_type == 'THUẬN':
        # Bệt 5 → theo lý thuyết thường gãy
        if len(groups) == 1:
            return _opp(last5[0]), 55, cau_type, {'reason': 'theory_thuan_5'}
        # 4-1 → theo hướng mới (phiên đầu)
        return last5[0], 56, cau_type, {'reason': 'theory_thuan_41'}
    if cau_type == 'NGHỊCH':
        return _opp(last5[0]), 56, cau_type, {'reason': 'theory_nghich'}
    if cau_type == '1-1':
        return _opp(last5[0]), 55, cau_type, {'reason': 'theory_11'}
    # KHÁC
    if len(last5) >= 2 and last5[0] == last5[1]:
        return _opp(last5[0]), 53, cau_type, {'reason': 'theory_khac_opp'}
    return last5[0], 52, cau_type, {'reason': 'theory_khac_follow'}


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
        PATTERN_DB.clear()
        HASH_DB.clear()
        CAU_DB.clear()
        CAU_DIR_DB.clear()
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
    """Xem trạng thái 4 DB chia kết quả"""
    try:
        return jsonify({
            'pattern_db_size': len(PATTERN_DB),
            'hash_db_size': len(HASH_DB),
            'cau_db': dict(CAU_DB),
            'cau_dir_db_size': len(CAU_DIR_DB),
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
