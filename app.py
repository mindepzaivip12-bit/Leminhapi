import os
import math
from datetime import datetime
from collections import defaultdict
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
MAX_CONFIDENCE = 92
MIN_CONFIDENCE = 52
RESET_ID = 0

# =====================================================================
# HTML TEMPLATE (giữ nguyên 100% từ bản gốc của bạn)
# =====================================================================
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
        let trClass = row.is_next ? 'class="row-next"' : '';
        let predHtml = `<span class="badge badge-empty">-</span>`;
        if (row.prediction === "Tài") predHtml = `<span class="badge badge-tai">TÀI</span>`;
        if (row.prediction === "Xỉu") predHtml = `<span class="badge badge-xiu">XỈU</span>`;
        let confHtml = "";
        if (row.conf && row.prediction !== "-") {
            const cls = row.conf >= 70 ? 'conf-badge high' : 'conf-badge';
            confHtml = `<div class="${cls}">${row.conf}%</div>`;
        }
        let predFull = `<div style="display:flex; flex-direction:column; align-items:center; gap:2px;">${predHtml}${confHtml}</div>`;
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
# UTILS
# =====================================================================
def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"

def format_tx(results, length):
    if len(results) < length:
        return None
    return "-".join("T" if r == "Tài" else "X" for r in results[:length])

def _tx(seq):
    return "".join("T" if r == "Tài" else "X" for r in seq)


# =====================================================================
# 🧠 ENGINE v3 — BAYESIAN + ENTROPY + REGIME DETECTION
# =====================================================================

class AlternatingDetector:
    """
    Phát hiện đảo 1-1, 2-2, 1-2 với binomial confidence.
    p_alt: xác suất phiên tiếp theo là ĐẢO (ngược phiên gần nhất).
    """

    @staticmethod
    def detect(seq):
        if len(seq) < 4:
            return 0.0, 0.0, "none"

        s = _tx(seq)
        candidates = []

        for period, cap in [(1, 0.95), (2, 0.85), (3, 0.72)]:
            score, n_blocks = AlternatingDetector._match_period(s, period)
            if score > 0:
                # Confidence dựa trên binomial: n block khớp liên tiếp
                # P >= n_block khớp ngẫu nhiên = 0.5^(n_blocks-1)
                binomial_conf = 1.0 - (0.5 ** max(1, n_blocks - 1))
                conf = binomial_conf * cap * score
                candidates.append((period, score, conf, n_blocks))

        if not candidates:
            return 0.0, 0.0, "none"

        # Ưu tiên period nhỏ nếu conf tương đương
        best = max(candidates, key=lambda x: (x[2], -x[0]))
        period, score, conf, n_blocks = best

        if conf < 0.20:
            return 0.0, 0.0, "none"

        # p_alt scale từ score
        p_alt = 0.5 + score * 0.48  # 0.5 → 0.98
        p_alt = min(0.98, max(0.5, p_alt))

        type_map = {1: "alt1", 2: "alt2", 3: "alt3"}
        return p_alt, min(1.0, conf), type_map[period]

    @staticmethod
    def _match_period(s, period):
        """Trả về (score 0..1, số block khớp liên tiếp)."""
        if len(s) < period * 2 + 1:
            return 0.0, 0

        tail = s[:period * 2]
        block_a = tail[:period]
        block_b = tail[period:period * 2]
        if block_a == block_b:
            return 0.0, 0

        matched = 0
        max_blocks = len(s) // period
        for i in range(max_blocks):
            start = i * period
            end = start + period
            if end > len(s):
                break
            block = s[start:end]
            expected = block_a if i % 2 == 0 else block_b
            if block == expected:
                matched += 1
            else:
                break

        if matched < 2:
            return 0.0, matched

        # Score: tỷ lệ khớp, bonus nếu chuỗi dài
        base = matched / max_blocks
        if matched >= 4:
            base = min(1.0, base + 0.10)
        if matched >= 6:
            base = min(1.0, base + 0.08)
        return base, matched


