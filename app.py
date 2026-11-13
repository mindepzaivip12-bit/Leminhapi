import os
import math
import traceback
from datetime import datetime
from collections import defaultdict
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
RESET_ID = 0

# =====================================================================
# BẢNG TRA CỨU MẪU 13 KÝ TỰ (T = Tài, X = Xỉu)
# =====================================================================
PATTERN_MAP = {
    "TTTTTTTTTTTTT": "Tài", "TTTTTTTTTTTTX": "Tài",
    "TTTTTTTTTTTXT": "Xỉu", "TTTTTTTTTTTXX": "Xỉu",
    "TTTTTTTTTTXTT": "Tài", "TTTTTTTTTTXTX": "Tài",
    "TTTTTTTTTTXXT": "Xỉu", "TTTTTTTTTTXXX": "Tài",
    "TTTTTTTTTXTTT": "Xỉu", "TTTTTTTTTXTTX": "Xỉu",
    "TTTTTTTTTXTXT": "Xỉu", "TTTTTTTTTXTXX": "Xỉu",
    "TTTTTTTTTXXTT": "Tài", "TTTTTTTTTXXTX": "Tài",
    "TTTTTTTTTXXXT": "Xỉu", "TTTTTTTTTXXXX": "Tài",
    "TTTTTTTTXTTTT": "Tài", "TTTTTTTTXTTTX": "Tài",
    "TTTTTTTTXTTXT": "Xỉu", "TTTTTTTTXTTXX": "Xỉu",
    "TTTTTTTTXTXTT": "Tài", "TTTTTTTTXTXTX": "Tài",
    "TTTTTTTTXTXXT": "Tài", "TTTTTTTTXTXXX": "Tài",
    "TTTTTTTTXXTTT": "Tài", "TTTTTTTTXXTTX": "Tài",
    "TTTTTTTTXXTXT": "Xỉu", "TTTTTTTTXXTXX": "Xỉu",
    "TTTTTTTTXXXTT": "Tài", "TTTTTTTTXXXTX": "Tài",
    "TTTTTTTTXXXXT": "Xỉu", "TTTTTTTTXXXXX": "Xỉu",
    "TTTTTTTXTTTTT": "Tài", "TTTTTTTXTTTTX": "Tài",
    "TTTTTTTXTTTXT": "Xỉu", "TTTTTTTXTTTXX": "Xỉu",
    "TTTTTTTXTTXTT": "Tài", "TTTTTTTXTTXTX": "Tài",
    "TTTTTTTXTTXXT": "Tài", "TTTTTTTXTTXXX": "Xỉu",
    "TTTTTTTXTXTTT": "Tài", "TTTTTTTXTXTTX": "Tài",
    "TTTTTTTXTXTXT": "Xỉu", "TTTTTTTXTXTXX": "Xỉu",
    "TTTTTTTXTXXTT": "Tài", "TTTTTTTXTXXTX": "Tài",
    "TTTTTTTXTXXXT": "Xỉu", "TTTTTTTXTXXXX": "Xỉu",
    "TTTTTTTXXTTTT": "Tài", "TTTTTTTXXTTTX": "Tài",
    "TTTTTTTXXTTXT": "Xỉu", "TTTTTTTXXTTXX": "Xỉu",
    "TTTTTTTXXTXTT": "Tài", "TTTTTTTXXTXTX": "Tài",
    "TTTTTTTXXTXXT": "Tài", "TTTTTTTXXTXXX": "Tài",
    "TTTTTTTXXXTTT": "Tài", "TTTTTTTXXXTTX": "Tài",
    "TTTTTTTXXXTXT": "Xỉu", "TTTTTTTXXXTXX": "Xỉu",
    "TTTTTTTXXXXTT": "Tài", "TTTTTTTXXXXTX": "Tài",
    "TTTTTTTXXXXXT": "Xỉu", "TTTTTTTXXXXXX": "Xỉu",
    "TTTTTTXTTTTTT": "Tài", "TTTTTTXTTTTTX": "Tài",
    "TTTTTTXTTTTXT": "Xỉu", "TTTTTTXTTTTXX": "Xỉu",
    "TTTTTTXTTTXTT": "Tài", "TTTTTTXTTTXTX": "Tài",
    "TTTTTTXTTTXXT": "Tài", "TTTTTTXTTTXXX": "Tài",
    "TTTTTTXTTXTTT": "Tài", "TTTTTTXTTXTTX": "Tài",
    "TTTTTTXTTXTXT": "Xỉu", "TTTTTTXTTXTXX": "Xỉu",
    "TTTTTTXTTXXTT": "Tài", "TTTTTTXTTXXTX": "Tài",
    "TTTTTTXTTXXXT": "Xỉu", "TTTTTTXTTXXXX": "Tài",
    "TTTTTTXTXTTTT": "Tài", "TTTTTTXTXTTTX": "Tài",
    "TTTTTTXTXTTXT": "Xỉu", "TTTTTTXTXTTXX": "Xỉu",
    "TTTTTTXTXTXTT": "Tài", "TTTTTTXTXTXTX": "Tài",
    "TTTTTTXTXTXXT": "Tài", "TTTTTTXTXTXXX": "Tài",
    "TTTTTTXTXXTTT": "Tài", "TTTTTTXTXXTTX": "Xỉu",
    "TTTTTTXTXXTXT": "Xỉu", "TTTTTTXTXXTXX": "Xỉu",
    "TTTTTTXTXXXTT": "Tài", "TTTTTTXTXXXTX": "Tài",
    "TTTTTTXTXXXXT": "Xỉu", "TTTTTTXTXXXXX": "Xỉu",
    "TTTTTTXXTTTTT": "Tài", "TTTTTTXXTTTTX": "Tài",
    "TTTTTTXXTTTXT": "Xỉu", "TTTTTTXXTTTXX": "Xỉu",
    "TTTTTTXXTTXTT": "Tài", "TTTTTTXXTTXTX": "Tài",
    "TTTTTTXXTTXXT": "Tài", "TTTTTTXXTTXXX": "Xỉu",
    "TTTTTTXXTXTTT": "Tài", "TTTTTTXXTXTTX": "Tài",
    "TTTTTTXXTXTXT": "Xỉu", "TTTTTTXXTXTXX": "Xỉu",
    "TTTTTTXXTXXTT": "Tài", "TTTTTTXXTXXTX": "Tài",
    "TTTTTTXXTXXXT": "Xỉu", "TTTTTTXXTXXXX": "Xỉu",
    "TTTTTTXXXTTTT": "Tài", "TTTTTTXXXTTTX": "Tài",
    "TTTTTTXXXTTXT": "Xỉu", "TTTTTTXXXTTXX": "Xỉu",
    "TTTTTTXXXTXTT": "Tài", "TTTTTTXXXTXTX": "Tài",
    "TTTTTTXXXTXXT": "Tài", "TTTTTTXXXTXXX": "Xỉu",
    "TTTTTTXXXXTTT": "Tài", "TTTTTTXXXXTTX": "Tài",
    "TTTTTTXXXXTXT": "Xỉu", "TTTTTTXXXXTXX": "Xỉu",
    "TTTTTTXXXXXTT": "Tài", "TTTTTTXXXXXTX": "Tài",
    "TTTTTTXXXXXXT": "Xỉu", "TTTTTTXXXXXXX": "Xỉu",
    "TTTTTXTTTTTTT": "Tài", "TTTTTXTTTTTTX": "Tài",
    "TTTTTXTTTTTXT": "Xỉu", "TTTTTXTTTTTXX": "Xỉu",
    "TTTTTXTTTTXTT": "Tài", "TTTTTXTTTTXTX": "Tài",
    "TTTTTXTTTTXXT": "Tài", "TTTTTXTTTTXXX": "Tài",
    "TTTTTXTTTXTTT": "Tài", "TTTTTXTTTXTTX": "Tài",
    "TTTTTXTTTXTXT": "Xỉu", "TTTTTXTTTXTXX": "Xỉu",
    "TTTTTXTTTXXTT": "Tài", "TTTTTXTTTXXTX": "Tài",
    "TTTTTXTTTXXXT": "Xỉu", "TTTTTXTTTXXXX": "Tài",
    "TTTTTXTTXTTTT": "Tài", "TTTTTXTTXTTTX": "Tài",
    "TTTTTXTTXTTXT": "Xỉu", "TTTTTXTTXTTXX": "Xỉu",
    "TTTTTXTTXTXTT": "Tài", "TTTTTXTTXTXTX": "Tài",
    "TTTTTXTTXTXXT": "Xỉu", "TTTTTXTTXTXXX": "Xỉu",
    "TTTTTXTTXXTTT": "Tài", "TTTTTXTTXXTTX": "Tài",
    "TTTTTXTTXXTXT": "Xỉu", "TTTTTXTTXXTXX": "Xỉu",
    "TTTTTXTTXXXTT": "Tài", "TTTTTXTTXXXTX": "Tài",
    "TTTTTXTTXXXXT": "Xỉu", "TTTTTXTTXXXXX": "Xỉu",
    "TTTTTXTXTTTTT": "Tài", "TTTTTXTXTTTTX": "Tài",
    "TTTTTXTXTTTXT": "Xỉu", "TTTTTXTXTTTXX": "Xỉu",
    "TTTTTXTXTTXTT": "Tài", "TTTTTXTXTTXTX": "Tài",
    "TTTTTXTXTTXXT": "Tài", "TTTTTXTXTTXXX": "Xỉu",
    "TTTTTXTXTXTTT": "Tài", "TTTTTXTXTXTTX": "Tài",
    "TTTTTXTXTXTXT": "Xỉu", "TTTTTXTXTXTXX": "Xỉu",
    "TTTTTXTXTXXTT": "Tài", "TTTTTXTXTXXTX": "Tài",
    "TTTTTXTXTXXXT": "Xỉu", "TTTTTXTXTXXXX": "Tài",
    "TTTTTXTXXTTTT": "Tài", "TTTTTXTXXTTTX": "Tài",
    "TTTTTXTXXTTXT": "Xỉu", "TTTTTXTXXTTXX": "Xỉu",
    "TTTTTXTXXTXTT": "Tài", "TTTTTXTXXTXTX": "Tài",
    "TTTTTXTXXTXXT": "Tài", "TTTTTXTXXTXXX": "Tài",
    "TTTTTXTXXXTTT": "Xỉu", "TTTTTXTXXXTTX": "Tài",
    "TTTTTXTXXXTXT": "Xỉu", "TTTTTXTXXXTXX": "Xỉu",
    "TTTTTXTXXXXTT": "Tài", "TTTTTXTXXXXTX": "Tài",
    "TTTTTXTXXXXXT": "Xỉu", "TTTTTXTXXXXXX": "Xỉu",
    "TTTTTXXTTTTTT": "Tài", "TTTTTXXTTTTTX": "Tài",
    "TTTTTXXTTTTXT": "Xỉu", "TTTTTXXTTTTXX": "Xỉu",
    "TTTTTXXTTTXTT": "Tài", "TTTTTXXTTTXTX": "Tài",
    "TTTTTXXTTTXXT": "Xỉu", "TTTTTXXTTTXXX": "Xỉu",
    "TTTTTXXTTXTTT": "Tài", "TTTTTXXTTXTTX": "Xỉu",
    "TTTTTXXTTXTXT": "Xỉu", "TTTTTXXTTXTXX": "Xỉu",
    "TTTTTXXTTXXTT": "Tài", "TTTTTXXTTXXTX": "Tài",
    "TTTTTXXTTXXXT": "Xỉu", "TTTTTXXTTXXXX": "Xỉu",
    "TTTTTXXTXTTTT": "Tài", "TTTTTXXTXTTTX": "Tài",
    "TTTTTXXTXTTXT": "Xỉu", "TTTTTXXTXTTXX": "Xỉu",
    "TTTTTXXTXTXTT": "Tài", "TTTTTXXTXTXTX": "Tài",
    "TTTTTXXTXTXXT": "Tài", "TTTTTXXTXTXXX": "Xỉu",
    "TTTTTXXTXXTTT": "Tài", "TTTTTXXTXXTTX": "Xỉu",
    "TTTTTXXTXXTXT": "Xỉu", "TTTTTXXTXXTXX": "Xỉu",
    "TTTTTXXTXXXTT": "Tài", "TTTTTXXTXXXTX": "Tài",
    "TTTTTXXTXXXXT": "Xỉu", "TTTTTXXTXXXXX": "Xỉu",
    "TTTTTXXXTTTTT": "Tài", "TTTTTXXXTTTTX": "Tài",
    "TTTTTXXXTTTXT": "Xỉu", "TTTTTXXXTTTXX": "Xỉu",
    "TTTTTXXXTTXTT": "Tài", "TTTTTXXXTTXTX": "Tài",
    "TTTTTXXXTTXXT": "Xỉu", "TTTTTXXXTTXXX": "Xỉu",
    "TTTTTXXXTXTTT": "Xỉu", "TTTTTXXXTXTTX": "Tài",
    "TTTTTXXXTXTXT": "Xỉu", "TTTTTXXXTXTXX": "Xỉu",
    "TTTTTXXXTXXTT": "Tài", "TTTTTXXXTXXTX": "Tài",
    "TTTTTXXXTXXXT": "Xỉu", "TTTTTXXXTXXXX": "Xỉu",
    "TTTTTXXXXTTTT": "Tài", "TTTTTXXXXTTTX": "Tài",
    "TTTTTXXXXTTXT": "Xỉu", "TTTTTXXXXTTXX": "Xỉu",
    "TTTTTXXXXTXTT": "Tài", "TTTTTXXXXTXTX": "Tài",
    "TTTTTXXXXTXXT": "Xỉu", "TTTTTXXXXTXXX": "Tài",
    "TTTTTXXXXXTTT": "Xỉu", "TTTTTXXXXXTTX": "Tài",
    "TTTTTXXXXXTXT": "Xỉu", "TTTTTXXXXXTXX": "Xỉu",
    "TTTTTXXXXXXTT": "Tài", "TTTTTXXXXXXTX": "Tài",
    "TTTTTXXXXXXXT": "Xỉu", "TTTTTXXXXXXXX": "Xỉu",
    "TTTTXTTTTTTTT": "Tài", "TTTTXTTTTTTTX": "Tài",
    "TTTTXTTTTTTXT": "Xỉu", "TTTTXTTTTTTXX": "Xỉu",
    "TTTTXTTTTTXTT": "Tài", "TTTTXTTTTTXTX": "Tài",
    "TTTTXTTTTTXXT": "Tài", "TTTTXTTTTTXXX": "Xỉu",
    "TTTTXTTTTXTTT": "Tài", "TTTTXTTTTXTTX": "Tài",
    "TTTTXTTTTXTXT": "Xỉu", "TTTTXTTTTXTXX": "Xỉu",
    "TTTTXTTTTXXTT": "Tài", "TTTTXTTTTXXTX": "Tài",
    "TTTTXTTTTXXXT": "Xỉu", "TTTTXTTTTXXXX": "Tài",
    "TTTTXTTTXTTTT": "Tài", "TTTTXTTTXTTTX": "Tài",
    "TTTTXTTTXTTXT": "Xỉu", "TTTTXTTTXTTXX": "Xỉu",
    "TTTTXTTTXTXTT": "Tài", "TTTTXTTTXTXTX": "Tài",
    "TTTTXTTTXTXXT": "Tài", "TTTTXTTTXTXXX": "Tài",
    "TTTTXTTTXXTTT": "Tài", "TTTTXTTTXXTTX": "Tài",
    "TTTTXTTTXXTXT": "Xỉu", "TTTTXTTTXXTXX": "Xỉu",
    "TTTTXTTTXXXTT": "Tài", "TTTTXTTTXXXTX": "Tài",
    "TTTTXTTTXXXXT": "Xỉu", "TTTTXTTTXXXXX": "Xỉu",
    "TTTTXTTXTTTTT": "Tài", "TTTTXTTXTTTTX": "Tài",
    "TTTTXTTXTTTXT": "Xỉu", "TTTTXTTXTTTXX": "Xỉu",
    "TTTTXTTXTTXTT": "Tài", "TTTTXTTXTTXTX": "Tài",
    "TTTTXTTXTTXXT": "Xỉu", "TTTTXTTXTTXXX": "Tài",
    "TTTTXTTXTXTTT": "Tài", "TTTTXTTXTXTTX": "Tài",
    "TTTTXTTXTXTXT": "Xỉu", "TTTTXTTXTXTXX": "Xỉu",
    "TTTTXTTXTXXTT": "Tài", "TTTTXTTXTXXTX": "Tài",
    "TTTTXTTXTXXXT": "Xỉu", "TTTTXTTXTXXXX": "Xỉu",
    "TTTTXTTXXTTTT": "Tài", "TTTTXTTXXTTTX": "Tài",
    "TTTTXTTXXTTXT": "Xỉu", "TTTTXTTXXTTXX": "Xỉu",
    "TTTTXTTXXTXTT": "Tài", "TTTTXTTXXTXTX": "Tài",
    "TTTTXTTXXTXXT": "Tài", "TTTTXTTXXTXXX": "Tài",
    "TTTTXTTXXXTTT": "Tài", "TTTTXTTXXXTTX": "Tài",
    "TTTTXTTXXXTXT": "Xỉu", "TTTTXTTXTTTXT": "Tài",
}

