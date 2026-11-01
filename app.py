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
<title>LE MINH</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-page: #0f172a;
        --bg-card: #1e293b;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --border-color: #334155;
        
        --tai-color: #38bdf8;
        --tai-bg: rgba(56, 189, 248, 0.15);
        --xiu-color: #f472b6;
        --xiu-bg: rgba(244, 114, 182, 0.15);
        
        --win-color: #34d399;
        --win-bg: rgba(52, 211, 153, 0.15);
        --lose-color: #f87171;
        --lose-bg: rgba(248, 113, 113, 0.15);
        --wait-color: #fbbf24;
        --wait-bg: rgba(251, 191, 36, 0.15);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }

    body {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: var(--text-main);
        min-height: 100vh;
        padding-bottom: 40px;
    }

    .header {
        background: rgba(30, 41, 59, 0.85);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid var(--border-color);
        padding: 16px 24px;
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
        color: #38bdf8;
        display: flex;
        align-items: center;
        gap: 10px;
        text-shadow: 0 0 20px rgba(56, 189, 248, 0.4);
    }
    .header-title span {
        font-size: 11px;
        background: linear-gradient(135deg, #38bdf8, #ec4899);
        color: #fff;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 800;
        letter-spacing: 1px;
        box-shadow: 0 0 15px rgba(236, 72, 153, 0.4);
    }
    .header-actions { display: flex; gap: 12px; align-items: center; }
    
    .time-update { font-size: 12px; color: var(--text-muted); font-weight: 600; }
    
    .btn-refresh {
        background: var(--bg-card);
        color: var(--text-main);
        border: 1px solid var(--border-color);
        width: 38px;
        height: 38px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 16px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: 0.2s;
    }
    .btn-refresh:hover { background: var(--border-color); transform: rotate(180deg); }
    
    .btn-reset {
        background: rgba(248, 113, 113, 0.2);
        color: var(--lose-color);
        border: 1px solid var(--lose-color);
        padding: 8px 16px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 13px;
        cursor: pointer;
        transition: 0.2s;
    }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 15px rgba(248, 113, 113, 0.4); }

    .tabs-container {
        max-width: 800px;
        margin: 24px auto 0;
        padding: 0 16px;
        display: flex;
        gap: 12px;
    }
    .tab-btn {
        flex: 1;
        padding: 14px;
        border: 1px solid var(--border-color);
        background: var(--bg-card);
        color: var(--text-muted);
        font-weight: 700;
        font-size: 14px;
        border-radius: 12px;
        cursor: pointer;
        transition: 0.3s;
    }
    .tab-btn.active {
        background: linear-gradient(135deg, #0ea5e9, #2563eb);
        border-color: transparent;
        color: #fff;
        box-shadow: 0 8px 25px rgba(14, 165, 233, 0.4);
    }

    .stats-bar {
        max-width: 800px;
        margin: 16px auto;
        padding: 0 16px;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
    }
    .stat-item {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px; letter-spacing: 0.5px; }
    .stat-value { font-size: 24px; font-weight: 800; color: var(--text-main); }
    .stat-value.win { color: var(--tai-color); text-shadow: 0 0 15px rgba(56, 189, 248, 0.3); }

    .table-wrapper {
        max-width: 800px;
        margin: 0 auto;
        padding: 0 16px;
    }
    .table-container {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        max-height: 65vh;
        overflow-y: auto;
    }
    
    .data-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
    }
    .data-table th {
        background: #111827;
        color: var(--text-muted);
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 16px 12px;
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
    .data-table tr:hover { background: rgba(255, 255, 255, 0.02); }
    
    .row-next { background: rgba(14, 165, 233, 0.08); border-left: 4px solid var(--tai-color); }

    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        min-width: 70px;
        text-align: center;
    }
    .badge-tai { background: var(--tai-bg); color: var(--tai-color); border: 1px solid rgba(56, 189, 248, 0.3); box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); }
    .badge-xiu { background: var(--xiu-bg); color: var(--xiu-color); border: 1px solid rgba(244, 114, 182, 0.3); box-shadow: 0 0 10px rgba(244, 114, 182, 0.2); }
    .badge-empty { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); }
    
    .status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; padding: 6px 14px; border-radius: 20px; }
    .st-win { background: var(--win-bg); color: var(--win-color); border: 1px solid rgba(52, 211, 153, 0.3); }
    .st-lose { background: var(--lose-bg); color: var(--lose-color); border: 1px solid rgba(248, 113, 113, 0.3); }
    .st-wait { background: var(--wait-bg); color: var(--wait-color); border: 1px solid rgba(251, 191, 36, 0.3); animation: pulse 1.5s infinite; }

    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }

    .dice-text { font-size: 11px; color: var(--text-muted); display: block; margin-top: 4px; font-weight: 500; }
    .conf-badge { font-size: 11px; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 2px 8px; border-radius: 10px; margin-top: 4px; display: inline-block; font-weight: 700; }
    .loading { text-align: center; padding: 40px; color: var(--tai-color); font-weight: 600; }

    @media (max-width: 500px) {
        .data-table th, .data-table td { padding: 10px 6px; font-size: 12px; }
        .badge { padding: 4px 8px; font-size: 11px; min-width: 50px; }
        .header-title { font-size: 18px; }
        .time-update { display: none; }
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-title">
        LE MINH <span>CTEWW</span>
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

        let confHtml = "";
        if (row.conf && row.prediction !== "-") {
            confHtml = `<div class="conf-badge">${row.conf}%</div>`;
        }
        let predFull = `<div style="display:flex; flex-direction:column; align-items:center;">${predHtml}${confHtml}</div>`;

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
            statusHtml = `<span class="status st-wait">⏳ Chờ kết quả</span>`;
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
                <td>${predFull}</td>
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
        background: '#1e293b',
        color: '#f8fafc',
        showCancelButton: true,
        confirmButtonColor: '#0ea5e9',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Đồng ý',
        cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, background: '#1e293b', color: '#f8fafc', didOpen: () => { Swal.showLoading() } });
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
                        background: '#1e293b',
                        color: '#f8fafc',
                        confirmButtonColor: '#0ea5e9'
                    });
                    isResetting = false;
                    fetchData();
                } else {
                    throw new Error(data.message);
                }
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
    return [], False

