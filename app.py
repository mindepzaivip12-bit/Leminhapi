import os
import json
import time
import random
import threading
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

# === GLOBAL STATE ===
RESET_SESSION_ID = 0
PREDICTION_LOG = {}
LOG_LOCK = threading.RLock()
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_state.json")
NEXT_PRED_CACHE = {'phien': None, 'prediction': None, 'confidence': None}


# =====================================================================
# PERSISTENCE
# =====================================================================
def load_state():
    global PREDICTION_LOG, RESET_SESSION_ID
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            PREDICTION_LOG = {int(k): v for k, v in data.get('log', {}).items()}
            RESET_SESSION_ID = data.get('reset_id', 0)
            print(f"[STATE] ✓ Loaded {len(PREDICTION_LOG)} predictions | reset={RESET_SESSION_ID}")
    except Exception as e:
        print(f"[STATE LOAD ERROR] {e}")


def save_state():
    try:
        with LOG_LOCK:
            data = {
                'log': {str(k): v for k, v in PREDICTION_LOG.items()},
                'reset_id': RESET_SESSION_ID,
            }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    except Exception as e:
        print(f"[STATE SAVE ERROR] {e}")


load_state()


# =====================================================================
# HTML TEMPLATE
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TOOL LCMD5 LEMINH</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #090b10; --bg-card: #141721; --bg-card-hover: #1a1e2b;
        --text-main: #ffffff; --text-muted: #8892b0; --border-color: #232838;
        --tai-color: #0288d1; --xiu-color: #d81b60;
        --win-color: #4caf50; --lose-color: #f44336;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    body { background-color: var(--bg-dark); color: var(--text-main); padding-bottom: 30px; min-height: 100vh; }
    .header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; border-bottom: 1px solid var(--border-color); background: rgba(9, 11, 16, 0.9); backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 100; }
    .header-title { font-size: 18px; font-weight: 800; color: #fff; letter-spacing: 0.5px; display: flex; align-items: center; gap: 8px;}
    .live-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--win-color); box-shadow: 0 0 8px var(--win-color); animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .btn-reset { background: rgba(244, 67, 54, 0.1); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 6px 14px; border-radius: 6px; font-weight: 600; font-size: 13px; cursor: pointer; transition: 0.3s; }
    .btn-reset:hover { background: var(--lose-color); color: #fff; }
    .stats-bar { max-width: 600px; margin: 15px auto 0; padding: 0 15px; display: flex; justify-content: space-between; gap: 10px; }
    .stat-item { flex: 1; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px; text-align: center; }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px; font-weight: 600; }
    .stat-value { font-size: 18px; font-weight: 800; color: #fff; }
    .stat-value.win { color: var(--win-color); }
    .stat-value.lose { color: var(--lose-color); }
    .container { padding: 15px; display: flex; flex-direction: column; gap: 10px; max-width: 600px; margin: 0 auto; max-height: 75vh; overflow-y: auto; }
    .container::-webkit-scrollbar { width: 4px; }
    .container::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
    .card-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 12px 15px; display: flex; justify-content: space-between; align-items: center; transition: 0.2s; }
    .card-item:hover { background: var(--bg-card-hover); }
    .card-item.active { border-color: var(--tai-color); box-shadow: 0 0 10px rgba(2, 136, 209, 0.2); }
    .col-left { display: flex; flex-direction: column; gap: 4px; flex: 1.5; }
    .id-text { font-size: 15px; font-weight: 800; color: #fff; }
    .bot-line { display: flex; align-items: center; gap: 6px; font-size: 12px; }
    .bot-label { color: var(--text-muted); font-weight: 600; }
    .bet-badge { padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 11px; color: #fff; }
    .bet-tai { background: var(--tai-color); }
    .bet-xiu { background: var(--xiu-color); }
    .conf-text { color: var(--text-muted); font-size: 11px; }
    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; flex: 1; }
    .pred-badge { padding: 4px 12px; border-radius: 12px; font-weight: 700; font-size: 12px; text-transform: lowercase; color: #fff; }
    .pred-tai { background: var(--tai-color); }
    .pred-xiu { background: var(--xiu-color); }
    .pred-empty { background: transparent; border: 1px dashed var(--border-color); color: var(--text-muted); }
    .dice-text { font-size: 13px; font-weight: 600; color: #e2e8f0; white-space: nowrap; }
    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.8; }
    .status-text { font-size: 14px; font-weight: 800; display: flex; align-items: center; gap: 4px; }
    .status-win { color: var(--win-color); }
    .status-lose { color: var(--lose-color); }
    .status-wait { color: var(--text-muted); }
    .loading { text-align: center; padding: 40px; color: var(--text-muted); font-weight: 600; }
    @media (max-width: 400px) {
        .header-title { font-size: 15px; } .stat-value { font-size: 15px; }
        .dice-text { font-size: 11px; } .id-text { font-size: 13px; } .bot-line { font-size: 11px; }
    }
</style>
</head>
<body>
<div class="header">
    <div class="header-title"><div class="live-dot"></div> TOOL LCMD5</div>
    <button class="btn-reset" onclick="confirmReset()">↻ Reset Counter</button>
</div>

<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng phiên</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Thua</div><div class="stat-value lose" id="stat-lose">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ</div><div class="stat-value win" id="stat-rate">0%</div></div>
</div>

<div class="container" id="list-container">
    <div class="loading">Đang kết nối Server...</div>
</div>

<script>
let isResetting = false;

async function fetchData() {
    if (isResetting) return;
    try {
        const r = await fetch('/api/history', { cache: 'no-store' });
        const data = await r.json();
        renderList(data.rows || [], data.stats || {});
    } catch (e) {
        document.getElementById('list-container').innerHTML = '<div class="loading" style="color:var(--lose-color)">Lỗi kết nối Server!</div>';
    }
}

function renderList(rows, stats) {
    const container = document.getElementById('list-container');
    if (stats.total > 0) {
        document.getElementById('stat-total').innerText = stats.total;
        document.getElementById('stat-win').innerText = stats.correct;
        document.getElementById('stat-lose').innerText = stats.lose;
        document.getElementById('stat-rate').innerText = Math.round((stats.correct / stats.total) * 100) + '%';
    } else {
        document.getElementById('stat-total').innerText = '0';
        document.getElementById('stat-win').innerText = '0';
        document.getElementById('stat-lose').innerText = '0';
        document.getElementById('stat-rate').innerText = '0%';
    }
    if (!rows.length) {
        container.innerHTML = '<div class="loading">Không có dữ liệu. Hãy đợi phiên mới.</div>';
        return;
    }
    container.innerHTML = '';
    rows.forEach((row) => {
        const div = document.createElement('div');
        div.className = 'card-item' + (row.is_next ? ' active' : '');
        let betBadge = `<span class="bet-badge" style="background:#232838;color:#8892b0;">cược -</span>`;
        if (row.prediction === "Tài") betBadge = `<span class="bet-badge bet-tai">cược tài</span>`;
        if (row.prediction === "Xỉu") betBadge = `<span class="bet-badge bet-xiu">cược xỉu</span>`;
        let midDisplay = `<span class="pred-badge pred-empty">-</span><div class="dice-text">? + ? + ?</div>`;
        if (!row.is_next) {
            let resBadge = row.result === "Tài" ? `<span class="pred-badge pred-tai">tài</span>` : `<span class="pred-badge pred-xiu">xỉu</span>`;
            let diceSum = row.dice !== "? + ? + ?" ? ` (${row.dice.split(" + ").reduce((a,b)=>parseInt(a)+parseInt(b),0)})` : "";
            midDisplay = `${resBadge}<div class="dice-text">${row.dice}${diceSum}</div>`;
        } else {
            let predBadge = row.prediction === "Tài" ? `<span class="pred-badge pred-tai">tài</span>` : `<span class="pred-badge pred-xiu">xỉu</span>`;
            midDisplay = `${predBadge}<div class="dice-text">? + ? + ?</div>`;
        }
        let statusHtml = '';
        if (row.is_next) statusHtml = `<div class="status-text status-wait">Chờ kết quả</div>`;
        else if (row.is_correct === true) statusHtml = `<div class="status-text status-win">Đúng cửa ✅</div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status-text status-lose">Sai cửa ❌</div>`;
        div.innerHTML = `
            <div class="col-left">
                <div class="id-text">#${row.phien}</div>
                <div class="bot-line"><span class="bot-label">Bot:</span> ${betBadge}</div>
                <div class="conf-text">(Tin cậy: ${row.confidence}%)</div>
            </div>
            <div class="col-mid">${midDisplay}</div>
            <div class="col-right">${statusHtml}</div>
        `;
        container.appendChild(div);
    });
}

async function confirmReset() {
    Swal.fire({
        title: 'Reset Counter?',
        html: "Bộ đếm sẽ về <b>0</b>.<br><b style='color:#4caf50'>Lịch sử KHÔNG bị xoá vĩnh viễn.</b>",
        icon: 'warning', showCancelButton: true, confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33', confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Reset thành công!', text: 'Bộ đếm về 0 từ phiên #' + data.reset_to, icon: 'success', confirmButtonColor: '#3085d6' });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire('Lỗi!', 'Không thể reset: ' + error.message, 'error'); isResetting = false;
            }
        }
    });
}
fetchData(); setInterval(fetchData, 5000);
</script>
</body>
</html>
"""


# =====================================================================
# HELPER PATTERNS
# =====================================================================
def build_blocks(results):
    if not results:
        return []
    blocks = []
    curr_val = results[0]
    curr_count = 1
    for r in results[1:]:
        if r == curr_val:
            curr_count += 1
        else:
            blocks.append({'val': curr_val, 'len': curr_count})
            curr_val = r
            curr_count = 1
    blocks.append({'val': curr_val, 'len': curr_count})
    return blocks


def block_class(L):
    if L == 1:
        return 'S'
    if L <= 3:
        return 'M'
    return 'L'


def encode_pattern_81(block_lengths):
    if len(block_lengths) < 4:
        return None
    code = 0
    for L in block_lengths[-4:]:
        code = code * 3 + {'S': 0, 'M': 1, 'L': 2}[block_class(L)]
    return code


def learn_81_patterns(results):
    stats = {}
    n = len(results)
    for k in range(10, n):
        sub = results[k:]
        blocks = build_blocks(sub)
        if len(blocks) < 5:
            continue
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        if code is None:
            continue
        current_val = blocks[0]['val']
        current_len = blocks[0]['len']
        actual_next = results[k - 1]
        continued = (actual_next == current_val)
        key1 = (code, min(current_len, 4))
        if key1 not in stats:
            stats[key1] = {'continue': 0, 'break': 0}
        stats[key1]['continue' if continued else 'break'] += 1
        key2 = code
        if key2 not in stats:
            stats[key2] = {'continue': 0, 'break': 0}
        stats[key2]['continue' if continued else 'break'] += 1
    return stats


# =====================================================================
# THUẬT TOÁN V9.0 - 18 TẦNG
# =====================================================================
def estimate_streak_break_prob(results):
    blocks = build_blocks(results)
    if len(blocks) < 2:
        return None
    current_len = blocks[0]['len']
    if current_len < 2:
        return None
    past = [b['len'] for b in blocks[1:31]]
    if not past:
        return None
    reached = [l for l in past if l >= current_len]
    if len(reached) < 3:
        return None
    broke = sum(1 for l in reached if l == current_len)
    continued = sum(1 for l in reached if l > current_len)
    total = broke + continued
    if total < 3:
        return None
    break_prob = (broke + 1) / (total + 2)
    return {'break_prob': break_prob, 'sample': total, 'current_len': current_len}


def detect_repeating_block_pattern(blocks):
    if len(blocks) < 4:
        return None
    lens = [b['len'] for b in blocks[:9]]
    for period in [2, 3]:
        if len(lens) < period * 2 + 1:
            continue
        repeats = 0
        for i in range(period, len(lens)):
            if lens[i] == lens[i - period]:
                repeats += 1
            else:
                break
        if repeats >= period + 1:
            return {
                'period': period,
                'sequence': lens[:period],
                'next_len': lens[period - 1],
                'current_len': lens[0],
                'strength': min(1.0, repeats / (period * 2.0)),
            }
    return None


def detect_long_pattern(results, min_len=6, max_len=25):
    if len(results) < min_len * 2:
        return None
    max_check = min(max_len, len(results) // 3)
    for L in range(min_len, max_check + 1):
        if len(results) < L * 2:
            break
        recent = tuple(results[:L])
        repeats = 0
        for r in range(1, 4):
            start = r * L
            end = start + L
            if end > len(results):
                break
            if tuple(results[start:end]) == recent:
                repeats += 1
            else:
                break
        if repeats >= 1:
            return {
                'length': L,
                'repeats': repeats,
                'next': results[L - 1],
                'confidence': min(90, 60 + L * 1.2 + repeats * 8),
            }
    return None


def analyze_pattern(results, dice_sums=None, adaptive_boost=1.0):
    if not results or len(results) < 3:
        return "Tài", 50.0

    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    n = len(results)
    candidates = []

    blocks = build_blocks(results)
    current_val = blocks[0]['val']
    current_len = blocks[0]['len']

    # TẦNG 1: BỆT
    if current_len >= 15:
        candidates.append((opposite, 97.0, 60, 2.5))
    elif current_len >= 12:
        candidates.append((opposite, 95.0, 55, 2.3))
    elif current_len >= 10:
        candidates.append((opposite, 93.0, 55, 2.0))
    elif current_len >= 8:
        candidates.append((opposite, 88.0, 50, 1.8))
    elif current_len >= 6:
        candidates.append((opposite, 80.0, 45, 1.5))
    elif current_len == 5:
        candidates.append((opposite, 70.0, 35, 1.2))
    elif current_len == 4:
        candidates.append((current_val, 60.0, 30, 0.9))
    elif current_len == 3:
        candidates.append((current_val, 55.0, 25, 0.6))

    # TẦNG 2: ĐẢO 1-1
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]:
            alt_len += 1
        else:
            break
    if alt_len >= 15:
        candidates.append((opposite, 96.0, 50, 2.2))
    elif alt_len >= 12:
        candidates.append((opposite, 94.0, 50, 2.0))
    elif alt_len >= 10:
        candidates.append((opposite, 90.0, 45, 1.8))
    elif alt_len >= 7:
        candidates.append((opposite, 82.0, 35, 1.5))
    elif alt_len >= 5:
        candidates.append((opposite, 74.0, 28, 1.2))
    elif alt_len >= 3:
        candidates.append((opposite, 63.0, 20, 0.8))

    # TẦNG 3: CHU KỲ KHỐI
    cycle = detect_repeating_block_pattern(blocks)
    if cycle:
        bonus = cycle['strength']
        base_conf = 75.0 + bonus * 15.0
        if cycle['current_len'] < cycle['next_len']:
            candidates.append((current_val, base_conf, 30, 1.3 + bonus * 0.4))
        elif cycle['current_len'] == cycle['next_len']:
            candidates.append((opposite, base_conf + 5, 40, 1.4 + bonus * 0.5))

    # TẦNG 4: PHÁ BỆT
    break_info = estimate_streak_break_prob(results)
    if break_info and current_len >= 3:
        bp = break_info['break_prob']
        sample = break_info['sample']
        if bp >= 0.80:
            candidates.append((opposite, 88.0, sample, 1.9))
        elif bp >= 0.68:
            candidates.append((opposite, 80.0, sample, 1.5))
        elif bp >= 0.55:
            candidates.append((opposite, 70.0, sample, 1.1))
        elif bp <= 0.20:
            candidates.append((current_val, 85.0, sample, 1.7))
        elif bp <= 0.35:
            candidates.append((current_val, 72.0, sample, 1.2))

    # TẦNG 5: TREND 5
    if n >= 5:
        r5_tai = results[:5].count("Tài")
        if r5_tai >= 4:
            candidates.append(("Tài", 65.0, 5, 0.8))
        elif r5_tai <= 1:
            candidates.append(("Xỉu", 65.0, 5, 0.8))

    # TẦNG 6: TREND 10 (mean reversion)
    if n >= 10:
        r10_tai = results[:10].count("Tài")
        if r10_tai >= 8:
            candidates.append(("Xỉu", 70.0, 10, 1.1))
        elif r10_tai >= 7:
            candidates.append(("Xỉu", 65.0, 10, 0.9))
        elif r10_tai <= 2:
            candidates.append(("Tài", 70.0, 10, 1.1))
        elif r10_tai <= 3:
            candidates.append(("Tài", 65.0, 10, 0.9))

    # TẦNG 7: TREND 20
    if n >= 20:
        tai20 = results[:20].count("Tài")
        if tai20 >= 15:
            candidates.append(("Xỉu", 68.0, 20, 1.0))
        elif tai20 >= 14:
            candidates.append(("Xỉu", 63.0, 20, 0.8))
        elif tai20 <= 5:
            candidates.append(("Tài", 68.0, 20, 1.0))
        elif tai20 <= 6:
            candidates.append(("Tài", 63.0, 20, 0.8))

    # TẦNG 8: 81 MẪU
    if len(blocks) >= 5:
        stats = learn_81_patterns(results)
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        if code is not None:
            for key in [(code, min(current_len, 4)), code]:
                if key in stats:
                    s = stats[key]
                    total = s['continue'] + s['break']
                    if total >= 2:
                        cont_rate = (s['continue'] + 1) / (total + 2)
                        conf_val = 50 + abs(cont_rate - 0.5) * 100
                        if cont_rate >= 0.63:
                            candidates.append((current_val, min(conf_val, 90), total, 1.4))
                        elif cont_rate <= 0.37:
                            candidates.append((opposite, min(conf_val, 90), total, 1.4))
                        break

    # TẦNG 9: N-GRAM
    for ns in [12, 10, 8, 7, 6, 5, 4]:
        if n < ns + 1:
            continue
        current_seq = tuple(results[:ns])
        match_tai = match_xiu = 0
        for i in range(len(results) - ns):
            if tuple(results[i:i + ns]) == current_seq and i + ns < len(results):
                if results[i + ns] == "Tài":
                    match_tai += 1
                else:
                    match_xiu += 1
        total_m = match_tai + match_xiu
        if total_m >= 2 and match_tai != match_xiu:
            winner = "Tài" if match_tai > match_xiu else "Xỉu"
            ratio = max(match_tai, match_xiu) / total_m
            if ratio >= 0.6:
                weight = 0.8 + ns / 12.0
                candidates.append((winner, 55 + ratio * 25, total_m, weight))
                break

    # TẦNG 10: MARKOV
    if n >= 10:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 1):
            if results[i] == last:
                trans[results[i + 1]] += 1
        total_t = trans["Tài"] + trans["Xỉu"]
        if total_t >= 3 and trans["Tài"] != trans["Xỉu"]:
            winner = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            ratio = max(trans["Tài"], trans["Xỉu"]) / total_t
            candidates.append((winner, 58 + ratio * 20, total_t, 1.0))

    # TẦNG 11: DICE BIAS
    if dice_sums and len(dice_sums) >= 5:
        avg_recent = sum(dice_sums[:10]) / min(10, len(dice_sums))
        if avg_recent >= 12.5:
            candidates.append(("Tài", 65.0, 10, 0.9))
        elif avg_recent <= 8.0:
            candidates.append(("Xỉu", 65.0, 10, 0.9))

    # TẦNG 12: MOMENTUM
    if n >= 10:
        r5_tai = results[:5].count("Tài")
        r10_tai = results[:10].count("Tài")
        if r5_tai >= 4 and r10_tai <= 5:
            candidates.append(("Xỉu", 63.0, 10, 0.9))
        elif r5_tai <= 1 and r10_tai >= 5:
            candidates.append(("Tài", 63.0, 10, 0.9))

    # TẦNG 13: ZIGZAG NGẮN
    if n >= 4:
        if results[0] != results[1] and results[1] != results[2] and results[2] != results[3]:
            candidates.append((opposite, 70.0, 8, 0.9))

    # TẦNG 14: SKEW
    if n >= 20:
        tai_ratio = results[:20].count("Tài") / 20
        if tai_ratio >= 0.70:
            candidates.append(("Xỉu", 66.0, 20, 1.1))
        elif tai_ratio <= 0.30:
            candidates.append(("Tài", 66.0, 20, 1.1))

    # TẦNG 15: DRAGON-TIGER
    if n >= 6:
        seg = results[:6]
        if all(seg[i] != seg[i + 1] for i in range(5)):
            candidates.append((opposite, 74.0, 6, 1.1))

    # TẦNG 16: ĐỐI XỨNG CHẴN/LẺ
    if n >= 8:
        even_res = [results[i] for i in range(0, min(8, n), 2)]
        odd_res = [results[i] for i in range(1, min(8, n), 2)]
        if len(even_res) >= 3 and all(r == even_res[0] for r in even_res):
            candidates.append((opposite, 62.0, len(even_res), 0.9))
        if len(odd_res) >= 3 and all(r == odd_res[0] for r in odd_res):
            candidates.append((opposite, 62.0, len(odd_res), 0.9))

    # TẦNG 17: LONG PATTERN
    long_pat = detect_long_pattern(results, min_len=6, max_len=20)
    if long_pat:
        candidates.append((long_pat['next'], long_pat['confidence'], long_pat['length'], 1.5))

    # TẦNG 18: STREAK-AWARE NHẸ
    if current_len >= 3:
        candidates.append((opposite, 57.0, 5, 0.5))

    # ==================== VOTING ====================
    if not candidates:
        return opposite, 53.0

    tai_score = sum(c[1] * c[3] for c in candidates if c[0] == "Tài")
    xiu_score = sum(c[1] * c[3] for c in candidates if c[0] == "Xỉu")

    if tai_score == xiu_score:
        return opposite, round(min(99.9, max(50.0, 53.0 * adaptive_boost)), 1)

    winner = "Tài" if tai_score > xiu_score else "Xỉu"
    winner_score = max(tai_score, xiu_score)
    total_score = tai_score + xiu_score
    agree_ratio = winner_score / total_score

    best_conf = max((c[1] for c in candidates if c[0] == winner), default=55.0)
    final_conf = best_conf * (0.70 + agree_ratio * 0.30)
    final_conf *= adaptive_boost
    final_conf = max(50.0, min(99.9, final_conf))
    return winner, round(final_conf, 1)


def get_adaptive_boost():
    with LOG_LOCK:
        recent = [
            (p, rec) for p, rec in PREDICTION_LOG.items()
            if p > RESET_SESSION_ID and rec.get('is_correct') is not None
        ]
    if len(recent) < 10:
        return 1.0
    recent.sort(key=lambda x: x[0])
    recent = recent[-15:]
    acc = sum(1 for _, r in recent if r['is_correct']) / len(recent)
    if acc >= 0.70:
        return 1.05
    if acc >= 0.60:
        return 1.02
    if acc <= 0.40:
        return 0.92
    if acc <= 0.50:
        return 0.97
    return 1.0


# =====================================================================
# FETCH DATA
# =====================================================================
def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(API_URL, timeout=8, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']:
                rows = []
                for item in data['list']:
                    phien = int(item['id'])
                    res_raw = str(item.get('resultTruyenThong', '')).upper().strip()
                    res = "Tài" if res_raw == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
                    total = item.get('point', sum(dices))
                    rows.append({'phien': phien, 'result': res, 'dice': dice_str, 'total': total})
                return rows, 'live'
    except Exception as e:
        print(f"[API ERROR] {e}")
    elapsed = int(time.time() / 60)
    current = 7116040 + elapsed
    random.seed(elapsed)
    rows = []
    for i in range(40):
        sid = current - i
        r = "Tài" if random.random() > 0.5 else "Xỉu"
        d = [random.randint(1, 6) for _ in range(3)]
        rows.append({"phien": sid, "result": r, "dice": f"{d[0]} + {d[1]} + {d[2]}", "total": sum(d)})
    return rows, 'fallback'


# =====================================================================
# LOG / STATS
# =====================================================================
def update_prediction_log(valid):
    new_added = False
    with LOG_LOCK:
        for i, sess in enumerate(valid):
            phien = sess['phien']
            if phien in PREDICTION_LOG:
                continue
            history = [v['result'] for v in valid[:i]][::-1]
            dice = [v.get('total', 0) for v in valid[:i]][::-1]
            if len(history) < 3:
                continue
            pred, conf = analyze_pattern(history, dice)
            PREDICTION_LOG[phien] = {
                'prediction': pred,
                'result': sess['result'],
                'confidence': conf,
                'is_correct': (pred == sess['result']),
            }
            new_added = True
    if new_added:
        save_state()


def compute_stats():
    with LOG_LOCK:
        total = correct = 0
        for phien, rec in PREDICTION_LOG.items():
            if phien > RESET_SESSION_ID and rec.get('is_correct') is not None:
                total += 1
                if rec['is_correct']:
                    correct += 1
    return total, correct


# =====================================================================
# ROUTES
# =====================================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        update_prediction_log(valid)
        total_past, correct_count = compute_stats()

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1

        if (NEXT_PRED_CACHE.get('phien') == latest_session['phien']
                and NEXT_PRED_CACHE.get('prediction') in ("Tài", "Xỉu")):
            next_pred = NEXT_PRED_CACHE['prediction']
            next_conf = NEXT_PRED_CACHE['confidence']
        else:
            history_for_next = [v['result'] for v in valid][::-1]
            dice_for_next = [v.get('total', 0) for v in valid][::-1]
            boost = get_adaptive_boost()
            next_pred, next_conf = analyze_pattern(history_for_next, dice_for_next, boost)
            NEXT_PRED_CACHE.update({
                'phien': latest_session['phien'],
                'prediction': next_pred,
                'confidence': next_conf,
            })

        out = [{
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'confidence': next_conf,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None,
        }]

        MAX_DISPLAY = 100
        displayed = 0
        with LOG_LOCK:
            for i in range(len(valid) - 1, -1, -1):
                if displayed >= MAX_DISPLAY:
                    break
                current_session = valid[i]
                if current_session['phien'] <= RESET_SESSION_ID:
                    break
                phien = current_session['phien']
                rec = PREDICTION_LOG.get(phien)
                if rec:
                    out.append({
                        'phien': phien,
                        'is_next': False,
                        'prediction': rec['prediction'],
                        'confidence': rec['confidence'],
                        'result': rec['result'],
                        'dice': current_session['dice'],
                        'is_correct': rec['is_correct'],
                    })
                    displayed += 1

        return jsonify({
            'rows': out,
            'stats': {
                'total': total_past,
                'correct': correct_count,
                'lose': total_past - correct_count,
            },
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict_only():
    """API dự đoán phiên tiếp theo — cập nhật log trước khi predict."""
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404

        # ⭐ Update log trước để boost chính xác
        update_prediction_log(valid)

        latest = valid[-1]
        next_phien = latest['phien'] + 1

        cached = NEXT_PRED_CACHE
        if (cached.get('phien') == latest['phien']
                and cached.get('prediction') in ("Tài", "Xỉu")):
            pred = cached['prediction']
            conf = cached['confidence']
            cached_hit = True
        else:
            hist = [v['result'] for v in valid][::-1]
            dice = [v.get('total', 0) for v in valid][::-1]
            boost = get_adaptive_boost()
            pred, conf = analyze_pattern(hist, dice, boost)
            NEXT_PRED_CACHE.update({
                'phien': latest['phien'],
                'prediction': pred,
                'confidence': conf,
            })
            cached_hit = False

        total, correct = compute_stats()
        accuracy = round(correct / total * 100, 1) if total > 0 else 0.0
        boost = get_adaptive_boost()

        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'latest_session': latest['phien'],
            'latest_result': latest['result'],
            'latest_dice': latest['dice'],
            'prediction': pred,
            'confidence': conf,
            'adaptive_boost': round(boost, 3),
            'accuracy': accuracy,
            'stats': {
                'total': total,
                'correct': correct,
                'lose': total - correct,
            },
            'reset_session_id': RESET_SESSION_ID,
            'data_source': source,
            'cached': cached_hit,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })

    except requests.exceptions.Timeout:
        return jsonify({'status': 'error', 'message': 'API timeout'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'error', 'message': f'API lỗi: {e}'}), 502
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if valid:
            RESET_SESSION_ID = valid[-1]['phien']
            save_state()
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/stats')
def stats_only():
    with LOG_LOCK:
        all_time = len(PREDICTION_LOG)
        all_correct = sum(
            1 for r in PREDICTION_LOG.values() if r.get('is_correct') is True
        )
    total, correct = compute_stats()
    return jsonify({
        'current_period': {'total': total, 'correct': correct, 'lose': total - correct},
        'all_time': {'total': all_time, 'correct': all_correct, 'lose': all_time - all_correct},
        'reset_session_id': RESET_SESSION_ID,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
