import os
from datetime import datetime
from collections import defaultdict, Counter
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
# CORE UTILS
# =====================================================================
def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"


def format_tx(results, length):
    if len(results) < length:
        return None
    return "-".join("T" if r == "Tài" else "X" for r in results[:length])


# =====================================================================
# THUẬT TOÁN NÂNG CẤP - MULTI-LAYER SCORING
# =====================================================================

def _streak_info(results):
    """Trả về (value, length) của chuỗi bệt hiện tại (mới nhất)."""
    if not results:
        return None, 0
    cur = results[0]
    length = 1
    for r in results[1:]:
        if r == cur:
            length += 1
        else:
            break
    return cur, length


def _markov_next(results, window=40):
    """
    Markov bậc 1 trên `window` phiên gần nhất.
    Trả về (prediction, prob) hoặc None nếu chưa đủ data.
    """
    seq = results[:window]
    if len(seq) < 6:
        return None
    trans = Counter()
    for i in range(len(seq) - 1):
        trans[(seq[i], seq[i + 1])] += 1
    cur_state = seq[0]
    total_from = sum(c for (a, b), c in trans.items() if a == cur_state)
    if total_from == 0:
        return None
    p_tai = trans.get((cur_state, "Tài"), 0) / total_from
    p_xiu = trans.get((cur_state, "Xỉu"), 0) / total_from
    if p_tai >= p_xiu:
        return ("Tài", p_tai)
    return ("Xỉu", p_xiu)


def _pattern_score(results):
    """
    Chấm điểm pattern đa tầng. Trả về list các (prediction, weight, label).
    weight = 0..1 (độ mạnh pattern).
    """
    hits = []
    if len(results) < 5:
        return hits

    last5 = results[:5]
    cur, slen = _streak_info(results)

    # 1) BỆT (streak)
    if slen >= 6:
        hits.append((cur, 0.92, f"Bệt cực mạnh {slen}P"))
    elif slen == 5:
        hits.append((cur, 0.86, "Bệt 5P"))
    elif slen == 4:
        hits.append((cur, 0.78, "Bệt 4P"))
    elif slen == 3:
        hits.append((cur, 0.68, "Bệt 3P"))

    # 2) ĐẢO 1-1
    alt5 = sum(1 for i in range(4) if last5[i] != last5[i + 1])
    if alt5 == 4:
        hits.append((_opp(last5[0]), 0.80, "Đảo 1-1 (5P)"))
        if len(results) >= 8:
            last8 = results[:8]
            alt8 = sum(1 for i in range(7) if last8[i] != last8[i + 1])
            if alt8 >= 6:
                hits.append((_opp(last5[0]), 0.88, "Đảo 1-1 mạnh (8P)"))

    # 3) CẦU 2-2 (T T X X T T ...)
    if len(results) >= 5:
        # T T X X -> phiên tiếp nên cùng với X (đang 2-2)
        if last5[0] == last5[1] and last5[2] == last5[3] and last5[0] != last5[2]:
            # nếu 4 phiên đầu đã đối lập -> phiên 5 nên đảo (bắt đầu chu kỳ mới)
            hits.append((_opp(last5[0]), 0.70, "Cầu 2-2"))

    # 4) CẦU 1-2-1 / 2-1-2 (nhịp đối xứng)
    if len(results) >= 5:
        if last5[0] != last5[1] and last5[1] == last5[2] and last5[2] != last5[3] and last5[3] == last5[4]:
            # X T T X X -> pattern đối xứng
            hits.append((_opp(last5[0]), 0.66, "Cầu 1-2-2-1"))

    # 5) BẺ CẦU: đang bệt 2-3 mà phiên cuối lệch
    if slen == 1 and len(results) >= 4:
        # phiên mới nhất lệch so với 3 phiên trước (vừa gãy bệt)
        if results[1] == results[2] == results[3] and results[0] != results[1]:
            # xu hướng tiếp tục theo phiên mới (đảo)
            hits.append((results[0], 0.62, "Gãy bệt (theo mới)"))
            # hoặc quay lại bệt (nghịch)
            hits.append((results[1], 0.58, "Hồi bệt"))

    return hits


def _majority_score(results, window=15):
    """Đa số trong window phiên gần nhất."""
    seq = results[:window]
    if not seq:
        return None
    t = seq.count("Tài")
    x = len(seq) - t
    total = len(seq)
    if t > x:
        return ("Tài", t / total)
    elif x > t:
        return ("Xỉu", x / total)
    return None


