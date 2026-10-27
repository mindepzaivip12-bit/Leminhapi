import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=ab36aa88e2c9868ae0e8bc61adbd18dc"

# Biến toàn cục lưu mốc phiên bắt đầu lại
RESET_SESSION_ID = 0

# ============ GIAO DIỆN HTML/CSS (BOOTSTRAP 5) ============
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API LC MD5 MINHLE</title>
<!-- Bootstrap 5 CSS -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<!-- SweetAlert2 -->
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-color: #0b0f19;
        --card-bg: #151b2b;
        --text-main: #e2e8f0;
        --text-muted: #94a3b8;
        --neon-blue: #3b82f6;
        --neon-green: #10b981;
        --neon-red: #ef4444;
        --neon-gold: #f59e0b;
    }
    body {
        background-color: var(--bg-color);
        color: var(--text-main);
        font-family: 'Inter', sans-serif;
        min-height: 100vh;
    }
    /* HEADER */
    .header-glass {
        background: rgba(21, 27, 43, 0.7);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(255,255,255,0.05);
        padding: 15px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .brand-title {
        font-size: 20px;
        font-weight: 700;
        letter-spacing: 1px;
        background: linear-gradient(90deg, #60a5fa, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    /* TABLE CONTAINER */
    .table-container {
        background: var(--card-bg);
        border-radius: 16px;
        padding: 15px;
        margin: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        border: 1px solid rgba(255,255,255,0.05);
        animation: fadeIn 0.5s ease-in-out;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    /* CUSTOM TABLE */
    .table {
        color: var(--text-main);
        margin-bottom: 0;
        border-collapse: separate;
        border-spacing: 0 8px;
    }
    .table thead th {
        border-bottom: 1px solid rgba(255,255,255,0.1);
        color: var(--text-muted);
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        padding: 12px;
    }
    .table tbody tr {
        background: #1e293b;
        transition: all 0.3s ease;
    }
    .table tbody tr:hover {
        background: #2a3b54;
        transform: scale(1.005);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .table tbody td {
        padding: 14px 12px;
        vertical-align: middle;
        border: none;
    }
    .table tbody td:first-child { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
    .table tbody td:last-child { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
    
    /* BADGES */
    .badge-custom {
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 12px;
        letter-spacing: 0.5px;
        display: inline-block;
        min-width: 55px;
        text-align: center;
    }
    .badge-tai { background: rgba(16, 185, 129, 0.15); color: var(--neon-green); border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-xiu { background: rgba(59, 130, 246, 0.15); color: var(--neon-blue); border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-empty { background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.1); }

    /* TEXT COLORS */
    .text-gold { color: var(--neon-gold); font-weight: 700; }
    .text-conf { color: #c084fc; font-weight: 700; }
    
    /* STATUS INDICATORS */
    .status-waiting { color: #fbbf24; font-weight: 600; display: flex; align-items: center; gap: 5px; }
    .status-win { color: var(--neon-green); font-weight: 600; display: flex; align-items: center; gap: 5px; }
    .status-lose { color: var(--neon-red); font-weight: 600; display: flex; align-items: center; gap: 5px; }
    
    .spin {
        width: 12px; height: 12px; border: 2px solid #fbbf24; border-top-color: transparent;
        border-radius: 50%; animation: spin 1s linear infinite; display: inline-block;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* RESET BUTTON */
    .btn-reset {
        background: linear-gradient(135deg, #ef4444, #b91c1c);
        color: white; border: none; padding: 8px 16px; border-radius: 8px;
        font-weight: 600; transition: all 0.3s; display: flex; align-items: center; gap: 6px;
    }
    .btn-reset:hover { transform: translateY(-2px); box-shadow: 0 0 15px rgba(239, 68, 68, 0.5); color: white; }

    /* CUSTOM SCROLLBAR */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: var(--bg-color); }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #475569; }
</style>
</head>
<body>

<!-- HEADER -->
<div class="header-glass">
    <div class="brand-title">API LC MD5 MINHLE</div>
    <button class="btn-reset" onclick="confirmReset()">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-arrow-counterclockwise" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M8 3a5 5 0 1 1-4.546 2.914.5.5 0 0 0-.908-.417A6 6 0 1 0 8 2z"/>
          <path d="M8 4.466V.534a.25.25 0 0 0-.41-.192L5.23 2.308a.25.25 0 0 0 0 .384l2.36 1.966A.25.25 0 0 0 8 4.466"/>
        </svg>
        Bắt đầu lại
    </button>
</div>

<!-- MAIN CONTENT -->
<div class="container-fluid">
    <div class="table-container">
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Phiên</th>
                        <th>Xúc Xắc</th>
                        <th>Dự Đoán</th>
                        <th>Kết Quả</th>
                        <th>Độ Tin Cậy</th>
                        <th>Trạng Thái</th>
                    </tr>
                </thead>
                <tbody id="table-body">
                    <tr><td colspan="6" class="text-center text-muted py-4">Đang tải dữ liệu...</td></tr>
                </tbody>
            </table>
        </div>
        <div class="mt-3 text-muted text-end" style="font-size: 12px;">
            <span id="stats-display">Tỷ lệ thắng: --% | Tổng: 0 phiên</span>
        </div>
    </div>
</div>

<script>
let isResetting = false;

async function fetchData() {
  if (isResetting) return; // Không fetch khi đang reset
  
  try {
    const r = await fetch('/api/history', { cache: 'no-store' });
    const data = await r.json();
    renderTable(data);
  } catch (e) {
    console.error("Lỗi tải dữ liệu:", e);
  }
}

function renderTable(data) {
  const tbody = document.getElementById('table-body');
  const rows = data.rows || [];
  
  // Cập nhật Stats
  const stats = data.stats || {};
  document.getElementById('stats-display').innerText = 
      `Tỷ lệ thắng: ${stats.winrate || 0}% | Tổng: ${stats.total || 0} phiên`;

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Không có dữ liệu. Hãy chờ phiên tiếp theo.</td></tr>';
    return;
  }

  tbody.innerHTML = '';
  rows.forEach((row, index) => {
    const tr = document.createElement('tr');
    
    // Xử lý Xúc Xắc
    let diceDisplay = row.dice === "? + ? + ?" ? "[?]" : "[" + row.dice.replace(/ \+ /g, ", ") + "]";

    // Xử lý Dự đoán
    let predBadge = `<span class="badge-custom badge-empty">-</span>`;
    if (row.prediction === "Tài") predBadge = `<span class="badge-custom badge-tai">TÀI</span>`;
    if (row.prediction === "Xỉu") predBadge = `<span class="badge-custom badge-xiu">XỈU</span>`;

    // Xử lý Kết quả
    let resultBadge = `<span class="badge-custom badge-empty">-</span>`;
    if (row.result === "Tài") resultBadge = `<span class="badge-custom badge-tai">TÀI</span>`;
    if (row.result === "Xỉu") resultBadge = `<span class="badge-custom badge-xiu">XỈU</span>`;

    // Xử lý Trạng thái
    let statusHtml = '';
    if (row.is_next) {
        statusHtml = `<div class="status-waiting"><span class="spin"></span> Chờ...</div>`;
    } else if (row.is_correct === true) {
        statusHtml = `<div class="status-win">✅ Thắng</div>`;
    } else if (row.is_correct === false) {
        statusHtml = `<div class="status-lose">❌ Thua</div>`;
    } else {
        statusHtml = `<div class="text-muted">-</div>`;
    }

    tr.innerHTML = `
        <td class="text-gold">#${row.phien}</td>
        <td class="text-muted font-monospace">${diceDisplay}</td>
        <td>${predBadge}</td>
        <td>${resultBadge}</td>
        <td class="text-conf">${row.is_next ? row.confidence : (row.confidence + '%')}</td>
        <td>${statusHtml}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function confirmReset() {
    Swal.fire({
        title: 'Bắt đầu lại?',
        text: "Toàn bộ lịch sử dự đoán và tỷ lệ thắng sẽ được đặt lại từ phiên hiện tại!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#334155',
        confirmButtonText: 'Đồng ý Reset',
        cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, didOpen: () => { Swal.showLoading() } });
            
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                
                if (data.status === 'success') {
                    Swal.fire('Thành công!', 'Đã đặt lại mốc dự đoán tại phiên #' + data.reset_to, 'success');
                    isResetting = false;
                    fetchData(); // Tải lại dữ liệu ngay lập tức
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
# CÁC ROUTES API
# =======================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/history')
def history():
    global RESET_SESSION_ID
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        
        out = []
        correct_count = 0
        total_past = 0

        # Dự đoán phiên tiếp theo
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        next_pred, next_conf, _ = analyze_pattern(history_for_next)
        
        out.append({
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'confidence': next_conf,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None
        })

        # Lấy lịch sử quá khứ (Chỉ lấy các phiên LỚN HƠN RESET_SESSION_ID)
        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            
            if current_session['phien'] <= RESET_SESSION_ID:
                break # Dừng lại nếu chạm mốc reset
                
            if len(out) > 20: break # Giới hạn 20 phiên
                
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

        winrate = round((correct_count / total_past) * 100, 1) if total_past > 0 else 0

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count, 'winrate': winrate},
            'source': source
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict')
def predict_only():
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid: return jsonify({'status': 'error'}), 404

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

@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if valid:
            # Đặt mốc reset bằng ID của phiên mới nhất hiện tại
            RESET_SESSION_ID = valid[-1]['phien']
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
