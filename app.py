import os
import time
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Cấu hình API
API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
API_URL_TX = "https://wtx.tele68.com/v1/tx/lite-sessions?cp=R&cl=R&pf=web&at=6c4df7b574bc9f42dda8d0a266682894"

# Bộ nhớ đệm lưu trữ lịch sử vĩnh viễn
HISTORY_CACHE = {'md5': {}, 'tx': {}}
RESET_IDS = {'md5': 0, 'tx': 0}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH </title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-page: #f0f4f8;
        --bg-card: #ffffff;
        --text-main: #1e293b;
        --text-muted: #64748b;
        --border-color: #e2e8f0;
        
        --tai-color: #0ea5e9;
        --tai-bg: #e0f2fe;
        --xiu-color: #ec4899;
        --xiu-bg: #fce7f3;
        
        --win-color: #10b981;
        --win-bg: #d1fae5;
        --lose-color: #ef4444;
        --lose-bg: #fee2e2;
        --wait-color: #f59e0b;
        --wait-bg: #fef3c7;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }

    body {
        background-color: var(--bg-page);
        color: var(--text-main);
        min-height: 100vh;
        padding-bottom: 40px;
    }

    .header {
        background: var(--bg-card);
        padding: 15px 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .header-title {
        font-size: 22px;
        font-weight: 800;
        color: var(--tai-color);
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .header-title span {
        font-size: 12px;
        background: var(--tai-bg);
        color: var(--tai-color);
        padding: 2px 8px;
        border-radius: 10px;
        font-weight: 700;
    }
    .header-actions { display: flex; gap: 10px; align-items: center; }
    
    .time-update { font-size: 11px; color: var(--text-muted); font-weight: 600; }
    
    .btn-refresh {
        background: var(--bg-page);
        color: var(--text-main);
        border: 1px solid var(--border-color);
        padding: 8px 12px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 13px;
        cursor: pointer;
        transition: 0.2s;
    }
    .btn-refresh:hover { background: var(--border-color); }
    
    .btn-reset {
        background: var(--lose-bg);
        color: var(--lose-color);
        border: 1px solid var(--lose-color);
        padding: 8px 16px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 13px;
        cursor: pointer;
        transition: 0.2s;
    }
    .btn-reset:hover { background: var(--lose-color); color: #fff; }

    .tabs-container {
        max-width: 800px;
        margin: 20px auto 0;
        padding: 0 15px;
        display: flex;
        gap: 10px;
    }
    .tab-btn {
        flex: 1;
        padding: 12px;
        border: none;
        background: var(--bg-card);
        color: var(--text-muted);
        font-weight: 700;
        font-size: 14px;
        border-radius: 10px;
        cursor: pointer;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: 0.3s;
    }
    .tab-btn.active {
        background: var(--tai-color);
        color: #fff;
        box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
    }

    .stats-bar {
        max-width: 800px;
        margin: 15px auto;
        padding: 0 15px;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
    }
    .stat-item {
        background: var(--bg-card);
        border-radius: 10px;
        padding: 12px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 5px; }
    .stat-value { font-size: 22px; font-weight: 800; color: var(--text-main); }
    .stat-value.win { color: var(--tai-color); }

    .table-wrapper {
        max-width: 800px;
        margin: 0 auto;
        padding: 0 15px;
    }
    .table-container {
        background: var(--bg-card);
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        max-height: 65vh;
        overflow-y: auto;
    }
    
    .data-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
    }
    .data-table th {
        background: #f8fafc;
        color: var(--text-muted);
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        padding: 15px 12px;
        text-align: center;
        border-bottom: 1px solid var(--border-color);
        position: sticky;
        top: 0;
        z-index: 10;
    }
    .data-table td {
        padding: 14px 12px;
        text-align: center;
        border-bottom: 1px solid var(--border-color);
        font-size: 14px;
        font-weight: 600;
    }
    .data-table tr:last-child td { border-bottom: none; }
    .data-table tr:hover { background: #f8fafc; }
    
    .row-next { background: #f0f9ff; border-left: 3px solid var(--tai-color); }

    .badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        min-width: 60px;
        text-align: center;
    }
    .badge-tai { background: var(--tai-bg); color: var(--tai-color); }
    .badge-xiu { background: var(--xiu-bg); color: var(--xiu-color); }
    .badge-empty { background: #f1f5f9; color: var(--text-muted); }
    
    .status { display: inline-flex; align-items: center; gap: 5px; font-size: 13px; font-weight: 700; padding: 6px 12px; border-radius: 20px; }
    .st-win { background: var(--win-bg); color: var(--win-color); }
    .st-lose { background: var(--lose-bg); color: var(--lose-color); }
    .st-wait { background: var(--wait-bg); color: var(--wait-color); }

    .dice-text { font-size: 12px; color: var(--text-muted); display: block; margin-top: 4px; font-weight: 500; }
    .loading { text-align: center; padding: 40px; color: var(--tai-color); font-weight: 600; }

    @media (max-width: 500px) {
        .data-table th, .data-table td { padding: 10px 5px; font-size: 12px; }
        .badge { padding: 4px 8px; font-size: 11px; }
        .dice-text { font-size: 10px; }
        .header-title { font-size: 18px; }
        .time-update { display: none; }
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-title">
        LE MINH <span>🐼</span>
    </div>
    <div class="header-actions">
        <div class="time-update" id="time-update">--:--:--</div>
        <button class="btn-refresh" onclick="fetchData()">↻</button>
        <button class="btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>

<div class="tabs-container">
    <button class="tab-btn active" id="tab-md5" onclick="switchTab('md5')">TX MD5</button>
    <button class="tab-btn" id="tab-tx" onclick="switchTab('tx')">TX Thường</button>
</div>

<div class="stats-bar">
    <div class="stat-item">
        <div class="stat-label">Tổng phiên</div>
        <div class="stat-value" id="stat-total">0</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Thắng</div>
        <div class="stat-value win" id="stat-win">0</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Tỷ lệ</div>
        <div class="stat-value win" id="stat-rate">0%</div>
    </div>
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
let currentType = 'md5';
let isResetting = false;

function switchTab(type) {
    if (currentType === type) return;
    currentType = type;
    
    document.getElementById('tab-md5').classList.remove('active');
    document.getElementById('tab-tx').classList.remove('active');
    document.getElementById('tab-' + type).classList.add('active');
    
    document.getElementById('table-body').innerHTML = '<tr><td colspan="4" class="loading">Đang tải dữ liệu...</td></tr>';
    fetchData();
}

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
        const r = await fetch(`/api/history?type=${currentType}`, { cache: 'no-store' });
        const data = await r.json();
        
        const now = new Date();
        document.getElementById('time-update').innerText = now.toLocaleTimeString('vi-VN');
        
        renderTable(data.rows || [], data.stats || {});
    } catch (e) {
        console.error("Lỗi tải dữ liệu:", e);
    }
}

function renderTable(rows, stats) {
    const tbody = document.getElementById('table-body');

    if (stats.total > 0) {
        animateNumber(document.getElementById('stat-total'), stats.total);
        animateNumber(document.getElementById('stat-win'), stats.correct);
        const rate = (stats.correct / stats.total) * 100;
        animateNumber(document.getElementById('stat-rate'), Math.round(rate), '%');
    } else {
        document.getElementById('stat-total').innerText = '0';
        document.getElementById('stat-win').innerText = '0';
        document.getElementById('stat-rate').innerText = '0%';
    }

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading">Không có dữ liệu. Hãy đợi phiên mới.</td></tr>';
        return;
    }

    let html = '';
    rows.forEach((row) => {
        const trClass = row.is_next ? 'class="row-next"' : '';

        let predHtml = `<span class="badge badge-empty">-</span>`;
        if (row.prediction === "Tài") predHtml = `<span class="badge badge-tai">TÀI</span>`;
        if (row.prediction === "Xỉu") predHtml = `<span class="badge badge-xiu">XỈU</span>`;

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
            statusHtml = `<span class="status st-wait"> Chờ </span>`;
        } else if (row.is_correct === true) {
            statusHtml = `<span class="status st-win">✔ THẮNG</span>`;
        } else if (row.is_correct === false) {
            statusHtml = `<span class="status st-lose">✖ THUA</span>`;
        } else {
            statusHtml = `<span class="status" style="color:var(--text-muted)">-</span>`;
        }

        html += `
            <tr ${trClass}>
                <td>#${row.phien}</td>
                <td>${predHtml}</td>
                <td>${resultFull}</td>
                <td>${statusHtml}</td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?',
        text: "Toàn bộ lịch sử hiển thị của bảng này sẽ bị xoá và bắt đầu lại từ đầu!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#0ea5e9',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Đồng ý',
        cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type: currentType })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({
                        title: 'Thành công!',
                        text: 'Đã xoá lịch sử và bắt đầu lại.',
                        icon: 'success',
                        confirmButtonColor: '#0ea5e9'
                    });
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

fetchData();
setInterval(fetchData, 5000);
</script>
</body>
</html>
"""

def fetch_sessions(api_type='md5'):
    url = API_URL_MD5 if api_type == 'md5' else API_URL_TX
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(url, timeout=5, headers=headers)
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
        print(f"[API ERROR] {api_type}: {e}")
    return [], False # Trả về mảng rỗng nếu API lỗi, không tự bịa dữ liệu


# =====================================================================
# THUẬT TOÁN THỰC (DETERMINISTIC SCORING MODEL)
# 100% Không Random, Không đoán mò. Tính điểm dựa trên Xác suất & Cầu.
# =====================================================================
def analyze_pattern(results):
    """
    results: Mảng kết quả (Tài/Xỉu) đã được sắp xếp TỪ MỚI NHẤT ĐẾN CŨ NHẤT.
    """
    if not results:
        return "Tài", 50.0 # Mặc định nếu chưa có dữ liệu (chỉ xảy ra 1 lần đầu)
    
    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    
    if len(results) < 3:
        # Nếu quá ít dữ liệu, bám theo kết quả vừa ra (hoặc bẻ nếu là 1-1)
        if len(results) == 2 and results[0] != results[1]:
            return opposite, 60.0
        return last, 60.0

    # Khởi tạo điểm số (Score)
    score_tai = 0.0
    score_xiu = 0.0

    # ---------------------------------------------------------
    # YẾU TỐ 1: PATTERN MATCHING (Nhận diện cầu) - Trọng số cao
    # ---------------------------------------------------------
    groups = []
    current_val = results[0]
    count = 1
    for r in results[1:]:
        if r == current_val:
            count += 1
        else:
            groups.append(count)
            current_val = r
            count = 1
    groups.append(count)
    
    lengths = groups

    # Cầu bệt (Streak >= 4)
    if lengths[0] >= 4:
        if last == "Tài": score_xiu += 5.0
        else: score_tai += 5.0

    # Cầu 1-1 (Đảo liên tục 4 nhịp)
    if len(lengths) >= 4 and lengths[:4] == [1, 1, 1, 1]:
        if last == "Tài": score_xiu += 4.5
        else: score_tai += 4.5

    # Cầu 2-2 (Đảo nhóm 2)
    if len(lengths) >= 3 and lengths[:3] == [2, 2, 2]:
        if last == "Tài": score_xiu += 4.0
        else: score_tai += 4.0

    # Cầu 1-2-3 / 3-2-1
    if len(lengths) >= 3:
        if lengths[:3] == [1, 2, 3] or lengths[:3] == [3, 2, 1]:
            if last == "Tài": score_xiu += 4.5
            else: score_tai += 4.5
            
    # Cầu 2-3-1 / 1-3-2
    if len(lengths) >= 3:
        if lengths[:3] == [2, 3, 1] or lengths[:3] == [1, 3, 2]:
            if last == "Tài": score_xiu += 4.0
            else: score_tai += 4.0

    # ---------------------------------------------------------
    # YẾU TỐ 2: MARKOV CHAIN (Xác suất chuyển đổi trạng thái)
    # ---------------------------------------------------------
    # Đếm xem khi ra Tài thì bao nhiêu lần tiếp theo là Tài/Xỉu
    transitions = {"Tài": {"Tài": 0, "Xỉu": 0}, "Xỉu": {"Tài": 0, "Xỉu": 0}}
    for i in range(len(results) - 1):
        current_state = results[i+1]
        next_state = results[i]
        transitions[current_state][next_state] += 1
        
    total_from_last = sum(transitions[last].values())
    if total_from_last > 0:
        prob_tai = transitions[last]["Tài"] / total_from_last
        prob_xiu = transitions[last]["Xỉu"] / total_from_last
        
        # Nếu xác suất lệch rõ rệt (vd: > 60%)
        if prob_tai > 0.6: score_tai += 3.0
        elif prob_xiu > 0.6: score_xiu += 3.0

    # ---------------------------------------------------------
    # YẾU TỐ 3: MOMENTUM (Động lượng / Xu hướng nghiêng)
    # ---------------------------------------------------------
    # Lấy 20 phiên gần nhất để xem đang nghiêng bên nào
    recent = results[:20]
    count_tai = recent.count("Tài")
    count_xiu = recent.count("Xỉu")
    
    # Nếu nghiêng quá mức (vd 15/20 là Tài), khả năng cao sẽ đảo chiều (bẻ)
    if count_tai >= 14: score_xiu += 3.5
    elif count_xiu >= 14: score_tai += 3.5

    # ---------------------------------------------------------
    # YẾU TỐ 4: NHỊP ĐỘ GẦN NHẤT (Recent Rhythm)
    # ---------------------------------------------------------
    # Nếu 3 phiên gần nhất là 2 Tài 1 Xỉu, xu hướng thường là theo chân phiên cuối
    if len(results) >= 3:
        if results[0] == results[1] and results[1] != results[2]:
            # Đang bám bệt 2, khả năng cao ra tiếp
            if last == "Tài": score_tai += 1.5
            else: score_xiu += 1.5

    # ---------------------------------------------------------
    # TỔNG HỢP VÀ QUYẾT ĐỊNH
    # ---------------------------------------------------------
    if score_tai > score_xiu:
        confidence = min(50.0 + (score_tai * 5), 99.0) # Quy đổi điểm ra %
        return "Tài", confidence
    elif score_xiu > score_tai:
        confidence = min(50.0 + (score_xiu * 5), 99.0)
        return "Xỉu", confidence
    else:
        # Nếu điểm hòa nhau (hiếm gặp), sử dụng quy tắc bẻ nhịp (Không dùng random)
        return opposite, 50.0

# =====================================================================
# API ROUTES
# =====================================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/history')
def history():
    api_type = request.args.get('type', 'md5')
    reset_id = RESET_IDS.get(api_type, 0)
    
    try:
        raw_rows, success = fetch_sessions(api_type)
        
        if not success and not HISTORY_CACHE[api_type]:
            return jsonify({'error': 'Không thể kết nối API'}), 500
            
        # Ghi dữ liệu vào bộ nhớ đệm
        for row in raw_rows:
            HISTORY_CACHE[api_type][row['phien']] = row
            
        # Dọn dẹp bộ nhớ đệm nếu có phiên cũ hơn mốc reset
        keys_to_remove = [k for k in HISTORY_CACHE[api_type] if k <= reset_id]
        for k in keys_to_remove:
            del HISTORY_CACHE[api_type][k]

        valid = sorted(HISTORY_CACHE[api_type].values(), key=lambda x: x['phien'])

        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0}})

        out = []
        correct_count = 0
        total_past = 0

        # Dự đoán phiên tương lai
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        next_pred, next_conf = analyze_pattern(history_for_next)

        out.append({
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None
        })

        # Quét lịch sử (giới hạn 500 phiên để web mượt)
        scan_limit = min(len(valid), 500)
        
        for i in range(len(valid) - 1, len(valid) - scan_limit - 1, -1):
            if i < 0: break
            current_session = valid[i]
            history = [v['result'] for v in valid[:i]][::-1]
            
            if history:
                pred, conf = analyze_pattern(history)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct:
                    correct_count += 1
            else:
                pred, conf = "-", 0
                is_correct = None

            out.append({
                'phien': current_session['phien'],
                'is_next': False,
                'prediction': pred,
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

@app.route('/api/reset', methods=['POST'])
def reset_api():
    data = request.json or {}
    api_type = data.get('type', 'md5')
    
    try:
        raw_rows, success = fetch_sessions(api_type)
        if success:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                max_id = valid[-1]['phien']
                RESET_IDS[api_type] = max_id
                HISTORY_CACHE[api_type] = {}
                return jsonify({'status': 'success', 'reset_to': max_id})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng, không thể xác nhận mốc Reset'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
