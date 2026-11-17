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
MAX_CONFIDENCE = 88

LEARNED_PHIEN = 0
LEARN_LOCK = threading.Lock()

# Chỉ giữ DB cho 5P hash-deep
HASH_DEEP_DB = {
    5: defaultdict(lambda: {"Tài": 0, "Xỉu": 0}),
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 V12</title>
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
    .row-next.recovery { background: rgba(251, 146, 60, 0.1); border-left: 4px solid var(--recovery-color); }
    .badge { display: inline-block; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; min-width: 70px; text-align: center; }
    .badge-tai { background: var(--tai-bg); color: var(--tai-color); border: 1px solid rgba(56, 189, 248, 0.3); }
    .badge-xiu { background: var(--xiu-bg); color: var(--xiu-color); border: 1px solid rgba(244, 114, 182, 0.3); }
    .badge-empty { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); }
    .recovery-badge { display: inline-block; margin-left: 6px; padding: 2px 8px; border-radius: 8px; font-size: 10px; font-weight: 800; background: var(--recovery-bg); color: var(--recovery-color); border: 1px solid var(--recovery-color); }
    .status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; padding: 6px 14px; border-radius: 20px; }
    .st-win { background: var(--win-bg); color: var(--win-color); }
    .st-lose { background: var(--lose-bg); color: var(--lose-color); }
    .st-wait { background: var(--wait-bg); color: var(--wait-color); animation: pulse 1.5s infinite; }
    .st-recover { background: var(--recovery-bg); color: var(--recovery-color); animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .dice-text { font-size: 11px; color: var(--text-muted); display: block; margin-top: 4px; }
    .conf-badge { font-size: 11px; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 2px 8px; border-radius: 10px; margin-top: 4px; display: inline-block; font-weight: 700; }
    .conf-badge.high { color: #34d399; background: rgba(52, 211, 153, 0.15); }
    .cau-badge { font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 8px; margin-top: 4px; display: inline-block; letter-spacing: 0.3px; }
    .cau-dao { background: rgba(251, 146, 60, 0.2); color: #fb923c; }
    .cau-thuan { background: rgba(52, 211, 153, 0.2); color: #34d399; }
    .cau-nghich { background: rgba(244, 114, 182, 0.2); color: #f472b6; }
    .cau-11 { background: rgba(56, 189, 248, 0.2); color: #38bdf8; }
    .cau-none { background: rgba(148, 163, 184, 0.15); color: #94a3b8; }
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
    <div class="header-title">LE MINH <span>V12</span></div>
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
function getCauClass(type) {
    if (!type) return 'cau-none';
    const t = type.toLowerCase();
    if (t.includes('đảo') || t.includes('dao')) return 'cau-dao';
    if (t.includes('thuận') || t.includes('thuan')) return 'cau-thuan';
    if (t.includes('nghịch') || t.includes('nghich')) return 'cau-nghich';
    if (t.includes('1-1')) return 'cau-11';
    return 'cau-none';
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
        let trClass = '';
        if (row.is_next) trClass = row.recovery_flipped ? 'class="row-next recovery"' : 'class="row-next"';
        let predHtml = `<span class="badge badge-empty">-</span>`;
        if (row.prediction === "Tài") predHtml = `<span class="badge badge-tai">TÀI</span>`;
        if (row.prediction === "Xỉu") predHtml = `<span class="badge badge-xiu">XỈU</span>`;
        let recBadge = row.recovery_flipped ? `<span class="recovery-badge">⚡</span>` : "";
        let confHtml = "";
        if (row.conf && row.prediction !== "-") {
            const cls = row.conf >= 70 ? 'conf-badge high' : 'conf-badge';
            confHtml = `<div class="${cls}">${row.conf}%</div>`;
        }
        let cauHtml = "";
        if (row.cau_type) {
            cauHtml = `<div class="cau-badge ${getCauClass(row.cau_type)}">${row.cau_type}</div>`;
        }
        let predFull = `<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">${predHtml}${confHtml}${cauHtml}${recBadge}</div>`;
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
        if (row.is_next) {
            statusHtml = row.recovery_flipped ? `<span class="status st-recover">⚡ Đảo chiều</span>` : `<span class="status st-wait">Chờ kết quả</span>`;
        } else if (row.is_correct === true) statusHtml = `<span class="status st-win">✔ THẮNG</span>`;
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
# CÁC HÀM CƠ BẢN
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

def learn_incremental(valid):
    """Chỉ học 5P hash-deep."""
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
        LEARNED_PHIEN = valid[-1]['phien']

# =====================================================================
# ★★★ V12 CORE: 5P PATTERN ENGINE ★★★
# =====================================================================
def classify_5p_pattern(last5):
    """
    Phân loại 5 phiên gần nhất thành 4 cầu:
    - ĐẢO: 5 phiên xen kẽ hoàn toàn (T-X-T-X-T hoặc X-T-X-T-X)
    - THUẬN: 5 phiên cùng loại (T-T-T-T-T hoặc X-X-X-X-X)
              hoặc 4-1 với 4 phiên đầu giống nhau
    - NGHỊCH: 3-1-1 / 1-1-3 / 3-2 (cầu đổi hướng)
    - 1-1: 2-2-1 / 1-2-2 / 2-1-2 (zigzag 2 phiên)
    """
    if len(last5) < 5:
        return None
    groups = get_groups(last5)
    alt_count = sum(1 for i in range(4) if last5[i] != last5[i+1])

    # ĐẢO: xen kẽ hoàn toàn
    if alt_count == 4:
        return {'type': 'ĐẢO', 'groups': groups, 'alt': alt_count}

    # THUẬN: 5-0
    if len(groups) == 1 and groups[0] == 5:
        return {'type': 'THUẬN', 'groups': groups, 'alt': alt_count}

    # THUẬN 4-1
    if len(groups) == 2 and (groups[0] == 4 or groups[1] == 4):
        return {'type': 'THUẬN', 'groups': groups, 'alt': alt_count}

    # NGHỊCH: 3-1-1 / 1-1-3 / 3-2
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

    # 1-1: 2-2-1 / 1-2-2 / 2-1-2 / 2-2-1
    if len(groups) == 3 and (
        (groups[0] == 2 and groups[1] == 2 and groups[2] == 1) or
        (groups[0] == 1 and groups[1] == 2 and groups[2] == 2) or
        (groups[0] == 2 and groups[1] == 1 and groups[2] == 2)
    ):
        return {'type': '1-1', 'groups': groups, 'alt': alt_count}

    # 1-1 mở rộng: 2-1-1-1 (4 groups)
    if len(groups) == 4 and (groups[0] == 2 or groups[3] == 2):
        return {'type': '1-1', 'groups': groups, 'alt': alt_count}

    # Fallback: 2-2 (nếu chỉ có 4 phiên khớp) hoặc không xác định
    if len(groups) == 2 and groups[0] == 2 and groups[1] == 2:
        return {'type': '1-1', 'groups': groups, 'alt': alt_count}

    return {'type': 'KHÁC', 'groups': groups, 'alt': alt_count}


def lookup_pattern_stats(results, key_len, key_tuple, max_scan=80):
    """Tra cứu pattern trong lịch sử, trả (p_tai, total_seen, z)."""
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
    """Tra MD5 hash-deep 5P, trả (pred, total, z, p_tai)."""
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


def predict_5p_pattern(results):
    """
    ★ THUẬT TOÁN CHÍNH V12 ★
    Chỉ dùng 5 phiên gần nhất + hash-deep 5P xác nhận.
    Trả (pred, conf, cau_type, detail).

    Logic:
    1. Phân loại cầu 5P (ĐẢO/THUẬN/NGHỊCH/1-1)
    2. Tra pattern stats trong lịch sử
    3. Tra hash-deep 5P
    4. Kết hợp: pattern + hash → quyết định cuối
    5. KHÔNG nghiêng 1 phiên: nếu 2 nguồn ngược nhau → conf thấp
    """
    n = len(results)
    if n < 5:
        # Không đủ dữ liệu → dùng heuristic nhẹ
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
    pattern = classify_5p_pattern(last5)
    cau_type = pattern['type']
    groups = pattern['groups']
    alt = pattern['alt']

    # ===== Tra pattern stats =====
    key_tuple = tuple(last5)
    p_tai_pat, total_pat, z_pat = lookup_pattern_stats(results, 5, key_tuple)

    # ===== Tra hash-deep 5P =====
    hash_result = lookup_hash_deep_5p(results)

    # ===== Quyết định theo từng loại cầu =====
    pred = None
    conf = 50
    reason = ""

    # ====== ĐẢO ======
    if cau_type == 'ĐẢO':
        # Lý thuyết: đảo → phiên tiếp theo đảo tiếp
        theory_pred = _opp(last5[0])
        if total_pat >= 5 and abs(z_pat) >= 0.8:
            data_pred = "Tài" if p_tai_pat > 0.5 else "Xỉu"
            if data_pred == theory_pred:
                pred = data_pred
                conf = 60 + min(20, abs(z_pat) * 10)
                reason = f"dao_data_{total_pat}"
            else:
                # Data ngược lý thuyết → giảm conf
                pred = data_pred
                conf = 55 + min(10, abs(z_pat) * 6)
                reason = f"dao_data_conflict_{total_pat}"
        else:
            pred = theory_pred
            conf = 58
            reason = "dao_theory"

    # ====== THUẬN ======
    elif cau_type == 'THUẬN':
        current = last5[0]
        if len(groups) == 1:
            # 5-0: kiểm tra lịch sử chuỗi 5 cùng loại
            cont = brk = 0
            for i in range(min(n - 5, 80)):
                if all(results[i+j] == current for j in range(5)):
                    if i + 5 < n:
                        if results[i+5] == current: cont += 1
                        else: brk += 1
            total_streak = cont + brk
            if total_streak >= 5:
                p_cont = (cont + 1) / (total_streak + 2)
                z_cont = (p_cont - 0.5) / math.sqrt(0.25 / (total_streak + 2))
                if abs(z_cont) >= 0.8:
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
        else:
            # 4-1: ưu tiên phiên cuối (đang là 1)
            # Nhưng không nghiêng: nếu 1 ở đầu (4 cuối giống nhau) → theo nhóm 4
            if groups[0] == 4:
                # 4 phiên đầu giống, phiên cuối khác → xu hướng tiếp tục nhóm 4
                pred = last5[0]; conf = 56; reason = "thuan_4_1_head"
            else:
                # 1 đầu, 4 cuối giống → phiên cuối đang break
                pred = last5[0]; conf = 55; reason = "thuan_4_1_tail"

    # ====== NGHỊCH ======
    elif cau_type == 'NGHỊCH':
        # Nghịch: đổi hướng → phiên tiếp theo thường đảo so với phiên cuối
        theory_pred = _opp(last5[0])
        if total_pat >= 5 and abs(z_pat) >= 0.8:
            data_pred = "Tài" if p_tai_pat > 0.5 else "Xỉu"
            if data_pred == theory_pred:
                pred = data_pred
                conf = 58 + min(18, abs(z_pat) * 9)
                reason = f"nghich_data_{total_pat}"
            else:
                pred = data_pred
                conf = 54 + min(10, abs(z_pat) * 6)
                reason = f"nghich_data_conflict_{total_pat}"
        else:
            pred = theory_pred; conf = 56; reason = "nghich_theory"

    # ====== 1-1 ======
    elif cau_type == '1-1':
        # 1-1 zigzag 2 phiên → phiên tiếp theo đảo
        theory_pred = _opp(last5[0])
        if total_pat >= 5 and abs(z_pat) >= 0.8:
            data_pred = "Tài" if p_tai_pat > 0.5 else "Xỉu"
            if data_pred == theory_pred:
                pred = data_pred
                conf = 57 + min(17, abs(z_pat) * 8)
                reason = f"11_data_{total_pat}"
            else:
                pred = data_pred
                conf = 54 + min(10, abs(z_pat) * 6)
                reason = f"11_data_conflict_{total_pat}"
        else:
            pred = theory_pred; conf = 55; reason = "11_theory"

    # ====== KHÁC ======
    else:
        # Pattern không xác định → dùng pattern stats + hash
        if total_pat >= 5 and abs(z_pat) >= 1.0:
            pred = "Tài" if p_tai_pat > 0.5 else "Xỉu"
            conf = 55 + min(15, abs(z_pat) * 8)
            reason = f"khac_data_{total_pat}"
        else:
            # fallback nhẹ
            if n >= 2 and results[0] == results[1]:
                pred = _opp(results[0]); conf = 53; reason = "khac_fallback_streak"
            else:
                pred = results[0]; conf = 51; reason = "khac_fallback_follow"

    # ====== HASH-DEEP 5P XÁC NHẬN ======
    hash_info = {}
    if hash_result:
        h_pred, h_total, h_z, h_p_tai = hash_result
        hash_info = {'pred': h_pred, 'total': h_total, 'z': round(h_z, 2)}

        if h_total >= 5 and abs(h_z) >= 1.0:
            if h_pred == pred:
                # Hash đồng thuận → tăng conf vừa phải
                conf += min(8, abs(h_z) * 3)
                reason += "+hash_agree"
            else:
                # Hash ngược → giảm conf, KHÔNG đảo pred
                conf -= min(10, abs(h_z) * 4)
                reason += "+hash_conflict"

    # ====== GUARD CHỐNG NGHIÊNG 1 PHIÊN ======
    # Nếu chỉ có 1 nguồn (pattern only) → conf tối đa 62
    # Nếu 2 nguồn đồng thuận → conf tối đa 82
    # Nếu 2 nguồn xung đột → conf tối đa 58
    if hash_result and hash_info.get('pred') != pred:
        conf = min(conf, 58)
    elif not hash_result:
        conf = min(conf, 62)
    else:
        conf = min(conf, 82)

    # Không quá tự tin khi data ít
    if total_pat < 8:
        conf = min(conf, 68)

    conf = int(max(50, min(MAX_CONFIDENCE, round(conf))))

    detail = {
        'cau_type': cau_type,
        'groups': groups,
        'pattern_total': total_pat,
        'pattern_p_tai': round(p_tai_pat, 3),
        'pattern_z': round(z_pat, 2),
        'hash_info': hash_info,
        'reason': reason,
    }

    return pred, conf, cau_type, detail


# =====================================================================
# RECOVERY — đơn giản, dựa trên loss streak
# =====================================================================
def compute_loss_streak(valid, max_scan=8):
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


def apply_recovery(base_pred, conf, loss_streak, results=None):
    """
    Recovery đơn giản:
    - loss 0-1: giữ nguyên
    - loss 2: giữ, conf -5
    - loss 3: flip, conf 70
    - loss 4+: flip, conf 75
    """
    if loss_streak < 2:
        return base_pred, conf, False, None
    if loss_streak == 2:
        return base_pred, max(50, conf - 5), False, "hold_2"
    if loss_streak == 3:
        return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 70)), True, "flip_3"
    return _opp(base_pred), min(MAX_CONFIDENCE, max(conf, 75)), True, "flip_4plus"


def get_stable_next_prediction(valid):
    if not valid:
        return None, 50, False, None, None
    next_phien = valid[-1]['phien'] + 1
    if next_phien in NEXT_PREDICTION_CACHE:
        return NEXT_PREDICTION_CACHE[next_phien]
    results = [v['result'] for v in valid][::-1]
    loss_streak = compute_loss_streak(valid)
    base_pred, base_conf, cau_type, _ = predict_5p_pattern(results)
    pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak, results)
    NEXT_PREDICTION_CACHE[next_phien] = (pred, conf, flipped, reason, base_pred, cau_type)
    if len(NEXT_PREDICTION_CACHE) > 200:
        oldest = min(NEXT_PREDICTION_CACHE.keys())
        del NEXT_PREDICTION_CACHE[oldest]
    return NEXT_PREDICTION_CACHE[next_phien]


def reset_all_databases():
    global LEARNED_PHIEN
    with LEARN_LOCK:
        HASH_DEEP_DB[5].clear()
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
            next_pred, next_conf, flipped, reason, base_pred, cau_type = cached_next
        else:
            results_now = [v['result'] for v in valid][::-1]
            ls_now = compute_loss_streak(valid)
            bp, bc, ct, _ = predict_5p_pattern(results_now)
            next_pred, next_conf, flipped, reason = apply_recovery(bp, bc, ls_now, results_now)
            base_pred = bp
            cau_type = ct
            NEXT_PREDICTION_CACHE[next_phien] = (next_pred, next_conf, flipped, reason, bp, ct)

        loss_streak = compute_loss_streak(valid)
        out = []; correct_count = 0; total_past = 0

        out.append({
            'phien': next_phien, 'is_next': True,
            'prediction': next_pred, 'result': 'Chờ...',
            'dice': "? + ? + ?", 'is_correct': None,
            'conf': next_conf, 'recovery_flipped': flipped,
            'cau_type': cau_type,
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
            # Lấy cầu type cho phiên đó (dùng history trước nó)
            hist = [v['result'] for v in valid[:i]][::-1]
            cau_type_hist = None
            if len(hist) >= 5:
                ct_info = classify_5p_pattern(hist[:5])
                cau_type_hist = ct_info['type'] if ct_info else None
            out.append({'phien': current_session['phien'], 'is_next': False,
                        'prediction': pred, 'result': current_session['result'],
                        'dice': current_session['dice'], 'is_correct': is_correct,
                        'conf': conf, 'recovery_flipped': False,
                        'cau_type': cau_type_hist})

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
        base_pred, base_conf, cau_type, detail = predict_5p_pattern(results)
        pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak, results)

        return jsonify({
            'last_phien': valid[-1]['phien'], 'next_phien': valid[-1]['phien'] + 1,
            'last_result': valid[-1]['result'], 'last_dice': valid[-1]['dice'],
            'prediction': pred, 'confidence': conf,
            'cau_type': cau_type,
            'base_prediction': base_pred, 'base_confidence': base_conf,
            'recovery_flipped': flipped, 'recovery_reason': reason,
            'loss_streak': loss_streak, 'total_sessions': len(valid),
            'detail': detail,
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
        base_pred, base_conf, cau_type, detail = predict_5p_pattern(results)
        pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak, results)

        last = valid[-1]; next_phien = last['phien'] + 1
        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])

        return jsonify({
            'Id': 'le minh md5 v12',
            'Phien': str(next_phien),
            'Ket_qua': last['result'].lower(),
            'Lich_su': lich_su,
            'Du_doan': pred,
            'Do_tin_cay': f"{conf}%",
            'Cau_5P': cau_type,
            'Cau_5P_Detail': detail.get('reason', ''),
            'Base_du_doan': base_pred if flipped else None,
            'Auto_flip': flipped,
            'Chuoi_thua': loss_streak,
            'Recovery_reason': reason,
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
        base_pred, base_conf, cau_type, detail = predict_5p_pattern(results)
        pred, conf, flipped, reason = apply_recovery(base_pred, base_conf, loss_streak, results)

        last = valid[-1]
        dice_parts = last['dice'].split(" + ")
        dice_short = "-".join(dice_parts) if len(dice_parts) == 3 else last['dice']
        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])
        next_phien = last['phien'] + 1

        return jsonify({
            'id': '@cskhleminh v12', 'phien': str(next_phien),
            'ket_qua': f"{last['result'].lower()} {dice_short}",
            'du_doan': pred, 'do_tin_cay': f"{conf}%",
            'lich_su': lich_su,
            'cau_5p': cau_type,
            'cau_5p_detail': detail.get('reason', ''),
            'base_du_doan': base_pred if flipped else None,
            'auto_flip': flipped, 'chuoi_thua': loss_streak,
            'recovery_reason': reason,
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