class RegimeDetector:
    """
    Phát hiện chế độ cầu hiện tại: BET (bệt), ALT (đảo), MIX (hỗn tạp).
    Trả về dict với regime + confidence cho từng chế độ.
    """
    @staticmethod
    def detect(seq):
        if len(seq) < 6:
            return {"regime": "unknown", "bet_conf": 0.0, "alt_conf": 0.0, "mix_conf": 1.0}

        recent = seq[:20]
        flips = sum(1 for i in range(len(recent) - 1) if recent[i] != recent[i + 1])
        n_pairs = len(recent) - 1
        flip_rate = flips / n_pairs if n_pairs > 0 else 0.5

        # Streak hiện tại
        streak_val = recent[0]
        streak_len = 1
        for r in recent[1:]:
            if r == streak_val:
                streak_len += 1
            else:
                break

        bet_conf = 0.0
        alt_conf = 0.0
        mix_conf = 0.0

        # Bệt: streak dài, flip_rate thấp
        if streak_len >= 3:
            bet_conf = min(1.0, 0.4 + 0.15 * (streak_len - 2))
        if flip_rate < 0.35:
            bet_conf = max(bet_conf, 0.7 - flip_rate * 1.0)

        # Đảo: flip_rate cao
        if flip_rate > 0.65:
            alt_conf = min(1.0, (flip_rate - 0.5) * 3.0)
        if flip_rate >= 0.85:
            alt_conf = max(alt_conf, 0.85)

        # Hỗn tạp: flip_rate trung bình
        if 0.35 <= flip_rate <= 0.65:
            mix_conf = 1.0 - abs(flip_rate - 0.5) * 2.5
            mix_conf = max(0.0, min(1.0, mix_conf))

        # Normalize
        total = bet_conf + alt_conf + mix_conf
        if total > 0:
            bet_conf /= total
            alt_conf /= total
            mix_conf /= total
        else:
            mix_conf = 1.0

        if bet_conf >= max(alt_conf, mix_conf):
            regime = "bet"
        elif alt_conf >= max(bet_conf, mix_conf):
            regime = "alt"
        else:
            regime = "mix"

        return {
            "regime": regime,
            "bet_conf": bet_conf,
            "alt_conf": alt_conf,
            "mix_conf": mix_conf,
            "flip_rate": flip_rate,
            "streak_len": streak_len,
            "streak_val": streak_val,
        }


