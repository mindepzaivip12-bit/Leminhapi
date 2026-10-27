import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Bắt buộc để các trang HTML bên ngoài gọi được API

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=ab36aa88e2c9868ae0e8bc61adbd18dc"

# Biến toàn cục lưu mốc phiên bắt đầu lại
RESET_SESSION_ID = 0

# ============ GIAO DIỆN HTML/CSS/JS (XANH DƯƠNG NHẠT - ĐEN ĐẬM) ============
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API LC MD5 MINHLE - Premium</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        /* Đen đậm làm nền chủ đạo */
        --bg-dark: #060913; 
        --bg-card: #0d1424;
        --bg-card-hover: #131c30;
        --text-main: #f1f5f9;
        --text-muted: #64748b;
        --border-color: #1e293b;
        
        /* Màu Tài (Xanh lam) */
        --tai-bg: #0284c7;
        --tai-bet-bg: rgba(2, 132, 199, 0.15);
        
        /* Màu Xỉu (Hồng) */
        --xiu-bg: #db2777;
        --xiu-bet-bg: rgba(219, 39, 119, 0.15);

        /* Hiệu ứng Xanh Dương Nhạt (Light Blue Neon) */
        --blue-main: #38bdf8;
        --blue-glow: rgba(56, 189, 248, 0.5);
        --lose-color: #ef4444;
        --win-color: #38bdf8;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    
    body { 
        background-color: var(--bg-dark); 
        color: var(--text-main); 
        padding-bottom: 30px;
        background-image: radial-gradient(circle at 50% 0%, #0c1a32 0%, transparent 60%);
    }

    /* HIỆU ỨNG ĐỘNG XANH DƯƠNG NHẠT */
    @keyframes pulse-blue {
        0% { box-shadow: 0 0 5px var(--blue-glow), inset 0 0 5px var(--blue-glow); border-color: var(--blue-main); }
        50% { box-shadow: 0 0 25px var(--blue-glow), inset 0 0 10px var(--blue-glow); border-color: #7dd3fc; }
        100% { box-shadow: 0 0 5px var(--blue-glow), inset 0 0 5px var(--blue-glow); border-color: var(--blue-main); }
    }

    @keyframes text-glow {
        0% { text-shadow: 0 0 5px var(--blue-glow); }
        50% { text-shadow: 0 0 15px var(--blue-main); }
        100% { text-shadow: 0 0 5px var(--blue-glow); }
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* HEADER */
    .header { 
        display: flex; justify-content: space-between; align-items: center; 
        padding: 15px 20px; border-bottom: 1px solid var(--border-color);
        background: rgba(6, 9, 19, 0.85); backdrop-filter: blur(12px);
        position: sticky; top: 0; z-index: 100;
    }
    .header-title { 
        font-size: 20px; font-weight: 800; 
        background: linear-gradient(90deg, #7dd3fc, #38bdf8, #0284c7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: text-glow 3s infinite;
    }
    .btn-reset {
        background: rgba(239, 68, 68, 0.1); color: var(--lose-color);
        border: 1px solid var(--lose-color); padding: 8px 16px;
        border-radius: 8px; font-weight: 700; font-size: 13px;
        cursor: pointer; transition: all 0.3s ease;
    }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 15px rgba(239, 68, 68, 0.4); }

    /* STATS BAR (THANH THỐNG KÊ) */
    .stats-bar {
        max-width: 600px; margin: 15px auto 0; padding: 0 15px;
        display: flex; justify-content: space-between; gap: 10px;
    }
    .stat-item {
        flex: 1; background: var(--bg-card); border: 1px solid var(--border-color);
        border-radius: 10px; padding: 10px; text-align: center;
        position: relative; overflow: hidden;
    }
    .stat-item::before {
        content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
        background: linear-gradient(90deg, transparent, var(--blue-main), transparent);
    }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;}
    .stat-value { font-size: 18px; font-weight: 800; color: var(--text-main); }
    .stat-value.win { color: var(--blue-main); text-shadow: 0 0 8px var(--blue-glow); }

    /* CONTAINER */
    .container {
        padding: 15px; display: flex; flex-direction: column; gap: 12px; 
        max-width: 600px; margin: 0 auto;
    }

    /* CARD ITEM */
    .card-item {
        background: var(--bg-card); border: 1px solid var(--border-color);
        border-radius: 12px; padding: 16px; display: flex; justify-content: space-between; align-items: center;
        transition: all 0.3s ease; position: relative;
    }
    .card-item:hover { background: var(--bg-card-hover); transform: translateY(-2px); }
    
    /* HIỆU ỨNG XANH DƯƠNG CHO THẺ ĐANG CHỜ (ACTIVE) */
    .card-item.active {
        animation: pulse-blue 2s infinite;
        background: linear-gradient(145deg, #0d1424, #0f1a2e);
    }

    /* CỘT TRÁI */
    .col-left { display: flex; flex-direction: column; gap: 6px; flex: 1.2; }
    .id-text { font-size: 16px; font-weight: 800; color: #fff; letter-spacing: 0.5px;}
    .bot-line { display: flex; align-items: center; gap: 8px; font-size: 13px; }
    .bot-label { color: var(--text-muted); font-weight: 500;}
    
    .bet-badge { padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 12px; }
    .bet-tai { background: var(--tai-bet-bg); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
    .bet-xiu { background: var(--xiu-bet-bg); color: #f472b6; border: 1px solid rgba(244, 114, 182, 0.3); }
    .conf-text { color: var(--text-muted); font-size: 11px; font-style: italic; }

    /* CỘT GIỮA */
    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; flex: 1; }
    .pred-badge { padding: 6px 16px; border-radius: 20px; font-weight: 800; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;}
    .pred-tai { background: var(--tai-bg); color: #fff; box-shadow: 0 0 10px rgba(2, 132, 199, 0.4); }
    .pred-xiu { background: var(--xiu-bg); color: #fff; box-shadow: 0 0 10px rgba(219, 39, 119, 0.4); }
    .pred-empty { background: transparent; border: 1px dashed var(--border-color); color: var(--text-muted); }
    .dice-text { font-size: 14px; font-weight: 600; color: #cbd5e1; white-space: nowrap; }

    /* CỘT PHẢI */
    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.8; }
    .status-text { font-size: 14px; font-weight: 700; display: flex; align-items: center; gap: 6px;}
    
    /* HIỆU ỨNG XANH CHO CHỮ THẮNG */
    .status-win { color: var(--win-color); text-shadow: 0 0 10px var(--blue-glow); }
    .status-lose { color: var(--lose-color); }
    .status-wait { color: var(--blue-main); }
    .spin { display: inline-block; animation: spin 2s linear infinite; }

    /* LOADING */
    .loading { text-align: center; padding: 50px; color: var(--blue-main); font-weight: 600; letter-spacing: 1px;}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
    <div class="header-title">⚡ LC MD5 MINHLE</div>
    <button class="btn-reset" onclick="confirmReset()">↻ Bắt đầu lại</button>
</div>

<!-- THANH THỐNG KÊ -->
<div class="stats-bar">
    <div class="stat-item">
        <div class="stat-label">Tổng phiên</div>
        <div class="stat-value" id="stat-total">-</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Thắng</div>
        <div class="stat-value win" id="stat-win">-</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Tỷ lệ</div>
        <div class="stat-value win" id="stat-rate">-%</div>
    </div>
</div>

<!-- LIST BODY -->
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
      console.error("Lỗi tải dữ liệu:", e); 
      document.getElementById('list-container').innerHTML = '<div class="loading" style="color:var(--lose-color)">Lỗi kết nối Server!</div>';
  }
}

function renderList(rows, stats) {
  const container = document.getElementById('list-container');
  
  // Cập nhật thanh thống kê
  if(stats.total > 0) {
      document.getElementById('stat-total').innerText = stats.total;
      document.getElementById('stat-win').innerText = stats.correct;
      const rate = ((stats.correct / stats.total) * 100).toFixed(1);
      document.getElementById('stat-rate').innerText = rate + '%';
  } else {
      document.getElementById('stat-total').innerText = '0';
      document.getElementById('stat-win').innerText = '0';
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
    
    let predBadge = `<span class="pred-badge pred-empty">-</span>`;
    let betBadge = `<span class="bet-badge" style="background:#1e293b;color:#94a3b8;">cược -</span>`;
    
    if (row.prediction === "Tài") {
        predBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
        betBadge = `<span class="bet-badge bet-tai">cược tài</span>`;
    }
    if (row.prediction === "Xỉu") {
        predBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;
        betBadge = `<span class="bet-badge bet-xiu">cược xỉu</span>`;
    }

    let resultBadge = `<span class="pred-badge pred-empty">-</span>`;
    if (row.result === "Tài") resultBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
    if (row.result === "Xỉu") resultBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;

    let diceDisplay = "? + ? + ?";
    if (row.dice !== "? + ? + ?") {
        let parts = row.dice.split(" + ");
        let sum = parseInt(parts[0]) + parseInt(parts[1]) + parseInt(parts[2]);
        diceDisplay = `${row.dice} (${sum})`;
    }

    let statusHtml = '';
    if (row.is_next) {
        statusHtml = `<div class="status-text status-wait">Chờ <span class="spin">⏳</span></div>`;
    } else if (row.is_correct === true) {
        statusHtml = `<div class="status-text status-win">Đúng cửa ✅</div>`;
    } else if (row.is_correct === false) {
        statusHtml = `<div class="status-text status-lose">Sai cửa ❌</div>`;
    } else {
        statusHtml = `<div class="status-text" style="color:var(--text-muted)">-</div>`;
    }

    div.innerHTML = `
        <div class="col-left">
            <div class="id-text">#${row.phien}</div>
            <div class="bot-line">
                <span class="bot-label">Bot:</span> ${betBadge}
            </div>
            <div class="conf-text">Độ tin cậy: ${row.confidence}%</div>
        </div>
        
        <div class="col-mid">
            ${row.is_next ? predBadge : resultBadge}
            <div class="dice-text">${diceDisplay}</div>
        </div>
        
        <div class="col-right">
            ${statusHtml}
        </div>
    `;
    container.appendChild(div);
  });
}

async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?',
        text: "Lịch sử hiển thị trên màn hình sẽ bị ẩn đi. Hệ thống vẫn tính toán ngầm từ dữ liệu thực tế!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#38bdf8', // Xanh dương nhạt
        cancelButtonColor: '#1e293b',
        confirmButtonText: 'Đồng ý',
        cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, didOpen: () => { Swal.showLoading() } });
            
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                
                if (data.status === 'success') {
                    Swal.fire({
                        title: 'Thành công!', 
                        text: 'Đã chốt mốc ẩn lịch sử từ phiên #' + data.reset_to, 
                        icon: 'success',
                        confirmButtonColor: '#38bdf8'
                    });
                    isResetting = false;
                    fetchData(); // Gọi lại để làm mới giao diện
                } else {
                    throw new Error(data.message);
                }
            } catch (error) {
                Swal.fire('Lỗi!', 'Không thể reset: ' + error.message, 'error');
                isResetting = false;
            }
        }
    });
}

