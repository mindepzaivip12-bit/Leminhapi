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
# GIAO DIỆN HTML PREMIUM V6.1 - SỐNG ĐỘNG
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LC MD5 MINHLE ⚡ Premium </title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #030512; --bg-deep: #060a1c; --bg-card: rgba(13, 20, 36, 0.72);
        --bg-card-hover: rgba(19, 28, 48, 0.9);
        --text-main: #f8fafc; --text-muted: #64748b;
        --border-color: rgba(30, 41, 59, 0.85);
        --tai-bg: linear-gradient(135deg, #0ea5e9, #0284c7); 
        --xiu-bg: linear-gradient(135deg, #ec4899, #be185d);
        --blue-main: #38bdf8; --blue-glow: rgba(56, 189, 248, 0.65);
        --cyan: #22d3ee; --purple: #a78bfa; --pink: #f472b6; --gold: #fbbf24;
        --lose-color: #ef4444; --win-color: #38bdf8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    html, body { height: 100%; }
    
    @keyframes bgFloat { 0%,100%{transform:translateY(0) translateX(0)} 50%{transform:translateY(-40px) translateX(30px)} }
    @keyframes bgFloat2 { 0%,100%{transform:translateY(0) translateX(0)} 50%{transform:translateY(30px) translateX(-35px)} }
    @keyframes bgFloat3 { 0%,100%{transform:translateY(0) scale(1)} 50%{transform:translateY(-25px) scale(1.3)} }
    @keyframes orbA { 0%,100%{transform:translate(0,0) scale(1); opacity: 0.5} 50%{transform:translate(60px,-80px) scale(1.15); opacity: 0.8} }
    @keyframes orbB { 0%,100%{transform:translate(0,0) scale(1); opacity: 0.4} 50%{transform:translate(-70px,60px) scale(1.2); opacity: 0.75} }
    @keyframes orbC { 0%,100%{transform:translate(0,0) scale(1); opacity: 0.35} 50%{transform:translate(40px,50px) scale(1.1); opacity: 0.7} }
    
    @keyframes rainbow-border { 0%{border-color:#38bdf8;box-shadow:0 0 25px rgba(56,189,248,0.65),inset 0 0 25px rgba(56,189,248,0.1)} 
        33%{border-color:#a78bfa;box-shadow:0 0 25px rgba(167,139,250,0.65),inset 0 0 25px rgba(167,139,250,0.1)}
        66%{border-color:#f472b6;box-shadow:0 0 25px rgba(244,114,182,0.65),inset 0 0 25px rgba(244,114,182,0.1)}
        100%{border-color:#38bdf8;box-shadow:0 0 25px rgba(56,189,248,0.65),inset 0 0 25px rgba(56,189,248,0.1)} }
    
    @keyframes textGlow { 0%,100%{text-shadow:0 0 8px var(--blue-glow),0 0 20px rgba(56,189,248,0.4)} 50%{text-shadow:0 0 20px var(--blue-main),0 0 40px rgba(56,189,248,0.6)} }
    @keyframes titleShine { 0%{background-position:-200% center} 100%{background-position:200% center} }
    @keyframes spin { to{transform:rotate(360deg)} }
    @keyframes slideIn { from{opacity:0;transform:translateY(24px) scale(0.94)} to{opacity:1;transform:translateY(0) scale(1)} }
    @keyframes shimmerBar { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
    @keyframes statPulse { 0%,100%{text-shadow:0 0 10px var(--blue-glow)} 50%{text-shadow:0 0 25px var(--blue-main),0 0 40px var(--blue-glow)} }
    @keyframes dotPulse { 0%,100%{box-shadow:0 0 0 0 rgba(56,189,248,0.75)} 70%{box-shadow:0 0 0 14px rgba(56,189,248,0)} }
    @keyframes ripple { 0%{transform:scale(0);opacity:0.7} 100%{transform:scale(4);opacity:0} }
    @keyframes breathe { 0%,100%{opacity:0.6;transform:scale(1)} 50%{opacity:1;transform:scale(1.05)} }
    @keyframes wave { 0%{transform:translateX(-100%)} 100%{transform:translateX(100%)} }
    @keyframes diceRoll { 0%{transform:rotate(0) scale(1)} 50%{transform:rotate(180deg) scale(1.15)} 100%{transform:rotate(360deg) scale(1)} }
    @keyframes fadeInUp { from{opacity:0;transform:translateY(30px)} to{opacity:1;transform:translateY(0)} }
    @keyframes borderFlow { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
    @keyframes iconFloat { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }
    
    body {
        background: var(--bg-dark);
        color: var(--text-main);
        padding-bottom: 40px;
        min-height: 100vh;
        overflow-x: hidden;
        position: relative;
        background-image: 
            radial-gradient(circle at 20% 0%, rgba(56,189,248,0.12) 0%, transparent 45%),
            radial-gradient(circle at 80% 30%, rgba(167,139,250,0.10) 0%, transparent 45%),
            radial-gradient(circle at 50% 100%, rgba(244,114,182,0.08) 0%, transparent 50%),
            linear-gradient(180deg, #030512 0%, #060a1c 100%);
    }
    
    /* Floating orbs background */
    .bg-orbs { position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
    .bg-orbs::before, .bg-orbs::after {
        content: ''; position: absolute; border-radius: 50%; filter: blur(80px);
    }
    .bg-orbs::before {
        width: 350px; height: 350px; top: -100px; left: -80px;
        background: radial-gradient(circle, rgba(56,189,248,0.35), transparent 70%);
        animation: orbA 18s ease-in-out infinite;
    }
    .bg-orbs::after {
        width: 400px; height: 400px; bottom: -120px; right: -100px;
        background: radial-gradient(circle, rgba(167,139,250,0.3), transparent 70%);
        animation: orbB 22s ease-in-out infinite;
    }
    .bg-orb-c {
        position: fixed; width: 280px; height: 280px; top: 40%; left: 50%;
        background: radial-gradient(circle, rgba(244,114,182,0.22), transparent 70%);
        filter: blur(80px); border-radius: 50%;
        animation: orbC 25s ease-in-out infinite; pointer-events: none; z-index: 0;
    }
    /* Stars twinkling */
    .stars { position: fixed; inset: 0; pointer-events: none; z-index: 0; }
    .stars::before {
        content: ''; position: absolute; inset: 0;
        background-image: 
            radial-gradient(1.5px 1.5px at 15% 20%, rgba(56,189,248,0.7), transparent 60%),
            radial-gradient(1px 1px at 85% 60%, rgba(167,139,250,0.6), transparent 60%),
            radial-gradient(1.5px 1.5px at 45% 85%, rgba(34,211,238,0.7), transparent 60%),
            radial-gradient(1px 1px at 70% 15%, rgba(244,114,182,0.55), transparent 60%),
            radial-gradient(2px 2px at 25% 70%, rgba(56,189,248,0.5), transparent 60%),
            radial-gradient(1.5px 1.5px at 60% 45%, rgba(251,191,36,0.5), transparent 60%);
        animation: bgFloat 20s ease-in-out infinite;
    }
    .stars::after {
        content: ''; position: absolute; inset: 0;
        background-image: 
            radial-gradient(1px 1px at 10% 50%, rgba(56,189,248,0.5), transparent 60%),
            radial-gradient(1px 1px at 90% 30%, rgba(167,139,250,0.5), transparent 60%),
            radial-gradient(1.5px 1.5px at 55% 90%, rgba(244,114,182,0.5), transparent 60%),
            radial-gradient(1.5px 1.5px at 35% 10%, rgba(56,189,248,0.55), transparent 60%);
        animation: bgFloat2 25s ease-in-out infinite;
    }
    
    /* HEADER */
    .header {
        display: flex; justify-content: space-between; align-items: center;
        padding: 15px 20px;
        border-bottom: 1px solid var(--border-color);
        background: linear-gradient(180deg, rgba(6,9,25,0.92), rgba(6,9,25,0.7));
        backdrop-filter: blur(20px);
        position: sticky; top: 0; z-index: 100;
        box-shadow: 0 4px 30px rgba(56,189,248,0.08);
    }
    .header-left { display: flex; align-items: center; gap: 11px; }
    .header-live-dot {
        width: 11px; height: 11px; border-radius: 50%;
        background: radial-gradient(circle, #7dd3fc, #38bdf8);
        animation: dotPulse 1.8s infinite;
        box-shadow: 0 0 12px var(--blue-main);
    }
    .header-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 19px; font-weight: 900; letter-spacing: 0.5px;
        background: linear-gradient(90deg, #7dd3fc, #38bdf8, #a78bfa, #f472b6, #38bdf8, #7dd3fc);
        background-size: 300% auto;
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
        animation: titleShine 5s linear infinite, textGlow 3s infinite;
    }
    .btn-reset {
        position: relative; overflow: hidden;
        background: rgba(239, 68, 68, 0.12);
        color: var(--lose-color);
        border: 1px solid var(--lose-color);
        padding: 8px 18px; border-radius: 10px;
        font-weight: 700; font-size: 13px; cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 0 15px rgba(239,68,68,0.15);
    }
    .btn-reset:hover {
        background: var(--lose-color); color: #fff;
        box-shadow: 0 0 25px rgba(239,68,68,0.65), inset 0 0 15px rgba(255,255,255,0.2);
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
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 12px 10px; text-align: center;
        position: relative; overflow: hidden;
        backdrop-filter: blur(14px);
        transition: all 0.35s ease;
    }
    .stat-item:hover {
        border-color: rgba(56,189,248,0.55);
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(56,189,248,0.15);
    }
    .stat-item::before {
        content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
        background: linear-gradient(90deg, transparent, var(--blue-main), var(--purple), transparent);
        background-size: 200% 100%;
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
        animation: statPulse 2.5s infinite;
    }
    .stat-value.win {
        background: linear-gradient(135deg, #38bdf8, #22d3ee);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
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
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 15px 17px;
        display: flex; justify-content: space-between; align-items: center;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative; overflow: hidden;
        animation: slideIn 0.5s ease-out backwards;
        backdrop-filter: blur(14px);
    }
    .card-item::before {
        content: ''; position: absolute;
        left: 0; top: 0; bottom: 0; width: 3px;
        background: linear-gradient(180deg, transparent, var(--blue-main), var(--purple), transparent);
        opacity: 0; transition: opacity 0.35s;
    }
    .card-item:hover {
        background: var(--bg-card-hover);
        transform: translateY(-3px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.4), 0 0 20px rgba(56,189,248,0.1);
        border-color: rgba(56,189,248,0.4);
    }
    .card-item:hover::before { opacity: 1; }
    
    .card-item.active {
        background: linear-gradient(145deg, rgba(13,20,36,0.95), rgba(15,26,46,0.95));
        animation: slideIn 0.5s ease-out backwards, rainbow-border 3.5s linear infinite;
        border-width: 1.5px;
        position: relative;
    }
    .card-item.active::after {
        content: '';
        position: absolute; top: 12px; right: 14px;
        width: 9px; height: 9px; border-radius: 50%;
        background: radial-gradient(circle, #7dd3fc, #38bdf8);
        box-shadow: 0 0 12px var(--blue-main);
        animation: dotPulse 1.5s infinite;
    }
    .card-item.active .id-text {
        background: linear-gradient(90deg, #fff, #7dd3fc, #a78bfa, #fff);
        background-size: 200% auto;
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        animation: titleShine 3s linear infinite;
    }
    
    /* COLUMNS */
    .col-left { display: flex; flex-direction: column; gap: 6px; flex: 1.2; }
    .id-text {
        font-family: 'Orbitron', sans-serif;
        font-size: 16px; font-weight: 800; color: #fff;
        letter-spacing: 0.4px;
        background: linear-gradient(90deg, #fff, #7dd3fc);
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
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25), transparent);
        animation: wave 2.5s infinite;
    }
    .bet-tai {
        background: rgba(2, 132, 199, 0.22); color: #7dd3fc;
        border: 1px solid rgba(56,189,248,0.5);
        box-shadow: 0 0 12px rgba(56,189,248,0.2);
    }
    .bet-xiu {
        background: rgba(219, 39, 119, 0.22); color: #f9a8d4;
        border: 1px solid rgba(244,114,182,0.5);
        box-shadow: 0 0 12px rgba(244,114,182,0.2);
    }
    .conf-text {
        color: var(--text-muted); font-size: 10.5px;
        font-style: italic; font-weight: 500;
    }
    .conf-text b {
        color: var(--cyan); font-weight: 800; font-style: normal;
        font-size: 12px;
    }
    .conf-bar-wrap {
        height: 4px; background: rgba(56,189,248,0.12);
        border-radius: 3px; overflow: hidden; margin-top: 4px;
        position: relative;
    }
    .conf-bar {
        height: 100%; border-radius: 3px;
        background: linear-gradient(90deg, #38bdf8, #22d3ee, #a78bfa, #f472b6, #38bdf8);
        background-size: 300% 100%;
        animation: shimmerBar 2s linear infinite;
        transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 0 8px var(--blue-glow);
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
        background: var(--tai-bg); color: #fff;
        box-shadow: 0 0 18px rgba(2,132,199,0.7), inset 0 0 10px rgba(255,255,255,0.15);
    }
    .pred-xiu {
        background: var(--xiu-bg); color: #fff;
        box-shadow: 0 0 18px rgba(219,39,119,0.7), inset 0 0 10px rgba(255,255,255,0.15);
    }
    .pred-empty {
        background: transparent;
        border: 1px dashed var(--border-color);
        color: var(--text-muted);
    }
    .pred-empty::before { display: none; }
    .dice-text {
        font-family: 'Orbitron', sans-serif;
        font-size: 13px; font-weight: 700;
        color: #cbd5e1; white-space: nowrap;
        letter-spacing: 0.5px;
    }
    .card-item.active .dice-text {
        color: var(--cyan);
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
    .status-win {
        color: var(--win-color);
        text-shadow: 0 0 14px var(--blue-glow);
        animation: statPulse 2s infinite;
    }
    .status-lose { color: var(--lose-color); }
    .status-wait { color: var(--blue-main); }
    .spin { display: inline-block; animation: spin 2s linear infinite; }
    
    .loading {
        text-align: center; padding: 55px;
        color: var(--blue-main); font-weight: 700;
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
<div class="bg-orbs"></div>
<div class="bg-orb-c"></div>
<div class="stars"></div>

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
            '<div class="loading" style="color:var(--lose-color)">⚠ Lỗi kết nối Server</div>';
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
        let betBadge = `<span class="bet-badge" style="background:rgba(100,116,139,0.15);color:#94a3b8;border:1px solid rgba(100,116,139,0.3)">CƯỢC -</span>`;
        
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
        if (row.is_next) {
            statusHtml = `<div class="status-text status-wait">Chờ <span class="spin"></span></div>`;
        } else if (row.is_correct === true) {
            statusHtml = `<div class="status-text status-win">Đúng Cửa ✅</div>`;
        } else if (row.is_correct === false) {
            statusHtml = `<div class="status-text status-lose">Sai Cửa❌</div>`;
        } else {
            statusHtml = `<div class="status-text" style="color:var(--text-muted)">-</div>`;
        }
        
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
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#38bdf8',
        cancelButtonColor: '#1e293b',
        confirmButtonText: 'Đồng ý',
        cancelButtonText: 'Hủy',
        background: '#0d1424',
        color: '#f1f5f9'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ 
                title: 'Đang Reset...', 
                allowOutsideClick: false, 
                didOpen: () => Swal.showLoading(),
                background: '#0d1424', color: '#f1f5f9'
            });
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ 
                        title: 'Thành công!', 
                        text: 'Đã chốt mốc #' + data.reset_to, 
                        icon: 'success', 
                        confirmButtonColor: '#38bdf8',
                        background: '#0d1424', color: '#f1f5f9'
                    });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire({
                    title: 'Lỗi!', text: error.message, icon: 'error',
                    background: '#0d1424', color: '#f1f5f9'
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
# THUẬT TOÁN V6.1 - 46 MẪU CẦU (ẨN KHỎI UI, VẪN TRẢ VỀ API)
# =====================================================================
def analyze_pattern(results, dice_sums=None):
    """
    Trả về: (prediction, confidence, pattern_name, top_signals, signal_count)
    - Đầy đủ 46 mẫu: đảo / bệt / chu kỳ / ngram / markov / dice / momentum /
      fibonacci / symmetry / pattern / extreme / chuyển cầu
    - Voting đa tầng với agreement boost
    """
    if not results or len(results) < 3:
        return "Tài", 50.0, "Khởi tạo", [], 0
    
    n = len(results)
    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    candidates = []
    
    def add(pred, conf, name, priority):
        candidates.append((pred, round(conf, 1), name, priority))
    
    # ---- BLOCKS ----
    blocks = []
    curr_val, curr_count = results[0], 1
    for r in results[1:]:
        if r == curr_val:
            curr_count += 1
        else:
            blocks.append({'val': curr_val, 'len': curr_count})
            curr_val, curr_count = r, 1
    blocks.append({'val': curr_val, 'len': curr_count})
    
    # ============ 1-8: CẦU BỆT ============
    streak = blocks[0]['len']
    if streak == 2: add(last, 52.0, "Bám bệt 2", 52)
    elif streak == 3: add(last, 56.0, "Bám bệt 3", 56)
    elif streak == 4: add(last, 62.0, "Bám bệt 4", 62)
    elif streak == 5: add(opposite, 68.0, "Bẻ bệt 5", 68)
    elif streak == 6: add(opposite, 76.0, "Bẻ bệt 6", 76)
    elif streak == 7: add(opposite, 82.0, "Bẻ bệt 7", 82)
    elif streak == 8: add(opposite, 85.0, "Bẻ bệt 8", 85)
    elif streak >= 9: add(opposite, min(95.0, 88.0 + streak - 9), f"Bẻ bệt siêu mạnh {streak}", 90)
    
    # ============ 9-12: ĐẢO 1-1 ============
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]: alt_len += 1
        else: break
    
    if 3 <= alt_len <= 4: add(opposite, 62.0, f"Đảo 1-1 ({alt_len})", 62)
    elif 5 <= alt_len <= 6: add(opposite, 72.0, f"Đảo 1-1 ({alt_len})", 72)
    elif 7 <= alt_len <= 8: add(opposite, 82.0, f"Đảo 1-1 dài ({alt_len})", 82)
    elif alt_len >= 9: add(opposite, 90.0, f"Đảo 1-1 siêu dài ({alt_len})", 90)
    
    # ============ 13-18: CHU KỲ 2-2 / 3-3 / 4-4 ============
    if len(blocks) >= 3:
        is_alt = True
        for i in range(1, min(len(blocks), 6)):
            if blocks[i]['val'] == blocks[i-1]['val']:
                is_alt = False; break
        
        if is_alt:
            if blocks[1]['len'] == 2 and blocks[2]['len'] == 2:
                curr = blocks[0]['len']
                if curr < 2: add(blocks[0]['val'], 88.0, "Bám cầu 2-2 (dở)", 88)
                elif curr == 2: add(opposite, 92.0, "Bẻ cầu 2-2", 92)
            if blocks[1]['len'] == 3 and blocks[2]['len'] == 3:
                curr = blocks[0]['len']
                if curr < 3: add(blocks[0]['val'], 90.0, "Bám cầu 3-3 (dở)", 90)
                elif curr == 3: add(opposite, 94.0, "Bẻ cầu 3-3", 94)
            if blocks[1]['len'] == 4 and blocks[2]['len'] == 4:
                curr = blocks[0]['len']
                if curr < 4: add(blocks[0]['val'], 92.0, "Bám cầu 4-4 (dở)", 92)
                elif curr == 4: add(opposite, 95.0, "Bẻ cầu 4-4", 95)
    
    # ============ 19-24: CẦU PHỨC TẠP ============
    if len(blocks) >= 4:
        lens = [b['len'] for b in blocks[:5]]
        if lens[0] == 1 and lens[1] == 2 and lens[2] == 1: add(opposite, 82.0, "Cầu 1-2-1", 82)
        if lens[0] == 2 and lens[1] == 1 and lens[2] == 2: add(opposite, 82.0, "Cầu 2-1-2", 82)
        if lens[0] == 2 and lens[1] == 1 and lens[2] == 1: add(blocks[0]['val'], 74.0, "Cầu 1-1-2", 74)
        if lens[0] == 1 and lens[1] == 2 and lens[2] == 2: add(blocks[0]['val'], 74.0, "Cầu 2-2-1", 74)
        if lens[0] == 3 and lens[1] == 1 and lens[2] == 3: add(blocks[0]['val'], 78.0, "Cầu 3-1-3", 78)
        if lens[0] == 3 and lens[1] == 2 and lens[2] == 1: add(blocks[0]['val'], 76.0, "Cầu 1-2-3", 76)
    
    # ============ 25-29: N-GRAM ============
    for ns in [3, 4, 5, 6, 7]:
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
                add(winner, conf, f"N-gram {ns} ({max(match_tai, match_xiu)}/{total})", 60 + (8 - ns))
    
    # ============ 30: MARKOV ============
    if n >= 6:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 1):
            if results[i] == last: trans[results[i + 1]] += 1
        total = trans["Tài"] + trans["Xỉu"]
        if total >= 3 and trans["Tài"] != trans["Xỉu"]:
            winner = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            ratio = max(trans["Tài"], trans["Xỉu"]) / total
            add(winner, 62 + ratio * 15, "Markov chuyển tiếp", 65)
    
    # ============ 31-34: DICE BIAS ============
    if dice_sums and len(dice_sums) >= 5:
        recent = dice_sums[:8]
        avg = sum(recent) / len(recent)
        if avg >= 12.5: add("Tài", 68.0, f"Xúc xắc lệch Tài mạnh ({avg:.1f})", 66)
        elif avg <= 8.5: add("Xỉu", 68.0, f"Xúc xắc lệch Xỉu mạnh ({avg:.1f})", 66)
        elif avg >= 11.5: add("Tài", 58.0, f"Xúc xắc nghiêng Tài ({avg:.1f})", 55)
        elif avg <= 9.5: add("Xỉu", 58.0, f"Xúc xắc nghiêng Xỉu ({avg:.1f})", 55)
    
    # ============ 35-37: MOMENTUM ============
    if n >= 10:
        tai_count = results[:10].count("Tài")
        xiu_count = 10 - tai_count
        if tai_count >= 8: add("Tài", 68.0, f"Momentum Tài ({tai_count}/10)", 66)
        elif xiu_count >= 8: add("Xỉu", 68.0, f"Momentum Xỉu ({xiu_count}/10)", 66)
        elif tai_count >= 7: add("Tài", 60.0, f"Xu hướng Tài ({tai_count}/10)", 58)
        elif xiu_count >= 7: add("Xỉu", 60.0, f"Xu hướng Xỉu ({xiu_count}/10)", 58)
    
    if n >= 12:
        tai_c = results[:12].count("Tài")
        xiu_c = 12 - tai_c
        if tai_c >= 10: add("Xỉu", 70.0, f"Đảo xu hướng Tài ({tai_c}/12)", 68)
        elif xiu_c >= 10: add("Tài", 70.0, f"Đảo xu hướng Xỉu ({xiu_c}/12)", 68)
    
    # ============ 38-40: FIBONACCI ============
    if len(blocks) >= 3:
        fib = [b['len'] for b in blocks[:4]]
        if fib[:3] == [1, 1, 2]: add(blocks[0]['val'], 72.0, "Fibonacci 1-1-2", 70)
        elif fib[:3] == [1, 2, 3]: add(blocks[0]['val'], 72.0, "Fibonacci 1-2-3", 70)
        elif len(fib) >= 4 and fib[:4] == [1, 1, 2, 3]: add(blocks[0]['val'], 76.0, "Fibonacci 1-1-2-3", 74)
    
    # ============ 41-42: ĐỐI XỨNG ============
    if n >= 8:
        left, right = results[:4], results[4:8]
        if left == right: add(results[0], 70.0, "Đối xứng 4-4", 68)
        elif left == right[::-1]: add(opposite, 68.0, "Đối xứng gương", 66)
    
    # ============ 43: PATTERN 2 PHIÊN ============
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
    
    # ============ 44: DICE EXTREME ============
    if dice_sums and len(dice_sums) >= 6:
        last3 = dice_sums[:3]
        if all(s >= 14 for s in last3): add("Xỉu", 62.0, "3 phiên Tài cao đột biến", 60)
        elif all(s <= 7 for s in last3): add("Tài", 62.0, "3 phiên Xỉu thấp đột biến", 60)
    
    # ============ 45: CHU KỲ 4 LẶP ============
    if n >= 8:
        if results[4:8] == results[:4]: add(opposite, 66.0, "Chu kỳ 4 phiên lặp", 64)
    
    # ============ 46: CHUYỂN CẦU MỚI ============
    if len(blocks) == 2 and blocks[1]['len'] >= 4 and blocks[0]['len'] <= 2:
        add(blocks[0]['val'], 74.0, f"Chuyển cầu mới (bệt {blocks[1]['len']} vừa gãy)", 72)
    
    # ============ VOTING ============
    if not candidates:
        return opposite, 55.0, "Đảo nhịp (mặc định)", [], 0
    
    tai_w = sum(c[1] for c in candidates if c[0] == "Tài")
    xiu_w = sum(c[1] for c in candidates if c[0] == "Xỉu")
    total_w = tai_w + xiu_w
    final_pred = "Tài" if tai_w >= xiu_w else "Xỉu"
    win_w = max(tai_w, xiu_w)
    agreement = win_w / total_w if total_w > 0 else 0.5
    
    matching = [c for c in candidates if c[0] == final_pred]
    best_matching = max(matching, key=lambda x: (x[3], x[1]))
    base_conf = best_matching[1]
    
    if agreement >= 0.75: final_conf = min(98.0, base_conf * 1.10)
    elif agreement >= 0.65: final_conf = min(96.0, base_conf * 1.05)
    elif agreement >= 0.55: final_conf = base_conf
    elif agreement >= 0.45: final_conf = base_conf * 0.92
    else: final_conf = base_conf * 0.85
    
    top_signals = sorted(candidates, key=lambda x: (x[3], x[1]), reverse=True)[:5]
    signal_names = [f"{s[2]}→{s[0]}({s[1]}%)" for s in top_signals]
    
    return final_pred, round(final_conf, 1), best_matching[2], signal_names, len(candidates)


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
        
        next_pred, next_conf, next_pat, _, _ = analyze_pattern(h_next, d_next)
        
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
    """API dự đoán nhanh phiên tiếp theo"""
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
    """API chi tiết tất cả tín hiệu (debug/analysis)"""
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
            'algorithm_version': 'V6.1',
            'total_patterns': 46,
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
