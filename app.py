import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=ab36aa88e2c9868ae0e8bc61adbd18dc"

# ============ GIAO DIỆN HTML/CSS DẠNG BẢNG ============
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SICSUN AI - BS2 MD5</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Roboto', sans-serif; }
    body { background-color: #0b1017; color: #c9d1d9; padding: 10px; }
    
    /* HEADER */
    .header { display: flex; justify-content: space-between; align-items: center; padding: 10px 0 20px 0; border-bottom: 1px solid #21262d; margin-bottom: 10px; }
    .btn-menu { background: #161b22; color: #d29922; border: 1px solid #30363d; padding: 5px 15px; border-radius: 5px; cursor: pointer; font-weight: bold; }
    .title { color: #d29922; font-weight: 700; font-size: 18px; letter-spacing: 1px; }
    .spacer { width: 60px; } /* Cân bằng với nút menu */

    /* TABLE */
    .table-container { width: 100%; overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; text-align: center; font-size: 13px; }
    
    /* TABLE HEADER */
    thead th { padding: 12px 5px; color: #8b949e; font-weight: 500; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #21262d; }
    
    /* TABLE BODY */
    tbody tr { border-bottom: 1px solid #161b22; transition: background 0.2s; }
    tbody tr:hover { background-color: #121821; }
    tbody td { padding: 12px 5px; vertical-align: middle; }

    /* CỘT PHIÊN */
    .col-phien { color: #d29922; font-weight: 700; font-size: 13px; text-align: left; padding-left: 15px; }
    
    /* CỘT XÚC XẮC */
    .col-dice { color: #8b949e; font-family: monospace; font-size: 13px; }

    /* BADGES TÀI XỈU */
    .badge { display: inline-block; padding: 3px 0; width: 45px; border-radius: 4px; font-weight: 700; font-size: 11px; color: #fff; text-transform: uppercase; }
    .badge.tai { background-color: #238636; /* Xanh lá mạ giống ảnh */ }
    .badge.xiu { background-color: #1f6feb; /* Xanh dương giống ảnh */ }
    .badge.empty { background-color: transparent; border: 1px solid #30363d; color: #8b949e; }

    /* CỘT ĐỘ TIN CẬY */
    .col-conf { color: #58a6ff; font-weight: 700; }

    /* TRẠNG THÁI */
    .status-box { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 500; }
    .status-box.wait { color: #8b949e; }
    .status-box.win { color: #3fb950; }
    .status-box.lose { color: #f85149; }
    
    /* ICON */
    .icon { font-size: 14px; }

    /* LOADING */
    .loading { text-align: center; padding: 50px; color: #8b949e; }
</style>
</head>
<body>

<div class="header">
    <button class="btn-menu">☰ Đổi</button>
    <div class="title">BS2 - MD5</div>
    <div class="spacer"></div>
</div>

<div class="table-container">
    <table>
        <thead>
            <tr>
                <th style="text-align: left; padding-left: 15px;">Phiên</th>
                <th>Xúc Xắc</th>
                <th>Dự Đoán</th>
                <th>Kết Quả</th>
                <th>Độ Tin Cậy</th>
                <th>Trạng Thái</th>
            </tr>
        </thead>
        <tbody id="table-body">
            <tr><td colspan="6" class="loading">Đang tải dữ liệu...</td></tr>
        </tbody>
    </table>
</div>

<script>
async function fetchData() {
  try {
    const r = await fetch('/api/history', { cache: 'no-store' });
    const data = await r.json();
    renderTable(data.rows || []);
  } catch (e) {
    console.error("Lỗi:", e);
  }
}

function renderTable(rows) {
  const tbody = document.getElementById('table-body');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading">Không có dữ liệu</td></tr>';
    return;
  }

  tbody.innerHTML = '';
  rows.forEach((row, index) => {
    const tr = document.createElement('tr');
    
    // Xử lý cột Xúc Xắc (Dạng [x,y,z])
    let diceDisplay = row.dice;
    if (diceDisplay && diceDisplay !== "? + ? + ?") {
        diceDisplay = "[" + diceDisplay.replace(/ \+ /g, ",") + "]";
    } else {
        diceDisplay = "[?]";
    }

    // Xử lý Cột Dự đoán
    let predBadge = `<span class="badge empty">-</span>`;
    if (row.prediction === "Tài") predBadge = `<span class="badge tai">TÀI</span>`;
    if (row.prediction === "Xỉu") predBadge = `<span class="badge xiu">XỈU</span>`;

    // Xử lý Cột Kết quả
    let resultBadge = `<span class="badge empty">-</span>`;
    if (row.result === "Tài") resultBadge = `<span class="badge tai">TÀI</span>`;
    if (row.result === "Xỉu") resultBadge = `<span class="badge xiu">XỈU</span>`;

    // Xử lý Trạng thái
    let statusHtml = '';
    if (row.is_next) {
        statusHtml = `<div class="status-box wait"><span class="icon">⚙️</span> Chờ</div>`;
    } else if (row.is_correct === true) {
        statusHtml = `<div class="status-box win"><span class="icon">✅</span> Thắng</div>`;
    } else if (row.is_correct === false) {
        statusHtml = `<div class="status-box lose"><span class="icon">❌</span> Thua</div>`;
    } else {
        statusHtml = `<div class="status-box wait"><span class="icon">-</span></div>`;
    }

    tr.innerHTML = `
        <td class="col-phien">#${row.phien}</td>
        <td class="col-dice">${diceDisplay}</td>
        <td>${predBadge}</td>
        <td>${resultBadge}</td>
        <td class="col-conf">${row.is_next ? row.confidence : (row.confidence + '%')}</td>
        <td>${statusHtml}</td>
    `;
    tbody.appendChild(tr);
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
    results: list kết quả (Mới nhất -> Cũ nhất)
    Trả về: (prediction, confidence, pattern_name)
    """
    if not results or len(results) < 3:
        return "Tài", 50.0, "Khởi tạo"

    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    
    # 1. NHẬN DIỆN CẦU BỆT (STREAK)
    streak = 1
    for r in results[1:]:
        if r == last:
            streak += 1
        else:
            break

    # Logic Bẻ Bệt / Bám Bệt chuyên sâu
    if streak >= 6:
        return opposite, 95.0, f"Bẻ bệt {streak} (Cực mạnh)"
    elif streak == 5:
        return opposite, 88.0, f"Bẻ bệt {streak}"
    elif streak == 4:
        return opposite, 75.0, f"Bẻ bệt {streak}"
    elif streak == 3:
        return last, 65.0, f"Bám bệt {streak}"
    elif streak == 2:
        return last, 55.0, f"Bám bệt {streak}"

    # 2. NHẬN DIỆN CẦU ĐẢO (1-1, 2-2, 3-3)
    if len(results) >= 6:
        # Cầu 1-1 (T-X-T-X-T-X)
        if results[0] != results[1] and results[1] != results[2] and results[2] != results[3] and results[3] != results[4] and results[4] != results[5]:
            return opposite, 90.0, "Đảo cầu 1-1"

        # Cầu 2-2 (T-T-X-X-T-T)
        if results[0] == results[1] and results[2] == results[3] and results[4] == results[5]:
            if results[1] != results[2] and results[3] != results[4]:
                return opposite, 88.0, "Đảo cầu 2-2"

    if len(results) >= 9:
        # Cầu 3-3 (T-T-T-X-X-X-T-T-T)
        if results[0] == results[1] == results[2] and results[3] == results[4] == results[5] and results[6] == results[7] == results[8]:
            if results[2] != results[3] and results[5] != results[6]:
                return opposite, 92.0, "Đảo cầu 3-3"

    # 3. CẦU HỖN HỢP (1-2-1, 2-1-2)
    if len(results) >= 5:
        # 1-2-1 (T-X-X-T) -> dự đoán X
        if results[0] == results[3] and results[1] == results[2] and results[0] != results[1]:
            return results[1], 80.0, "Cầu 1-2-1"
        # 2-1-2 (T-T-X-T-T) -> dự đoán X
        if results[0] == results[1] == results[3] == results[4] and results[2] != results[0]:
            return results[2], 80.0, "Cầu 2-1-2"

    # 4. CHUỖI MARKOV (Xác suất chuyển đổi)
    trans = {"Tài": 0, "Xỉu": 0}
    for i in range(len(results) - 1):
        if results[i] == last:
            trans[results[i+1]] += 1
    
    total_trans = trans["Tài"] + trans["Xỉu"]
    if total_trans > 2:
        if trans["Tài"] > trans["Xỉu"]:
            return "Tài", 72.0, "Xác suất Markov"
        elif trans["Xỉu"] > trans["Tài"]:
            return "Xỉu", 72.0, "Xác suất Markov"

    return opposite, 50.0, "Đảo nhịp"

# =======================================================
# CÁC ROUTES API
# =======================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/history')
def history():
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        
        out = []
        correct_count = 0
        total_past = 0

        # 1. Dự đoán phiên tiếp theo
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next)
        
        out.append({
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'confidence': next_conf,
            'pattern': next_pattern,
            'bet_amount': 2000 if next_conf < 85 else (4000 if next_conf < 92 else 10000),
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
                pred, conf, pattern = "Tài", 50.0, "Khởi tạo"
                is_correct = None
                
            out.append({
                'phien': current_session['phien'],
                'is_next': False,
                'prediction': pred,
                'confidence': conf,
                'pattern': pattern,
                'bet_amount': 2000 if conf < 85 else (4000 if conf < 92 else 10000),
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
    """API CHUYÊN BIỆT: Trả về JSON gọn cho Bot Telegram/Discord"""
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 404

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next)
        bet = 2000 if next_conf < 85 else (4000 if next_conf < 92 else 10000)

        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'prediction': next_pred,
            'confidence': next_conf,
            'pattern': next_pattern,
            'bet_amount': bet,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
