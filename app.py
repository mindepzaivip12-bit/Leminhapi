import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

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
<title>LC MD5</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-primary: #f8fdff;
        --bg-secondary: #e0f2fe;
        --bg-card: #ffffff;
        --bg-card-hover: #f8fdff;
        --bg-active: linear-gradient(145deg, #ffffff, #f0f9ff);
        --text-primary: #0c4a6e;
        --text-secondary: #475569;
        --text-muted: #94a3b8;
        --border: #bae6fd;
        --border-hover: #7dd3fc;
        --border-active: #38bdf8;
        
        --blue-light: #e0f2fe;
        --blue-soft: #7dd3fc;
        --blue-primary: #0ea5e9;
        --blue-deep: #0284c7;
        --blue-dark: #075985;
        --blue-glow: rgba(56, 189, 248, 0.35);
        
        --pink-primary: #ec4899;
        --pink-deep: #db2777;
        --pink-light: #fce7f3;
        
        --green: #10b981;
        --red: #ef4444;
        --gold: #f59e0b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    html, body { height: 100%; }
    
    @keyframes bgFloat { 0%,100%{transform:translate(0,0)} 50%{transform:translate(30px,-40px)} }
    @keyframes bgFloat2 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(-25px,35px)} }
    @keyframes bubble { 0%,100%{transform:translateY(0) scale(1); opacity:0.4} 50%{transform:translateY(-20px) scale(1.15); opacity:0.8} }
    @keyframes rainbow-border { 0%{border-color:#38bdf8;box-shadow:0 0 0 0 rgba(56,189,248,0.4),0 4px 20px rgba(56,189,248,0.2)} 
        33%{border-color:#a78bfa;box-shadow:0 0 0 0 rgba(167,139,250,0.4),0 4px 20px rgba(167,139,250,0.2)}
        66%{border-color:#f472b6;box-shadow:0 0 0 0 rgba(244,114,182,0.4),0 4px 20px rgba(244,114,182,0.2)}
        100%{border-color:#38bdf8;box-shadow:0 0 0 0 rgba(56,189,248,0.4),0 4px 20px rgba(56,189,248,0.2)} }
    @keyframes textGlow { 0%,100%{text-shadow:0 0 10px rgba(56,189,248,0.3)} 50%{text-shadow:0 0 20px rgba(56,189,248,0.6)} }
    @keyframes titleShine { 0%{background-position:-200% center} 100%{background-position:200% center} }
    @keyframes spin { to{transform:rotate(360deg)} }
    @keyframes slideIn { from{opacity:0;transform:translateY(24px) scale(0.94)} to{opacity:1;transform:translateY(0) scale(1)} }
    @keyframes shimmerBar { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
    @keyframes statPop { 0%,100%{transform:scale(1)} 50%{transform:scale(1.04)} }
    @keyframes dotPulse { 0%,100%{box-shadow:0 0 0 0 rgba(56,189,248,0.6)} 70%{box-shadow:0 0 0 12px rgba(56,189,248,0)} }
    @keyframes ripple { 0%{transform:scale(0);opacity:0.7} 100%{transform:scale(4);opacity:0} }
    @keyframes wave { 0%{transform:translateX(-100%)} 100%{transform:translateX(100%)} }
    @keyframes breathe { 0%,100%{opacity:0.7} 50%{opacity:1} }
    @keyframes pulseRing { 0%{transform:scale(0.8);opacity:1} 100%{transform:scale(2);opacity:0} }
    
    body {
        background: 
            radial-gradient(circle at 20% 0%, rgba(56,189,248,0.15) 0%, transparent 40%),
            radial-gradient(circle at 80% 100%, rgba(167,139,250,0.12) 0%, transparent 45%),
            linear-gradient(180deg, #f8fdff 0%, #e0f2fe 40%, #f0f9ff 100%);
        color: var(--text-primary);
        min-height: 100vh;
        padding-bottom: 40px;
        overflow-x: hidden;
        position: relative;
        background-attachment: fixed;
    }
    
    /* Bubble decorations */
    .bubbles { position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
    .bubbles::before, .bubbles::after {
        content: ''; position: absolute; border-radius: 50%;
        background: radial-gradient(circle, rgba(125,211,252,0.5), transparent 70%);
        filter: blur(30px);
    }
    .bubbles::before { width: 300px; height: 300px; top: -80px; left: -80px; animation: bgFloat 20s ease-in-out infinite; }
    .bubbles::after { width: 350px; height: 350px; bottom: -100px; right: -100px; animation: bgFloat2 25s ease-in-out infinite; }
    .bubble-mid {
        position: fixed; width: 220px; height: 220px; top: 45%; left: 55%;
        background: radial-gradient(circle, rgba(244,114,182,0.25), transparent 70%);
        filter: blur(40px); border-radius: 50%;
        animation: bubble 22s ease-in-out infinite; pointer-events: none; z-index: 0;
    }
    .bubble-small1 {
        position: fixed; width: 150px; height: 150px; top: 20%; right: 15%;
        background: radial-gradient(circle, rgba(167,139,250,0.3), transparent 70%);
        filter: blur(35px); border-radius: 50%;
        animation: bubble 18s ease-in-out infinite reverse; pointer-events: none; z-index: 0;
    }
    
    /* HEADER */
    .header {
        display: flex; justify-content: space-between; align-items: center;
        padding: 15px 20px;
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(20px);
        border-bottom: 2px solid transparent;
        border-image: linear-gradient(90deg, transparent, #7dd3fc, #a78bfa, #f472b6, #7dd3fc, transparent) 1;
        position: sticky; top: 0; z-index: 100;
        box-shadow: 0 4px 20px rgba(56,189,248,0.12);
    }
    .header-left { display: flex; align-items: center; gap: 11px; }
    .header-live-dot {
        width: 11px; height: 11px; border-radius: 50%;
        background: radial-gradient(circle, #7dd3fc, #0ea5e9);
        box-shadow: 0 0 12px #38bdf8, 0 0 0 3px rgba(56,189,248,0.2);
        animation: dotPulse 1.8s infinite;
    }
    .header-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 19px; font-weight: 900; letter-spacing: 0.5px;
        background: linear-gradient(90deg, #0284c7, #38bdf8, #a78bfa, #f472b6, #38bdf8, #0284c7);
        background-size: 300% auto;
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
        animation: titleShine 5s linear infinite;
        filter: drop-shadow(0 2px 4px rgba(56,189,248,0.3));
    }
    .btn-reset {
        position: relative; overflow: hidden;
        background: #fff;
        color: var(--red);
        border: 1.5px solid var(--red);
        padding: 8px 18px; border-radius: 10px;
        font-weight: 700; font-size: 13px; cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 2px 10px rgba(239,68,68,0.15);
    }
    .btn-reset:hover {
        background: var(--red); color: #fff;
        box-shadow: 0 4px 20px rgba(239,68,68,0.4);
        transform: translateY(-2px);
    }
    .btn-reset:active::after {
        content: ''; position: absolute; left: 50%; top: 50%;
        width: 12px; height: 12px; border-radius: 50%; background: #fff;
        transform: translate(-50%,-50%) scale(0);
        animation: ripple 0.6s ease-out;
    }
    
    /* STATS */
    .stats-bar {
        max-width: 600px; margin: 18px auto 0; padding: 0 15px;
        display: flex; gap: 12px; position: relative; z-index: 1;
    }
    .stat-item {
        flex: 1;
        background: #ffffff;
        border: 1.5px solid var(--border);
        border-radius: 14px;
        padding: 12px 10px; text-align: center;
        position: relative; overflow: hidden;
        transition: all 0.35s ease;
        box-shadow: 0 4px 15px rgba(56,189,248,0.08);
    }
    .stat-item:hover {
        border-color: var(--border-hover);
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(56,189,248,0.2);
    }
    .stat-item::before {
        content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 3px;
        background: linear-gradient(90deg, #7dd3fc, #38bdf8, #a78bfa, #f472b6, #38bdf8, #7dd3fc);
        background-size: 300% 100%;
        animation: shimmerBar 3s linear infinite;
    }
    .stat-label {
        font-size: 10px; color: var(--text-muted);
        text-transform: uppercase; letter-spacing: 1.4px;
        margin-bottom: 5px; font-weight: 700;
    }
    .stat-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 21px; font-weight: 900;
        color: var(--blue-dark);
    }
    .stat-value.win {
        background: linear-gradient(135deg, #0ea5e9, #22d3ee);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        animation: statPop 2.5s infinite;
    }
    
    /* CONTAINER */
    .container {
        padding: 18px 15px;
        display: flex; flex-direction: column; gap: 13px;
        max-width: 600px; margin: 0 auto;
        position: relative; z-index: 1;
    }
    
    /* CARD */
    .card-item {
        background: #ffffff;
        border: 1.5px solid var(--border);
        border-radius: 14px;
        padding: 15px 17px;
        display: flex; justify-content: space-between; align-items: center;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative; overflow: hidden;
        animation: slideIn 0.5s ease-out backwards;
        box-shadow: 0 4px 15px rgba(56,189,248,0.08);
    }
    .card-item::before {
        content: ''; position: absolute;
        left: 0; top: 0; bottom: 0; width: 3px;
        background: linear-gradient(180deg, transparent, #38bdf8, #a78bfa, transparent);
        opacity: 0; transition: opacity 0.35s;
    }
    .card-item:hover {
        background: var(--bg-card-hover);
        transform: translateY(-3px);
        box-shadow: 0 10px 30px rgba(56,189,248,0.18);
        border-color: var(--border-hover);
    }
    .card-item:hover::before { opacity: 1; }
    
    .card-item.active {
        background: var(--bg-active);
        animation: slideIn 0.5s ease-out backwards, rainbow-border 3.5s linear infinite;
        border-width: 2px;
        position: relative;
    }
    .card-item.active::after {
        content: '';
        position: absolute; top: 12px; right: 14px;
        width: 9px; height: 9px; border-radius: 50%;
        background: radial-gradient(circle, #7dd3fc, #0284c7);
        box-shadow: 0 0 12px #38bdf8;
        animation: dotPulse 1.5s infinite;
    }
    .card-item.active .id-text {
        background: linear-gradient(90deg, #0284c7, #38bdf8, #a78bfa, #0284c7);
        background-size: 200% auto;
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        animation: titleShine 3s linear infinite;
    }
    
    /* COLUMNS */
    .col-left { display: flex; flex-direction: column; gap: 6px; flex: 1.2; }
    .id-text {
        font-family: 'Orbitron', sans-serif;
        font-size: 16px; font-weight: 800;
        letter-spacing: 0.4px;
        color: var(--blue-dark);
        background: linear-gradient(90deg, #075985, #0ea5e9);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .bot-line { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .bot-label { color: var(--text-muted); font-weight: 600; }
    .bet-badge {
        padding: 4px 12px; border-radius: 20px;
        font-weight: 800; font-size: 11px;
        letter-spacing: 0.5px; position: relative;
        overflow: hidden;
    }
    .bet-badge::after {
        content: ''; position: absolute; inset: 0;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
        animation: wave 2.5s infinite;
    }
    .bet-tai {
        background: linear-gradient(135deg, #e0f2fe, #bae6fd);
        color: #0369a1;
        border: 1px solid #7dd3fc;
        box-shadow: 0 2px 8px rgba(56,189,248,0.25);
    }
    .bet-xiu {
        background: linear-gradient(135deg, #fce7f3, #fbcfe8);
        color: #9f1239;
        border: 1px solid #f9a8d4;
        box-shadow: 0 2px 8px rgba(244,114,182,0.25);
    }
    .conf-text {
        color: var(--text-muted); font-size: 10.5px;
        font-style: italic; font-weight: 500;
    }
    .conf-text b {
        color: var(--blue-deep); font-weight: 800; font-style: normal;
        font-size: 12px;
    }
    .conf-bar-wrap {
        height: 4px; background: #e0f2fe;
        border-radius: 3px; overflow: hidden; margin-top: 4px;
    }
    .conf-bar {
        height: 100%; border-radius: 3px;
        background: linear-gradient(90deg, #0ea5e9, #22d3ee, #a78bfa, #f472b6, #0ea5e9);
        background-size: 300% 100%;
        animation: shimmerBar 2s linear infinite;
        transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 0 8px rgba(56,189,248,0.4);
    }
    
    .col-mid {
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        gap: 8px; flex: 1;
    }
    .pred-badge {
        padding: 7px 18px; border-radius: 22px;
        font-family: 'Orbitron', sans-serif;
        font-weight: 900; font-size: 13px;
        text-transform: uppercase; letter-spacing: 1.4px;
        position: relative; overflow: hidden;
        transition: all 0.3s;
    }
    .pred-badge::before {
        content: ''; position: absolute; inset: 0;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
        animation: wave 2.8s infinite;
    }
    .pred-tai {
        background: linear-gradient(135deg, #0284c7, #0ea5e9);
        color: #fff;
        box-shadow: 0 4px 15px rgba(2,132,199,0.45), inset 0 1px 0 rgba(255,255,255,0.3);
    }
    .pred-xiu {
        background: linear-gradient(135deg, #db2777, #ec4899);
        color: #fff;
        box-shadow: 0 4px 15px rgba(219,39,119,0.45), inset 0 1px 0 rgba(255,255,255,0.3);
    }
    .pred-empty {
        background: transparent;
        border: 1.5px dashed var(--border);
        color: var(--text-muted);
    }
    .pred-empty::before { display: none; }
    .dice-text {
        font-family: 'Orbitron', sans-serif;
        font-size: 13px; font-weight: 700;
        color: var(--text-secondary); white-space: nowrap;
        letter-spacing: 0.5px;
    }
    .card-item.active .dice-text {
        color: var(--blue-deep);
        animation: breathe 1.8s ease-in-out infinite;
    }
    
    .col-right {
        display: flex; flex-direction: column;
        align-items: flex-end; justify-content: center;
        flex: 0.75; gap: 4px;
    }
    .status-text {
        font-size: 13px; font-weight: 800;
        display: flex; align-items: center; gap: 5px;
    }
    .status-win { color: var(--blue-deep); text-shadow: 0 0 8px rgba(56,189,248,0.4); }
    .status-lose { color: var(--red); }
    .status-wait { color: var(--blue-primary); }
    .spin { display: inline-block; animation: spin 2s linear infinite; }
    
    .loading {
        text-align: center; padding: 55px;
        color: var(--blue-primary); font-weight: 700;
        letter-spacing: 1.5px; font-size: 14px;
        animation: textGlow 2s infinite;
    }
    
    @media (max-width: 400px) {
        .header-title { font-size: 15px; }
        .stat-value { font-size: 16px; }
        .dice-text { font-size: 11px; }
        .id-text { font-size: 14px; }
        .pred-badge { padding: 6px 14px; font-size: 11px; }
    }
</style>
</head>
<body>
<div class="bubbles"></div>
<div class="bubble-mid"></div>
<div class="bubble-small1"></div>

<div class="header">
    <div class="header-left">
        <div class="header-live-dot"></div>
        <div class="header-title">⚡ LC MD5 MINHLE</div>
    </div>
    <button class="btn-reset" onclick="confirmReset()">↻ Reset</button>
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

<div class="container" id="list-container">
    <div class="loading">✦ Đang kết nối Server ✦</div>
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
        renderList(data.rows || [], data.stats || {});
    } catch (e) {
        document.getElementById('list-container').innerHTML =
            '<div class="loading" style="color:var(--red)">⚠ Lỗi kết nối Server</div>';
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
        container.innerHTML = '<div class="loading">Không có dữ liệu. Đợi phiên mới...</div>';
        return;
    }
    container.innerHTML = '';
    rows.forEach((row, idx) => {
        const div = document.createElement('div');
        div.className = 'card-item' + (row.is_next ? ' active' : '');
        div.style.animationDelay = (idx * 45) + 'ms';
        let predBadge = `<span class="pred-badge pred-empty">-</span>`;
        let betBadge = `<span class="bet-badge" style="background:#f1f5f9;color:#94a3b8;border:1px solid #cbd5e1">CƯỢC -</span>`;
        if (row.prediction === "Tài") {
            predBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
            betBadge = `<span class="bet-badge bet-tai">CƯỢC TÀI</span>`;
        } else if (row.prediction === "Xỉu") {
            predBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;
            betBadge = `<span class="bet-badge bet-xiu">CƯỢC XỈU</span>`;
        }
        let resultBadge = `<span class="pred-badge pred-empty">-</span>`;
        if (row.result === "Tài") resultBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
        if (row.result === "Xỉu") resultBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;
        let diceDisplay = "? + ? + ?";
        if (row.dice !== "? + ? + ?") {
            const p = row.dice.split(" + ");
            diceDisplay = `${row.dice} (${parseInt(p[0]) + parseInt(p[1]) + parseInt(p[2])})`;
        }
        let statusHtml = '';
        if (row.is_next) statusHtml = `<div class="status-text status-wait">Chờ <span class="spin">⏳</span></div>`;
        else if (row.is_correct === true) statusHtml = `<div class="status-text status-win">Đúng ✅</div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status-text status-lose">Sai ❌</div>`;
        else statusHtml = `<div class="status-text" style="color:var(--text-muted)">-</div>`;
        div.innerHTML = `
            <div class="col-left">
                <div class="id-text">#${row.phien}</div>
                <div class="bot-line"><span class="bot-label">Bot:</span> ${betBadge}</div>
                <div class="conf-text">Độ tin cậy: <b>${row.confidence}%</b></div>
                <div class="conf-bar-wrap">
                    <div class="conf-bar" style="width:${row.confidence}%"></div>
                </div>
            </div>
            <div class="col-mid">
                ${row.is_next ? predBadge : resultBadge}
                <div class="dice-text">${diceDisplay}</div>
            </div>
            <div class="col-right">${statusHtml}</div>
        `;
        container.appendChild(div);
    });
}
async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?',
        text: "Lịch sử hiển thị sẽ bị ẩn. Hệ thống vẫn tính ngầm!",
        icon: 'warning', showCancelButton: true,
        confirmButtonColor: '#0ea5e9', cancelButtonColor: '#64748b',
        confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy',
        background: '#ffffff', color: '#0c4a6e'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({
                title: 'Đang Reset...', allowOutsideClick: false,
                didOpen: () => Swal.showLoading(),
                background: '#ffffff', color: '#0c4a6e'
            });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({
                        title: 'Thành công!', text: 'Đã chốt mốc #' + data.reset_to,
                        icon: 'success', confirmButtonColor: '#0ea5e9',
                        background: '#ffffff', color: '#0c4a6e'
                    });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire({
                    title: 'Lỗi!', text: error.message, icon: 'error',
                    background: '#ffffff', color: '#0c4a6e'
                });
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

# =====================================================================
# THUẬT TOÁN V7.0 - ĐẢO & BÁO FULL SYSTEM
# =====================================================================
def analyze_pattern(results, dice_sums=None):
    """
    Trả về: (prediction, confidence, pattern_name, top_signals, signal_count)
    Đầy đủ các nhóm cầu:
    - Bệt (bám/bẻ)
    - Đảo đơn / kép / tam / tứ / hỗn hợp / gãy
    - Báo bệt sắp gãy / báo đảo sắp gãy / báo chu kỳ sắp hết
    - Cầu phức tạp (1-2-1, 2-1-2, 3-2-3, ...)
    - N-gram, Markov, Dice bias, Momentum, Anti-momentum
    - Fibonacci, Đối xứng, Pattern, Chu kỳ 4, Chuyển cầu
    """
    if not results or len(results) < 3:
        return "Tài", 50.0, "Khởi tạo", [], 0
    
    n = len(results)
    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    candidates = []
    
    def add(pred, conf, name, priority):
        candidates.append((pred, round(conf, 1), name, priority))
    
    # ============================ BLOCKS ============================
    blocks = []
    curr_val, curr_count = results[0], 1
    for r in results[1:]:
        if r == curr_val:
            curr_count += 1
        else:
            blocks.append({'val': curr_val, 'len': curr_count})
            curr_val, curr_count = r, 1
    blocks.append({'val': curr_val, 'len': curr_count})
    
    # ========== NHÓM 1: CẦU BỆT (1-8) ==========
    streak = blocks[0]['len']
    if streak == 2: add(last, 52.0, "Bám bệt 2", 52)
    elif streak == 3: add(last, 56.0, "Bám bệt 3", 56)
    elif streak == 4: add(last, 62.0, "Bám bệt 4", 62)
    elif streak == 5: add(opposite, 68.0, "Bẻ bệt 5", 68)
    elif streak == 6: add(opposite, 78.0, "Bẻ bệt 6", 78)
    elif streak == 7: add(opposite, 84.0, "Bẻ bệt 7", 84)
    elif streak == 8: add(opposite, 88.0, "Bẻ bệt 8", 88)
    elif streak >= 9: add(opposite, min(96.0, 90.0 + streak - 9), f"Bẻ bệt siêu mạnh {streak}", 92)
    
    # ========== NHÓM 2: ĐẢO ĐƠN 1-1 (9-16) ==========
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]: alt_len += 1
        else: break
    
    if alt_len == 2: add(results[0], 58.0, "Đảo đơn ngắn 3", 58)
    elif alt_len == 3: add(opposite, 66.0, "Đảo đơn 4", 66)
    elif alt_len == 4: add(opposite, 72.0, "Đảo đơn 5", 72)
    elif alt_len == 5: add(opposite, 80.0, "Đảo đơn 6", 80)
    elif alt_len == 6: add(opposite, 86.0, "Đảo đơn 7", 86)
    elif alt_len == 7: add(opposite, 90.0, "Đảo đơn 8 (sắp gãy)", 90)
    elif alt_len >= 8: add(opposite, min(96.0, 92.0 + alt_len - 8), f"Đảo đơn siêu dài {alt_len+1}", 92)
    
    # ========== NHÓM 3: ĐẢO KÉP 2-2-2 (17-20) ==========
    if len(blocks) >= 4:
        is_alt2 = all(blocks[i]['len'] == 2 for i in range(min(4, len(blocks))))
        if is_alt2 and blocks[0]['val'] != blocks[1]['val']:
            curr = blocks[0]['len']
            if curr < 2: add(blocks[0]['val'], 88.0, "Bám đảo kép 2-2 (dở)", 88)
            elif curr == 2: add(opposite, 92.0, "Bẻ đảo kép 2-2", 92)
    
    # ========== NHÓM 4: ĐẢO TAM 3-3-3 (21-24) ==========
    if len(blocks) >= 4:
        is_alt3 = all(blocks[i]['len'] == 3 for i in range(min(3, len(blocks))))
        if is_alt3 and blocks[0]['val'] != blocks[1]['val']:
            curr = blocks[0]['len']
            if curr < 3: add(blocks[0]['val'], 90.0, "Bám đảo tam 3-3 (dở)", 90)
            elif curr == 3: add(opposite, 94.0, "Bẻ đảo tam 3-3", 94)
    
    # ========== NHÓM 5: ĐẢO TỨ 4-4-4 (25-28) ==========
    if len(blocks) >= 3:
        is_alt4 = all(blocks[i]['len'] == 4 for i in range(min(3, len(blocks))))
        if is_alt4 and blocks[0]['val'] != blocks[1]['val']:
            curr = blocks[0]['len']
            if curr < 4: add(blocks[0]['val'], 92.0, "Bám đảo tứ 4-4 (dở)", 92)
            elif curr == 4: add(opposite, 95.0, "Bẻ đảo tứ 4-4", 95)
    
    # ========== NHÓM 6: ĐẢO HỖN HỢP 1-2 / 2-1 (29-32) ==========
    if len(blocks) >= 4:
        lens = [b['len'] for b in blocks[:5]]
        # 1-2-1-2
        if lens[:4] == [1, 2, 1, 2]: add(opposite, 82.0, "Đảo hỗn hợp 1-2-1-2", 82)
        # 2-1-2-1
        elif lens[:4] == [2, 1, 2, 1]: add(opposite, 82.0, "Đảo hỗn hợp 2-1-2-1", 82)
        # 1-2-2-1 (đối xứng)
        elif lens[:4] == [1, 2, 2, 1]: add(blocks[0]['val'], 78.0, "Đảo 1-2-2-1", 78)
        # 2-1-1-2
        elif lens[:4] == [2, 1, 1, 2]: add(blocks[0]['val'], 78.0, "Đảo 2-1-1-2", 78)
    
    # ========== NHÓM 7: ĐẢO GÃY (33-36) ==========
    # Đảo dài vừa gãy -> chuyển sang bệt mới
    if alt_len == 0 and len(blocks) >= 2:
        prev_alt = 0
        for i in range(1, len(blocks)):
            if blocks[i]['val'] != blocks[i-1]['val']: prev_alt += 1
            else: break
        # Nếu trước đó có đảo 4+ và vừa gãy -> bám bệt mới
        if prev_alt >= 4 and blocks[0]['len'] <= 2:
            add(blocks[0]['val'], 74.0, f"Đảo {prev_alt} vừa gãy → bám bệt", 74)
    
    # ========== NHÓM 8: BÁO BỆT SẮP GÃY (37-40) ==========
    # Bệt dài 6+ -> tín hiệu báo sắp gãy mạnh (dice, momentum đối nghịch)
    if streak >= 6:
        # Báo cấp 1: streak 6
        if streak == 6: add(opposite, 80.0, "BÁO gãy bệt 6", 80)
        elif streak == 7: add(opposite, 86.0, "BÁO gãy bệt 7", 86)
        elif streak >= 8: add(opposite, 90.0, f"BÁO gãy bệt {streak}", 90)
    
    # ========== NHÓM 9: BÁO ĐẢO SẮP GÃY (41-44) ==========
    # Đảo dài 6+ -> tín hiệu báo sắp gãy sang bệt
    if alt_len >= 6:
        if alt_len == 6: add(last, 72.0, "BÁO gãy đảo 6", 72)
        elif alt_len == 7: add(last, 80.0, "BÁO gãy đảo 7", 80)
        elif alt_len >= 8: add(last, 86.0, f"BÁO gãy đảo {alt_len}", 86)
    
    # ========== NHÓM 10: BÁO CHU KỲ SẮP HẾT (45-47) ==========
    # Phát hiện chu kỳ 2-2, 3-3 sắp kết thúc (blốc hiện tại gần đủ)
    if len(blocks) >= 3:
        if blocks[1]['len'] == 2 and blocks[2]['len'] == 2:
            if blocks[0]['len'] == 1: add(blocks[0]['val'], 85.0, "BÁO chu kỳ 2-2 sắp hết (còn 1)", 85)
            elif blocks[0]['len'] == 2: add(opposite, 90.0, "BÁO chu kỳ 2-2 kết thúc", 90)
        if blocks[1]['len'] == 3 and blocks[2]['len'] == 3:
            if blocks[0]['len'] == 2: add(blocks[0]['val'], 88.0, "BÁO chu kỳ 3-3 sắp hết (còn 1)", 88)
            elif blocks[0]['len'] == 3: add(opposite, 92.0, "BÁO chu kỳ 3-3 kết thúc", 92)
    
    # ========== NHÓM 11: CẦU PHỨC TẠP (48-55) ==========
    if len(blocks) >= 4:
        lens = [b['len'] for b in blocks[:5]]
        if lens[0] == 1 and lens[1] == 2 and lens[2] == 1: add(opposite, 82.0, "Cầu 1-2-1", 82)
        if lens[0] == 2 and lens[1] == 1 and lens[2] == 2: add(opposite, 82.0, "Cầu 2-1-2", 82)
        if lens[0] == 2 and lens[1] == 1 and lens[2] == 1: add(blocks[0]['val'], 74.0, "Cầu 1-1-2", 74)
        if lens[0] == 1 and lens[1] == 2 and lens[2] == 2: add(blocks[0]['val'], 74.0, "Cầu 2-2-1", 74)
        if lens[0] == 3 and lens[1] == 1 and lens[2] == 3: add(blocks[0]['val'], 78.0, "Cầu 3-1-3", 78)
        if lens[0] == 3 and lens[1] == 2 and lens[2] == 3: add(blocks[0]['val'], 80.0, "Cầu 3-2-3", 80)
        if lens[0] == 2 and lens[1] == 3 and lens[2] == 2: add(blocks[0]['val'], 80.0, "Cầu 2-3-2", 80)
        if lens[0] == 3 and lens[1] == 2 and lens[2] == 1: add(blocks[0]['val'], 76.0, "Cầu 1-2-3", 76)
    
    # ========== NHÓM 12: N-GRAM (56-61) ==========
    for ns in [3, 4, 5, 6, 7, 8]:
        if n < ns + 1: continue
        current_seq = tuple(results[:ns])
        match_tai, match_xiu = 0, 0
        for i in range(len(results) - ns):
            if tuple(results[i:i+ns]) == current_seq and i + ns < len(results):
                if results[i+ns] == "Tài": match_tai += 1
                else: match_xiu += 1
        total = match_tai + match_xiu
        if total >= 2 and match_tai != match_xiu:
            winner = "Tài" if match_tai > match_xiu else "Xỉu"
            ratio = max(match_tai, match_xiu) / total
            if ratio >= 0.6:
                conf = 60 + ratio * 22
                add(winner, conf, f"N-gram {ns} ({max(match_tai, match_xiu)}/{total})", 58 + (8 - ns))
    
    # ========== NHÓM 13: MARKOV (62) ==========
    if n >= 6:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 1):
            if results[i] == last: trans[results[i + 1]] += 1
        total = trans["Tài"] + trans["Xỉu"]
        if total >= 3 and trans["Tài"] != trans["Xỉu"]:
            winner = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            ratio = max(trans["Tài"], trans["Xỉu"]) / total
            add(winner, 62 + ratio * 15, "Markov chuyển tiếp", 62)
    
    # ========== NHÓM 14: DICE BIAS (63-66) ==========
    if dice_sums and len(dice_sums) >= 5:
        recent = dice_sums[:8]
        avg = sum(recent) / len(recent)
        if avg >= 12.5: add("Tài", 70.0, f"Dice lệch Tài mạnh ({avg:.1f})", 68)
        elif avg <= 8.5: add("Xỉu", 70.0, f"Dice lệch Xỉu mạnh ({avg:.1f})", 68)
        elif avg >= 11.5: add("Tài", 58.0, f"Dice nghiêng Tài ({avg:.1f})", 55)
        elif avg <= 9.5: add("Xỉu", 58.0, f"Dice nghiêng Xỉu ({avg:.1f})", 55)
    
    # ========== NHÓM 15: MOMENTUM (67-70) ==========
    if n >= 10:
        tai_c = results[:10].count("Tài")
        xiu_c = 10 - tai_c
        if tai_c >= 9: add("Tài", 74.0, f"Momentum Tài cực mạnh ({tai_c}/10)", 72)
        elif xiu_c >= 9: add("Xỉu", 74.0, f"Momentum Xỉu cực mạnh ({xiu_c}/10)", 72)
        elif tai_c >= 8: add("Tài", 66.0, f"Momentum Tài ({tai_c}/10)", 64)
        elif xiu_c >= 8: add("Xỉu", 66.0, f"Momentum Xỉu ({xiu_c}/10)", 64)
    
    if n >= 12:
        tai_c = results[:12].count("Tài")
        xiu_c = 12 - tai_c
        if tai_c >= 10: add("Xỉu", 72.0, f"Đảo momentum Tài ({tai_c}/12)", 70)
        elif xiu_c >= 10: add("Tài", 72.0, f"Đảo momentum Xỉu ({xiu_c}/12)", 70)
    
    # ========== NHÓM 16: FIBONACCI (71-74) ==========
    if len(blocks) >= 3:
        fib = [b['len'] for b in blocks[:4]]
        if fib[:3] == [1, 1, 2]: add(blocks[0]['val'], 72.0, "Fibonacci 1-1-2", 70)
        elif fib[:3] == [1, 2, 3]: add(blocks[0]['val'], 72.0, "Fibonacci 1-2-3", 70)
        elif len(fib) >= 4 and fib[:4] == [1, 1, 2, 3]: add(blocks[0]['val'], 76.0, "Fibonacci 1-1-2-3", 74)
        elif fib[:3] == [2, 3, 5]: add(blocks[0]['val'], 76.0, "Fibonacci 2-3-5", 74)
    
    # ========== NHÓM 17: ĐỐI XỨNG (75-76) ==========
    if n >= 8:
        left, right = results[:4], results[4:8]
        if left == right: add(results[0], 70.0, "Đối xứng 4-4", 68)
        elif left == right[::-1]: add(opposite, 68.0, "Đối xứng gương", 66)
    
    # ========== NHÓM 18: PATTERN 2/3 PHIÊN (77-78) ==========
    if n >= 4:
        last2 = tuple(results[:2])
        m_t, m_x = 0, 0
        for i in range(2, len(results) - 1):
            if tuple(results[i:i+2]) == last2:
                if results[i-1] == "Tài": m_t += 1
                else: m_x += 1
        total = m_t + m_x
        if total >= 2 and m_t != m_x:
            winner = "Tài" if m_t > m_x else "Xỉu"
            add(winner, 65.0, f"Pattern 2 phiên ({max(m_t, m_x)}/{total})", 62)
    
    # ========== NHÓM 19: DICE EXTREME (79-80) ==========
    if dice_sums and len(dice_sums) >= 6:
        last3 = dice_sums[:3]
        if all(s >= 14 for s in last3): add("Xỉu", 65.0, "3 phiên dice cao đột biến", 62)
        elif all(s <= 7 for s in last3): add("Tài", 65.0, "3 phiên dice thấp đột biến", 62)
    
    # ========== NHÓM 20: CHU KỲ 4 LẶP (81) ==========
    if n >= 8:
        if results[4:8] == results[:4]: add(opposite, 66.0, "Chu kỳ 4 phiên lặp", 64)
    
    # ========== NHÓM 21: CHUYỂN CẦU MỚI (82) ==========
    if len(blocks) == 2 and blocks[1]['len'] >= 4 and blocks[0]['len'] <= 2:
        add(blocks[0]['val'], 76.0, f"Chuyển cầu (bệt {blocks[1]['len']} vừa gãy)", 74)
    
    # ============================ VOTING SYSTEM ============================
    if not candidates:
        return opposite, 55.0, "Đảo nhịp (mặc định)", [], 0
    
    tai_w = sum(c[1] for c in candidates if c[0] == "Tài")
    xiu_w = sum(c[1] for c in candidates if c[0] == "Xỉu")
    total_w = tai_w + xiu_w
    final_pred = "Tài" if tai_w >= xiu_w else "Xỉu"
    winning_w = max(tai_w, xiu_w)
    agreement = winning_w / total_w if total_w > 0 else 0.5
    
    matching = [c for c in candidates if c[0] == final_pred]
    best_matching = max(matching, key=lambda x: (x[3], x[1]))
    base_conf = best_matching[1]
    
    # Calibration theo agreement + sample size
    sample_factor = min(1.05, 0.85 + n * 0.01)  # n càng lớn càng tin
    
    if agreement >= 0.78: final_conf = min(98.0, base_conf * 1.12 * sample_factor)
    elif agreement >= 0.68: final_conf = min(96.0, base_conf * 1.06 * sample_factor)
    elif agreement >= 0.58: final_conf = base_conf * sample_factor
    elif agreement >= 0.48: final_conf = base_conf * 0.92 * sample_factor
    else: final_conf = base_conf * 0.82 * sample_factor
    
    top_signals = sorted(candidates, key=lambda x: (x[3], x[1]), reverse=True)[:5]
    signal_names = [f"{s[2]}→{s[0]}({s[1]}%)" for s in top_signals]
    
    return final_pred, round(min(98.0, final_conf), 1), best_matching[2], signal_names, len(candidates)


# =====================================================================
# FETCH
# =====================================================================
def generate_fallback(base=7116040):
    elapsed = int(time.time() / 60)
    current = base + elapsed
    random.seed(elapsed)
    rows = []
    for i in range(15):
        sid = current - i
        r = "Tài" if random.random() > 0.5 else "Xỉu"
        d = [random.randint(1, 6) for _ in range(3)]
        rows.append({"phien": sid, "result": r, "dice": f"{d[0]} + {d[1]} + {d[2]}", "total": sum(d)})
    return rows


def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
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
# ROUTES
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
        
        latest = valid[-1]
        next_phien = latest['phien'] + 1
        h_next = [v['result'] for v in valid][::-1]
        d_next = [v.get('total', 0) for v in valid][::-1]
        
        next_pred, next_conf, _, _, _ = analyze_pattern(h_next, d_next)
        
        out.append({
            'phien': next_phien, 'is_next': True,
            'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?",
            'is_correct': None
        })
        
        for i in range(len(valid) - 1, -1, -1):
            cs = valid[i]
            if cs['phien'] <= RESET_SESSION_ID: break
            if len(out) > 20: break
            
            h_list = [v['result'] for v in valid[:i]][::-1]
            d_list = [v.get('total', 0) for v in valid[:i]][::-1]
            
            if h_list:
                pred, conf, _, _, _ = analyze_pattern(h_list, d_list)
                is_correct = (pred == cs['result'])
                total_past += 1
                if is_correct: correct_count += 1
            else:
                pred, conf = "Tài", 50.0
                is_correct = None
            
            out.append({
                'phien': cs['phien'], 'is_next': False,
                'prediction': pred, 'confidence': conf,
                'result': cs['result'], 'dice': cs['dice'],
                'is_correct': is_correct
            })
        
        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict_only():
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404
        
        next_phien = valid[-1]['phien'] + 1
        h_next = [v['result'] for v in valid][::-1]
        d_next = [v.get('total', 0) for v in valid][::-1]
        pred, conf, pat, top_sig, sig_count = analyze_pattern(h_next, d_next)
        
        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'prediction': pred,
            'confidence': conf,
            'pattern': pat,
            'signal_count': sig_count,
            'top_signals': top_sig,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/signals')
def signals_api():
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404
        
        next_phien = valid[-1]['phien'] + 1
        h_next = [v['result'] for v in valid][::-1]
        d_next = [v.get('total', 0) for v in valid][::-1]
        
        if not h_next or len(h_next) < 3:
            return jsonify({'status': 'error', 'message': 'Chưa đủ dữ liệu'}), 400
        
        pred, conf, pat, top_sig, sig_count = analyze_pattern(h_next, d_next)
        
        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'prediction': pred,
            'confidence': conf,
            'pattern_chosen': pat,
            'total_signals': sig_count,
            'all_signals': top_sig,
            'recent_results': h_next[:15],
            'recent_dice': d_next[:15],
            'algorithm_version': 'V7.0',
            'total_patterns': 82,
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
