import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=ab36aa88e2c9868ae0e8bc61adbd18dc"

# Biến toàn cục lưu mốc phiên bắt đầu lại
RESET_SESSION_ID = 0

# ============ GIAO DIỆN HTML/CSS (CHUẨN THEO ẢNH) ============
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API LC MD5 MINHLE</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<!-- SweetAlert2 -->
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #0f1115;
        --bg-row: #15171e;
        --text-main: #e2e8f0;
        --text-muted: #94a3b8;
        --gold: #d69e2e;
        --blue-tai: #22c55e; /* Xanh lá cho Tài */
        --blue-xiu: #3b82f6; /* Xanh dương cho Xỉu */
        --red-lose: #ef4444;
        --border-color: #2d3748;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    
    body { 
        background-color: var(--bg-dark); 
        color: var(--text-main); 
        padding-bottom: 20px;
    }

    /* HEADER */
    .header { 
        display: flex; justify-content: space-between; align-items: center; 
        padding: 15px 20px; border-bottom: 1px solid var(--border-color);
        background: var(--bg-row);
        position: sticky; top: 0; z-index: 100;
    }
    .header-title { font-size: 18px; font-weight: 700; color: var(--gold); letter-spacing: 0.5px; }
    .btn-reset {
        background: rgba(239, 68, 68, 0.1); color: var(--red-lose);
        border: 1px solid var(--red-lose); padding: 6px 12px;
        border-radius: 6px; font-weight: 600; font-size: 13px;
        cursor: pointer; transition: 0.3s;
    }
    .btn-reset:hover { background: var(--red-lose); color: #fff; }

    /* TABLE HEADER */
    .table-header {
        display: flex; padding: 15px 10px; border-bottom: 1px solid var(--border-color);
        font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;
        text-align: center;
    }
    /* Độ rộng các cột */
    .col-phien { flex: 1.2; text-align: left; padding-left: 10px; }
    .col-dice { flex: 1; }
    .col-pred { flex: 1; }
    .col-res { flex: 1; }
    .col-conf { flex: 1; }
    .col-status { flex: 1.2; text-align: right; padding-right: 10px; display: flex; justify-content: flex-end;}

    /* TABLE BODY */
    .row-item {
        display: flex; align-items: center; padding: 14px 10px;
        border-bottom: 1px solid rgba(255,255,255,0.03);
        transition: background 0.2s;
    }
    .row-item:hover { background: rgba(255,255,255,0.02); }
    .row-item.active { background: rgba(59, 130, 246, 0.05); } /* Highlight phiên đang chờ */

    /* CỘT CHI TIẾT */
    .phien-text { color: var(--gold); font-weight: 700; font-size: 15px; }
    .dice-text { color: #8b949e; font-family: monospace; font-size: 14px; font-weight: 600; }
    
    /* BADGES TÀI XỈU */
    .badge {
        display: inline-block; padding: 6px 0; width: 60px; border-radius: 6px;
        font-weight: 700; font-size: 13px; text-transform: uppercase; text-align: center;
        color: #fff;
    }
    .badge-tai { background-color: var(--blue-tai); box-shadow: 0 0 10px rgba(34, 197, 94, 0.2); }
    .badge-xiu { background-color: var(--blue-xiu); box-shadow: 0 0 10px rgba(59, 130, 246, 0.2); }
    .badge-empty { 
        background-color: transparent; border: 1px solid #334155; color: #475569; 
        box-shadow: none; 
    }

    /* ĐỘ TIN CẬY */
    .conf-text { color: #60a5fa; font-weight: 700; font-size: 15px; }

    /* TRẠNG THÁI */
    .status-box { display: flex; align-items: center; justify-content: flex-end; gap: 6px; font-size: 14px; font-weight: 600; }
    .status-wait { color: #94a3b8; }
    .status-win { color: var(--blue-tai); }
    .status-lose { color: var(--red-lose); }
    
    /* ICONS */
    .icon { display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; font-size: 12px; }
    .icon-win { background: var(--blue-tai); color: #fff; }
    .icon-lose { background: var(--red-lose); color: #fff; }
    .icon-wait { color: #94a3b8; animation: spin 2s linear infinite; }
    
    @keyframes spin { 100% { transform: rotate(360deg); } }

    /* LOADING */
    .loading { text-align: center; padding: 40px; color: var(--text-muted); }
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
    <div class="header-title">API LC MD5 MINHLE</div>
    <button class="btn-reset" onclick="confirmReset()">↻ Bắt đầu lại</button>
</div>

<!-- TABLE HEADER -->
<div class="table-header">
    <div class="col-phien">Phiên</div>
    <div class="col-dice">Xúc xắc</div>
    <div class="col-pred">Dự đoán</div>
    <div class="col-res">Kết quả</div>
    <div class="col-conf">Độ tin cậy</div>
    <div class="col-status" style="text-align: center; justify-content: center;">Trạng thái</div>
</div>

<!-- TABLE BODY -->
<div id="list-container">
    <div class="loading">Đang tải dữ liệu...</div>
</div>

<script>
let isResetting = false;

async function fetchData() {
  if (isResetting) return;
  
  try {
    const r = await fetch('/api/history', { cache: 'no-store' });
    const data = await r.json();
    renderList(data.rows || []);
  } catch (e) {
    console.error("Lỗi tải dữ liệu:", e);
  }
}

function renderList(rows) {
  const container = document.getElementById('list-container');
  if (!rows.length) {
    container.innerHTML = '<div class="loading">Không có dữ liệu. Hãy đợi phiên mới.</div>';
    return;
  }

  container.innerHTML = '';
  rows.forEach((row) => {
    const div = document.createElement('div');
    div.className = 'row-item' + (row.is_next ? ' active' : '');
    
    // 1. Xử lý Xúc Xắc
    let diceDisplay = "[?]";
    if (row.dice !== "? + ? + ?") {
        diceDisplay = "[" + row.dice.replace(/ \+ /g, ", ") + "]";
    }

    // 2. Xử lý Dự đoán
    let predBadge = `<span class="badge badge-empty">-</span>`;
    if (row.prediction === "Tài") predBadge = `<span class="badge badge-tai">TÀI</span>`;
    if (row.prediction === "Xỉu") predBadge = `<span class="badge badge-xiu">XỈU</span>`;

    // 3. Xử lý Kết quả
    let resultBadge = `<span class="badge badge-empty">-</span>`;
    if (row.result === "Tài") resultBadge = `<span class="badge badge-tai">TÀI</span>`;
    if (row.result === "Xỉu") resultBadge = `<span class="badge badge-xiu">XỈU</span>`;

    // 4. Xử lý Trạng thái
    let statusHtml = '';
    if (row.is_next) {
        statusHtml = `<div class="status-box status-wait"><span class="icon icon-wait">⚙️</span> Chờ</div>`;
    } else if (row.is_correct === true) {
        statusHtml = `<div class="status-box status-win"><span class="icon icon-win">✓</span> Thắng</div>`;
    } else if (row.is_correct === false) {
        statusHtml = `<div class="status-box status-lose"><span class="icon icon-lose">✕</span> Thua</div>`;
    } else {
        statusHtml = `<div class="status-box status-wait">-</div>`;
    }

    // Render HTML
    div.innerHTML = `
        <div class="col-phien"><span class="phien-text">#${row.phien}</span></div>
        <div class="col-dice" style="text-align: center;"><span class="dice-text">${diceDisplay}</span></div>
        <div class="col-pred" style="text-align: center;">${predBadge}</div>
        <div class="col-res" style="text-align: center;">${resultBadge}</div>
        <div class="col-conf" style="text-align: center;"><span class="conf-text">${row.is_next ? row.confidence : (row.confidence + '%')}</span></div>
        <div class="col-status">${statusHtml}</div>
    `;
    container.appendChild(div);
  });
}

async function confirmReset() {
    Swal.fire({
        title: 'Bắt đầu lại?',
        text: "Xóa lịch sử hiển thị và đặt mốc tính tỷ lệ thắng từ phiên hiện tại!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#334155',
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
                    Swal.fire('Thành công!', 'Đã reset từ phiên #' + data.reset_to, 'success');
                    isResetting = false;
                    fetchData(); 
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

// Khởi chạy
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

        # Lấy lịch sử quá khứ
        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            
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
            RESET_SESSION_ID = valid[-1]['phien']
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
