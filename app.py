import os
import time
import math
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ================= CẤU HÌNH API =================
LOGIN_URL = "https://lc79b.bet/v1/lobby/auth/login?cp=R&cl=R&pf=web&at="
BASE_SESSION_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at="

# Lưu trữ Token toàn cục. Ban đầu để trống, sẽ được nạp khi đăng nhập.
CURRENT_USER = {
    "username": "",
    "token": "", 
    "balance": 0.0,
    "is_logged_in": False
}
RESET_SESSION_ID = 0

# =====================================================================
# GIAO DIỆN HTML (V13.0 - AUTO AUTH)
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>LC MD5 - AUTOMATED HYPERION VIP</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #050814; 
        --bg-card: rgba(15, 23, 42, 0.7);
        --text-main: #f8fafc; 
        --text-muted: #94a3b8; 
        --border-glass: rgba(255, 255, 255, 0.08);
        --tai-color: #0ea5e9; 
        --tai-glow: rgba(14, 165, 233, 0.5);
        --xiu-color: #ec4899; 
        --xiu-glow: rgba(236, 72, 153, 0.5);
        --gold: #fbbf24;
        --lose: #ef4444;
        --win: #10b981;
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

    body::before {
        content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
        background-image: radial-gradient(1px 1px at 10% 20%, #fff, transparent), radial-gradient(1.5px 1.5px at 80% 40%, #fff, transparent), radial-gradient(1px 1px at 40% 80%, #fff, transparent), radial-gradient(2px 2px at 70% 10%, #fff, transparent);
        background-size: 200px 200px; animation: floatStars 4s ease-in-out infinite; opacity: 0.4;
    }

    /* --- CSS MODAL LOGIN --- */
    .modal-overlay {
        display: none; position: fixed; inset: 0; z-index: 9999;
        background: rgba(5, 8, 20, 0.85); backdrop-filter: blur(10px);
        justify-content: center; align-items: center;
    }
    .modal-overlay.active { display: flex; }
    .login-box {
        background: var(--bg-card); border: 1px solid var(--border-glass);
        padding: 30px; border-radius: 20px; width: 90%; max-width: 400px;
        text-align: center; box-shadow: 0 20px 50px rgba(0,0,0,0.6);
        animation: borderGlow 3s infinite alternate;
    }
    .login-box h2 { color: var(--gold); margin-bottom: 20px; font-size: 22px; text-shadow: 0 0 10px rgba(251,191,36,0.3); }
    .input-group { margin-bottom: 15px; text-align: left; }
    .input-group label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 5px; font-weight: 700; }
    .input-group input { 
        width: 100%; padding: 12px 15px; border-radius: 10px; border: 1px solid var(--border-glass);
        background: rgba(0,0,0,0.3); color: #fff; font-size: 14px; outline: none; transition: 0.3s;
    }
    .input-group input:focus { border-color: var(--tai-color); box-shadow: 0 0 10px var(--tai-glow); }
    .btn-login {
        width: 100%; padding: 12px; border-radius: 10px; border: none;
        background: linear-gradient(135deg, #0284c7, #38bdf8); color: #fff;
        font-weight: 800; font-size: 16px; cursor: pointer; margin-top: 10px;
        box-shadow: 0 0 15px var(--tai-glow); transition: 0.3s;
    }
    .btn-login:hover { transform: translateY(-2px); box-shadow: 0 0 25px var(--tai-glow); }
    .btn-login:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
    .btn-close { position: absolute; top: 15px; right: 20px; font-size: 24px; color: var(--text-muted); cursor: pointer; }

    /* --- CSS MAIN APP --- */
    #main-app { opacity: 0; transition: opacity 0.5s ease; }
    .header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: rgba(5, 8, 20, 0.8); backdrop-filter: blur(20px); border-bottom: 1px solid var(--border-glass); position: sticky; top: 0; z-index: 100; }
    .header-title { font-size: 18px; font-weight: 800; background: linear-gradient(90deg, #fff, #bae6fd, #f472b6, #fff); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: shimmer 3s linear infinite; }
    
    .user-info { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; cursor: pointer; }
    .user-name { font-size: 11px; color: var(--text-muted); font-weight: 600; }
    .user-balance { font-size: 16px; font-weight: 800; color: var(--gold); text-shadow: 0 0 10px rgba(251,191,36,0.5); animation: pulseNum 2s infinite; }

    .stats-bar { max-width: 600px; margin: 16px auto 0; padding: 0 16px; display: flex; gap: 12px; position: relative; z-index: 1; }
    .stat-box { flex: 1; background: var(--bg-card); border: 1px solid var(--border-glass); border-radius: 16px; padding: 12px; text-align: center; backdrop-filter: blur(10px); position: relative; overflow: hidden; }
    .stat-box::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, var(--tai-color), transparent); background-size: 200% 100%; animation: shimmer 2s linear infinite; }
    .stat-lbl { font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 4px; }
    .stat-val { font-size: 20px; font-weight: 800; color: #fff; animation: pulseNum 2.5s infinite; }
    .stat-val.highlight { color: var(--tai-color); }

    .container { padding: 16px; display: flex; flex-direction: column; gap: 12px; max-width: 600px; margin: 0 auto; position: relative; z-index: 1; }
    .card { background: var(--bg-card); border: 1px solid var(--border-glass); border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; backdrop-filter: blur(10px); transition: all 0.3s; position: relative; }
    .card:hover { transform: translateY(-3px); border-color: rgba(255,255,255,0.2); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    .card.active { animation: borderGlow 2s infinite alternate; background: linear-gradient(145deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.8)); }
    
    .col-left { display: flex; flex-direction: column; gap: 6px; flex: 1.2; }
    .session-id { font-size: 16px; font-weight: 800; color: #fff; }
    .bot-info { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 11px; text-transform: uppercase; }
    .badge-tai { background: rgba(14, 165, 233, 0.15); color: #7dd3fc; border: 1px solid rgba(14, 165, 233, 0.4); }
    .badge-xiu { background: rgba(236, 72, 153, 0.15); color: #f9a8d4; border: 1px solid rgba(236, 72, 153, 0.4); }
    .conf-wrap { margin-top: 6px; width: 100%; max-width: 150px; }
    .conf-text { font-size: 10px; color: var(--text-muted); font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 2px; }
    .conf-bg { height: 5px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
    .conf-bar { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--tai-color), #818cf8, var(--tai-color)); background-size: 200% 100%; animation: shimmer 2s linear infinite; transition: width 0.8s; }
    .conf-bar.xiu { background: linear-gradient(90deg, var(--xiu-color), #f472b6, var(--xiu-color)); background-size: 200% 100%; }
    .engine-tag { font-size: 8px; color: var(--gold); opacity: 0.8; margin-top: 4px; display: block; text-transform: uppercase; }

    .col-mid { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 4px; }
    .pred-circle { padding: 6px 16px; border-radius: 20px; font-weight: 800; font-size: 14px; text-transform: uppercase; }
    .pred-tai { background: linear-gradient(135deg, #0284c7, #38bdf8); color: #fff; box-shadow: 0 0 15px var(--tai-glow); }
    .pred-xiu { background: linear-gradient(135deg, #be185d, #ec4899); color: #fff; box-shadow: 0 0 15px var(--xiu-glow); }
    .pred-wait { border: 1px dashed rgba(255,255,255,0.2); color: var(--text-muted); }
    .dice { font-size: 12px; font-weight: 600; color: #cbd5e1; white-space: nowrap; }

    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.8; }
    .status { font-size: 13px; font-weight: 800; display: flex; align-items: center; gap: 4px; }
    .st-win { color: var(--win); }
    .st-lose { color: var(--lose); }
    .st-wait { color: var(--gold); }
    .spin-icon { display: inline-block; animation: spinWait 2s linear infinite; }
    .loading { text-align: center; padding: 40px; color: var(--tai-color); font-weight: 600; animation: pulseNum 2s infinite; }
    
    /* Banner thông báo lỗi */
    .error-banner { background: rgba(239, 68, 68, 0.1); border: 1px solid var(--lose); color: #fca5a5; padding: 15px; border-radius: 10px; text-align: center; font-weight: 600; margin-bottom: 10px; display: none; }
</style>
</head>
<body>

<!-- MODAL LOGIN -->
<div class="modal-overlay" id="login-modal">
    <div class="login-box" style="position: relative;">
        <span class="btn-close" onclick="closeLoginModal()">&times;</span>
        <h2>ĐĂNG NHẬP LC79B</h2>
        <div class="input-group">
            <label>Tài khoản</label>
            <input type="text" id="ip-user" placeholder="Nhập tên đăng nhập...">
        </div>
        <div class="input-group">
            <label>Mật khẩu</label>
            <input type="password" id="ip-pass" placeholder="Nhập mật khẩu...">
        </div>
        <button class="btn-login" id="btn-login" onclick="doLogin()">Xác Nhận Đăng Nhập</button>
    </div>
</div>

<!-- MAIN APP -->
<div id="main-app">
    <div class="header">
        <div class="header-title">⚡ HYPERION OMNI VIP</div>
        <div class="user-info" id="user-info" onclick="openLoginModal()">
            <div class="user-name" id="ui-username">Khách (Chưa đăng nhập)</div>
            <div class="user-balance" id="ui-balance">---</div>
        </div>
    </div>

    <div class="stats-bar">
        <div class="stat-box"><div class="stat-lbl">Tổng Phiên</div><div class="stat-val" id="stat-total">0</div></div>
        <div class="stat-box"><div class="stat-lbl">Thắng</div><div class="stat-val highlight" id="stat-win">0</div></div>
        <div class="stat-box"><div class="stat-lbl">Tỷ Lệ</div><div class="stat-val highlight" id="stat-rate">0%</div></div>
    </div>

    <div class="container">
        <div class="error-banner" id="error-banner">Lỗi: Không lấy được dữ liệu. Vui lòng đăng nhập!</div>
        <div id="list-container">
            <div class="loading">Đang tải dữ liệu...</div>
        </div>
    </div>
</div>

<script>
let isResetting = false;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById('main-app').style.opacity = '1';
    fetchData(); // Load data ngay khi vào
});

function openLoginModal() { document.getElementById('login-modal').classList.add('active'); }
function closeLoginModal() { document.getElementById('login-modal').classList.remove('active'); }

// ================= LOGIN LOGIC =================
async function doLogin() {
    const user = document.getElementById('ip-user').value;
    const pass = document.getElementById('ip-pass').value;
    const btn = document.getElementById('btn-login');
    
    if(!user || !pass) { Swal.fire({title: 'Lỗi', text: 'Nhập đủ Tài khoản và Mật khẩu!', icon: 'warning', background: '#0f172a', color: '#fff'}); return; }
    
    btn.innerText = "Đang xác thực..."; btn.disabled = true;
    
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: user, password: pass})
        });
        const data = await res.json();
        
        if(data.status === 'success') {
            document.getElementById('ui-username').innerText = data.username;
            document.getElementById('ui-balance').innerText = formatMoney(data.balance);
            closeLoginModal();
            document.getElementById('error-banner').style.display = 'none';
            
            Swal.fire({title: 'Đăng nhập thành công!', text: `Chào mừng ${data.username}`, icon: 'success', background: '#0f172a', color: '#fff', timer: 1500, showConfirmButton: false});
            fetchData(); 
        } else {
            Swal.fire({title: 'Đăng nhập thất bại', text: data.message, icon: 'error', background: '#0f172a', color: '#fff'});
            btn.innerText = "Xác Nhận Đăng Nhập"; btn.disabled = false;
        }
    } catch(e) {
        Swal.fire({title: 'Lỗi Server', text: 'Không thể kết nối tới Backend', icon: 'error', background: '#0f172a', color: '#fff'});
        btn.innerText = "Xác Nhận Đăng Nhập"; btn.disabled = false;
    }
}

function formatMoney(amount) {
    return new Intl.NumberFormat('vi-VN').format(amount) + ' đ';
}

// ================= FETCH DATA =================
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
            // Tự động bật form đăng nhập nếu lỗi (do chưa có token hoặc token hết hạn)
            document.getElementById('error-banner').style.display = 'block';
            document.getElementById('error-banner').innerText = "Lỗi: " + data.error;
            document.getElementById('list-container').innerHTML = '<div class="loading" style="color:var(--lose)">Vui lòng đăng nhập để lấy dữ liệu!</div>';
            
            if(!data.is_logged_in) {
                openLoginModal();
            }
            return;
        }
        
        document.getElementById('error-banner').style.display = 'none';
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

    if (!rows.length) { container.innerHTML = '<div class="loading">Không có dữ liệu.</div>'; return; }

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
        if (row.is_next) statusHtml = `<div class="status st-wait">Chờ <span class="spin-icon">⏳</span></div>`;
        else if (row.is_correct === true) statusHtml = `<div class="status st-win">Đúng ✅</div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status st-lose">Sai ❌</div>`;

        html += `
            <div class="card${isActive}">
                <div class="col-left">
                    <div class="session-id">#${row.phien}</div>
                    <div class="bot-info"><span class="bot-lbl">Bot:</span> ${badgeHtml}</div>
                    <div class="conf-wrap">
                        <div class="conf-text"><span>Độ tin cậy</span><span>${row.confidence}%</span></div>
                        <div class="conf-bg"><div class="${confClass}" style="width:${row.confidence}%"></div></div>
                        <span class="engine-tag">30 Models Active</span>
                    </div>
                </div>
                <div class="col-mid">${predHtml}<div class="dice">${diceHtml}</div></div>
                <div class="col-right">${statusHtml}</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

setInterval(() => { fetchData(); }, 4000);
</script>
</body>
</html>
"""

# =====================================================================
# HELPER FUNCTIONS & LOGIC TOÁN HỌC (GIỮ NGUYÊN BẢN V10.1)
# =====================================================================
def build_blocks(results):
    if not results: return []
    blocks = []
    curr_val = results[0]
    curr_count = 1
    for r in results[1:]:
        if r == curr_val: curr_count += 1
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

def evaluate_30_models(results, dice_sums=None):
    models = []
    n = len(results)
    if n < 10: return models
    blocks = build_blocks(results)
    curr_val = blocks[0]['val']
    curr_len = blocks[0]['len']
    opp_val = "Xỉu" if curr_val == "Tài" else "Tài"
    last = results[0]

    for target_len in range(1, 11):
        if curr_len == target_len or (target_len == 10 and curr_len >= 10):
            cont, brk = 0, 0
            for k in range(10, n):
                sub_blocks = build_blocks(results[k:])
                if len(sub_blocks) >= 2 and sub_blocks[0]['len'] == target_len and sub_blocks[0]['val'] == curr_val:
                    if results[k-1] == curr_val: cont += 1
                    else: brk += 1
            tot = cont + brk
            if tot >= 2:
                p_cont = (cont + 1) / (tot + 2)
                if p_cont > 0.55: models.append({'id': f'S{target_len}', 'name': f'Bám bệt {target_len}', 'prediction': curr_val, 'win_rate': p_cont, 'weight': 5.0 + target_len*0.5})
                elif p_cont < 0.45: models.append({'id': f'S{target_len}', 'name': f'Bẻ bệt {target_len}', 'prediction': opp_val, 'win_rate': 1-p_cont, 'weight': 5.0 + target_len*0.5})
    
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]: alt_len += 1
        else: break
    for target_alt in range(1, 6):
        if alt_len == target_alt or (target_alt == 5 and alt_len >= 5):
            cont, brk = 0, 0
            for k in range(10, n):
                sub_alt = 0
                for i in range(k, n - 1):
                    if results[i] != results[i + 1]: sub_alt += 1
                    else: break
                if sub_alt == target_alt:
                    if results[k-1] != results[k]: cont += 1
                    else: brk += 1
            tot = cont + brk
            if tot >= 2:
                p_cont = (cont + 1) / (tot + 2)
                if p_cont > 0.55: models.append({'id': f'A{target_alt}', 'name': f'Đảo {target_alt} tiếp', 'prediction': opp_val if target_alt % 2 != 0 else curr_val, 'win_rate': p_cont, 'weight': 4.0 + target_alt*0.8})
                elif p_cont < 0.45: models.append({'id': f'A{target_alt}', 'name': f'Đảo {target_alt} gãy', 'prediction': curr_val if target_alt % 2 != 0 else opp_val, 'win_rate': 1-p_cont, 'weight': 4.0 + target_alt*0.8})
    
    for ns in [4, 5, 6, 7, 8]:
        if n < ns + 1: continue
        curr_seq = tuple(results[:ns])
        m_tai, m_xiu = 0, 0
        for i in range(n - ns):
            if tuple(results[i:i+ns]) == curr_seq and i + ns < n:
                if results[i+ns] == "Tài": m_tai += 1
                else: m_xiu += 1
        tot = m_tai + m_xiu
        if tot >= 2:
            p_win_tai = (m_tai + 1) / (tot + 2)
            if p_win_tai > 0.55: models.append({'id': f'NG{ns}', 'name': f'N-gram {ns} (Tài)', 'prediction': 'Tài', 'win_rate': p_win_tai, 'weight': 3.0 + ns*0.2})
            elif p_win_tai < 0.45: models.append({'id': f'NG{ns}', 'name': f'N-gram {ns} (Xỉu)', 'prediction': 'Xỉu', 'win_rate': 1-p_win_tai, 'weight': 3.0 + ns*0.2})
    
    if len(blocks) >= 5:
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        if code is not None:
            stats_81 = {}
            for k in range(10, n):
                sub_blocks = build_blocks(results[k:])
                if len(sub_blocks) < 5: continue
                sub_code = encode_pattern_81([b['len'] for b in sub_blocks[1:5]])
                if sub_code is None: continue
                cont = (results[k-1] == sub_blocks[0]['val'])
                key = (sub_code, min(sub_blocks[0]['len'], 4))
                if key not in stats_81: stats_81[key] = {'c':0, 'b':0}
                stats_81[key]['c' if cont else 'b'] += 1
            key_exact = (code, min(curr_len, 4))
            if key_exact in stats_81:
                s = stats_81[key_exact]
                tot = s['c'] + s['b']
                if tot >= 2:
                    p_c = (s['c'] + 1) / (tot + 2)
                    models.append({'id': 'M81_EX', 'name': 'Mẫu 81 Exact', 'prediction': curr_val if p_c>0.5 else opp_val, 'win_rate': max(p_c, 1-p_c), 'weight': 7.0})
    
    if n >= 10:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(n - 1):
            if results[i] == last: trans[results[i + 1]] += 1
        tot_t = trans["Tài"] + trans["Xỉu"]
        if tot_t >= 3:
            p_tai = (trans["Tài"] + 1) / (tot_t + 2)
            models.append({'id': 'MK1', 'name': 'Markov Bậc 1', 'prediction': 'Tài' if p_tai>0.5 else 'Xỉu', 'win_rate': max(p_tai, 1-p_tai), 'weight': 4.0})
    
    return models

def analyze_pattern(results, dice_sums=None):
    if not results or len(results) < 5: return "Tài", 50.0, "Khởi tạo"
    models = evaluate_30_models(results, dice_sums)
    if not models: return results[0], 50.0, "Nhiễu"
        
    tai_score = sum(m['win_rate'] * m['weight'] for m in models if m['prediction'] == 'Tài')
    xiu_score = sum(m['win_rate'] * m['weight'] for m in models if m['prediction'] == 'Xỉu')
    total_score = tai_score + xiu_score
    if total_score == 0: return results[0], 50.0, "Nhiễu"

    win_ratio = max(tai_score, xiu_score) / total_score
    winner = "Tài" if tai_score > xiu_score else "Xỉu"

    shift_ratio = win_ratio - 0.5
    sigmoid_val = 1 / (1 + math.exp(-14 * shift_ratio))
    final_conf = 50.0 + ((sigmoid_val - 0.5) * 2 * 50.0)
    
    if min(tai_score, xiu_score) > max(tai_score, xiu_score) * 0.6:
        final_conf -= 8.0 

    final_conf = max(50.0, min(100.0, final_conf))
    best_model = max(models, key=lambda x: x['weight'] if x['prediction'] == winner else 0)
    
    return winner, round(final_conf, 1), best_model['name']

def fetch_sessions(token):
    """
    Thêm Headers Origin và Referer để vượt qua bộ lọc của nhà cái
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://lc79b.bet',
            'Referer': 'https://lc79b.bet/'
        }
        url = BASE_SESSION_URL + token
        r = requests.get(url, timeout=8, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']:
                rows = []
                for item in data['list']:
                    res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    rows.append({'phien': int(item['id']), 'result': res, 'dice': f"{dices[0]} + {dices[1]} + {dices[2]}", 'total': item.get('point', sum(dices))})
                return rows
        return []
    except Exception as e:
        print(f"[API ERROR] {e}")
        return []

# =====================================================================
# FLASK ROUTES
# =====================================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    user = data.get('username')
    pwd = data.get('password')
    
    try:
        payload = {
            "username": user, 
            "password": pwd,
            "deviceId": "web_bot_lc79",
            "platform": "web"
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://lc79b.bet',
            'Referer': 'https://lc79b.bet/'
        }
        
        r = requests.post(LOGIN_URL, json=payload, headers=headers, timeout=10)
        
        if r.status_code == 200:
            res_data = r.json()
            
            if res_data.get('code') == 0 or res_data.get('status') == 'success':
                data_obj = res_data.get('data', {})
                token = data_obj.get('accessToken') or data_obj.get('token') or data_obj.get('at')
                balance = data_obj.get('balance') or data_obj.get('money') or 0.0
                
                if token:
                    CURRENT_USER['username'] = user
                    CURRENT_USER['token'] = token
                    CURRENT_USER['balance'] = float(balance)
                    CURRENT_USER['is_logged_in'] = True
                    return jsonify({"status": "success", "username": user, "balance": CURRENT_USER['balance']})
                else:
                    return jsonify({"status": "error", "message": "Không lấy được Token từ API"}), 401
            else:
                msg = res_data.get('message') or res_data.get('msg') or 'Tài khoản hoặc mật khẩu không chính xác!'
                return jsonify({"status": "error", "message": msg}), 401
        else:
            return jsonify({"status": "error", "message": f"Lỗi HTTP {r.status_code} từ nhà cái"}), 400
            
    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        return jsonify({"status": "error", "message": "Không thể kết nối đến server của nhà cái"}), 500

@app.route('/api/history')
def history():
    global RESET_SESSION_ID
    
    # Nếu chưa đăng nhập hoặc mất token, trả về lỗi để Frontend bật form Login
    if not CURRENT_USER['token']:
        return jsonify({'error': 'Vui lòng đăng nhập để lấy dữ liệu!', 'is_logged_in': False}), 401

    try:
        valid = sorted(fetch_sessions(CURRENT_USER['token']), key=lambda x: x['phien'])
        
        # Nếu token hết hạn, API trả về list rỗng
        if not valid: 
            CURRENT_USER['token'] = "" # Xóa token cũ để bắt đăng nhập lại
            return jsonify({'error': 'Phiên đăng nhập đã hết hạn hoặc API bị lỗi. Vui lòng đăng nhập lại!', 'is_logged_in': False}), 401

        out = []
        correct_count = 0
        total_past = 0
        
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        
        next_pred, next_conf, _ = analyze_pattern(history_for_next, dice_for_next)
        
        out.append({
            'phien': next_phien, 'is_next': True, 'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None
        })
        
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