class HouseEngine:
    """
    Engine v3: Bayesian weighted ensemble + regime-aware + entropy confidence.
    KHÔNG random.
    """

    # Base weights (sẽ được adaptive theo performance)
    BASE_WEIGHTS = {
        "markov1": 0.12,
        "markov2": 0.16,
        "markov3": 0.10,
        "pattern_memory": 0.15,
        "multi_tf": 0.10,
        "streak_physics": 0.08,
        "bias_detector": 0.05,
        "alternating": 0.18,
        "regime_align": 0.06,
    }

    ALT_OVERRIDE_P_ALT = 0.70     # ngưỡng p_alt để override
    ALT_OVERRIDE_MARGIN = 0.06
    BET_OVERRIDE_STREAK = 5       # streak >= 5 → ưu tiên bệt mạnh
    MIX_MIN_CONF_CAP = 68         # conf tối đa khi cầu hỗn tạp

    def __init__(self):
        self.weights = dict(self.BASE_WEIGHTS)
        self.perf_history = []        # list of 0/1
        self.signal_perf = defaultdict(lambda: {"win": 0, "total": 0})
        self.last_signal_biases = {}

    # ---------------- STATIC FEATURES ----------------

    @staticmethod
    def _markov_1(seq):
        tt = tx = xt = xx = 0
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i + 1]
            if a == "Tài" and b == "Tài": tt += 1
            elif a == "Tài" and b == "Xỉu": tx += 1
            elif a == "Xỉu" and b == "Tài": xt += 1
            else: xx += 1
        last = seq[0]
        if last == "Tài":
            denom = tt + tx
            return tt / denom if denom else 0.5
        else:
            denom = xt + xx
            return xt / denom if denom else 0.5

    @staticmethod
    def _markov_n(seq, n):
        if len(seq) < n + 2:
            return None
        ctx = tuple(seq[:n])
        s = _tx(seq)
        pat = _tx(ctx)
        t_after = x_after = 0
        for i in range(len(s) - n):
            if s[i:i + n] == pat:
                if s[i + n] == "T": t_after += 1
                else: x_after += 1
        total = t_after + x_after
        if total == 0:
            return None
        return t_after / total

    @staticmethod
    def _pattern_memory(seq, max_len=4):
        s = _tx(seq)
        results = {}
        for L in range(2, max_len + 1):
            if len(s) < L + 1:
                continue
            tail = s[:L]
            t_after = x_after = 0
            for i in range(0, len(s) - L):
                if s[i:i + L] == tail:
                    if s[i + L] == "T": t_after += 1
                    else: x_after += 1
            total = t_after + x_after
            if total >= 2:
                results[L] = (t_after / total, total)
            else:
                results[L] = (None, total)
        return results

    @staticmethod
    def _multi_tf_bias(seq):
        weights = {3: 0.35, 5: 0.30, 8: 0.18, 12: 0.12, 20: 0.05}
        total_w = 0.0
        bias = 0.0
        for w_len, w in weights.items():
            if len(seq) >= w_len:
                p_tai = sum(1 for r in seq[:w_len] if r == "Tài") / w_len
                bias += (p_tai - 0.5) * w
                total_w += w
        if total_w == 0:
            return 0.0
        return bias / total_w

    @staticmethod
    def _streak_physics(seq):
        if not seq:
            return 0.0, 0
        val = seq[0]
        n = 1
        for r in seq[1:]:
            if r == val: n += 1
            else: break

        # Bệt: đi theo bệt (không phải chống)
        if n >= 3:
            decay = min(0.30, 0.08 * (n - 2))
            bias = decay if val == "Tài" else -decay
            return bias, n
        return 0.0, n

    @staticmethod
    def _bias_detector(seq):
        if len(seq) < 15:
            return 0.0
        recent = seq[:30]
        p_tai = sum(1 for r in recent if r == "Tài") / len(recent)
        dev = p_tai - 0.5
        if abs(dev) < 0.10:
            return 0.0
        # Mean reversion: lệch nhiều → kéo về
        return -dev * 0.6

    @staticmethod
    def _volatility(seq):
        if len(seq) < 10:
            return 0.5
        recent = seq[:15]
        p = sum(1 for r in recent if r == "Tài") / len(recent)
        if p in (0.0, 1.0):
            return 0.0
        ent = -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
        return ent

    # ---------------- LEARNING ----------------

    def update_performance(self, pred, actual, last_biases=None):
        if pred not in ("Tài", "Xỉu") or actual not in ("Tài", "Xỉu"):
            return
        win = 1 if pred == actual else 0
        self.perf_history.append(win)
        if len(self.perf_history) > 80:
            self.perf_history.pop(0)

        # Cập nhật per-signal performance
        if last_biases:
            for name, bias in last_biases.items():
                if abs(bias) < 0.01:
                    continue
                signal_pred = "Tài" if bias > 0 else "Xỉu"
                self.signal_perf[name]["total"] += 1
                if signal_pred == actual:
                    self.signal_perf[name]["win"] += 1

    def _adaptive_weights(self):
        """Bayesian adaptive weights dựa trên hiệu suất gần đây của từng signal."""
        w = dict(self.BASE_WEIGHTS)

        # Global performance
        if len(self.perf_history) >= 20:
            recent = self.perf_history[-40:]
            acc = sum(recent) / len(recent)
            if acc < 0.48:
                w["bias_detector"] += 0.04
                w["markov1"] -= 0.02
                w["pattern_memory"] -= 0.02
            elif acc > 0.58:
                w["pattern_memory"] += 0.03
                w["markov2"] += 0.02
                w["bias_detector"] -= 0.02

        # Per-signal Bayesian adjustment: Laplace smoothing
        for name, stats in self.signal_perf.items():
            if name not in w:
                continue
            total = stats["total"]
            if total < 8:
                continue
            # Laplace-smoothed accuracy
            acc = (stats["win"] + 1) / (total + 2)
            # Nếu acc > 0.55 → tăng weight; < 0.45 → giảm
            multiplier = 1.0 + (acc - 0.5) * 0.8  # 0.5→1.0, 0.55→1.04, 0.45→0.96
            w[name] *= multiplier

        # Normalize
        s = sum(w.values())
        if s > 0:
            w = {k: v / s for k, v in w.items()}
        return w

    # ---------------- PREDICT ----------------

    def predict(self, results, return_biases=False):
        if not results:
            return ("Tài", 50, "empty") + (({}) if return_biases else ())

        if len(results) < 5:
            t = results.count("Tài")
            x = len(results) - t
            if t > x: pred, conf = "Tài", 55
            elif x > t: pred, conf = "Xỉu", 55
            else: pred, conf = results[0], 52
            base = (pred, conf, "short-majority")
            return base + (({}) if return_biases else ())

        signals = {}
        supports = {}

        # 1) Markov 1
        p1 = self._markov_1(results)
        signals["markov1"] = p1 - 0.5
        supports["markov1"] = 0.55

        # 2) Markov 2 & 3
        for n in (2, 3):
            pn = self._markov_n(results, n)
            if pn is not None:
                signals[f"markov{n}"] = pn - 0.5
                supports[f"markov{n}"] = 0.70 if n == 2 else 0.45

        # 3) Pattern memory
        pm = self._pattern_memory(results, max_len=4)
        pm_bias = 0.0
        pm_weight_sum = 0.0
        pm_total = 0
        for L, (p, sup) in pm.items():
            if p is not None:
                w = {2: 0.5, 3: 0.3, 4: 0.2}.get(L, 0.1)
                pm_bias += (p - 0.5) * w
                pm_weight_sum += w
                pm_total += sup
        if pm_weight_sum > 0:
            pm_bias /= pm_weight_sum
        signals["pattern_memory"] = pm_bias
        supports["pattern_memory"] = min(1.0, pm_total / 12.0)

        # 4) Multi-timeframe
        signals["multi_tf"] = self._multi_tf_bias(results)
        supports["multi_tf"] = 0.75

        # 5) Streak physics (theo bệt)
        sp_bias, streak_len = self._streak_physics(results)
        signals["streak_physics"] = sp_bias
        supports["streak_physics"] = 0.65 if streak_len >= 3 else 0.0

        # 6) Bias detector (mean reversion)
        signals["bias_detector"] = self._bias_detector(results)
        supports["bias_detector"] = 0.55

        # 7) Alternating detector
        p_alt, alt_conf, alt_type = AlternatingDetector.detect(results)
        last = results[0]
        if alt_type != "none" and alt_conf > 0.15:
            alt_target = _opp(last)
            alt_sign = 1.0 if alt_target == "Tài" else -1.0
            signals["alternating"] = alt_sign * min(1.0, alt_conf)
            supports["alternating"] = min(1.0, alt_conf + 0.15)
        else:
            signals["alternating"] = 0.0
            supports["alternating"] = 0.0

        # 8) Regime align (signal phụ thuộc chế độ)
        regime = RegimeDetector.detect(results)
        regime_bias = 0.0
        if regime["regime"] == "bet":
            # Đi theo bệt
            s_val = regime["streak_val"]
            regime_bias = (0.10 if s_val == "Tài" else -0.10) * regime["bet_conf"]
        elif regime["regime"] == "alt":
            # Đi theo đảo
            alt_target = _opp(last)
            regime_bias = (0.10 if alt_target == "Tài" else -0.10) * regime["alt_conf"]
        signals["regime_align"] = regime_bias
        supports["regime_align"] = max(regime["bet_conf"], regime["alt_conf"])

        # ---- Weighted ensemble ----
        w = self._adaptive_weights()
        total_score = 0.0
        total_weight = 0.0
        for name, bias in signals.items():
            if name in w and supports.get(name, 0) > 0:
                eff_w = w[name] * supports[name]
                total_score += bias * eff_w
                total_weight += eff_w

        if total_weight == 0:
            base = (results[0], 52, "fallback")
            return base + ((signals,) if return_biases else ())

        score = total_score / total_weight

        # ---- Override logic ----
        override_mode = None
        override_strength = 0.0

        # Override 1: Đảo mạnh
        if alt_type != "none" and p_alt >= self.ALT_OVERRIDE_P_ALT:
            alt_target = _opp(last)
            alt_sign = 1.0 if alt_target == "Tài" else -1.0
            if score * alt_sign < self.ALT_OVERRIDE_MARGIN:
                score = alt_sign * max(abs(score), self.ALT_OVERRIDE_MARGIN + 0.02)
                override_mode = "alt"
                override_strength = alt_conf

        # Override 2: Bệt cực mạnh
        if streak_len >= self.BET_OVERRIDE_STREAK and override_mode is None:
            s_val = results[0]
            bet_sign = 1.0 if s_val == "Tài" else -1.0
            # Nếu score ngược hướng bệt → kéo về
            if score * bet_sign < 0:
                score = bet_sign * max(abs(score) * 0.7, 0.05)
                override_mode = "bet"
                override_strength = min(1.0, 0.5 + 0.1 * (streak_len - 4))

        pred = "Tài" if score >= 0 else "Xỉu"

        # ---- Confidence via Bayesian ensemble ----
        # Đếm số signal đồng thuận
        pred_sign = 1.0 if pred == "Tài" else -1.0
        agreeing = 0
        total_sig = 0
        for name, bias in signals.items():
            if abs(bias) < 0.01:
                continue
            total_sig += 1
            if bias * pred_sign > 0:
                agreeing += 1
        agreement_ratio = agreeing / total_sig if total_sig > 0 else 0.5

        # Confidence components
        strength_conf = min(1.0, abs(score) * 4.0)          # strength of ensemble score
        agreement_conf = agreement_ratio                      # consensus
        alt_bonus = 0.0
        if alt_type != "none" and alt_conf > 0.5:
            alt_target = _opp(last)
            if pred == alt_target:
                alt_bonus = min(0.20, alt_conf * 0.25)

        # Entropy penalty: cầu càng volatile → conf càng giảm
        vol = self._volatility(results)  # 0..1
        entropy_factor = 1.0 - 0.30 * vol

        # Base confidence: blend strength + agreement
        raw_conf = 0.5 + (0.5 * strength_conf + 0.5 * agreement_conf) * 0.45
        raw_conf = raw_conf * entropy_factor + alt_bonus

        # Override boost
        if override_mode:
            raw_conf += 0.06 * override_strength

        # Regime cap: cầu hỗn tạp → không bao giờ quá tự tin
        if regime["regime"] == "mix":
            cap = self.MIX_MIN_CONF_CAP / 100.0
            raw_conf = min(raw_conf, cap)

        conf = int(round(raw_conf * 100))
        conf = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, conf))

        # ---- Label ----
        seq5 = results[:5]
        pattern = _tx(seq5)
        if alt_type == "alt1" and alt_conf > 0.5:
            mode = f"Đảo1-1({int(alt_conf*100)}%)"
        elif alt_type == "alt2":
            mode = f"Đảo2-2({int(alt_conf*100)}%)"
        elif alt_type == "alt3":
            mode = f"Đảo1-2({int(alt_conf*100)}%)"
        elif streak_len >= 4:
            mode = f"Bệt{streak_len}P"
        elif regime["regime"] == "mix":
            mode = "Hỗn tạp"
        else:
            mode = "Cân bằng"

        if override_mode == "alt":
            mode += " ⚡ALT"
        elif override_mode == "bet":
            mode += " ⚡BET"

        label = f"{mode} | flips={regime['flip_rate']:.2f} | {pattern}"

        result = (pred, conf, label)
        if return_biases:
            return result + (signals,)
        return result


