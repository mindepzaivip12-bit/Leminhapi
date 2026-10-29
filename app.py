import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =====================================================================
# CẤU HÌNH API (Cập nhật Token mới nếu bị lỗi)
# =====================================================================
API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
RESET_SESSION_ID = 0

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LC MD5 </title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-body: linear-gradient(180deg, #f0f9ff 0%, #e0f2fe 45%, #f8fafc 100%);
        --bg-card: #ffffff;
        --bg-card-hover: #f8fbff;
        --bg-subtle: #f1f5f9;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --text-soft: #94a3b8;
        --border-color: #e2e8f0;
        --border-blue: #bae6fd;
        --border-blue-strong: #7dd3fc;
        --tai-solid: #0284c7;
        --tai-bg: #e0f2fe;
        --tai-text: #0369a1;
        --xiu-solid: #e11d48;
        --xiu-bg: #ffe4e6;
        --xiu-text: #be123c;
        --accent: #0ea5e9;
        --accent-soft: #38bdf8;
        --accent-glow: rgba(14, 165, 233, 0.25);
        --win: #10b981;
        --win-bg: #d1fae5;
        --lose: #ef4444;
        --lose-bg: #fee2e2;
        --gold: #f59e0b;
        --gold-bg: #fef3c7;
        --shadow-sm: 0 2px 8px rgba(14, 165, 233, 0.06);
        --shadow-md: 0 4px 16px rgba(14, 165, 233, 0.10);
        --shadow-lg: 0 8px 24px rgba(14, 165, 233, 0.15);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    @keyframes titleShine { 0% { background-position: -200% center; } 100% { background-position: 200% center; } }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes slideIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
    @keyframes ringPulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(14,165,233,0.5); } 70% { box-shadow: 0 0 0 8px rgba(14,165,233,0); } }
    
    body {
        background: var(--bg-body);
        background-attachment: fixed;
        color: var(--text-main);
        padding-bottom: 30px;
        min-height: 100vh;
    }
    
    /* HEADER */
    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 20px;
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-bottom: 1px solid var(--border-blue);
        position: sticky;
        top: 0;
        z-index: 100;
        box-shadow: var(--shadow-sm);
    }
    .header-left { display: flex; align-items: center; gap: 10px; }
    .header-live-dot {
        width: 10px; height: 10px; border-radius: 50%;
        background: var(--win);
        animation: ringPulse 2s infinite;
    }
    .header-title {
        font-size: 19px; font-weight: 900;
        background: linear-gradient(90deg, #0284c7, #0ea5e9, #38bdf8, #0ea5e9, #0284c7);
        background-size: 300% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: titleShine 5s linear infinite;
        letter-spacing: -0.4px;
    }
    .btn-reset {
        background: #fff;
        color: var(--lose);
        border: 1.5px solid var(--lose);
        padding: 8px 16px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.25s ease;
        box-shadow: var(--shadow-sm);
    }
    .btn-reset:hover { background: var(--lose); color: #fff; box-shadow: 0 4px 14px rgba(239,68,68,0.35); transform: translateY(-1px); }
    
    /* STATS */
    .stats-bar {
        max-width: 720px;
        margin: 16px auto 0;
        padding: 0 16px;
        display: flex;
        gap: 10px;
    }
    .stat-item {
        flex: 1;
        background: var(--bg-card);
        border: 1px solid var(--border-blue);
        border-radius: 12px;
        padding: 12px 10px;
        text-align: center;
        box-shadow: var(--shadow-sm);
        transition: all 0.25s;
    }
    .stat-item:hover { border-color: var(--border-blue-strong); box-shadow: var(--shadow-md); transform: translateY(-2px); }
    .stat-label {
        font-size: 10px; color: var(--text-muted);
        text-transform: uppercase; letter-spacing: 1.2px;
        margin-bottom: 5px; font-weight: 700;
    }
    .stat-value { font-size: 22px; font-weight: 900; color: var(--text-main); }
    .stat-value.accent { color: var(--accent); }
    .stat-value.win { color: var(--win); }
    
    /* CONTAINER */
    .container {
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        max-width: 720px;
        margin: 0 auto;
    }
    
    /* CARD */
    .card-item {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        overflow: hidden;
        transition: all 0.3s ease;
        animation: slideIn 0.4s ease-out backwards;
        box-shadow: var(--shadow-sm);
    }
    .card-item:hover { border-color: var(--border-blue-strong); box-shadow: var(--shadow-md); }
    .card-item.active {
        border: 2px solid var(--accent);
        box-shadow: 0 0 0 4px var(--accent-glow), var(--shadow-md);
        background: linear-gradient(180deg, #ffffff 0%, #f0f9ff 100%);
    }
    .card-item.lose-card { border-left: 4px solid var(--lose); }
    .card-item.win-card { border-left: 4px solid var(--win); }
    .card-item.wait-card { border-left: 4px solid var(--accent); }
    
    .card-main {
        padding: 14px 16px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .col-left { display: flex; flex-direction: column; gap: 6px; flex: 1.3; min-width: 0; }
    .id-text {
        font-size: 17px; font-weight: 800;
        color: var(--text-main);
        letter-spacing: -0.3px;
    }
    .card-item.active .id-text {
        background: linear-gradient(90deg, #0284c7, #0ea5e9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .bot-line { display: flex; align-items: center; gap: 6px; font-size: 12px; flex-wrap: wrap; }
    .bot-label { color: var(--text-muted); font-weight: 600; }
    .bet-badge {
        padding: 3px 10px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 11px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .bet-tai { background: var(--tai-bg); color: var(--tai-text); border: 1px solid #7dd3fc; }
    .bet-xiu { background: var(--xiu-bg); color: var(--xiu-text); border: 1px solid #fda4af; }
    .bet-none { background: var(--bg-subtle); color: var(--text-muted); border: 1px solid var(--border-color); }
    .conf-row { display: flex; align-items: center; gap: 8px; }
    .conf-text { color: var(--text-muted); font-size: 11px; font-weight: 600; white-space: nowrap; }
    .conf-bar-wrap { flex: 1; height: 5px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
    .conf-bar {
        height: 100%; border-radius: 3px;
        background: linear-gradient(90deg, #38bdf8, #0ea5e9, #0284c7);
        transition: width 0.6s ease;
    }
    .conf-bar.high { background: linear-gradient(90deg, #34d399, #10b981); }
    .conf-bar.low { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
    
    .col-mid { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 0.9; }
    .pred-badge {
        padding: 7px 16px;
        border-radius: 10px;
        font-weight: 900;
        font-size: 14px;
        letter-spacing: 1.5px;
        min-width: 70px;
        text-align: center;
    }
    .pred-tai { background: var(--tai-solid); color: #fff; box-shadow: 0 3px 10px rgba(2,132,199,0.35); }
    .pred-xiu { background: var(--xiu-solid); color: #fff; box-shadow: 0 3px 10px rgba(225,29,72,0.35); }
    .pred-empty { background: transparent; border: 1.5px dashed var(--border-color); color: var(--text-soft); }
    .dice-text {
        font-size: 12px;
        font-weight: 700;
        color: var(--text-muted);
        font-family: 'Courier New', monospace;
        white-space: nowrap;
    }
    .dice-sum {
        display: inline-block;
        background: var(--bg-subtle);
        color: var(--text-main);
        padding: 1px 6px;
        border-radius: 6px;
        font-size: 11px;
        margin-left: 4px;
    }
    .dice-sum.tai { background: var(--tai-bg); color: var(--tai-text); }
    .dice-sum.xiu { background: var(--xiu-bg); color: var(--xiu-text); }
    
    .col-right { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex: 0.7; }
    .status-text {
        font-size: 12px;
        font-weight: 800;
        padding: 4px 10px;
        border-radius: 20px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .status-win { background: var(--win-bg); color: var(--win); }
    .status-lose { background: var(--lose-bg); color: var(--lose); }
    .status-wait { background: var(--tai-bg); color: var(--tai-text); animation: pulse 1.6s infinite; }
    .spin { display: inline-block; animation: spin 2s linear infinite; }
    
    /* ALGORITHM DETAILS */
    .algo-toggle {
        background: var(--bg-subtle);
        border: none;
        border-top: 1px solid var(--border-color);
        width: 100%;
        padding: 8px 16px;
        font-size: 11.5px;
        font-weight: 700;
        color: var(--text-muted);
        cursor: pointer;
        text-align: left;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.2s;
    }
    .algo-toggle:hover { background: #e0f2fe; color: var(--accent); }
    .algo-toggle .arrow { transition: transform 0.3s; font-size: 10px; }
    .algo-toggle.open .arrow { transform: rotate(180deg); }
    .algo-toggle.open { background: #e0f2fe; color: var(--accent); }
    
    .algo-body {
        background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
        border-top: 1px dashed var(--border-blue);
        padding: 12px 16px;
        display: none;
        font-size: 12px;
        animation: slideIn 0.25s ease;
    }
    .algo-body.open { display: block; }
    
    .algo-row {
        margin-bottom: 10px;
        display: flex;
        gap: 6px;
        align-items: flex-start;
        flex-wrap: wrap;
    }
    .algo-label {
        font-size: 10px;
        font-weight: 800;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        padding: 2px 6px;
        background: var(--bg-subtle);
        border-radius: 4px;
        white-space: nowrap;
    }
    .algo-value { font-weight: 700; color: var(--text-main); }
    .algo-value.code {
        font-family: 'Courier New', monospace;
        color: var(--accent);
        background: var(--tai-bg);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
    }
    
    .score-compare {
        display: flex;
        gap: 10px;
        margin: 10px 0;
    }
    .score-col { flex: 1; }
    .score-head {
        display: flex;
        justify-content: space-between;
        font-size: 11px;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .score-head.tai { color: var(--tai-text); }
    .score-head.xiu { color: var(--xiu-text); }
    .score-track {
        height: 8px;
        background: #e2e8f0;
        border-radius: 4px;
        overflow: hidden;
    }
    .score-fill { height: 100%; transition: width 0.5s ease; border-radius: 4px; }
    .score-fill.tai { background: linear-gradient(90deg, #38bdf8, #0284c7); }
    .score-fill.xiu { background: linear-gradient(90deg, #fb7185, #e11d48); }
    
    .evidence-list {
        display: flex;
        flex-direction: column;
        gap: 5px;
        margin-top: 8px;
    }
    .evidence-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        background: #fff;
        border: 1px solid var(--border-color);
        border-radius: 8px;
        font-size: 11.5px;
    }
    .evidence-item.tai { border-left: 3px solid var(--tai-solid); }
    .evidence-item.xiu { border-left: 3px solid var(--xiu-solid); }
    .ev-dir {
        font-size: 9.5px;
        font-weight: 900;
        padding: 2px 6px;
        border-radius: 4px;
        color: #fff;
        min-width: 34px;
        text-align: center;
    }
    .ev-dir.tai { background: var(--tai-solid); }
    .ev-dir.xiu { background: var(--xiu-solid); }
    .ev-name { flex: 1; color: var(--text-main); font-weight: 600; }
    .ev-weight {
        font-size: 11px;
        font-weight: 900;
        color: var(--accent);
        background: var(--tai-bg);
        padding: 2px 8px;
        border-radius: 12px;
    }
    .no-evidence {
        padding: 12px;
        text-align: center;
        color: var(--text-soft);
        font-style: italic;
        font-size: 11.5px;
    }
    
    .loading {
        text-align: center;
        padding: 50px;
        color: var(--accent);
        font-weight: 600;
        animation: pulse 2s infinite;
    }
    .error-box {
        text-align: center;
        padding: 24px;
        background: var(--lose-bg);
        border: 1.5px solid var(--lose);
        border-radius: 12px;
        color: var(--lose);
        font-weight: 700;
        margin: 20px auto;
        max-width: 500px;
        line-height: 1.6;
        font-size: 13px;
    }
    
    @media (max-width: 480px) {
        .header-title { font-size: 16px; }
        .stat-value { font-size: 18px; }
        .dice-text { font-size: 11px; }
        .pred-badge { min-width: 60px; padding: 6px 12px; font-size: 13px; }
        .col-mid { flex: 0.8; }
        .score-compare { flex-direction: column; gap: 6px; }
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-left">
        <div class="header-live-dot"></div>
        <div class="header-title">⚡ LC MD5 MINHLE </div>
    </div>
    <button class="btn-reset" onclick="confirmReset()">↻ Reset</button>
</div>

<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng phiên</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ</div><div class="stat-value accent" id="stat-rate">0%</div></div>
</div>

<div class="container" id="list-container">
    <div class="loading">Đang kết nối Server...</div>
</div>

<script>
let isResetting = false;

function animateNumber(el, target, suffix = '') {
    const start = parseInt(el.innerText.replace(/[^0-9]/g, '')) || 0;
    if (start === target) { el.innerText = target + suffix; return; }
    const dur = 700, t0 = performance.now();
    function step(t) {
        const p = Math.min((t - t0) / dur, 1);
        const e = 1 - Math.pow(1 - p, 3);
        el.innerText = Math.floor(start + (target - start) * e) + suffix;
        if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

function toggleAlgo(btn) {
    btn.classList.toggle('open');
    const body = btn.nextElementSibling;
    body.classList.toggle('open');
}

function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

async function fetchData() {
    if (isResetting) return;
    try {
        const r = await fetch('/api/history?v=' + Date.now(), { cache: 'no-store' });
        const data = await r.json();
        if (data.error) {
            document.getElementById('list-container').innerHTML = 
                `<div class="error-box">⚠️ LỖI API<br><br>${escapeHtml(data.error)}<br><br><span style="font-size:11px;color:#64748b;">(F5 trang hoặc cập nhật Token API mới)</span></div>`;
            return;
        }
        renderList(data.rows || [], data.stats || {});
    } catch (e) {
        document.getElementById('list-container').innerHTML = '<div class="error-box">⚠️ Không kết nối được Server</div>';
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
        container.innerHTML = '<div class="loading">Không có dữ liệu</div>';
        return;
    }
    container.innerHTML = '';
    rows.forEach((row, idx) => {
        const div = document.createElement('div');
        let cardClass = 'card-item';
        if (row.is_next) cardClass += ' active wait-card';
        else if (row.is_correct === true) cardClass += ' win-card';
        else if (row.is_correct === false) cardClass += ' lose-card';
        div.className = cardClass;
        div.style.animationDelay = (idx * 30) + 'ms';
        
        // Prediction badge
        let predBadge = `<span class="pred-badge pred-empty">-</span>`;
        let betBadge = `<span class="bet-badge bet-none">cược -</span>`;
        if (row.prediction === "Tài") {
            predBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
            betBadge = `<span class="bet-badge bet-tai">cược TÀI</span>`;
        } else if (row.prediction === "Xỉu") {
            predBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;
            betBadge = `<span class="bet-badge bet-xiu">cược XỈU</span>`;
        }
        
        // Result badge
        let resultBadge = `<span class="pred-badge pred-empty">-</span>`;
        if (row.result === "Tài") resultBadge = `<span class="pred-badge pred-tai">TÀI</span>`;
        if (row.result === "Xỉu") resultBadge = `<span class="pred-badge pred-xiu">XỈU</span>`;
        
        // Dice display
        let diceDisplay = "? + ? + ?";
        let diceSumClass = "";
        if (row.dice !== "? + ? + ?") {
            const parts = row.dice.split(" + ");
            const sum = parseInt(parts[0]) + parseInt(parts[1]) + parseInt(parts[2]);
            diceSumClass = sum >= 11 ? "tai" : "xiu";
            diceDisplay = `${row.dice}<span class="dice-sum ${diceSumClass}">${sum}</span>`;
        }
        
        // Status
        let statusHtml = '';
        if (row.is_next) statusHtml = `<div class="status-text status-wait">Chờ <span class="spin">⏳</span></div>`;
        else if (row.is_correct === true) statusHtml = `<div class="status-text status-win">ĐÚNG ✓</div>`;
        else if (row.is_correct === false) statusHtml = `<div class="status-text status-lose">SAI ✕</div>`;
        else statusHtml = `<div class="status-text" style="color:#94a3b8">—</div>`;
        
        // Confidence bar color
        const conf = row.confidence || 50;
        let confClass = '';
        if (conf >= 75) confClass = 'high';
        else if (conf < 60) confClass = 'low';
        
        // Algorithm details
        const det = row.details || {};
        const evidences = det.evidences || [];
        const taiW = det.tai_w || 0;
        const xiuW = det.xiu_w || 0;
        const totalW = taiW + xiuW;
        const taiPct = totalW > 0 ? Math.round((taiW / totalW) * 100) : 50;
        const xiuPct = 100 - taiPct;
        
        let evidenceHtml = '';
        if (evidences.length > 0) {
            evidenceHtml = evidences.map(ev => {
                const d = ev.dir === "Tài" ? "tai" : "xiu";
                const dirLabel = ev.dir === "Tài" ? "TÀI" : "XỈU";
                return `<div class="evidence-item ${d}">
                    <span class="ev-dir ${d}">${dirLabel}</span>
                    <span class="ev-name">${escapeHtml(ev.name)}</span>
                    <span class="ev-weight">${ev.weight.toFixed(1)}</span>
                </div>`;
            }).join('');
        } else {
            evidenceHtml = '<div class="no-evidence">Không đủ tín hiệu — dự đoán theo đảo nhịp</div>';
        }
        
        const blocksSig = det.blocks_sig || '—';
        const p81 = det.pattern_81 ? det.pattern_81 : '—';
        
        // Auto-open for next session
        const isNext = row.is_next;
        
        div.innerHTML = `
            <div class="card-main">
                <div class="col-left">
                    <div class="id-text">#${row.phien}</div>
                    <div class="bot-line">
                        <span class="bot-label">Bot:</span>
                        ${betBadge}
                    </div>
                    <div class="conf-row">
                        <span class="conf-text">${conf}%</span>
                        <div class="conf-bar-wrap"><div class="conf-bar ${confClass}" style="width:${conf}%"></div></div>
                    </div>
                </div>
                <div class="col-mid">
                    ${isNext ? predBadge : resultBadge}
                    <div class="dice-text">${diceDisplay}</div>
                </div>
                <div class="col-right">
                    ${statusHtml}
                </div>
            </div>
            <button class="algo-toggle ${isNext ? 'open' : ''}" onclick="toggleAlgo(this)">
                <span>🔬 Chi tiết thuật toán ${evidences.length > 0 ? '(' + evidences.length + ' tín hiệu)' : '(mặc định)'}</span>
                <span class="arrow">▼</span>
            </button>
            <div class="algo-body ${isNext ? 'open' : ''}">
                <div class="algo-row">
                    <span class="algo-label">Cầu</span>
                    <span class="algo-value code">${escapeHtml(blocksSig)}</span>
                </div>
                <div class="algo-row">
                    <span class="algo-label">Mẫu 81</span>
                    <span class="algo-value code">${escapeHtml(p81)}</span>
                </div>
                <div class="score-compare">
                    <div class="score-col">
                        <div class="score-head tai"><span>TÀI</span><span>${taiW.toFixed(2)}</span></div>
                        <div class="score-track"><div class="score-fill tai" style="width:${taiPct}%"></div></div>
                    </div>
                    <div class="score-col">
                        <div class="score-head xiu"><span>XỈU</span><span>${xiuW.toFixed(2)}</span></div>
                        <div class="score-track"><div class="score-fill xiu" style="width:${xiuPct}%"></div></div>
                    </div>
                </div>
                <div class="evidence-list">${evidenceHtml}</div>
            </div>
        `;
        container.appendChild(div);
    });
}

async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?',
        text: "Lịch sử hiển thị sẽ bị ẩn. Hệ thống vẫn tính toán ngầm!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#0ea5e9',
        cancelButtonColor: '#94a3b8',
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
                    Swal.fire({ title: 'Thành công!', text: 'Đã reset từ phiên #' + data.reset_to, icon: 'success', confirmButtonColor: '#0ea5e9' });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
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

# =====================================================================
# HELPERS V7.0
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

def pattern_signature(block_lengths):
    if len(block_lengths) < 4: return "----"
    return ''.join(block_class(L) for L in block_lengths[-4:])

def analyze_streak_history(chrono):
    hist = {}
    N = len(chrono)
    i = 0
    while i < N:
        val = chrono[i]
        j = i + 1
        while j < N and chrono[j] == val:
            j += 1
        streak = j - i
        if j < N:
            key = min(streak, 8)
            if key not in hist:
                hist[key] = {'cont': 0, 'brk': 0}
            if chrono[j] == val: hist[key]['cont'] += 1
            else: hist[key]['brk'] += 1
        i = j
    return hist

def learn_81_weighted(chrono, decay=0.95):
    stats = {}
    N = len(chrono)
    for k in range(6, N):
        blocks = build_blocks(chrono[:k])
        if len(blocks) < 5: continue
        last4 = [b['len'] for b in blocks[-5:-1]]
        code = encode_pattern_81(last4)
        if code is None: continue
        current_val = blocks[-1]['val']
        continued = (chrono[k] == current_val)
        weight = decay ** (N - k)
        key = (code, min(blocks[-1]['len'], 4))
        if key not in stats: stats[key] = {'cont_w': 0.0, 'brk_w': 0.0, 'cont_c': 0, 'brk_c': 0}
        if continued: stats[key]['cont_w'] += weight; stats[key]['cont_c'] += 1
        else: stats[key]['brk_w'] += weight; stats[key]['brk_c'] += 1
    return stats

def analyze_dice_trend(dice_chrono):
    if len(dice_chrono) < 5: return None
    recent = dice_chrono[-10:]
    avg = sum(recent) / len(recent)
    ma3 = sum(dice_chrono[-3:]) / 3
    if ma3 > avg + 1.5 and avg > 10.5:
        return ("Tài", min(0.85, (ma3 - 10.5) / 7.5), f"Dice Tài (MA3={ma3:.1f})")
    if ma3 < avg - 1.5 and avg < 10.5:
        return ("Xỉu", min(0.85, (10.5 - ma3) / 7.5), f"Dice Xỉu (MA3={ma3:.1f})")
    return None

# =====================================================================
# THUẬT TOÁN V7.0 — TRẢ VỀ CẢ DETAILS
# =====================================================================
def analyze_pattern(results, dice_sums=None):
    """
    Trả về: (winner, confidence, pattern_name, details_dict)
    details_dict chứa: evidences, tai_w, xiu_w, blocks_sig, pattern_81
    """
    default_detail = {
        'evidences': [], 'tai_w': 0, 'xiu_w': 0,
        'tai_ratio': 0.5, 'blocks_sig': '—', 'pattern_81': None
    }
    
    if not results:
        return "Tài", 50.0, "Khởi tạo", default_detail
    
    if len(results) < 3:
        opposite = "Xỉu" if results[0] == "Tài" else "Tài"
        blocks_sig = ' → '.join(f"{'T' if r == 'Tài' else 'X'}(1)" for r in reversed(results))
        return opposite, 52.0, "Đảo nhịp (ít dữ liệu)", {
            **default_detail, 'blocks_sig': blocks_sig
        }
    
    chrono = list(reversed(results))
    dice_chrono = list(reversed(dice_sums)) if dice_sums else []
    N = len(chrono)
    last = chrono[-1]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    blocks = build_blocks(chrono)
    current_val = blocks[-1]['val']
    current_len = blocks[-1]['len']
    evidences = []
    
    # Block signature cho UI
    blocks_sig = ' → '.join(
        f"{'T' if b['val']=='Tài' else 'X'}({b['len']})" for b in blocks[-6:]
    )
    
    # 81-pattern code
    p81_code_str = None
    p81_sig = None
    if len(blocks) >= 5:
        last4 = [b['len'] for b in blocks[-5:-1]]
        code = encode_pattern_81(last4)
        if code is not None:
            p81_code_str = f"81#{code+1:02d}"
            p81_sig = pattern_signature(last4)
    
    # ---- E1: STREAK HISTORY ----
    streak_hist = analyze_streak_history(chrono)
    if current_len in streak_hist:
        h = streak_hist[current_len]
        tot = h['cont'] + h['brk']
        if tot >= 2:
            cont_rate = h['cont'] / tot
            edge = abs(cont_rate - 0.5) * 2
            weight = min(2.5, tot / 5) * edge * 2
            if weight > 0.3:
                direction = current_val if cont_rate > 0.5 else opposite
                evidences.append((direction, weight,
                    f"Bệt {current_len} hist {h['cont']}/{tot}",
                    85 if edge > 0.4 else 70))
    
    # ---- E2: RHYTHM ----
    if len(blocks) >= 3:
        prev_len, prev_val = blocks[-2]['len'], blocks[-2]['val']
        prev2_len, prev2_val = blocks[-3]['len'], blocks[-3]['val']
        is_alt = (prev_val != prev2_val and current_val != prev_val)
        
        if is_alt and prev_len == prev2_len and prev_len >= 2:
            cycle = prev_len
            if current_len < cycle:
                evidences.append((current_val, 3.5, f"Rhythm {cycle}-{cycle} dở", 92))
            elif current_len == cycle:
                evidences.append((opposite, 4.0, f"Rhythm {cycle}-{cycle} đủ", 96))
        
        if is_alt and len(blocks) >= 4:
            b3 = blocks[-4]['len']
            if b3 == prev_len == prev2_len:
                if current_len < prev_len:
                    evidences.append((current_val, 2.5, "Chain x3 dở", 85))
                elif current_len == prev_len:
                    evidences.append((opposite, 3.0, "Chain x3 đủ", 90))
    
    # ---- E3: 81-PATTERN ----
    if len(blocks) >= 5:
        p81 = learn_81_weighted(chrono)
        last4 = [b['len'] for b in blocks[-5:-1]]
        code = encode_pattern_81(last4)
        sig = pattern_signature(last4)
        if code is not None:
            for key in [(code, min(current_len, 4)), code]:
                if key in p81:
                    s = p81[key]
                    tot_w = s['cont_w'] + s['brk_w']
                    raw = s['cont_c'] + s['brk_c']
                    if tot_w > 0.3 and raw >= 2:
                        cr = s['cont_w'] / tot_w
                        if cr >= 0.62:
                            w = min(2.5, raw / 4) * (cr - 0.5) * 4
                            evidences.append((current_val, w,
                                f"81#{code+1:02d}[{sig}] tiếp {s['cont_c']}/{raw}", 90))
                        elif cr <= 0.38:
                            w = min(2.5, raw / 4) * (0.5 - cr) * 4
                            evidences.append((opposite, w,
                                f"81#{code+1:02d}[{sig}] gãy {s['brk_c']}/{raw}", 90))
                        break
    
    # ---- E4: N-GRAM ----
    for ns in [7, 6, 5, 4]:
        if N < ns + 1: continue
        target = tuple(chrono[-ns:])
        m_tai = m_xiu = 0
        for i in range(N - ns):
            if tuple(chrono[i:i+ns]) == target and i + ns < N:
                if chrono[i+ns] == "Tài": m_tai += 1
                else: m_xiu += 1
        tot = m_tai + m_xiu
        if tot >= 2 and m_tai != m_xiu:
            ratio = max(m_tai, m_xiu) / tot
            if ratio >= 0.6:
                direction = "Tài" if m_tai > m_xiu else "Xỉu"
                w = (ratio - 0.5) * 3 * min(1.5, tot / 3)
                evidences.append((direction, w,
                    f"Ngram{ns} ({m_tai}T-{m_xiu}X)", 70 + ns))
    
    # ---- E5: MARKOV ----
    if N >= 8:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(N - 1):
            if chrono[i] == last:
                trans[chrono[i + 1]] += 1
        tot = trans["Tài"] + trans["Xỉu"]
        if tot >= 3 and trans["Tài"] != trans["Xỉu"]:
            ratio = max(trans["Tài"], trans["Xỉu"]) / tot
            direction = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            evidences.append((direction, (ratio - 0.5) * 2.5,
                f"Markov ({trans['Tài']}T-{trans['Xỉu']}X)", 60))
    
    # ---- E6: DICE TREND ----
    dice_sig = analyze_dice_trend(dice_chrono)
    if dice_sig:
        direction, strength, name = dice_sig
        evidences.append((direction, strength * 2.0, name, 65))
    
    # ---- ENSEMBLE ----
    if not evidences:
        return opposite, 55.0, "Đảo nhịp (Mặc định)", {
            **default_detail,
            'blocks_sig': blocks_sig,
            'pattern_81': f"{p81_code_str}[{p81_sig}]" if p81_code_str else None
        }
    
    tai_w = sum(e[1] for e in evidences if e[0] == "Tài")
    xiu_w = sum(e[1] for e in evidences if e[0] == "Xỉu")
    total_w = tai_w + xiu_w
    
    if total_w < 0.01:
        return opposite, 55.0, "Đảo nhịp (Mặc định)", {
            **default_detail,
            'blocks_sig': blocks_sig,
            'pattern_81': f"{p81_code_str}[{p81_sig}]" if p81_code_str else None
        }
    
    tai_ratio = tai_w / total_w
    winner = "Tài" if tai_ratio > 0.5 else "Xỉu"
    posterior = tai_ratio if winner == "Tài" else (1 - tai_ratio)
    
    # Confidence calibration an toàn
    confidence = 52 + (posterior - 0.5) * 2 * 38
    confidence += min(5, len(evidences) * 0.4)
    
    same_dir = [e for e in evidences if e[0] == winner]
    if same_dir:
        best = max(same_dir, key=lambda x: (x[3], x[1]))
        pattern_name = best[2]
    else:
        pattern_name = f"Tổng hợp ({len(evidences)} tín hiệu)"
    
    # Build details
    details = {
        'evidences': [
            {'dir': e[0], 'weight': round(e[1], 2), 'name': e[2], 'priority': e[3]}
            for e in sorted(evidences, key=lambda x: (x[3], x[1]), reverse=True)
        ],
        'tai_w': round(tai_w, 2),
        'xiu_w': round(xiu_w, 2),
        'tai_ratio': round(tai_ratio, 3),
        'blocks_sig': blocks_sig,
        'pattern_81': f"{p81_code_str}[{p81_sig}]" if p81_code_str else None
    }
    
    return winner, round(min(97.0, confidence), 1), pattern_name, details

# =====================================================================
# FETCH DỮ LIỆU
# =====================================================================
def fetch_sessions():
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    try:
        r = requests.get(API_URL, timeout=10, headers=headers)
        if r.status_code != 200:
            return None, f"Mã HTTP {r.status_code} — Token có thể đã hết hạn."
        
        data = r.json()
        if 'list' not in data or not data['list']:
            return None, "API trả về danh sách trống."
        
        rows = []
        for item in data['list']:
            res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
            dices = item.get('dices', [0, 0, 0])
            rows.append({
                'phien': int(item['id']), 'result': res,
                'dice': f"{dices[0]} + {dices[1]} + {dices[2]}",
                'total': item.get('point', sum(dices))
            })
        
        rows.sort(key=lambda x: x['phien'])
        latest_id = rows[-1]['phien']
        
        if latest_id < 7000000 or latest_id > 8000000:
            return None, f"Sai phòng! API trả về phiên #{latest_id} (không phải LC79). Hãy lấy Token mới."
        
        return rows, 'live'
    except requests.exceptions.RequestException:
        return None, "Không kết nối được máy chủ API."
    except Exception as e:
        return None, f"Lỗi xử lý: {str(e)}"

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
        raw_rows, error = fetch_sessions()
        if error:
            return jsonify({'error': error}), 500

        valid = raw_rows
        out = []
        correct_count = 0
        total_past = 0

        latest = valid[-1]
        next_phien = latest['phien'] + 1
        hist_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        next_pred, next_conf, next_pattern, next_det = analyze_pattern(hist_for_next, dice_for_next)

        out.append({
            'phien': next_phien, 'is_next': True,
            'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?",
            'is_correct': None, 'pattern': next_pattern,
            'details': next_det
        })

        for i in range(len(valid) - 1, -1, -1):
            cs = valid[i]
            if cs['phien'] <= RESET_SESSION_ID: break
            if len(out) > 20: break

            hist_list = [v['result'] for v in valid[:i]][::-1]
            dice_list = [v.get('total', 0) for v in valid[:i]][::-1]

            if hist_list:
                pred, conf, pattern, det = analyze_pattern(hist_list, dice_list)
                is_correct = (pred == cs['result'])
                total_past += 1
                if is_correct: correct_count += 1
            else:
                pred, conf, pattern = "Tài", 50.0, "Khởi tạo"
                det = {'evidences': [], 'tai_w': 0, 'xiu_w': 0, 'tai_ratio': 0.5, 'blocks_sig': '—', 'pattern_81': None}
                is_correct = None

            out.append({
                'phien': cs['phien'], 'is_next': False,
                'prediction': pred, 'confidence': conf,
                'result': cs['result'], 'dice': cs['dice'],
                'is_correct': is_correct, 'pattern': pattern,
                'details': det
            })

        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': f"Lỗi Server: {str(e)}"}), 500

@app.route('/api/predict')
def predict_only():
    try:
        raw_rows, error = fetch_sessions()
        if error:
            return jsonify({'status': 'error', 'message': error}), 500
        
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        latest = valid[-1]
        hist = [v['result'] for v in valid][::-1]
        dice = [v.get('total', 0) for v in valid][::-1]
        pred, conf, pat, det = analyze_pattern(hist, dice)
        return jsonify({
            'status': 'success', 'next_session': latest['phien'] + 1,
            'prediction': pred, 'confidence': conf, 'pattern': pat,
            'details': det,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        raw_rows, error = fetch_sessions()
        if error:
            return jsonify({'status': 'error', 'message': error}), 500
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if valid:
            RESET_SESSION_ID = valid[-1]['phien']
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
