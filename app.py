import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=ab36aa88e2c9868ae0e8bc61adbd18dc"
RESET_SESSION_ID = 0

# =====================================================================
# HỆ THỐNG 81 MẪU CẦU (3^4 = 81 TỔ HỢP)
# =====================================================================
ALL_81_PATTERNS = {}
for _i in range(81):
    _sig = ''
    _temp = _i
    for _ in range(4):
        _sig = 'SML'[_temp % 3] + _sig
        _temp //= 3
    ALL_81_PATTERNS[_i] = _sig

# =====================================================================
# GIAO DIỆN HTML (GIAO DIỆN VIP - ĐÃ XÓA TAG CẦU)
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>LC MD5 MINHLE </title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #050814; 
        --bg-card: rgba(15, 23, 42, 0.65);
        --text-main: #f8fafc; 
        --text-muted: #94a3b8; 
        --border-glass: rgba(255, 255, 255, 0.08);
        --tai-color: #0ea5e9; 
        --tai-glow: rgba(14, 165, 233, 0.4);
        --xiu-color: #ec4899; 
        --xiu-glow: rgba(236, 72, 153, 0.4);
        --gold: #fbbf24;
        --lose: #ef4444;
        --win: #10b981;
    }
    
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    
    body { 
        background-color: var(--bg-dark); 
        color: var(--text-main); 
        padding-bottom: 30px; 
        min-height: 100vh; 
        background-image: 
            radial-gradient(circle at 15% 50%, rgba(14, 165, 233, 0.08) 0%, transparent 50%),
            radial-gradient(circle at 85% 30%, rgba(236, 72, 153, 0.08) 0%, transparent 50%);
        overflow-x: hidden; 
        position: relative; 
    }

    /* Header VIP */
    .header { 
        display: flex; justify-content: space-between; align-items: center; 
        padding: 16px 20px; 
        background: rgba(5, 8, 20, 0.7); 
        backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        border-bottom: 1px solid var(--border-glass);
        position: sticky; top: 0; z-index: 100; 
    }
    .header-left { display: flex; align-items: center; gap: 10px; }
    .live-dot { 
        width: 8px; height: 8px; border-radius: 50%; background: var(--gold); 
        box-shadow: 0 0 10px var(--gold); animation: pulse 1.5s infinite; 
    }
    @keyframes pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.5); opacity: 0.5; } }
    .header-title { 
        font-size: 18px; font-weight: 800; 
        background: linear-gradient(90deg, #fff, #bae6fd, #fff); 
        background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
        animation: shine 3s linear infinite; letter-spacing: -0.5px;
    }
    @keyframes shine { to { background-position: 200% center; } }
    
    .btn-reset { 
        background: rgba(239, 68, 68, 0.1); color: #fca5a5; 
        border: 1px solid rgba(239, 68, 68, 0.3); 
        padding: 8px 16px; border-radius: 8px; font-weight: 700; font-size: 12px; 
        cursor: pointer; transition: all 0.3s; 
    }
    .btn-reset:hover { background: rgba(239, 68, 68, 0.2); box-shadow: 0 0 15px rgba(239, 68, 68, 0.2); }

    /* Thanh Thống Kê */
    .stats-bar { 
        max-width: 600px; margin: 16px auto 0; padding: 0 16px; 
        display: flex; gap: 12px; 
    }
    .stat-box { 
        flex: 1; background: var(--bg-card); border: 1px solid var(--border-glass); 
        border-radius: 16px; padding: 12px; text-align: center; 
        backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
        position: relative; overflow: hidden;
    }
    .stat-box::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    }
    .stat-lbl { font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 4px; }
    .stat-val { font-size: 20px; font-weight: 800; color: #fff; }
    .stat-val.highlight { color: var(--tai-color); text-shadow: 0 0 15px var(--tai-glow); }

    /* Danh sách Card */
    .container { padding: 16px; display: flex; flex-direction: column; gap: 12px; max-width: 600px; margin: 0 auto; }
    
    .card { 
        background: var(--bg-card); 
        border: 1px solid var(--border-glass); 
        border-radius: 16px; padding: 16px; 
        display: flex; justify-content: space-between; align-items: center; 
        backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
        position: relative;
    }
    .card:hover { transform: translateY(-2px); border-color: rgba(255,255,255,0.15); box-shadow: 0 8px 30px rgba(0,0,0,0.4); }
    
    .card.active { 
        border-color: rgba(251, 191, 36, 0.4); 
        box-shadow: 0 0 25px rgba(251, 191, 36, 0.15), inset 0 0 20px rgba(251, 191, 36, 0.05); 
    }
    .card.active::after { 
        content: ''; position: absolute; top: 16px; right: 16px; 
        width: 6px; height: 6px; border-radius: 50%; background: var(--gold); 
        box-shadow: 0 0 10px var(--gold); animation: pulse 1.5s infinite;
    }

    /* Cột Trái */
    .col-left { display: flex; flex-direction: column; gap: 6px; flex: 1.2; }
    .session-id { font-size: 16px; font-weight: 800; color: #fff; letter-spacing: 0.5px; }
    .bot-info { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .bot-lbl { color: var(--text-muted); font-weight: 600; }
    
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge-tai { background: rgba(14, 165, 233, 0.15); color: #7dd3fc; border: 1px solid rgba(14, 165, 233, 0.3); }
    .badge-xiu { background: rgba(236, 72, 153, 0.15); color: #f9a8d4; border: 1px solid rgba(236, 72, 153, 0.3); }
    
    /* Thanh Độ Tin Cậy */
    .conf-wrap { margin-top: 6px; width: 100%; max-width: 140px; }
    .conf-text { font-size: 10px; color: var(--text-muted); font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 2px; }
    .conf-bg { height: 4px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
    .conf-bar { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--tai-color), #818cf8); transition: width 0.8s ease; }
    .conf-bar.xiu { background: linear-gradient(90deg, var(--xiu-color), #f472b6); }

    /* Cột Giữa */
    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 4px; }
    .pred-circle { 
        padding: 6px 16px; border-radius: 20px; font-weight: 800; font-size: 14px; 
        letter-spacing: 1px; text-transform: uppercase;
    }
    .pred-tai { background: linear-gradient(135deg, #0284c7, #38bdf8); color: #fff; box-shadow: 0 0 15px var(--tai-glow); }
    .pred-xiu { background: linear-gradient(135deg, #be185d, #ec4899); color: #fff; box-shadow: 0 0 15px var(--xiu-glow); }
    .pred-wait { border: 1px dashed rgba(255,255,255,0.2); color: var(--text-muted); }
    .dice { font-size: 12px; font-weight: 600; color: #cbd5e1; white-space: nowrap; }

    /* Cột Phải */
    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.8; }
    .status { font-size: 13px; font-weight: 800; display: flex; align-items: center; gap: 4px; }
    .st-win { color: var(--win); text-shadow: 0 0 10px rgba(16, 185, 129, 0.3); }
    .st-lose { color: var(--lose); }
    .st-wait { color: var(--gold); }
    
    .loading { text-align: center; padding: 40px; color: var(--tai-color); font-weight: 600; animation: pulse 2s infinite; }
    
    @media (max-width: 380px) {
        .header-title { font-size: 15px; }
        .stat-val { font-size: 16px; }
        .session-id { font-size: 14px; }
        .dice { font-size: 11px; }
        .pred-circle { font-size: 12px; padding: 4px 12px; }
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-left">
        <div class="live-dot"></div>
        <div class="header-title">⚡ LC MD5 MINHLE </div>
    </div>
    <button class="btn-reset" onclick="confirmReset()">↻ Reset</button>
</div>

<div class="stats-bar">
    <div class="stat-box"><div class="stat-lbl">Tổng Phiên</div><div class="stat-val" id="stat-total">0</div></div>
    <div class="stat-box"><div class="stat-lbl">Thắng</div><div class="stat-val highlight" id="stat-win">0</div></div>
    <div class="stat-box"><div class="stat-lbl">Tỷ Lệ</div><div class="stat-val highlight" id="stat-rate">0%</div></div>
</div>

<div class="container" id="list-container">
    <div class="loading">Đang tải dữ liệu siêu tốc...</div>
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
        renderList(data.rows || [], data.stats || {});
    } catch (e) {
        document.getElementById('list-container').innerHTML = '<div class="loading" style="color:var(--lose)">Lỗi kết nối Server!</div>';
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
        container.innerHTML = '<div class="loading">Không có dữ liệu.</div>';
        return;
    }

    let html = '';
    rows.forEach((row, idx) => {
        const isActive = row.is_next ? ' active' : '';
        const delay = (idx * 50);
        
        // Xử lý Badge Bot Cược
        let badgeHtml = `<span class="badge" style="background:rgba(255,255,255,0.05);color:#94a3b8;">Nghỉ</span>`;
        let confClass = 'conf-bar';
        if (row.prediction === "Tài") {
            badgeHtml = `<span class="badge badge-tai">Cược Tài</span>`;
        } else if (row.prediction === "Xỉu") {
            badgeHtml = `<span class="badge badge-xiu">Cược Xỉu</span>`;
            confClass = 'conf-bar xiu';
        }

        // Xử lý Dự đoán & Kết quả
        let predHtml = `<span class="pred-circle pred-wait">-</span>`;
        if (row.prediction === "Tài") predHtml = `<span class="pred-circle pred-tai">TÀI</span>`;
        if (row.prediction === "Xỉu") predHtml = `<span class="pred-circle pred-xiu">XỈU</span>`;
        
        let diceHtml = "? + ? + ?";
        if (row.dice !== "? + ? + ?") {
            const p = row.dice.split(" + ");
            diceHtml = `${row.dice} <span style="color:#94a3b8">(${parseInt(p[0]) + parseInt(p[1]) + parseInt(p[2])})</span>`;
        }

        // Xử lý Trạng thái
        let statusHtml = `<div class="status" style="color:#64748b">-</div>`;
        if (row.is_next) {
            statusHtml = `<div class="status st-wait">Chờ </div>`;
        } else if (row.is_correct === true) {
            statusHtml = `<div class="status st-win">Đúng ✅</div>`;
        } else if (row.is_correct === false) {
            statusHtml = `<div class="status st-lose">Sai ❌</div>`;
        }

        html += `
            <div class="card${isActive}" style="animation-delay: ${delay}ms">
                <div class="col-left">
                    <div class="session-id">#${row.phien}</div>
                    <div class="bot-info"><span class="bot-lbl">Bot:</span> ${badgeHtml}</div>
                    <div class="conf-wrap">
                        <div class="conf-text"><span>Độ tin cậy</span><span>${row.confidence}%</span></div>
                        <div class="conf-bg"><div class="${confClass}" style="width:${row.confidence}%"></div></div>
                    </div>
                </div>
                <div class="col-mid">
                    ${predHtml}
                    <div class="dice">${diceHtml}</div>
                </div>
                <div class="col-right">
                    ${statusHtml}
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', 
        text: "Ẩn lịch sử hiện tại, tiếp tục tính toán ngầm!",
        icon: 'warning',
        background: '#0f172a', color: '#fff',
        showCancelButton: true, 
        confirmButtonColor: '#0ea5e9', cancelButtonColor: '#334155', 
        confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ 
                title: 'Đang Reset...', 
                background: '#0f172a', color: '#fff',
                allowOutsideClick: false, didOpen: () => { Swal.showLoading() } 
            });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ 
                        title: 'Thành công!', 
                        text: 'Đã chốt mốc từ phiên #' + data.reset_to, 
                        icon: 'success', 
                        background: '#0f172a', color: '#fff',
                        confirmButtonColor: '#0ea5e9' 
                    });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire({
                    title: 'Lỗi!', text: error.message, icon: 'error',
                    background: '#0f172a', color: '#fff'
                }); 
                isResetting = false;
            }
        }
    });
}

fetchData(); 
setInterval(fetchData, 4000); // Cập nhật nhanh hơn (4s)
</script>
</body>
</html>
"""

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================
def build_blocks(results):
    if not results: return []
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
    if L == 1: return 'S'
    if L <= 3: return 'M'
    return 'L'

def encode_pattern_81(block_lengths):
    if len(block_lengths) < 4: return None
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
        if len(blocks) < 5: continue
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        if code is None: continue
        
        continued = (results[k - 1] == blocks[0]['val'])
        current_len = min(blocks[0]['len'], 4)
        
        for key in [(code, current_len), code]:
            if key not in stats: stats[key] = {'continue': 0, 'break': 0}
            stats[key]['continue' if continued else 'break'] += 1
    return stats

# =====================================================================
# THUẬT TOÁN V7.0 - TỐI ƯU HÓA ĐA TẦNG (FULL CẦU)
# =====================================================================
def analyze_pattern(results, dice_sums=None):
    if not results or len(results) < 3:
        return "Tài", 50.0, "Khởi tạo"
    
    n = len(results)
    candidates = []
    
    # 1. PHÂN TÍCH KHỐI (Bệt / Đảo)
    blocks = build_blocks(results)
    curr_val = blocks[0]['val']
    curr_len = blocks[0]['len']
    opp_val = "Xỉu" if curr_val == "Tài" else "Tài"

    # --- Cầu Bệt (Streak) ---
    if curr_len >= 10:   
        candidates.append((opp_val, 96.0, 100, "Bẻ bệt"))
    elif curr_len >= 8:  
        candidates.append((opp_val, 92.0, 90, "Bẻ bệt"))
    elif curr_len >= 6:  
        candidates.append((opp_val, 85.0, 80, "Bẻ bệt"))
    elif curr_len == 5:  
        candidates.append((opp_val, 75.0, 70, "Bẻ bệt"))
    elif curr_len == 4:  
        candidates.append((curr_val, 70.0, 65, "Bám bệt"))
    elif curr_len == 3:  
        candidates.append((curr_val, 60.0, 55, "Bám bệt"))
    
    # --- Đảo 1-1 ---
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]: alt_len += 1
        else: break
        
    if alt_len >= 10:    
        candidates.append((opp_val, 95.0, 95, "Đảo 1-1 dài"))
    elif alt_len >= 7:   
        candidates.append((opp_val, 88.0, 85, "Đảo 1-1"))
    elif alt_len >= 4:   
        candidates.append((opp_val, 78.0, 75, "Đảo 1-1 ngắn"))

    # --- Cầu Đảo Khối (2-2, 1-2-1) ---
    if len(blocks) >= 3:
        is_alt_block = all(blocks[i]['val'] != blocks[i-1]['val'] for i in range(1, min(len(blocks), 5)))
        if is_alt_block:
            p1, p2 = blocks[1]['len'], blocks[2]['len']
            if p1 == p2 and p1 >= 2:
                if curr_len < p1: 
                    candidates.append((curr_val, 92.0, 90, "Bám cầu đối xứng"))
                elif curr_len == p1: 
                    candidates.append((opp_val, 96.0, 98, "Bẻ cầu đối xứng"))
            if len(blocks) >= 4:
                p3 = blocks[3]['len']
                if p1 == p3 and p2 != p1 and p1 <= 5:
                    candidates.append((opp_val, 88.0, 85, "Cầu Palindrom"))

    # 2. HỆ THỐNG 81 MẪU (NÂNG CẤP)
    if len(blocks) >= 5:
        stats = learn_81_patterns(results)
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        
        if code is not None:
            for key in [(code, min(curr_len, 4)), code]:
                if key in stats:
                    s = stats[key]
                    total = s['continue'] + s['break']
                    if total >= 3: # Yêu cầu mẫu lặp lại ít nhất 3 lần
                        cont_rate = s['continue'] / total
                        if cont_rate >= 0.65: 
                            candidates.append((curr_val, 65 + cont_rate * 25, 70, "Mẫu 81 Tiếp"))
                        elif cont_rate <= 0.35: 
                            candidates.append((opp_val, 65 + (1 - cont_rate) * 25, 70, "Mẫu 81 Gãy"))
                        break

    # 3. N-GRAM (TÌM CHUỖI TƯƠNG ĐỒNG)
    for ns in [8, 7, 6, 5, 4]:
        if n < ns + 1: continue
        curr_seq = tuple(results[:ns])
        m_tai, m_xiu = 0, 0
        for i in range(len(results) - ns):
            if tuple(results[i:i+ns]) == curr_seq and i + ns < len(results):
                if results[i+ns] == "Tài": m_tai += 1
                else: m_xiu += 1
        tot = m_tai + m_xiu
        if tot >= 3 and abs(m_tai - m_xiu) >= 2: # Cần sự chênh lệch rõ rệt
            w = "Tài" if m_tai > m_xiu else "Xỉu"
            ratio = max(m_tai, m_xiu) / tot
            if ratio >= 0.65:
                candidates.append((w, 60 + ratio * 20, 65 + ns, "N-gram"))
                break

    # 4. MARKOV TRANSITION
    if n >= 10:
        trans = {"Tài": 0, "Xỉu": 0}
        last = results[0]
        for i in range(len(results) - 1):
            if results[i] == last: trans[results[i + 1]] += 1
        tot_t = trans["Tài"] + trans["Xỉu"]
        if tot_t >= 4 and trans["Tài"] != trans["Xỉu"]:
            w = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            ratio = max(trans["Tài"], trans["Xỉu"]) / tot_t
            candidates.append((w, 60 + ratio * 15, 60, "Markov"))

    # 5. XÚC XẮC BIAS (DICE TREND)
    if dice_sums and len(dice_sums) >= 5:
        recent_dice = dice_sums[:8] # Lấy 8 phiên gần nhất
        avg = sum(recent_dice) / len(recent_dice)
        if avg >= 12.5: 
            candidates.append(("Tài", 70.0, 65, "Bias Xúc Xắc"))
        elif avg <= 8.5: 
            candidates.append(("Xỉu", 70.0, 65, "Bias Xúc Xắc"))

    # === VOTING SYSTEM (TỔNG HỢP ĐIỂM) ===
    if not candidates:
        return opp_val, 55.0, "Đảo nhịp"

    score_tai = 0
    score_xiu = 0
    
    # Tính điểm dựa trên: Confidence * Priority (Độ ưu tiên)
    for pred, conf, prio, name in candidates:
        # Cầu có Priority càng cao (Bệt, Đảo dài) thì sức nặng càng lớn
        point = conf * (prio / 100.0) 
        if pred == "Tài": score_tai += point
        else: score_xiu += point

    winner = "Tài" if score_tai > score_xiu else "Xỉu"
    
    # Tính lại độ tin cậy cuối cùng (Dựa trên tỷ lệ điểm)
    total_score = score_tai + score_xiu
    win_score = score_tai if winner == "Tài" else score_xiu
    base_ratio = win_score / total_score if total_score > 0 else 0.5
    
    # Map tỷ lệ ra thang 50 - 98%
    final_conf = 50 + (base_ratio * 48)
    
    # Lấy tên cầu mạnh nhất để trả về (Dù UI không hiện, nhưng API vẫn trả ra cho ông nào dùng API)
    best_signal = max(candidates, key=lambda x: (x[2], x[1]))
    best_name = best_signal[3] if best_signal[0] == winner else "Tổng hợp đa cầu"

    return winner, round(final_conf, 1), best_name

# =====================================================================
# FETCH DỮ LIỆU
# =====================================================================
def generate_fallback(base=7116040):
    elapsed = int(time.time() / 60)
    current = base + elapsed
    random.seed(elapsed)
    rows = []
    for i in range(40):
        sid = current - i
        r = "Tài" if random.random() > 0.5 else "Xỉu"
        d = [random.randint(1, 6) for _ in range(3)]
        rows.append({"phien": sid, "result": r, "dice": f"{d[0]} + {d[1]} + {d[2]}", "total": sum(d)})
    return rows

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
                return rows, 'live'
    except Exception as e:
        print(f"[API ERROR] {e}")
    return generate_fallback(), 'fallback'

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
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        out = []
        correct_count = 0
        total_past = 0
        
        # Dự đoán phiên tiếp theo
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        
        next_pred, next_conf, _ = analyze_pattern(history_for_next, dice_for_next)
        
        out.append({
            'phien': next_phien, 'is_next': True, 'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None
        })
        
        # Đánh giá lịch sử
        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID: break
            if len(out) > 20: break
            
            history_list = [v['result'] for v in valid[:i]][::-1]
            dice_list = [v.get('total', 0) for v in valid[:i]][::-1]
            
            if history_list:
                pred, conf, _ = analyze_pattern(history_list, dice_list)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct: correct_count += 1
            else:
                pred, conf = "Tài", 50.0
                is_correct = None
            
            out.append({
                'phien': current_session['phien'], 'is_next': False, 'prediction': pred, 'confidence': conf,
                'result': current_session['result'], 'dice': current_session['dice'], 'is_correct': is_correct
            })
        
        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict')
def predict_only():
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid: return jsonify({'status': 'error', 'message': 'Lỗi data'}), 404
        
        latest = valid[-1]
        next_phien = latest['phien'] + 1
        h_next = [v['result'] for v in valid][::-1]
        d_next = [v.get('total', 0) for v in valid][::-1]
        
        pred, conf, pattern = analyze_pattern(h_next, d_next)
        
        return jsonify({
            'status': 'success', 
            'next_session': next_phien, 
            'prediction': pred,
            'confidence': conf,
            # Cầu vẫn được trả về API nhưng UI đã ẩn
            'hidden_pattern': pattern, 
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