ENGINE = HouseEngine()


def compute_prediction(results, return_biases=False):
    return ENGINE.predict(results, return_biases=return_biases)


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


def _load_history():
    """Load + refresh HISTORY_CACHE. Trả về list valid đã sort."""
    global RESET_ID
    raw_rows, _ = fetch_sessions()
    if raw_rows:
        for row in raw_rows:
            HISTORY_CACHE[row['phien']] = row
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
            del HISTORY_CACHE[k]
    return sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])


def _warmup_engine(history_results):
    """Replay để build performance history cho adaptive learning."""
    ENGINE.perf_history = []
    ENGINE.signal_perf = defaultdict(lambda: {"win": 0, "total": 0})
    n = len(history_results)
    # Replay từ cũ → mới
    for i in range(min(80, n - 1), 0, -1):
        hist_at_i = history_results[i:]
        if len(hist_at_i) < 1:
            continue
        pred, _, _, biases = ENGINE.predict(hist_at_i, return_biases=True)
        actual = history_results[i - 1]
        ENGINE.update_performance(pred, actual, last_biases=biases)


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    try:
        valid = _load_history()
        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0}})

        history_for_engine = [v['result'] for v in valid][::-1]

        # Warmup CHỈ MỘT LẦN mỗi request, không predict lặp lại
        _warmup_engine(history_for_engine)

        out = []
        correct_count = 0
        total_past = 0
        next_pred, next_conf, _ = compute_prediction(history_for_engine)

        # Phiên tiếp theo
        out.append({
            'phien': valid[-1]['phien'] + 1,
            'is_next': True,
            'prediction': next_pred,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None,
            'conf': next_conf,
        })

        # Lịch sử 150 phiên — predict cho từng phiên
        start_idx = max(0, len(valid) - 150)
        for i in range(len(valid) - 1, start_idx - 1, -1):
            hist = [v['result'] for v in valid[:i]][::-1]
            if len(hist) >= 5:
                pred, conf, _ = compute_prediction(hist)
            elif len(hist) > 0:
                t = hist.count("Tài")
                x = len(hist) - t
                if t > x: pred, conf = "Tài", 55
                elif x > t: pred, conf = "Xỉu", 55
                else: pred, conf = hist[0], 52
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
            })

        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e), 'rows': [], 'stats': {'total': 0, 'correct': 0}})


@app.route('/api/predict')
def predict():
    try:
        valid = _load_history()
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
            'ls_5p': ls_5p,
            'pattern_label': pattern_label,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/lc79')
@app.route('/lc79md5')
def lc79_api():
    try:
        valid = _load_history()
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
                # Reset engine state
                ENGINE.perf_history = []
                ENGINE.signal_perf = defaultdict(lambda: {"win": 0, "total": 0})
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
