import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=ab36aa88e2c9868ae0e8bc61adbd18dc"

# ============ GIAO DIỆN HTML/CSS ============
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SICSUN BOT - AI PREDICTOR</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Montserrat', sans-serif; }
    body { background: radial-gradient(circle at top, #1a2332 0%, #0a0f17 100%); color: #e6edf3; min-height: 100vh; padding: 16px; display: flex; justify-content: center; }
    .app { width: 100%; max-width: 520px; }
    .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding: 0 6px; }
    .logo { display: flex; align-items: center; gap: 10px; }
    .logo h2 { font-size: 18px; letter-spacing: 1.5px; color: #58a6ff; }
    .pulse { width: 10px; height: 10px; border-radius: 50%; background: #3fb950; box-shadow: 0 0 10px #3fb950; animation: pulse 1.5s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
    .stats { text-align: right; }
    .stats #winrate { font-size: 18px; font-weight: 800; color: #3fb950; }
    .stats small { display: block; color: #8b949e; font-size: 11px; }
    .status-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding: 8px 12px; background: rgba(255,255,255,0.03); border-radius: 10px; font-size: 12px; color: #8b949e; }
    .badge { padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 11px; }
    .badge.live { background: rgba(63,185,80,0.15); color: #3fb950; }
    .badge.demo { background: rgba(210,153,34,0.15); color: #d29922; }
    .session-list { display: flex; flex-direction: column; gap: 12px; }
    .card { background: linear-gradient(135deg, #161b22 0%, #0d1117 100%); border: 1px solid #21262d; border-radius: 14px; padding: 14px 16px; display: flex; align-items: center; gap: 10px; transition: all 0.3s; position: relative; overflow: hidden; }
    .card::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: transparent; transition: background 0.3s; }
    .card.next { border-color: #58a6ff; box-shadow: 0 0 20px rgba(88,166,255,0.25); background: linear-gradient(135deg, #1a2332 0%, #0d1117 100%); }
    .card.next::before { background: #58a6ff; }
    .col.left { flex: 1.6; min-width: 0; }
    .col.mid { flex: 1; text-align: center; }
    .col.right { flex: 1; text-align: right; }
    .sid { font-size: 15px; font-weight: 800; color: #e6edf3; margin-bottom: 5px; }
    .botline { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 12px; margin-bottom: 4px; }
    .bot-label { color: #8b949e; }
    .bet { padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 800; letter-spacing: 0.3px; }
    .bet.tai { background: #1f6feb; color: #fff; }
    .bet.xiu { background: #d0356c; color: #fff; }
    .amt { color: #8b949e; font-size: 11px; }
    .conf { color: #6e7681; font-size: 11px; font-style: italic; display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
    .pattern { background: rgba(88,166,255,0.1); color: #58a6ff; padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; border: 1px solid rgba(88,166,255,0.2); }
    .pred { font-size: 17px; font-weight: 800; letter-spacing: 0.5px; margin-bottom: 3px; }
    .text-tai { color: #58a6ff; }
    .text-xiu { color: #f85149; }
    .dice { font-size: 13px; color: #c9d1d9; font-weight: 600; letter-spacing: 0.5px; }
    .sum { font-size: 11px; color: #6e7681; margin-top: 2px; }
    .stt { font-size: 13px; font-weight: 700; }
    .stt.ok { color: #3fb950; }
    .stt.err { color: #f85149; }
    .stt.waiting { color: #d29922; display: inline-flex; align-items: center; gap: 6px; justify-content: flex-end; }
    .stt.na { color: #6e7681; }
    .spin { width: 11px; height: 11px; border-radius: 50%; border: 2px solid #d29922; border-top-color: transparent; animation: spin 0.8s linear infinite; display: inline-block; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (max-width: 400px) { .pred { font-size: 15px; } .sid { font-size: 14px; } .dice { font-size: 12px; } .conf { flex-direction: column; align-items: flex-start; gap: 2px; } }
    .loading { text-align: center; color: #8b949e; padding: 40px; }
</style>
</head>
<body>
<div class="app">
  <div class="header">
    <div class="logo">
      <span class="pulse"></span>
      <h2>SICSUN AI</h2>
    </div>
    <div class="stats" id="stats">
      <span id="winrate">--%</span>
      <small id="total">0 phiên</small>
    </div>
  </div>

  <div class="status-bar">
    <span id="source-badge" class="badge">● LIVE</span>
    <span id="updated">Đang tải...</span>
  </div>

  <div class="session-list" id="session-list">
    <div class="loading">Đang phân tích cầu...</div>
  </div>
</div>

<script>
async function fetchData() {
  try {
    const r = await fetch('/api/history', { cache: 'no-store' });
    const data = await r.json();
    render(data);
  } catch (e) {
    document.getElementById('updated').textContent = 'Mất kết nối';
  }
}

function render(data) {
  const list = document.getElementById('session-list');
  const rows = data.rows || [];
  if (!rows.length) {
    list.innerHTML = '<div class="loading">Không có dữ liệu</div>';
    return;
  }

  const s = data.stats || {};
  document.getElementById('winrate').textContent = (s.winrate || 0) + '%';
  document.getElementById('total').textContent = (s.total || 0) + ' phiên';
  document.getElementById('winrate').style.color = s.winrate >= 70 ? '#3fb950' : s.winrate >= 50 ? '#d29922' : '#f85149';

  const badge = document.getElementById('source-badge');
  if (data.source === 'live') {
    badge.textContent = '● LIVE';
    badge.className = 'badge live';
  } else {
    badge.textContent = '● DEMO';
    badge.className = 'badge demo';
  }
  document.getElementById('updated').textContent = 'Cập nhật: ' + data.updated_at;

  list.innerHTML = '';
  rows.forEach(row => {
    const isTai = row.prediction === 'Tài';
    const betClass = isTai ? 'tai' : 'xiu';
    const textClass = isTai ? 'text-tai' : 'text-xiu';

    let status = '';
    if (row.is_next) {
      status = `<div class="stt waiting"><span class="spin"></span> Chờ KQ</div>`;
    } else if (row.is_correct === true) {
      status = `<div class="stt ok">Đúng cửa ✅</div>`;
    } else if (row.is_correct === false) {
      status = `<div class="stt err">Sai cửa ❌</div>`;
    } else {
      status = `<div class="stt na">—</div>`;
    }

    const card = document.createElement('div');
    card.className = 'card' + (row.is_next ? ' next' : '');
    card.innerHTML = `
      <div class="col left">
        <div class="sid">#${row.phien}</div>
        <div class="botline">
          <span class="bot-label">Bot:</span>
          <span class="bet ${betClass}">CƯỢC ${row.prediction.toUpperCase()}</span>
          <span class="amt">(${row.bet_amount.toLocaleString('vi-VN')}đ)</span>
        </div>
        <div class="conf">
          <span>(Tin cậy: ${row.confidence}%)</span>
          ${row.pattern ? `<span class="pattern">${row.pattern}</span>` : ''}
        </div>
      </div>
      <div class="col mid">
        <div class="pred ${textClass}">${row.prediction.toUpperCase()}</div>
        <div class="dice">${row.dice}</div>
        <div class="sum">(${row.total})</div>
      </div>
      <div class="col right">${status}</div>
    `;
    list.appendChild(card);
  });
}

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
# THUẬT TOÁN DỰ ĐOÁN NÂNG CAO (BẺ BỆT - ĐẢO CẦU)
# =======================================================
def analyze_pattern(results):
    """
    results: list kết quả (Mới nhất -> Cũ nhất) vd: ['Tài', 'Tài', 'Xỉu', ...]
    Trả về: (prediction, confidence, pattern_name)
    """
    if not results or len(results) < 3:
        return "Tài", 72.0, "Khởi tạo"

    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    
    # 1. NHẬN DIỆN CẦU BỆT (STREAK)
    streak = 1
    for r in results[1:]:
        if r == last:
            streak += 1
        else:
            break

    if streak >= 6:
        return opposite, 95.5, f"Bẻ bệt {streak} (Cực mạnh)"
    elif streak == 5:
        return opposite, 88.0, f"Bẻ bệt {streak}"
    elif streak == 4:
        return opposite, 80.0, f"Bẻ bệt {streak}"
    elif streak == 3:
        return last, 78.0, f"Bám bệt {streak}"

    # 2. NHẬN DIỆN CẦU ĐẢO (1-1, 2-2, 3-3)
    if len(results) >= 6:
        if results[0] != results[1] and results[1] != results[2] and results[2] != results[3]:
            if results[3] != results[4] and results[4] != results[5]:
                return opposite, 92.0, "Đảo cầu 1-1"

        if results[0] == results[1] and results[2] == results[3] and results[4] == results[5]:
            if results[1] != results[2] and results[3] != results[4]:
                return opposite, 90.0, "Đảo cầu 2-2"

    if len(results) >= 9:
        if results[0] == results[1] == results[2] and results[3] == results[4] == results[5] and results[6] == results[7] == results[8]:
            if results[2] != results[3] and results[5] != results[6]:
                return opposite, 94.0, "Đảo cầu 3-3"

    # 3. CẦU 1-2-1 hoặc 2-1-2
    if len(results) >= 4:
        if results[0] == results[3] and results[1] == results[2] and results[0] != results[1]:
            return results[1], 85.0, "Cầu 1-2-1"
        if results[0] == results[1] == results[3] == results[4] and results[2] != results[0]:
            return results[2], 85.0, "Cầu 2-1-2"

    # 4. CHUỖI MARKOV
    trans = {"Tài": 0, "Xỉu": 0}
    for i in range(len(results) - 1):
        if results[i] == last:
            trans[results[i+1]] += 1
    
    total_trans = trans["Tài"] + trans["Xỉu"]
    if total_trans > 2:
        if trans["Tài"] > trans["Xỉu"]:
            return "Tài", 78.0, "Xác suất Markov"
        elif trans["Xỉu"] > trans["Tài"]:
            return "Xỉu", 78.0, "Xác suất Markov"

    return opposite, 75.0, "Đảo nhịp"

# =======================================================
# CÁC ROUTES API
# =======================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/history')
def history():
    """API lấy toàn bộ lịch sử để hiển thị lên giao diện Web"""
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        
        out = []
        correct_count = 0
        total_past = 0

        # 1. Dự đoán phiên tiếp theo (+1)
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next)
        bet = 2000 if next_conf < 85 else (4000 if next_conf < 92 else 10000)
        
        out.append({
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'confidence': next_conf,
            'pattern': next_pattern,
            'bet_amount': bet,
            'dice': "? + ? + ?",
            'total': "?",
            'result': 'Chờ...',
            'is_correct': None
        })

        # 2. Chạy lại quá khứ để tính đúng/sai
        for i in range(len(valid) - 1, -1, -1):
            if len(out) > 15: break
                
            current_session = valid[i]
            history = [v['result'] for v in valid[:i]][::-1]
            
            if history:
                pred, conf, pattern = analyze_pattern(history)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct: correct_count += 1
            else:
                pred, conf, pattern = "Tài", 75.0, "Khởi tạo"
                is_correct = None
                
            bet_past = 2000 if conf < 85 else (4000 if conf < 92 else 10000)
            
            out.append({
                'phien': current_session['phien'],
                'is_next': False,
                'prediction': pred,
                'confidence': conf,
                'pattern': pattern,
                'bet_amount': bet_past,
                'dice': current_session['dice'],
                'total': current_session['total'],
                'result': current_session['result'],
                'is_correct': is_correct
            })

        winrate = round((correct_count / total_past) * 100, 1) if total_past > 0 else 0

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count, 'winrate': winrate},
            'source': source,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict')
def predict_only():
    """API CHUYÊN BIỆT: Chỉ trả về kết quả phiên sắp tới và % tin cậy"""
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 404

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next)
        
        # Tính tiền cược đề xuất
        bet = 2000 if next_conf < 85 else (4000 if next_conf < 92 else 10000)

        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'prediction': next_pred,       # Trả về "Tài" hoặc "Xỉu"
            'confidence': next_conf,       # Trả về % (VD: 88.5)
            'pattern': next_pattern,       # Thuật toán đang bắt cầu gì
            'bet_amount': bet,             # Tiền cược đề xuất
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