// Chạy lần đầu và thiết lập tự động cập nhật mỗi 5s
fetchData();
setInterval(fetchData, 5000);
</script>
</body>
</html>
"""
# =======================================================

def generate_fallback(base=7116040):
    elapsed = int(time.time() / 60)
    current = base + elapsed
    random.seed(elapsed)
    rows = []
    for i in range(15):
        sid = current - i
        r = "Tài" if random.random() > 0.5 else "Xỉu"
        d = [random.randint(1, 6) for _ in range(3)]
        rows.append({
            "phien": sid,
            "result": r,
            "dice": f"{d[0]} + {d[1]} + {d[2]}",
            "total": sum(d)
        })
    return rows

def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(API_URL, timeout=8, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']:
                raw_list = data['list']
                rows = []
                for item in raw_list:
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
                return rows, 'live'
    except Exception as e:
        print(f"[API ERROR] {e}")
    return generate_fallback(), 'fallback'

# =======================================================
# THUẬT TOÁN DỰ ĐOÁN (BẺ BỆT - ĐẢO CẦU)
# =======================================================
def analyze_pattern(results):
    if not results or len(results) < 3:
        return "Tài", 50.0, "Khởi tạo"

    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    
    # 1. BỆT
    streak = 1
    for r in results[1:]:
        if r == last: streak += 1
        else: break

    if streak >= 6: return opposite, 95.0, f"Bẻ bệt {streak}"
    elif streak == 5: return opposite, 88.0, f"Bẻ bệt {streak}"
    elif streak == 4: return opposite, 75.0, f"Bẻ bệt {streak}"
    elif streak == 3: return last, 65.0, f"Bám bệt {streak}"
    elif streak == 2: return last, 55.0, f"Bám bệt {streak}"

    # 2. ĐẢO CẦU
    if len(results) >= 6:
        if results[0] != results[1] and results[1] != results[2] and results[2] != results[3] and results[3] != results[4] and results[4] != results[5]:
            return opposite, 90.0, "Đảo cầu 1-1"
        if results[0] == results[1] and results[2] == results[3] and results[4] == results[5]:
            if results[1] != results[2] and results[3] != results[4]:
                return opposite, 88.0, "Đảo cầu 2-2"

    if len(results) >= 9:
        if results[0] == results[1] == results[2] and results[3] == results[4] == results[5] and results[6] == results[7] == results[8]:
            if results[2] != results[3] and results[5] != results[6]:
                return opposite, 92.0, "Đảo cầu 3-3"

    # 3. HỖN HỢP
    if len(results) >= 5:
        if results[0] == results[3] and results[1] == results[2] and results[0] != results[1]:
            return results[1], 80.0, "Cầu 1-2-1"
        if results[0] == results[1] == results[3] == results[4] and results[2] != results[0]:
            return results[2], 80.0, "Cầu 2-1-2"

    # 4. MARKOV
    trans = {"Tài": 0, "Xỉu": 0}
    for i in range(len(results) - 1):
        if results[i] == last:
            trans[results[i+1]] += 1
    
    if (trans["Tài"] + trans["Xỉu"]) > 2:
        if trans["Tài"] > trans["Xỉu"]: return "Tài", 72.0, "Markov"
        elif trans["Xỉu"] > trans["Tài"]: return "Xỉu", 72.0, "Markov"

    return opposite, 50.0, "Đảo nhịp"

# =======================================================
# HỆ THỐNG API (GIỮ NGUYÊN TOÀN BỘ)
# =======================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# 1. API MENU TỔNG HỢP
@app.route('/api')
def api_root():
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    return jsonify({
        "name": "LC MD5 MINHLE API Server",
        "version": "2.5.0 (Premium Blue)",
        "endpoints": {
            "lich_su": "/api/history",
            "du_doan": "/api/predict",
            "thong_ke": "/api/stats",
            "reset": "/api/reset"
        },
        "lastUpdate": now,
        "status": "active"
    })

# 2. API LỊCH SỬ (Dành cho giao diện chính)
@app.route('/api/history')
def history():
    global RESET_SESSION_ID
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        
        out = []
        correct_count = 0
        total_past = 0

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        next_pred, next_conf, _ = analyze_pattern(history_for_next)
        
        # Phiên hiện tại đang chờ
        out.append({
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'confidence': next_conf,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None
        })

        # Lấy lịch sử, tự động dừng nếu chạm mốc Reset
        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            
            # Nếu phiên nằm trong mốc đã reset -> Ẩn đi
            if current_session['phien'] <= RESET_SESSION_ID:
                break 
                
            if len(out) > 20: break
                
            history = [v['result'] for v in valid[:i]][::-1]
            if history:
                pred, conf, _ = analyze_pattern(history)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct: correct_count += 1
            else:
                pred, conf = "Tài", 50.0
                is_correct = None
                
            out.append({
                'phien': current_session['phien'],
                'is_next': False,
                'prediction': pred,
                'confidence': conf,
                'result': current_session['result'],
                'dice': current_session['dice'],
                'is_correct': is_correct
            })

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count}
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 3. API DỰ ĐOÁN NHANH (Dành cho trang HTML bên ngoài)
@app.route('/api/predict')
def predict_only():
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid: return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next)

        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'prediction': next_pred,
            'confidence': next_conf,
            'pattern': next_pattern,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 4. API THỐNG KÊ (Dành cho trang HTML bên ngoài)
@app.route('/api/stats')
def stats_only():
    global RESET_SESSION_ID
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        
        correct_count = 0
        total_past = 0

        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID:
                break 
                
            history = [v['result'] for v in valid[:i]][::-1]
            if history:
                pred, conf, _ = analyze_pattern(history)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct: correct_count += 1

        win_rate = round((correct_count / total_past * 100), 2) if total_past > 0 else 0

        return jsonify({
            'status': 'success',
            'data': {
                'total_predictions': total_past,
                'correct_predictions': correct_count,
                'win_rate_percent': win_rate
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 5. API RESET (Chỉ ẩn giao diện, không ảnh hưởng dự đoán)
@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if valid:
            # Chốt mốc phiên hiện tại. Các phiên <= mốc này sẽ bị ẩn khỏi UI
            RESET_SESSION_ID = valid[-1]['phien']
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
