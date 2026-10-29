import os
import time
import math
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=ab36aa88e2c9868ae0e8bc61adbd18dc"
RESET_SESSION_ID = 0

# =====================================================================
# GIAO DIỆN HTML
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>BON LCMD5 </title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #050814; --bg-card: rgba(15, 23, 42, 0.7);
        --text-main: #f8fafc; --text-muted: #94a3b8;
        --border-glass: rgba(255, 255, 255, 0.08);
        --tai-color: #0ea5e9; --tai-glow: rgba(14, 165, 233, 0.5);
        --xiu-color: #ec4899; --xiu-glow: rgba(236, 72, 153, 0.5);
        --gold: #fbbf24; --lose: #ef4444; --win: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    @keyframes bgMove { 0% { background-position: 0% 0%; } 50% { background-position: 100% 100%; } 100% { background-position: 0% 0%; } }
    @keyframes floatStars { 0% { transform: translateY(0px); opacity: 0.3; } 50% { transform: translateY(-20px); opacity: 0.8; } 100% { transform: translateY(0px); opacity: 0.3; } }
    @keyframes borderGlow { 0%, 100% { box-shadow: 0 0 10px rgba(251, 191, 36, 0.2), inset 0 0 10px rgba(251, 191, 36, 0.1); border-color: rgba(251, 191, 36, 0.4); } 50% { box-shadow: 0 0 25px rgba(251, 191, 36, 0.6), inset 0 0 20px rgba(251, 191, 36, 0.3); border-color: rgba(251, 191, 36, 0.8); } }
    @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
    @keyframes pulseNum { 0%, 100% { text-shadow: 0 0 10px rgba(14, 165, 233, 0.3); transform: scale(1); } 50% { text-shadow: 0 0 25px rgba(14, 165, 233, 0.8); transform: scale(1.05); } }
    @keyframes spinWait { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    body {
        background-color: var(--bg-dark); color: var(--text-main); padding-bottom: 30px; min-height: 100vh;
        background-image: radial-gradient(circle at 15% 50%, rgba(14, 165, 233, 0.15) 0%, transparent 40%), radial-gradient(circle at 85% 30%, rgba(236, 72, 153, 0.15) 0%, transparent 40%), radial-gradient(circle at 50% 90%, rgba(251, 191, 36, 0.05) 0%, transparent 50%);
        background-size: 200% 200%; animation: bgMove 15s ease infinite; overflow-x: hidden; position: relative;
    }
    body::before { content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0; background-image: radial-gradient(1px 1px at 10% 20%, #fff, transparent), radial-gradient(1.5px 1.5px at 80% 40%, #fff, transparent), radial-gradient(1px 1px at 40% 80%, #fff, transparent), radial-gradient(2px 2px at 70% 10%, #fff, transparent); background-size: 200px 200px; animation: floatStars 4s ease-in-out infinite; opacity: 0.4; }
    .header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: rgba(5, 8, 20, 0.8); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-bottom: 1px solid var(--border-glass); position: sticky; top: 0; z-index: 100; }
    .header-left { display: flex; align-items: center; gap: 10px; }
    .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--win); box-shadow: 0 0 12px var(--win); animation: pulseNum 1.5s infinite; }
    .header-title { font-size: 18px; font-weight: 800; background: linear-gradient(90deg, #fff, #bae6fd, #f472b6, #fff); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: shimmer 3s linear infinite; letter-spacing: -0.5px; }
    .btn-reset { background: rgba(239, 68, 68, 0.1); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); padding: 8px 16px; border-radius: 8px; font-weight: 700; font-size: 12px; cursor: pointer; transition: all 0.3s; }
    .btn-reset:hover { background: rgba(239, 68, 68, 0.2); box-shadow: 0 0 15px rgba(239, 68, 68, 0.4); transform: translateY(-2px); }
    .stats-bar { max-width: 600px; margin: 16px auto 0; padding: 0 16px; display: flex; gap: 12px; position: relative; z-index: 1; }
    .stat-box { flex: 1; background: var(--bg-card); border: 1px solid var(--border-glass); border-radius: 16px; padding: 12px; text-align: center; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); position: relative; overflow: hidden; transition: transform 0.3s; }
    .stat-box:hover { transform: translateY(-3px); border-color: rgba(255,255,255,0.2); }
    .stat-box::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, var(--tai-color), transparent); background-size: 200% 100%; animation: shimmer 2s linear infinite; }
    .stat-lbl { font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 4px; }
    .stat-val { font-size: 20px; font-weight: 800; color: #fff; animation: pulseNum 2.5s infinite; }
    .stat-val.highlight { color: var(--tai-color); }
    .container { padding: 16px; display: flex; flex-direction: column; gap: 12px; max-width: 600px; margin: 0 auto; position: relative; z-index: 1; }
    .card { background: var(--bg-card); border: 1px solid var(--border-glass); border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); position: relative; }
    .card:hover { transform: translateY(-3px) scale(1.01); border-color: rgba(255,255,255,0.2); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    .card.active { animation: borderGlow 2s infinite alternate; background: linear-gradient(145deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.8)); }
    .col-left { display: flex; flex-direction: column; gap: 6px; flex: 1.2; }
    .session-id { font-size: 16px; font-weight: 800; color: #fff; letter-spacing: 0.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
    .bot-info { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .bot-lbl { color: var(--text-muted); font-weight: 600; }
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge-tai { background: rgba(14, 165, 233, 0.15); color: #7dd3fc; border: 1px solid rgba(14, 165, 233, 0.4); box-shadow: 0 0 10px inset rgba(14, 165, 233, 0.2); }
    .badge-xiu { background: rgba(236, 72, 153, 0.15); color: #f9a8d4; border: 1px solid rgba(236, 72, 153, 0.4); box-shadow: 0 0 10px inset rgba(236, 72, 153, 0.2); }
    .conf-wrap { margin-top: 6px; width: 100%; max-width: 150px; }
    .conf-text { font-size: 10px; color: var(--text-muted); font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 2px; }
    .conf-bg { height: 5px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; position: relative; }
    .conf-bar { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--tai-color), #818cf8, var(--tai-color)); background-size: 200% 100%; animation: shimmer 2s linear infinite; transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1); }
    .conf-bar.xiu { background: linear-gradient(90deg, var(--xiu-color), #f472b6, var(--xiu-color)); background-size: 200% 100%; animation: shimmer 2s linear infinite; }
    .engine-tag { font-size: 8px; color: var(--gold); opacity: 0.8; margin-top: 4px; display: block; text-transform: uppercase; letter-spacing: 1px;}
    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 4px; }
    .pred-circle { padding: 6px 16px; border-radius: 20px; font-weight: 800; font-size: 14px; letter-spacing: 1px; text-transform: uppercase; transition: all 0.3s; }
    .pred-tai { background: linear-gradient(135deg, #0284c7, #38bdf8); color: #fff; box-shadow: 0 0 15px var(--tai-glow); border: 1px solid #7dd3fc; }
    .pred-xiu { background: linear-gradient(135deg, #be185d, #ec4899); color: #fff; box-shadow: 0 0 15px var(--xiu-glow); border: 1px solid #f9a8d4; }
    .pred-wait { border: 1px dashed rgba(255,255,255,0.2); color: var(--text-muted); }
    .dice { font-size: 12px; font-weight: 600; color: #cbd5e1; white-space: nowrap; }
    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.8; }
    .status { font-size: 13px; font-weight: 800; display: flex; align-items: center; gap: 4px; }
    .st-win { color: var(--win); text-shadow: 0 0 12px rgba(16, 185, 129, 0.5); }
    .st-lose { color: var(--lose); text-shadow: 0 0 12px rgba(239, 68, 68, 0.5); }
    .st-wait { color: var(--gold); text-shadow: 0 0 12px rgba(251, 191, 36, 0.5); }
    .spin-icon { display: inline-block; animation: spinWait 2s linear infinite; }
    .loading { text-align: center; padding: 40px; color: var(--tai-color); font-weight: 600; animation: pulseNum 2s infinite; }
    @media (max-width: 380px) {
        .header-title { font-size: 15px; } .stat-val { font-size: 16px; }
        .session-id { font-size: 14px; } .dice { font-size: 11px; }
        .pred-circle { font-size: 12px; padding: 4px 12px; }
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-left">
        <div class="live-dot"></div>
        <div class="header-title">khánh ly xinhgai </div>
    </div>
    <button class="btn-reset" onclick="confirmReset()">↻ Reset</button>
</div>

<div class="stats-bar">
    <div class="stat-box"><div class="stat-lbl">Tổng Phiên</div><div class="stat-val" id="stat-total">0</div></div>
    <div class="stat-box"><div class="stat-lbl">Thắng</div><div class="stat-val highlight" id="stat-win">0</div></div>
    <div class="stat-box"><div class="stat-lbl">Tỷ Lệ</div><div class="stat-val highlight" id="stat-rate">0%</div></div>
</div>

<div class="container" id="list-container">
    <div class="loading">Khởi động 36 Patterns Engine...</div>
</div>

<script>
let isResetting = false;
function animateNumber(el, target, suffix = '') {
    const start = parseInt(el.innerText.replace(/[^0-9]/g, '')) || 0;
    if (start === target) { el.innerText = target + suffix; return; }
    const duration = 800; const startTime = performance.now();
    function update(t) {
        const p = Math.min((t - startTime) / duration, 1);
        const ease = 1 - Math.pow(1 - p, 4);
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
        if (data.error) {
            document.getElementById('list-container').innerHTML = `<div class="loading" style="color:var(--lose)">Lỗi API: ${data.error}. Đang thử lại...</div>`;
            return;
        }
        renderList(data.rows || [], data.stats || {});
    } catch (e) {
        document.getElementById('list-container').innerHTML = '<div class="loading" style="color:var(--lose)">Mất kết nối Server!</div>';
    }
}
function renderList(rows, stats) {
    const container = document.getElementById('list-container');
    if (stats.total > 0) {
        animateNumber(document.getElementById('stat-total'), stats.total);
        animateNumber(document.getElementById('stat-win'), stats.correct);
        animateNumber(document.getElementById('stat-rate'), Math.round((stats.correct / stats.total) * 100), '%');
    } else {
        document.getElementById('stat-total').innerText = '0';
        document.getElementById('stat-win').innerText = '0';
        document.getElementById('stat-rate').innerText = '0%';
    }
    if (!rows.length) {
        container.innerHTML = '<div class="loading">Không có dữ liệu từ API.</div>';
        return;
    }
    let html = '';
    rows.forEach((row) => {
        const isActive = row.is_next ? ' active' : '';
        let badgeHtml = `<span class="badge" style="background:rgba(255,255,255,0.05);color:#94a3b8;">Nghỉ</span>`;
        let confClass = 'conf-bar';
        if (row.prediction === "Tài") badgeHtml = `<span class="badge badge-tai">Cược Tài</span>`;
        else if (row.prediction === "Xỉu") { badgeHtml = `<span class="badge badge-xiu">Cược Xỉu</span>`; confClass = 'conf-bar xiu'; }
        let predHtml = `<span class="pred-circle pred-wait">-</span>`;
        if (row.prediction === "Tài") predHtml = `<span class="pred-circle pred-tai">TÀI</span>`;
        if (row.prediction === "Xỉu") predHtml = `<span class="pred-circle pred-xiu">XỈU</span>`;
        let diceHtml = "? + ? + ?";
        if (row.dice !== "? + ? + ?") {
            const p = row.dice.split(" + ");
            diceHtml = `${row.dice} <span style="color:#94a3b8">(${parseInt(p[0]) + parseInt(p[1]) + parseInt(p[2])})</span>`;
        }
        let statusHtml = `<div class="status" style="color:#64748b">-</div>`;
        if (row.is_next) statusHtml = `<div class="status st-wait">Chờ <span class="spin-icon"></span></div>`;
        else if (row.is_correct === true) statusHtml = `<div class="status st-win">Đúng</div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status st-lose">Sai</div>`;
        html += `
            <div class="card${isActive}">
                <div class="col-left">
                    <div class="session-id">#${row.phien}</div>
                    <div class="bot-info"><span class="bot-lbl">Bot:</span> ${badgeHtml}</div>
                    <div class="conf-wrap">
                        <div class="conf-text"><span>Độ tin cậy</span><span>${row.confidence}%</span></div>
                        <div class="conf-bg"><div class="${confClass}" style="width:${row.confidence}%"></div></div>
                        <span class="engine-tag">36 Patterns Active</span>
                    </div>
                </div>
                <div class="col-mid">${predHtml}<div class="dice">${diceHtml}</div></div>
                <div class="col-right">${statusHtml}</div>
            </div>`;
    });
    container.innerHTML = html;
}
async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', text: "Ẩn lịch sử hiện tại, tiếp tục tính toán ngầm!",
        icon: 'warning', background: '#0f172a', color: '#fff',
        showCancelButton: true, confirmButtonColor: '#0ea5e9', cancelButtonColor: '#334155',
        confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', background: '#0f172a', color: '#fff', allowOutsideClick: false, didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Thành công!', text: 'Đã chốt mốc #' + data.reset_to, icon: 'success', background: '#0f172a', color: '#fff', confirmButtonColor: '#0ea5e9' });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire({ title: 'Lỗi!', text: error.message, icon: 'error', background: '#0f172a', color: '#fff' });
                isResetting = false;
            }
        }
    });
}
fetchData(); setInterval(fetchData, 4000);
</script>
</body>
</html>
"""

# =====================================================================
# FETCH DỮ LIỆU
# =====================================================================
def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Accept': 'application/json'}
        r = requests.get(API_URL, timeout=8, headers=headers)
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
                return rows
        return []
    except Exception as e:
        print(f"[API ERROR] {e}")
        return []

# =====================================================================
# THUẬT TOÁN MẪU 36 - FULL PATTERN RECOGNITION
# =====================================================================
def find_historical_follow(results, pattern_chrono):
    """
    Tìm tất cả lần xuất hiện pattern_chrono (theo thứ tự thời gian cũ → mới)
    và đếm kết quả TIẾP THEO (Tài / Xỉu).
    """
    k = len(pattern_chrono)
    n = len(results)
    if n <= k + 1:
        return 0, 0
    chrono = list(reversed(results))  # cũ → mới
    tai, xiu = 0, 0
    for i in range(n - k - 1):  # bỏ lần xuất hiện cuối cùng (chính là hiện tại)
        match = True
        for j in range(k):
            if chrono[i + j] != pattern_chrono[j]:
                match = False
                break
        if match:
            if chrono[i + k] == "Tài":
                tai += 1
            else:
                xiu += 1
    return tai, xiu


def find_streak_follow(results, target_val, target_len):
    """Đếm kết quả sau các chuỗi bệt cùng giá trị, cùng độ dài."""
    chrono = list(reversed(results))
    n = len(chrono)
    tai, xiu = 0, 0
    i = 0
    while i < n:
        if chrono[i] == target_val:
            j = i
            while j < n and chrono[j] == target_val:
                j += 1
            streak = j - i
            matches = (streak == target_len) if target_len < 4 else (streak >= 4)
            if matches and j < n:  # bỏ streak đang diễn ra (cuối mảng)
                if chrono[j] == "Tài":
                    tai += 1
                else:
                    xiu += 1
            i = j
        else:
            i += 1
    return tai, xiu


def detect_36_patterns(results):
    """
    THUẬT TOÁN MẪU 36 - Phân tích 36 loại cầu khác nhau.
    Trả về list các pattern đang kích hoạt với dự đoán + win_rate + weight.
    """
    n = len(results)
    if n < 8:
        return []

    detections = []
    chrono = list(reversed(results))
    curr_val = results[0]
    opp_val = "Xỉu" if curr_val == "Tài" else "Tài"

    def try_ngram(pid, pname, chrono_pattern, weight, min_wr=0.55):
        tai, xiu = find_historical_follow(results, chrono_pattern)
        total = tai + xiu
        if total < 2:
            return
        if tai >= xiu:
            pred, wr = "Tài", tai / total
        else:
            pred, wr = "Xỉu", xiu / total
        if wr >= min_wr:
            detections.append({
                'id': pid, 'name': pname, 'prediction': pred,
                'win_rate': wr, 'weight': weight, 'samples': total
            })

    # ========= GROUP A: 8 N-GRAM PATTERNS (NG2 → NG9) =========
    for k in range(2, 10):
        if len(chrono) >= k:
            pattern = chrono[-k:]
            try_ngram(f'NG{k}', f'N-gram bậc {k}', pattern, weight=3.0 + k * 0.4, min_wr=0.55)

    # ========= GROUP B: 8 STREAK PATTERNS =========
    curr_streak = 1
    for i in range(1, n):
        if results[i] == curr_val:
            curr_streak += 1
        else:
            break
    for target in [1, 2, 3, 4]:
        if curr_streak == target or (target == 4 and curr_streak >= 4):
            tai_f, xiu_f = find_streak_follow(results, curr_val, target)
            total = tai_f + xiu_f
            if total < 2:
                continue
            if curr_val == "Tài":
                cont, brk = tai_f, xiu_f
            else:
                cont, brk = xiu_f, tai_f
            if cont >= brk:
                pred, wr = curr_val, (cont + 0.5) / (total + 1)
            else:
                pred, wr = opp_val, (brk + 0.5) / (total + 1)
            if wr >= 0.52:
                detections.append({
                    'id': f'ST{curr_val[0]}{target}',
                    'name': f'Bệt {curr_val} {target}',
                    'prediction': pred, 'win_rate': wr,
                    'weight': 5.5 + target * 1.0, 'samples': total
                })

    # ========= GROUP C: 4 ALTERNATING PATTERNS (ALT3 → ALT6) =========
    alt_len = 1
    for i in range(1, n):
        if results[i] != results[i - 1]:
            alt_len += 1
        else:
            break
    for target in [3, 4, 5, 6]:
        if alt_len == target or (target == 6 and alt_len >= 6):
            tpl = [curr_val if i % 2 == 0 else opp_val for i in range(target)]
            tpl = list(reversed(tpl))
            try_ngram(f'ALT{target}', f'Đảo 1-1 bậc {target}', tpl, weight=4.5 + target * 0.5, min_wr=0.55)

    # ========= HELPER: BLOCK PATTERN DETECTION =========
    def try_block_pattern(block_pattern, name, pid_prefix, weight):
        total_len = sum(block_pattern)
        if n < total_len + 2:
            return
        for start_val in ["Tài", "Xỉu"]:
            template = []
            val = start_val
            for bl in block_pattern:
                template.extend([val] * bl)
                val = "Xỉu" if val == "Tài" else "Tài"
            for plen in range(total_len, max(2, total_len - 2) - 1, -1):
                if len(template) < plen:
                    continue
                tail_tpl = template[-plen:]
                if len(chrono) >= plen and chrono[-plen:] == tail_tpl:
                    tai, xiu = find_historical_follow(results, tail_tpl)
                    total = tai + xiu
                    if total >= 2:
                        if tai >= xiu:
                            pred, wr = "Tài", tai / total
                        else:
                            pred, wr = "Xỉu", xiu / total
                        if wr >= 0.52:
                            detections.append({
                                'id': f'{pid_prefix}_{start_val[0]}_{plen}',
                                'name': name, 'prediction': pred,
                                'win_rate': wr, 'weight': weight, 'samples': total
                            })
                    return

    # ========= GROUP D: 4 MIXED PATTERNS =========
    try_block_pattern([1, 2], 'Pattern 1-2', 'M12', 6.0)
    try_block_pattern([2, 1], 'Pattern 2-1', 'M21', 6.0)
    try_block_pattern([1, 2, 1], 'Pattern 1-2-1', 'M121', 5.5)
    try_block_pattern([2, 1, 2], 'Pattern 2-1-2', 'M212', 5.5)

    # ========= GROUP E: 4 SYMMETRIC PATTERNS =========
    try_block_pattern([2, 2], 'Pattern 2-2', 'S22', 5.5)
    try_block_pattern([3, 3], 'Pattern 3-3', 'S33', 5.5)
    try_block_pattern([2, 2, 2], 'Pattern 2-2-2', 'S222', 5.0)
    try_block_pattern([3, 3, 3], 'Pattern 3-3-3', 'S333', 5.0)

    # ========= GROUP F: 4 EXTREME PATTERNS =========
    try_block_pattern([1, 3], 'Pattern 1-3', 'E13', 5.0)
    try_block_pattern([3, 1], 'Pattern 3-1', 'E31', 5.0)
    try_block_pattern([1, 3, 1], 'Pattern 1-3-1', 'E131', 4.5)
    try_block_pattern([3, 1, 3], 'Pattern 3-1-3', 'E313', 4.5)

    # ========= GROUP G: 4 MARKOV & BIAS PATTERNS =========
    # Markov 1
    m1_tai, m1_xiu = 0, 0
    for i in range(n - 1):
        if results[i] == curr_val:
            if results[i + 1] == "Tài":
                m1_tai += 1
            else:
                m1_xiu += 1
    total = m1_tai + m1_xiu
    if total >= 3:
        if m1_tai >= m1_xiu:
            pred, wr = "Tài", (m1_tai + 0.5) / (total + 1)
        else:
            pred, wr = "Xỉu", (m1_xiu + 0.5) / (total + 1)
        if wr >= 0.55:
            detections.append({
                'id': 'MK1', 'name': 'Markov Bậc 1',
                'prediction': pred, 'win_rate': wr,
                'weight': 4.0, 'samples': total
            })

    # Markov 2
    if n >= 3:
        last2 = (results[0], results[1])
        m2_tai, m2_xiu = 0, 0
        for i in range(n - 2):
            if (results[i], results[i + 1]) == last2:
                if results[i + 2] == "Tài":
                    m2_tai += 1
                else:
                    m2_xiu += 1
        total = m2_tai + m2_xiu
        if total >= 2:
            if m2_tai >= m2_xiu:
                pred, wr = "Tài", (m2_tai + 0.5) / (total + 1)
            else:
                pred, wr = "Xỉu", (m2_xiu + 0.5) / (total + 1)
            if wr >= 0.55:
                detections.append({
                    'id': 'MK2', 'name': 'Markov Bậc 2',
                    'prediction': pred, 'win_rate': wr,
                    'weight': 5.0, 'samples': total
                })

    # Bias Tài / Xỉu
    if n >= 15:
        recent = results[:15]
        tc = sum(1 for r in recent if r == "Tài")
        ratio = tc / 15.0
        if ratio >= 0.6:
            detections.append({
                'id': 'BIAS_T', 'name': 'Nghiêng Tài 60%+',
                'prediction': 'Tài', 'win_rate': ratio,
                'weight': 3.5, 'samples': 15
            })
        elif ratio <= 0.4:
            detections.append({
                'id': 'BIAS_X', 'name': 'Nghiêng Xỉu 60%+',
                'prediction': 'Xỉu', 'win_rate': 1 - ratio,
                'weight': 3.5, 'samples': 15
            })

    return detections


def analyze_pattern(results, dice_sums=None):
    """
    Tổng hợp 36 patterns → dự đoán cuối cùng + confidence 50-99%.
    """
    if not results or len(results) < 5:
        return "Tài", 50.0, "Khởi tạo"

    detections = detect_36_patterns(results)

    if not detections:
        recent = results[:5]
        tc = sum(1 for r in recent if r == "Tài")
        if tc > 2:
            return "Tài", 55.0, "Đa số 5 phiên gần nhất"
        return "Xỉu", 55.0, "Đa số 5 phiên gần nhất"

    tai_score, xiu_score = 0.0, 0.0
    for d in detections:
        sample_factor = min(d['samples'] / 10.0, 2.0)
        score = d['win_rate'] * d['weight'] * sample_factor
        if d['prediction'] == "Tài":
            tai_score += score
        else:
            xiu_score += score

    total = tai_score + xiu_score
    if total == 0:
        return results[0], 50.0, "Nhiễu"

    if tai_score > xiu_score:
        winner, win_ratio = "Tài", tai_score / total
    else:
        winner, win_ratio = "Xỉu", xiu_score / total

    # Confidence 50 → 99% (đường cong mũ)
    shift = win_ratio - 0.5
    conf = 50.0 + (shift * 2) ** 1.5 * 49.0
    max_samples = max(d['samples'] for d in detections)
    sample_factor = min(max_samples / 15.0, 1.0)
    conf = 50.0 + (conf - 50.0) * sample_factor
    conf = max(50.0, min(99.0, conf))

    winning = [d for d in detections if d['prediction'] == winner]
    if winning:
        best = max(winning, key=lambda x: x['win_rate'] * x['weight'])
        pattern_name = best['name']
    else:
        pattern_name = "Tổng hợp 36 Patterns"

    return winner, round(conf, 1), pattern_name


# =====================================================================
# FLASK ROUTES
# =====================================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    global RESET_SESSION_ID
    try:
        valid = sorted(fetch_sessions(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'error': 'Không lấy được dữ liệu từ API'}), 500

        out, correct_count, total_past = [], 0, 0
        latest = valid[-1]
        next_phien = latest['phien'] + 1
        h_next = [v['result'] for v in valid][::-1]
        d_next = [v.get('total', 0) for v in valid][::-1]
        next_pred, next_conf, _ = analyze_pattern(h_next, d_next)

        out.append({
            'phien': next_phien, 'is_next': True,
            'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None
        })

        for i in range(len(valid) - 1, -1, -1):
            current = valid[i]
            if current['phien'] <= RESET_SESSION_ID:
                break
            if len(out) > 20:
                break
            history_list = [v['result'] for v in valid[:i]][::-1]
            dice_list = [v.get('total', 0) for v in valid[:i]][::-1]
            if history_list:
                pred, conf, _ = analyze_pattern(history_list, dice_list)
                is_correct = (pred == current['result'])
                total_past += 1
                if is_correct:
                    correct_count += 1
            else:
                pred, conf = "Tài", 50.0
                is_correct = None
            out.append({
                'phien': current['phien'], 'is_next': False,
                'prediction': pred, 'confidence': conf,
                'result': current['result'], 'dice': current['dice'],
                'is_correct': is_correct
            })

        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict_only():
    try:
        valid = sorted(fetch_sessions(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu từ API'}), 500

        latest = valid[-1]
        next_phien = latest['phien'] + 1
        h_next = [v['result'] for v in valid][::-1]
        d_next = [v.get('total', 0) for v in valid][::-1]

        detections = detect_36_patterns(h_next)
        pred, conf, pattern = analyze_pattern(h_next, d_next)

        model_details = []
        for d in detections:
            model_details.append({
                'model_id': d['id'],
                'model_name': d['name'],
                'predicts': d['prediction'],
                'historical_winrate': f"{round(d['win_rate'] * 100, 1)}%",
                'weight_priority': round(d['weight'], 2),
                'samples': d['samples']
            })
        model_details.sort(key=lambda x: x['weight_priority'], reverse=True)

        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'final_prediction': pred,
            'final_confidence': conf,
            'strongest_pattern': pattern,
            'total_models_active': len(model_details),
            'max_patterns': 36,
            'api_models_breakdown': model_details,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        valid = sorted(fetch_sessions(), key=lambda x: x['phien'])
        if valid:
            RESET_SESSION_ID = valid[-1]['phien']
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