# =====================================================================
# HTML TEMPLATE
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-page: #0f172a; --bg-card: #1e293b; --text-main: #f8fafc;
        --text-muted: #94a3b8; --border-color: #334155;
        --tai-color: #38bdf8; --tai-bg: rgba(56, 189, 248, 0.15);
        --xiu-color: #f472b6; --xiu-bg: rgba(244, 114, 182, 0.15);
        --win-color: #34d399; --win-bg: rgba(52, 211, 153, 0.15);
        --lose-color: #f87171; --lose-bg: rgba(248, 113, 113, 0.15);
        --wait-color: #fbbf24; --wait-bg: rgba(251, 191, 36, 0.15);
        --recovery-color: #fb923c; --recovery-bg: rgba(251, 146, 60, 0.15);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: var(--text-main); min-height: 100vh; padding-bottom: 40px; }
    .header { background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-color); padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
    .header-title { font-size: 22px; font-weight: 800; color: #38bdf8; display: flex; align-items: center; gap: 10px; text-shadow: 0 0 20px rgba(56, 189, 248, 0.4); }
    .header-title span { font-size: 11px; background: linear-gradient(135deg, #38bdf8, #ec4899); color: #fff; padding: 4px 12px; border-radius: 20px; font-weight: 800; letter-spacing: 1px; box-shadow: 0 0 15px rgba(236, 72, 153, 0.4); }
    .header-actions { display: flex; gap: 12px; align-items: center; }
    .time-update { font-size: 12px; color: var(--text-muted); font-weight: 600; }
    .btn-refresh { background: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); width: 38px; height: 38px; border-radius: 10px; font-weight: 700; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: 0.2s; }
    .btn-refresh:hover { background: var(--border-color); transform: rotate(180deg); }
    .btn-reset { background: rgba(248, 113, 113, 0.2); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 8px 16px; border-radius: 10px; font-weight: 700; font-size: 13px; cursor: pointer; transition: 0.2s; }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 15px rgba(248, 113, 113, 0.4); }
    .stats-bar { max-width: 800px; margin: 24px auto 16px; padding: 0 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .stat-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 16px 10px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px; letter-spacing: 0.3px; }
    .stat-value { font-size: 22px; font-weight: 800; color: var(--text-main); }
    .stat-value.win { color: var(--win-color); text-shadow: 0 0 15px rgba(52, 211, 153, 0.4); }
    .stat-value.loss { color: var(--lose-color); text-shadow: 0 0 15px rgba(248, 113, 113, 0.4); }
    .stat-value.rate { color: var(--tai-color); text-shadow: 0 0 15px rgba(56, 189, 248, 0.4); }
    .table-wrapper { max-width: 800px; margin: 0 auto; padding: 0 16px; }
    .table-container { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); max-height: 70vh; overflow-y: auto; }
    .data-table { width: 100%; border-collapse: separate; border-spacing: 0; }
    .data-table th { background: #111827; color: var(--text-muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 16px 12px; text-align: center; border-bottom: 1px solid var(--border-color); position: sticky; top: 0; z-index: 10; }
    .data-table td { padding: 14px 12px; text-align: center; border-bottom: 1px solid var(--border-color); font-size: 14px; font-weight: 600; }
    .data-table tr:last-child td { border-bottom: none; }
    .data-table tr:hover { background: rgba(255, 255, 255, 0.02); }
    .row-next { background: rgba(14, 165, 233, 0.08); border-left: 4px solid var(--tai-color); }
    .row-next.recovery { background: rgba(251, 146, 60, 0.1); border-left: 4px solid var(--recovery-color); }
    .badge { display: inline-block; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; min-width: 70px; text-align: center; }
    .badge-tai { background: var(--tai-bg); color: var(--tai-color); border: 1px solid rgba(56, 189, 248, 0.3); box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); }
    .badge-xiu { background: var(--xiu-bg); color: var(--xiu-color); border: 1px solid rgba(244, 114, 182, 0.3); box-shadow: 0 0 10px rgba(244, 114, 182, 0.2); }
    .badge-empty { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); }
    .recovery-badge { display: inline-block; margin-left: 6px; padding: 2px 8px; border-radius: 8px; font-size: 10px; font-weight: 800; background: var(--recovery-bg); color: var(--recovery-color); border: 1px solid var(--recovery-color); box-shadow: 0 0 10px rgba(251, 146, 60, 0.3); animation: pulse 1.5s infinite; letter-spacing: 0.5px; }
    .status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; padding: 6px 14px; border-radius: 20px; }
    .st-win { background: var(--win-bg); color: var(--win-color); border: 1px solid rgba(52, 211, 153, 0.3); }
    .st-lose { background: var(--lose-bg); color: var(--lose-color); border: 1px solid rgba(248, 113, 113, 0.3); }
    .st-wait { background: var(--wait-bg); color: var(--wait-color); border: 1px solid rgba(251, 191, 36, 0.3); animation: pulse 1.5s infinite; }
    .st-recover { background: var(--recovery-bg); color: var(--recovery-color); border: 1px solid var(--recovery-color); animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .dice-text { font-size: 11px; color: var(--text-muted); display: block; margin-top: 4px; font-weight: 500; }
    .conf-badge { font-size: 11px; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 2px 8px; border-radius: 10px; margin-top: 4px; display: inline-block; font-weight: 700; }
    .conf-badge.high { color: #34d399; background: rgba(52, 211, 153, 0.15); box-shadow: 0 0 10px rgba(52, 211, 153, 0.2); }
    .loading { text-align: center; padding: 40px; color: var(--tai-color); font-weight: 600; }
    .prediction-bar { max-width: 800px; margin: 0 auto 16px; padding: 0 16px; }
    .prediction-box { background: linear-gradient(135deg, rgba(56, 189, 248, 0.15), rgba(236, 72, 153, 0.15)); border: 1px solid var(--tai-color); border-radius: 14px; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 0 20px rgba(56, 189, 248, 0.2); }
    .prediction-box .label { font-size: 12px; color: var(--text-muted); font-weight: 700; text-transform: uppercase; }
    .prediction-box .value { font-size: 20px; font-weight: 800; }
    .prediction-box .value.tai { color: var(--tai-color); text-shadow: 0 0 15px rgba(56, 189, 248, 0.6); }
    .prediction-box .value.xiu { color: var(--xiu-color); text-shadow: 0 0 15px rgba(244, 114, 182, 0.6); }
    .prediction-box .pattern { font-family: monospace; font-size: 12px; color: var(--text-muted); letter-spacing: 1px; }
    @media (max-width: 500px) {
        .data-table th, .data-table td { padding: 10px 6px; font-size: 12px; }
        .badge { padding: 4px 8px; font-size: 11px; min-width: 50px; }
        .header-title { font-size: 18px; }
        .time-update { display: none; }
        .stats-bar { grid-template-columns: repeat(2, 1fr); }
        .stat-value { font-size: 18px; }
        .prediction-box { flex-direction: column; gap: 8px; text-align: center; }
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-title">LE MINH <span>MD5</span></div>
    <div class="header-actions">
        <div class="time-update" id="time-update">--:--:--</div>
        <button class="btn-refresh" onclick="fetchData()">↻</button>
        <button class="btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>

<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng phiên</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Số phiên Tài</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Số phiên Xỉu</div><div class="stat-value loss" id="stat-lose">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ Tài</div><div class="stat-value rate" id="stat-rate">0%</div></div>
</div>

<div class="prediction-bar">
    <div class="prediction-box">
        <div>
            <div class="label">Dự đoán phiên tới</div>
            <div class="value" id="pred-value">--</div>
        </div>
        <div style="text-align:right">
            <div class="label">Mẫu 13 phiên gần nhất</div>
            <div class="pattern" id="pred-pattern">--</div>
        </div>
    </div>
</div>

<div class="table-wrapper">
    <div class="table-container">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Phiên</th>
                    <th>Thống kê</th>
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
let isResetting = false;
let lastPrediction = null;

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

async function fetchPrediction() {
    try {
        const r = await fetch('/lc79md5', { cache: 'no-store' });
        const data = await r.json();
        if (data.du_doan) {
            lastPrediction = data;
            const predEl = document.getElementById('pred-value');
            predEl.innerText = data.du_doan;
            predEl.className = 'value ' + (data.du_doan === 'Tài' ? 'tai' : 'xiu');
            document.getElementById('pred-pattern').innerText = data.lich_su || '--';
        } else {
            document.getElementById('pred-value').innerText = data.thong_bao || '--';
            document.getElementById('pred-value').className = 'value';
            document.getElementById('pred-pattern').innerText = '--';
        }
    } catch (e) { console.error("Lỗi dự đoán:", e); }
}

async function fetchData() {
    if (isResetting) return;
    try {
        const r = await fetch('/api/history', { cache: 'no-store' });
        const data = await r.json();
        const now = new Date();
        document.getElementById('time-update').innerText = now.toLocaleTimeString('vi-VN');
        renderTable(data.rows || [], data.stats || {});
        await fetchPrediction();
    } catch (e) { console.error("Lỗi tải dữ liệu:", e); }
}

function renderTable(rows, stats) {
    const tbody = document.getElementById('table-body');
    animateNumber(document.getElementById('stat-total'), stats.total || 0);
    animateNumber(document.getElementById('stat-win'), stats.tai || 0);
    animateNumber(document.getElementById('stat-lose'), stats.xiu || 0);
    const rate = stats.total > 0 ? (stats.tai / stats.total) * 100 : 0;
    animateNumber(document.getElementById('stat-rate'), Math.round(rate), '%');

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading">Không có dữ liệu. Hãy đợi phiên mới.</td></tr>';
        return;
    }
    let html = '';
    rows.forEach((row) => {
        const resultHtml = row.result === 'Tài'
            ? '<span class="badge badge-tai">TÀI</span>'
            : row.result === 'Xỉu'
                ? '<span class="badge badge-xiu">XỈU</span>'
                : '<span class="badge badge-empty">-</span>';
        let diceDisplay = '';
        if (row.dice && row.dice !== '? + ? + ?') {
            const p = row.dice.split(' + ').map(Number);
            const sum = p.length === 3 && p.every(Number.isFinite) ? ` (${p.reduce((a,b)=>a+b,0)})` : '';
            diceDisplay = `<span class="dice-text">${row.dice}${sum}</span>`;
        }
        const details = `<div style="display:flex;flex-direction:column;align-items:center">${resultHtml}${diceDisplay}</div>`;
        const neutral = '<span class="badge badge-empty">Thống kê</span>';
        html += `<tr><td>#${row.phien}</td><td>${neutral}</td><td>${details}</td><td><span class="status" style="color:var(--text-muted)">Đã ghi nhận</span></td></tr>`;
    });
    tbody.innerHTML = html;
}

async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', text: "Toàn bộ lịch sử hiển thị sẽ bị xoá và bắt đầu lại từ đầu!",
        icon: 'warning', background: '#1e293b', color: '#f8fafc',
        showCancelButton: true, confirmButtonColor: '#0ea5e9', cancelButtonColor: '#64748b',
        confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, background: '#1e293b', color: '#f8fafc', didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Thành công!', text: 'Đã đặt lại mốc thống kê lịch sử.', icon: 'success', background: '#1e293b', color: '#f8fafc', confirmButtonColor: '#0ea5e9' });
                    isResetting = false; fetchData();
                } else { throw new Error(data.message); }
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


# =====================================================================
# DATA FETCHER
# =====================================================================
def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(API_URL_MD5, timeout=5, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']:
                rows = []
                for item in data['list']:
                    res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
                    total = item.get('point', sum(dices))
                    rows.append({'phien': int(item['id']), 'result': res,
                                 'dice': dice_str, 'total': total})
                return rows, True
    except Exception as e:
        print(f"[API ERROR]: {e}")
    return [], False


# =====================================================================
# THUẬT TOÁN DỰ ĐOÁN THEO MẪU 13 KÝ TỰ
# =====================================================================
def get_prediction(valid_sessions):
    """
    Dựa trên 13 kết quả gần nhất, tra cứu PATTERN_MAP để dự đoán.
    Trả về (prediction, pattern_str, confidence).
    """
    if len(valid_sessions) < 13:
        return None, None, 0

    # Lấy 13 phiên gần nhất (đã sắp xếp tăng dần theo phiên)
    recent = valid_sessions[-13:]
    pattern = ''.join('T' if s['result'] == 'Tài' else 'X' for s in recent)
    prediction = PATTERN_MAP.get(pattern)
    if prediction is None:
        return None, pattern, 0

    # Độ tin cậy tạm tính: 100% nếu có trong bảng, có thể điều chỉnh
    confidence = 100
    return prediction, pattern, confidence


# =====================================================================
# THỐNG KÊ LỊCH SỬ TRUNG LẬP
# =====================================================================
def get_groups(results):
    if not results:
        return []
    groups = []
    current = results[0]
    count = 1
    for value in results[1:]:
        if value == current:
            count += 1
        else:
            groups.append(count)
            current = value
            count = 1
    groups.append(count)
    return groups


def _load_history():
    global RESET_ID
    raw_rows, success = fetch_sessions()
    if not success and not HISTORY_CACHE:
        return None, False
    for row in raw_rows:
        HISTORY_CACHE[row['phien']] = row
    for key in [key for key in HISTORY_CACHE if key < RESET_ID]:
        del HISTORY_CACHE[key]
    valid = sorted(HISTORY_CACHE.values(), key=lambda item: item['phien'])
    return valid, True


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    try:
        valid, success = _load_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'tai': 0, 'xiu': 0}})

        rows = []
        for item in reversed(valid[-200:]):
            rows.append({
                'phien': item['phien'],
                'result': item['result'],
                'dice': item['dice'],
            })
        tai_count = sum(1 for item in valid if item['result'] == 'Tài')
        xiu_count = sum(1 for item in valid if item['result'] == 'Xỉu')
        return jsonify({
            'rows': rows,
            'stats': {'total': len(valid), 'tai': tai_count, 'xiu': xiu_count},
            'mode': 'pattern_prediction_13',
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/api/predict')
def predict():
    try:
        valid, success = _load_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'}), 400
        last = valid[-1]
        prediction, pattern, confidence = get_prediction(valid)
        return jsonify({
            'last_phien': last['phien'],
            'last_result': last['result'],
            'last_dice': last['dice'],
            'prediction': prediction,
            'confidence': confidence,
            'pattern': pattern,
            'total_sessions': len(valid),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/lc79')
def lc79():
    try:
        valid, success = _load_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'}), 400
        last = valid[-1]
        results = [item['result'] for item in reversed(valid)]
        groups = get_groups(results)
        prediction, pattern, confidence = get_prediction(valid)
        return jsonify({
            'Id': 'le minh',
            'Phien': str(last['phien']),
            'Ket_qua': last['result'].lower(),
            'Lich_su': '-' + '-'.join(str(value) for value in groups[:4]),
            'Du_doan': prediction,
            'Do_tin_cay': confidence if prediction else None,
            'Mau_13': pattern,
            'Thong_bao': 'Dự đoán dựa trên mẫu 13 kết quả gần nhất.' if prediction else 'Mẫu chưa có trong bảng tra cứu.',
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/lc79md5')
def lc79md5():
    try:
        valid, success = _load_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'}), 400
        last = valid[-1]
        dice_parts = last['dice'].split(' + ')
        dice_short = '-'.join(dice_parts) if len(dice_parts) == 3 else last['dice']
        results = [item['result'] for item in reversed(valid)]
        groups = get_groups(results)
        prediction, pattern, confidence = get_prediction(valid)
        return jsonify({
            'id': '@cskhleminh',
            'phien': str(last['phien']),
            'ket_qua': f"{last['result'].lower()} {dice_short}",
            'du_doan': prediction,
            'do_tin_cay': confidence if prediction else None,
            'lich_su': pattern if pattern else ('-' + '-'.join(str(value) for value in groups[:4])),
            'mau_13': pattern,
            'thong_bao': 'Dự đoán  gần nhất.' if prediction else 'Mẫu chưa có trong bảng tra cứu.',
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE
    try:
        raw_rows, success = fetch_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng, không thể xác nhận mốc Reset'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