def compute_prediction(results):
    """
    Kết hợp đa tầng: Pattern + Markov + Majority.
    Trả về (prediction, confidence, pattern_label).
    """
    if not results:
        return ("Tài", 50, "Chưa có dữ liệu")

    # Chưa đủ data -> đa số đơn giản
    if len(results) < 5:
        t = results.count("Tài")
        x = len(results) - t
        if t > x:
            return ("Tài", 55, "Đa số ngắn hạn")
        elif x > t:
            return ("Xỉu", 55, "Đa số ngắn hạn")
        return (results[0], 52, "Theo phiên mới")

    # Thu thập các tín hiệu
    signals = []  # list[(prediction, score, label)]
    pattern_label = "-"

    # 1) Pattern (weight cao nhất)
    pattern_hits = _pattern_score(results)
    if pattern_hits:
        # Chọn pattern có weight cao nhất
        best = max(pattern_hits, key=lambda x: x[1])
        signals.append((best[0], best[1] * 3.0, best[2]))
        pattern_label = best[2]
        # Cộng thêm các pattern phụ cùng chiều
        for p in pattern_hits:
            if p[0] == best[0] and p[1] < best[1]:
                signals.append((p[0], p[1] * 1.0, p[2]))

    # 2) Markov
    mk = _markov_next(results, window=40)
    if mk:
        pred_mk, prob_mk = mk
        # chỉ dùng nếu prob đủ cao (>0.55)
        if prob_mk >= 0.55:
            signals.append((pred_mk, (prob_mk - 0.5) * 4.0, "Markov"))

    # 3) Majority (weight thấp - chỉ để cân bằng)
    mj = _majority_score(results, window=15)
    if mj:
        pred_mj, ratio_mj = mj
        if ratio_mj >= 0.55:
            signals.append((pred_mj, (ratio_mj - 0.5) * 2.0, "Đa số 15P"))

    # Nếu không có tín hiệu -> fallback theo phiên mới
    if not signals:
        return (results[0], 52, "Không tín hiệu (theo mới)")

    # Tổng hợp: weighted vote
    score_tai = 0.0
    score_xiu = 0.0
    for pred, w, _ in signals:
        if pred == "Tài":
            score_tai += w
        else:
            score_xiu += w

    total_w = score_tai + score_xiu
    if total_w == 0:
        return (results[0], 52, "Hòa tín hiệu")

    if score_tai >= score_xiu:
        pred = "Tài"
        raw_conf = score_tai / total_w
    else:
        pred = "Xỉu"
        raw_conf = score_xiu / total_w

    # Map raw_conf (0.5..1.0) -> confidence (52..90)
    conf = 52 + (raw_conf - 0.5) * 2 * (MAX_CONFIDENCE - 52)
    conf = int(max(52, min(MAX_CONFIDENCE, round(conf))))

    return (pred, conf, pattern_label)


# =====================================================================
# API & ROUTES
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


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if raw_rows:
            for row in raw_rows:
                HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
                del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0}})

        out = []
        correct_count = 0
        total_past = 0
        history_for_next = [v['result'] for v in valid][::-1]

        next_pred, next_conf, _ = compute_prediction(history_for_next)

        out.append({
            'phien': valid[-1]['phien'] + 1,
            'is_next': True,
            'prediction': next_pred,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None,
            'conf': next_conf,
            'recovery_flipped': False,
            'loss_streak': 0
        })

        for i in range(len(valid) - 1, max(-1, len(valid) - 150), -1):
            hist = [v['result'] for v in valid[:i]][::-1]
            if len(hist) >= 3:
                pred, conf, _ = compute_prediction(hist)
            elif len(hist) > 0:
                t = hist.count("Tài")
                x = len(hist) - t
                if t > x:
                    pred, conf = "Tài", 55
                elif x > t:
                    pred, conf = "Xỉu", 55
                else:
                    pred, conf = hist[0], 52
            else:
                pred, conf = "-", 50

            is_correct = (pred == valid[i]['result']) if pred != "-" else None
            if is_correct is not None:
                total_past += 1
            if is_correct:
                correct_count += 1

            out.append({
                'phien': valid[i]['phien'],
                'is_next': False,
                'prediction': pred,
                'result': valid[i]['result'],
                'dice': valid[i]['dice'],
                'is_correct': is_correct,
                'conf': conf,
                'recovery_flipped': False
            })

        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e), 'rows': [], 'stats': {'total': 0, 'correct': 0}})


@app.route('/api/predict')
def predict():
    global RESET_ID
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            for row in raw_rows:
                HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
                del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'})

        results = [v['result'] for v in valid][::-1]
        pred, conf, pattern_label = compute_prediction(results)

        ls_5p = format_tx(results, 5)

        return jsonify({
            'last_phien': valid[-1]['phien'],
            'next_phien': valid[-1]['phien'] + 1,
            'prediction': pred,
            'confidence': conf,
            'recovery_flipped': False,
            'loss_streak': 0,
            'ls_5p': ls_5p,
            'pattern_label': pattern_label,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/lc79')
@app.route('/lc79md5')
def lc79_api():
    """API đồng bộ output với /api/predict."""
    global RESET_ID
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            for row in raw_rows:
                HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
                del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'id': '@cskhleminh', 'phien': '-', 'du_doan': '-', 'do_tin_cay': '50%'})

        results = [v['result'] for v in valid][::-1]
        pred, conf, pattern_label = compute_prediction(results)
        ls_5p = format_tx(results, 5)

        return jsonify({
            'id': '@cskhleminh',
            'phien': str(valid[-1]['phien'] + 1),
            'ket_qua': f"{valid[-1]['result'].lower()} {valid[-1]['dice'].replace(' + ', '-')}",
            'du_doan': pred,
            'do_tin_cay': f"{conf}%",
            'ls_5p': ls_5p,
            'cau': pattern_label,
            'auto_flip': False,
            'chuoi_thua': 0
        })
    except Exception as e:
        return jsonify({'id': '@cskhleminh', 'phien': '-', 'du_doan': '-', 'do_tin_cay': '50%', 'error': str(e)})


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