# =====================================================================
# HỆ THỐNG ĐẢO CẦU & ENSEMBLE NÂNG CẤP (v16.0)
# =====================================================================

def get_groups(results):
    if not results: return []
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
    return groups

def algo_pattern_matrix_v16(results, groups):
    if not groups: return None
    # Bắt bẻ cầu bệt khi dài >= 4
    if groups[0] >= 4:
        return "Tài" if results[0] == "Xỉu" else "Xỉu"
    # Bắt cầu 1-1 hoặc cầu đảo nhịp
    if len(groups) >= 4 and groups[:4] == [1, 1, 1, 1]:
        return "Tài" if results[0] == "Xỉu" else "Xỉu"
    if len(groups) >= 3 and groups[:3] == [2, 2, 2]:
        return "Tài" if results[0] == "Xỉu" else "Xỉu"
    if len(groups) >= 3 and groups[:3] == [1, 2, 1]:
        return results[0]
    return None

def algo_markov_chain_v16(results):
    if len(results) < 15: return None
    sample_space = results[:40]
    last = sample_space[0]
    transitions = {"Tài": {"Tài": 0, "Xỉu": 0}, "Xỉu": {"Tài": 0, "Xỉu": 0}}
    for i in range(len(sample_space) - 1):
        transitions[sample_space[i+1]][sample_space[i]] += 1
    total = sum(transitions[last].values())
    if total >= 4:
        prob_tai = transitions[last]["Tài"] / total
        if prob_tai > 0.60: return "Tài"
        if prob_tai < 0.40: return "Xỉu"
    return None

def algo_bayesian_v16(results):
    if len(results) < 20: return None
    sample_space = results[:30]
    if len(sample_space) < 3: return None
    target_seq = tuple(sample_space[:3])
    count_target = 0
    count_next_tai = 0
    count_next_xiu = 0
    for i in range(len(sample_space) - 3):
        seq = tuple(sample_space[i+1:i+4])
        if seq == target_seq:
            count_target += 1
            if sample_space[i] == "Tài": count_next_tai += 1
            else: count_next_xiu += 1
    if count_target >= 1:
        total_matched = count_next_tai + count_next_xiu
        if total_matched > 0:
            if (count_next_tai / total_matched) >= 0.65: return "Tài"
            if (count_next_xiu / total_matched) >= 0.65: return "Xỉu"
    return None

def algo_oscillator_v16(results):
    if len(results) < 15: return None
    recent = results[:25]
    tai_count = recent.count("Tài")
    ratio = tai_count / len(recent)
    if ratio >= 0.75: return "Xỉu"
    if ratio <= 0.25: return "Tài"
    return None

def algo_mean_reversion_v16(results):
    if len(results) < 30: return None
    recent = results[:40]
    tai_ratio = recent.count("Tài") / len(recent)
    if tai_ratio > 0.70: return "Xỉu"
    if tai_ratio < 0.30: return "Tài"
    return None

def algo_streak_reversal_v16(groups, results):
    if not groups: return None
    # Nếu nhịp cầu ngắn liên tục (1,1,1,...) hoặc bệt vừa gãy
    if groups[0] >= 3:
        return "Tài" if results[0] == "Xỉu" else "Xỉu"
    return None

