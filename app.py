import os
import json
import urllib.parse
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS
import urllib3

# Tắt cảnh báo SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
RESET_SESSION_ID = 0

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API Dự Đoán Tài Xỉu Chuẩn Xác</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #060913; --bg-card: #0d1424; --bg-card-hover: #131c30;
        --text-main: #f1f5f9; --text-muted: #64748b; --border-color: #1e293b;
        --tai-bg: #0284c7; --tai-bet-bg: rgba(2, 132, 199, 0.15);
        --xiu-bg: #db2777; --xiu-bet-bg: rgba(219, 39, 119, 0.15);
        --blue-main: #38bdf8; --blue-glow: rgba(56, 189, 248, 0.5);
        --lose-color: #ef4444; --win-color: #38bdf8;
        --gold: #fbbf24;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    @keyframes bgFloat { 0%, 100% { transform: translateY(0); opacity: 0.6; } 50% { transform: translateY(-20px); opacity: 1; } }
    @keyframes rainbow-border { 0% { border-color: #38bdf8; box-shadow: 0 0 15px rgba(56,189,248,0.5); } 50% { border-color: #f472b6; box-shadow: 0 0 15px rgba(244,114,182,0.5); } 100% { border-color: #38bdf8; box-shadow: 0 0 15px rgba(56,189,248,0.5); } }
    @keyframes textGlow { 0%, 100% { text-shadow: 0 0 5px var(--blue-glow); } 50% { text-shadow: 0 0 15px var(--blue-main); } }
    @keyframes titleShine { 0% { background-position: -200% center; } 100% { background-position: 200% center; } }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes slideIn { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes shimmerBar { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
    @keyframes dotPulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(56,189,248,0.7); } 70% { box-shadow: 0 0 0 8px rgba(56,189,248,0); } }
    
    body { background-color: var(--bg-dark); color: var(--text-main); padding-bottom: 30px; min-height: 100vh; background-image: radial-gradient(circle at 50% 0%, #0c1a32 0%, transparent 60%); overflow-x: hidden; }
    
    .header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; border-bottom: 1px solid var(--border-color); background: rgba(6, 9, 19, 0.85); backdrop-filter: blur(14px); position: sticky; top: 0; z-index: 100; }
    .header-left { display: flex; align-items: center; gap: 10px; }
    .header-live-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--blue-main); animation: dotPulse 1.8s infinite; }
    .header-title { font-size: 20px; font-weight: 900; background: linear-gradient(90deg, #7dd3fc, #38bdf8, #a78bfa, #f472b6, #38bdf8); background-size: 300% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: titleShine 4s linear infinite, textGlow 3s infinite; }
    
    .btn-reset { background: rgba(239, 68, 68, 0.1); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 8px 16px; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; transition: all 0.3s; }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 15px rgba(239,68,68,0.5); }

    .stats-bar { max-width: 600px; margin: 15px auto 0; padding: 0 15px; display: flex; gap: 10px; }
    .stat-item { flex: 1; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px; text-align: center; position: relative; overflow: hidden; }
    .stat-item::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, var(--blue-main), transparent); background-size: 200% 100%; animation: shimmerBar 3s linear infinite; }
    .stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; font-weight: 600; }
    .stat-value { font-size: 20px; font-weight: 900; }
    .stat-value.win { color: var(--blue-main); }

    .container { padding: 15px; display: flex; flex-direction: column; gap: 12px; max-width: 600px; margin: 0 auto; }
    .card-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 16px; display: flex; justify-content: space-between; align-items: center; position: relative; animation: slideIn 0.4s ease-out backwards; }
    .card-item.active { background: linear-gradient(145deg, #0d1424, #0f1a2e); animation: slideIn 0.4s ease-out backwards, rainbow-border 3s linear infinite; border-width: 1.5px; }

    .col-left { display: flex; flex-direction: column; gap: 5px; flex: 1.2; }
    .id-text { font-size: 16px; font-weight: 800; color: #fff; }
    .bot-line { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .bot-label { color: var(--text-muted); font-weight: 600; }
    .bet-badge { padding: 3px 10px; border-radius: 20px; font-weight: 700; font-size: 11px; }
    .bet-tai { background: var(--tai-bet-bg); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); }
    .bet-xiu { background: var(--xiu-bet-bg); color: #f472b6; border: 1px solid rgba(244,114,182,0.3); }
    .conf-text { color: var(--text-muted); font-size: 11px; }
    .conf-bar-wrap { height: 3px; background: rgba(56,189,248,0.12); border-radius: 2px; overflow: hidden; margin-top: 3px; }
    .conf-bar { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #38bdf8, #a78bfa, #38bdf8); background-size: 200% 100%; animation: shimmerBar 2s linear infinite; }
    .pattern-tag { font-size: 10px; color: var(--gold); font-weight: 600; padding: 2px 8px; border-radius: 10px; background: rgba(251,191,36,0.08); border: 1px solid rgba(251,191,36,0.25); display: inline-block; margin-top: 3px; }

    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; flex: 1; }
    .pred-badge { padding: 5px 14px; border-radius: 20px; font-weight: 800; font-size: 13px; text-transform: uppercase; }
    .pred-tai { background: var(--tai-bg); color: #fff; box-shadow: 0 0 10px rgba(2,132,199,0.5); }
    .pred-xiu { background: var(--xiu-bg); color: #fff; box-shadow: 0 0 10px rgba(219,39,119,0.5); }
    .pred-empty { background: transparent; border: 1px dashed var(--border-color); color: var(--text-muted); }
    .dice-text { font-size: 13px; font-weight: 600; color: #cbd5e1; }

    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.8; }
    .status-text { font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 5px; }
    .status-win { color: var(--win-color); text-shadow: 0 0 10px var(--blue-glow); }
    .status-lose { color: var(--lose-color); }
    .status-wait { color: var(--blue-main); }
    .spin { display: inline-block; animation: spin 2s linear infinite; }
    .loading { text-align: center; padding: 50px; color: var(--blue-main); font-weight: 600; animation: textGlow 2s infinite; }
</style>
</head>
<body>
<div class="header">
    <div class="header-left">
        <div class="header-live-dot"></div>
        <div class="header-title">⚡ LC MD5 AI PREDICT</div>
    </div>
    <button class="btn-reset" onclick="confirmReset()">↻ Reset</button>
</div>
<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng phiên</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ</div><div class="stat-value win" id="stat-rate">0%</div></div>
</div>
<div class="container" id="list-container">
    <div class="loading">Đang kết nối Server...</div>
</div>
<script>
let isResetting = false;
function animateNumber(el, target, suffix = '') {
    const start = parseInt(el.innerText.replace(/[^0-9]/g, '')) || 0;
    if (start === target) { el.innerText = target + suffix; return; }
    const duration = 700; const startTime = performance.now();
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
        if (data.error) {
            document.getElementById('list-container').innerHTML = `<div class="loading" style="color:var(--lose-color); font-size:14px">⚠️ LỖI: ${data.error}</div>`;
            return;
        }
        renderList(data.rows || [], data.stats || {});
    } catch (e) {
        document.getElementById('list-container').innerHTML = '<div class="loading" style="color:var(--lose-color)">Lỗi kết nối mạng!</div>';
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
    container.innerHTML = '';
    rows.forEach((row, idx) => {
        const div = document.createElement('div');
        div.className = 'card-item' + (row.is_next ? ' active' : '');
        div.style.animationDelay = (idx * 30) + 'ms';
        
        let betBadge = `<span class="bet-badge bet-tai">cược tài</span>`;
        let predBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
        let resultBadge = `<span class="pred-badge pred-empty">-</span>`;

        if (row.prediction === "Xỉu") {
            predBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;
            betBadge = `<span class="bet-badge bet-xiu">cược xỉu</span>`;
        }
        if (row.result === "Tài") resultBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
        if (row.result === "Xỉu") resultBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;

        let diceDisplay = row.dice;
        if (row.dice !== "? + ? + ?") {
            const p = row.dice.split(" + ");
            diceDisplay = `${row.dice} (${parseInt(p[0]) + parseInt(p[1]) + parseInt(p[2])})`;
        }
        
        let statusHtml = '';
        if (row.is_next) statusHtml = `<div class="status-text status-wait">Chờ <span class="spin">⏳</span></div>`;
        else if (row.is_correct === true) statusHtml = `<div class="status-text status-win">Đúng ✅</div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status-text status-lose">Sai ❌</div>`;
        
        div.innerHTML = `
            <div class="col-left">
                <div class="id-text">#${row.phien}</div>
                <div class="bot-line"><span class="bot-label">Bot:</span> ${betBadge}</div>
                <div class="conf-text">Độ tin cậy: <b style="color:#38bdf8">${row.confidence}%</b></div>
                <div class="conf-bar-wrap"><div class="conf-bar" style="width:${row.confidence}%"></div></div>
                <div class="pattern-tag">${row.pattern}</div>
            </div>
            <div class="col-mid">${row.is_next ? predBadge : resultBadge}<div class="dice-text">${diceDisplay}</div></div>
            <div class="col-right">${statusHtml}</div>
        `;
        container.appendChild(div);
    });
}
async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', text: "Lịch sử trên màn hình sẽ bị ẩn!", icon: 'warning',
        showCancelButton: true, confirmButtonColor: '#38bdf8', cancelButtonColor: '#1e293b', confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Thành công!', text: 'Đã ẩn từ phiên #' + data.reset_to, icon: 'success', confirmButtonColor: '#38bdf8' });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire('Lỗi!', 'Không thể reset: ' + error.message, 'error'); isResetting = false;
            }
        }
    });
}
fetchData(); setInterval(fetchData, 4000);
</script>
</body>
</html>
"""

def get_blocks(results):
    """Chia mảng kết quả thành các khối (Block)"""
    if not results: return []
    blocks = []
    curr = results[0]
    count = 1
    for r in results[1:]:
        if r == curr:
            count += 1
        else:
            blocks.append({'val': curr, 'len': count})
            curr = r
            count = 1
    blocks.append({'val': curr, 'len': count})
    return blocks

def analyze_pattern(results):
    """
    Thuật toán phân tích cầu FULL - KHÔNG RANDOM
    results: Mảng kết quả, ván mới nhất ở index 0
    """
    if not results or len(results) < 3:
        return "Tài", 50.0, "Khởi tạo"
    
    last_result = results[0]
    opposite = "Xỉu" if last_result == "Tài" else "Tài"
    n = len(results)
    
    blocks = get_blocks(results)
    current_val = blocks[0]['val']
    current_len = blocks[0]['len']

    # 1. CẦU BỆT (Streak)
    if current_len >= 7:
        return opposite, 95.0, f"Bẻ Bệt {current_len} (Cực đại)"
    if current_len == 6:
        return opposite, 88.0, f"Bẻ Bệt {current_len}"
    if current_len == 5:
        return opposite, 80.0, f"Bẻ Bệt {current_len}"
    if current_len == 4:
        return current_val, 75.0, f"Bám Bệt {current_len}"
    if current_len == 3:
        return current_val, 65.0, f"Bám Bệt {current_len}"
        
    # 2. CẦU ĐẢO / CẦU DÀI
    if len(blocks) >= 2:
        prev_len = blocks[1]['len']
        
        # Cầu 1-1
        if current_len == 1 and prev_len == 1:
            is_alternating = all(b['len'] == 1 for b in blocks[:5])
            if is_alternating:
                return opposite, 85.0, "Cầu Đảo 1-1"
            return opposite, 70.0, "Cầu 1-1"

        # Cầu 2-2
        if current_len == 2 and prev_len == 2:
            if len(blocks) >= 3 and blocks[2]['len'] == 2:
                return opposite, 90.0, "Cầu 2-2-2"
            return opposite, 80.0, "Cầu 2-2"

        # Cầu 3-3
        if current_len == 3 and prev_len == 3:
            return opposite, 85.0, "Cầu 3-3"
            
        # Cầu 1-2-1, 2-1-2
        if len(blocks) >= 3:
            p2 = blocks[2]['len']
            if current_len == 1 and prev_len == 2 and p2 == 1:
                return opposite, 82.0, "Cầu 1-2-1"
            if current_len == 2 and prev_len == 1 and p2 == 2:
                return opposite, 82.0, "Cầu 2-1-2"
            if current_len == 1 and prev_len == 3 and p2 == 1:
                return opposite, 78.0, "Cầu 1-3-1"

    # 3. MARKOV / N-GRAM (Tìm chuỗi tương tự)
    for length in [6, 5, 4]:
        if n < length + 2: continue
        current_seq = tuple(results[:length])
        match_tai, match_xiu = 0, 0
        
        for i in range(1, n - length):
            if tuple(results[i:i+length]) == current_seq:
                next_res = results[i-1]
                if next_res == "Tài": match_tai += 1
                else: match_xiu += 1
                
        total = match_tai + match_xiu
        if total >= 2:
            if match_tai > match_xiu:
                conf = 60 + (match_tai/total)*20
                return "Tài", round(conf, 1), f"Markov N-{length} ({match_tai}T-{match_xiu}X)"
            elif match_xiu > match_tai:
                conf = 60 + (match_xiu/total)*20
                return "Xỉu", round(conf, 1), f"Markov N-{length} ({match_tai}T-{match_xiu}X)"

    # 4. FALLBACK (Đảo nhịp an toàn)
    conf = 55.0
    pattern_name = "Đảo Nhịp (Mặc định)"
    if len(results) >= 2 and results[0] == results[1]:
        pattern_name = "Bẻ Cầu Ngắn"
        conf = 60.0
    return opposite, conf, pattern_name


def fetch_sessions():
    """Fetch API với 5 lớp bảo vệ, giả lập trình duyệt để không bị chặn"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Origin': 'https://tele68.com',
        'Referer': 'https://tele68.com/',
        'Connection': 'keep-alive'
    }
    
    # Lớp 1: Gọi trực tiếp
    try:
        r = requests.get(API_URL, headers=headers, timeout=5, verify=False)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']: return data['list'], None
    except: pass
    
    # Lớp 2: AllOrigins
    try:
        url = f"https://api.allorigins.win/raw?url={urllib.parse.quote(API_URL, safe='')}"
        r = requests.get(url, timeout=8, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']: return data['list'], None
    except: pass
    
    # Lớp 3: CorsProxy
    try:
        url = f"https://corsproxy.io/?{urllib.parse.quote(API_URL, safe='')}"
        r = requests.get(url, timeout=8, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']: return data['list'], None
    except: pass

    # Lớp 4: CodeTabs
    try:
        url = f"https://api.codetabs.com/v1/proxy?quest={urllib.parse.quote(API_URL, safe='')}"
        r = requests.get(url, timeout=8, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']: return data['list'], None
    except: pass
    
    # Lớp 5: ThingProxy
    try:
        url = f"https://thingproxy.freeboard.io/fetch/{API_URL}"
        r = requests.get(url, timeout=8, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']: return data['list'], None
    except: pass
    
    return None, "Không thể lấy dữ liệu. Vui lòng kiểm tra kết nối mạng hoặc thử lại sau."


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/history')
def history():
    global RESET_SESSION_ID
    try:
        raw_list, error = fetch_sessions()
        if raw_list is None: 
            return jsonify({'error': error}), 500
            
        valid = []
        for item in raw_list:
            res = "Tài" if item.get('resultTruyenThong') == "TAI" else "Xỉu"
            dices = item.get('dices', [0, 0, 0])
            dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
            total = item.get('point', sum(dices))
            valid.append({'phien': int(item['id']), 'result': res, 'dice': dice_str, 'total': total})
            
        valid.sort(key=lambda x: x['phien'])
        
        out = []
        correct_count = 0
        total_past = 0
        
        # 1. Dự đoán phiên tiếp theo
        next_phien = valid[-1]['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next)
        
        out.append({
            'phien': next_phien, 'is_next': True, 'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None, 'pattern': next_pattern
        })
        
        # 2. Backtesting (Chạy thuật toán cho các phiên cũ để tính Đúng/Sai)
        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID: break
            if len(out) > 25: break
            
            history_list = [v['result'] for v in valid[:i]][::-1]
            
            if history_list:
                pred, conf, pattern = analyze_pattern(history_list)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct: correct_count += 1
            else:
                pred, conf, pattern = "Tài", 50.0, "Khởi tạo"
                is_correct = None
                
            out.append({
                'phien': current_session['phien'], 'is_next': False, 'prediction': pred, 'confidence': conf,
                'result': current_session['result'], 'dice': current_session['dice'],
                'is_correct': is_correct, 'pattern': pattern
            })
            
        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        raw_list, error = fetch_sessions()
        if raw_list is None: 
            return jsonify({'status': 'error', 'message': error}), 500
            
        valid = [{'phien': int(item['id'])} for item in raw_list]
        valid.sort(key=lambda x: x['phien'])
        
        if valid:
            RESET_SESSION_ID = valid[-1]['phien']
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