def algo_fairness_balancer_v16(pred_history):
    if len(pred_history) < 10: return None
    recent = pred_history[-10:]
    tai_preds = recent.count("Tài")
    if tai_preds >= 8: return "Xỉu"
    if tai_preds <= 2: return "Tài"
    return None


def adaptive_ensemble_predict(results, pred_history, algo_performance):
    if not results:
        return "Tài", 50
    if len(results) < 3:
        return results[0], 50

    groups = get_groups(results)
    
    raw_votes = {
        "pattern": algo_pattern_matrix_v16(results, groups),
        "markov": algo_markov_chain_v16(results),
        "bayes": algo_bayesian_v16(results),
        "oscillator": algo_oscillator_v16(results),
        "mean_rev": algo_mean_reversion_v16(results),
        "streak": algo_streak_reversal_v16(groups, results),
        "fairness": algo_fairness_balancer_v16(pred_history)
    }

    score_tai = 0.0
    score_xiu = 0.0

    base_weights = {
        "pattern": 15.0,
        "markov": 12.0,
        "bayes": 13.0,
        "oscillator": 10.0,
        "mean_rev": 10.0,
        "streak": 12.0,
        "fairness": 8.0
    }

    for algo_name, pred in raw_votes.items():
        if pred:
            perf = algo_performance.get(algo_name, {"correct": 0, "total": 0})
            if perf["total"] >= 3:
                accuracy = perf["correct"] / perf["total"]
                dynamic_factor = max(0.2, min(3.0, accuracy * 2.5))
            else:
                dynamic_factor = 1.0
                
            final_weight = base_weights[algo_name] * dynamic_factor
            
            if pred == "Tài": score_tai += final_weight
            elif pred == "Xỉu": score_xiu += final_weight

    total_score = score_tai + score_xiu
    if total_score == 0:
        return results[0], 50

    if score_tai > score_xiu:
        ratio = score_tai / total_score
        # Tự động scale độ tự tin từ 50% đến 100% cực kỳ chuẩn xác
        confidence = int(round(50 + (ratio - 0.5) * 100))
        confidence = max(50, min(100, confidence))
        return "Tài", confidence
    elif score_xiu > score_tai:
        ratio = score_xiu / total_score
        confidence = int(round(50 + (ratio - 0.5) * 100))
        confidence = max(50, min(100, confidence))
        return "Xỉu", confidence
    else:
        return ("Xỉu" if results[0] == "Tài" else "Tài"), 55


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
            
        for row in raw_rows:
            HISTORY_CACHE[api_type][row['phien']] = row
            
        keys_to_remove = [k for k in HISTORY_CACHE[api_type] if k <= reset_id]
        for k in keys_to_remove:
            del HISTORY_CACHE[api_type][k]

        valid = sorted(HISTORY_CACHE[api_type].values(), key=lambda x: x['phien'])

        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0}})

        out = []
        correct_count = 0
        total_past = 0

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        
        pred_history = []
        algo_performance = {k: {"correct": 0, "total": 0} for k in ["pattern", "markov", "bayes", "oscillator", "mean_rev", "streak", "fairness"]}
        
        next_pred, next_conf = adaptive_ensemble_predict(history_for_next, pred_history, algo_performance)

        out.append({
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None,
            'conf': next_conf
        })

        scan_limit = min(len(valid), 500)
        
        for i in range(len(valid) - 1, len(valid) - scan_limit - 1, -1):
            if i < 0: break
            current_session = valid[i]
            history = [v['result'] for v in valid[:i]][::-1]
            
            if history:
                pred, conf = adaptive_ensemble_predict(history, pred_history, algo_performance)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct:
                    correct_count += 1
            else:
                pred, conf = "-", 50
                is_correct = None

            if history and pred != "-":
                groups = get_groups(history)
                raw_votes = {
                    "pattern": algo_pattern_matrix_v16(history, groups),
                    "markov": algo_markov_chain_v16(history),
                    "bayes": algo_bayesian_v16(history),
                    "oscillator": algo_oscillator_v16(history),
                    "mean_rev": algo_mean_reversion_v16(history),
                    "streak": algo_streak_reversal_v16(groups, history),
                    "fairness": algo_fairness_balancer_v16(pred_history)
                }
                for algo_name, v in raw_votes.items():
                    if v:
                        algo_performance[algo_name]["total"] += 1
                        if v == current_session['result']:
                            algo_performance[algo_name]["correct"] += 1
                            
                pred_history.append(pred)

            out.append({
                'phien': current_session['phien'],
                'is_next': False,
                'prediction': pred,
                'result': current_session['result'],
                'dice': current_session['dice'],
                'is_correct': is_correct,
                'conf': conf
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
