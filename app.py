import os
import math
import traceback
from datetime import datetime
from collections import defaultdict, Counter
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =====================================================================
# API GỐC
# =====================================================================
API_URL_PRIMARY = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
API_URL_FALLBACK = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web"

HISTORY_CACHE = {}
RESET_ID = 0

# =====================================================================
# BẢNG TRA CỨU MẪU 13 KÝ TỰ
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
# FETCH SESSIONS
# =====================================================================
def fetch_sessions():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
        'Origin': 'https://tele68.com',
        'Referer': 'https://tele68.com/',
    }
    for url in (API_URL_PRIMARY, API_URL_FALLBACK):
        try:
            r = requests.get(url, timeout=6, headers=headers)
            if r.status_code != 200:
                continue
            data = r.json()
            if 'list' in data and data['list']:
                rows = []
                for item in data['list']:
                    res = "Tài" if item.get('resultTruyenThong') == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
                    total = item.get('point', sum(dices))
                    rows.append({'phien': int(item['id']), 'result': res,
                                 'dice': dice_str, 'total': total})
                return rows, True
        except Exception as e:
            print(f"[API ERROR {url}]: {e}")
    return [], False


# =====================================================================
# THUẬT TOÁN CONFIDENCE THỰC TẾ
# =====================================================================
def _streak_score(pattern: str) -> float:
    """
    Điểm dựa trên streak dài nhất trong chuỗi 13 ký tự.
    Streak càng dài => mẫu càng "rõ ràng" => tin cậy cao hơn.
    Trả về 0..1
    """
    if not pattern:
        return 0.0
    max_streak = 1
    cur = 1
    for i in range(1, len(pattern)):
        if pattern[i] == pattern[i - 1]:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 1
    # Streak 13 => 1.0, streak 7 => ~0.5
    return min(1.0, max_streak / 13.0)


def _balance_score(pattern: str) -> float:
    """
    Điểm dựa trên độ lệch T/X trong 13 phiên.
    Lệch càng nhiều => mẫu càng đặc biệt => tin cậy cao.
    Lệch 0 (7-6) => 0.0 ; Lệch 13 (13-0) => 1.0
    """
    if not pattern:
        return 0.0
    t = pattern.count('T')
    x = len(pattern) - t
    diff = abs(t - x)
    return diff / len(pattern)


def _backtest_confidence(pattern: str, valid_sessions: list) -> tuple:
    """
    Backtest mẫu 13 ký tự trên toàn bộ lịch sử.
    Tại mỗi vị trí i (>=12), lấy 13 phiên trước đó làm mẫu,
    so khớp với pattern hiện tại. Nếu khớp, xem kết quả phiên i+1
    có trùng với dự đoán PATTERN_MAP[pattern] không.
    Trả về (tỷ_lệ_đúng, số_lần_xuất_hiện).
    """
    if len(valid_sessions) < 14:
        return None, 0

    expected = PATTERN_MAP.get(pattern)
    if expected is None:
        return None, 0

    results = [s['result'] for s in valid_sessions]
    hits = 0
    total = 0
    n = len(results)
    plen = len(pattern)

    for i in range(plen, n):
        window = ''.join('T' if results[j] == 'Tài' else 'X' for j in range(i - plen, i))
        if window == pattern:
            total += 1
            actual = results[i]
            if actual == expected:
                hits += 1

    if total == 0:
        return None, 0
    return hits / total, total


def compute_confidence(pattern: str, valid_sessions: list) -> tuple:
    """
    Tính độ tin cậy thực tế dựa trên nhiều yếu tố:
      - backtest (nếu có dữ liệu lịch sử)
      - streak score
      - balance score
    Trả về (confidence_percent, breakdown_dict).
    """
    if not pattern:
        return 0, {}

    streak = _streak_score(pattern)
    balance = _balance_score(pattern)
    backtest_rate, occurrences = _backtest_confidence(pattern, valid_sessions)

    # Trọng số
    # - Backtest có dữ liệu: weight cao (0.55)
    # - Streak: 0.25
    # - Balance: 0.20
    if backtest_rate is not None and occurrences >= 3:
        conf = (backtest_rate * 0.55) + (streak * 0.25) + (balance * 0.20)
        method = 'backtest'
    elif backtest_rate is not None:
        conf = (backtest_rate * 0.45) + (streak * 0.30) + (balance * 0.25)
        method = 'backtest_low_sample'
    else:
        # Không có backtest => dựa vào streak + balance
        conf = (streak * 0.60) + (balance * 0.40)
        method = 'heuristic'

    # Scale về khoảng 50% - 100% (thuật toán dự đoán luôn có ít nhất 50% cơ sở)
    conf_pct = 50 + conf * 50
    conf_pct = max(50, min(100, conf_pct))

    breakdown = {
        'method': method,
        'streak_score': round(streak, 3),
        'balance_score': round(balance, 3),
        'backtest_rate': round(backtest_rate, 3) if backtest_rate is not None else None,
        'occurrences': occurrences,
        'final_percent': round(conf_pct, 1),
    }
    return round(conf_pct, 1), breakdown


# =====================================================================
# LOAD HISTORY
# =====================================================================
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


def get_prediction(valid_sessions):
    """
    Trả về (prediction, pattern, confidence_percent, breakdown).
    """
    if len(valid_sessions) < 13:
        return None, None, 0, {}
    recent = valid_sessions[-13:]
    pattern = ''.join('T' if s['result'] == 'Tài' else 'X' for s in recent)
    prediction = PATTERN_MAP.get(pattern)
    if prediction is None:
        return None, pattern, 0, {}
    confidence, breakdown = compute_confidence(pattern, valid_sessions)
    return prediction, pattern, confidence, breakdown


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
        --tai-color: #38bdf8; --xiu-color: #f472b6;
        --win-color: #34d399; --lose-color: #f87171;
        --low: #f87171; --mid: #fbbf24; --high: #34d399;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: var(--text-main); min-height: 100vh; padding-bottom: 40px; }
    .header { background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-color); padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
    .header-title { font-size: 22px; font-weight: 800; color: #38bdf8; display: flex; align-items: center; gap: 10px; }
    .header-title span { font-size: 11px; background: linear-gradient(135deg, #38bdf8, #ec4899); color: #fff; padding: 4px 12px; border-radius: 20px; font-weight: 800; letter-spacing: 1px; }
    .header-actions { display: flex; gap: 12px; align-items: center; }
    .time-update { font-size: 12px; color: var(--text-muted); font-weight: 600; }
    .btn-refresh { background: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); width: 38px; height: 38px; border-radius: 10px; cursor: pointer; }
    .btn-reset { background: rgba(248, 113, 113, 0.2); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 8px 16px; border-radius: 10px; font-weight: 700; font-size: 13px; cursor: pointer; }
    .stats-bar { max-width: 800px; margin: 24px auto 16px; padding: 0 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .stat-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 16px 10px; text-align: center; }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px; }
    .stat-value { font-size: 22px; font-weight: 800; }
    .stat-value.win { color: var(--win-color); }
    .stat-value.loss { color: var(--lose-color); }
    .stat-value.rate { color: var(--tai-color); }
    .prediction-bar { max-width: 800px; margin: 0 auto 16px; padding: 0 16px; }
    .prediction-box { background: linear-gradient(135deg, rgba(56,189,248,0.15), rgba(236,72,153,0.15)); border: 1px solid var(--tai-color); border-radius: 14px; padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
    .prediction-box .col { min-width: 120px; }
    .prediction-box .label { font-size: 11px; color: var(--text-muted); font-weight: 700; text-transform: uppercase; margin-bottom: 4px; }
    .prediction-box .value { font-size: 22px; font-weight: 800; }
    .prediction-box .value.tai { color: var(--tai-color); }
    .prediction-box .value.xiu { color: var(--xiu-color); }
    .prediction-box .value.none { color: var(--text-muted); font-size: 14px; }
    .prediction-box .pattern { font-family: monospace; font-size: 13px; color: #38bdf8; letter-spacing: 2px; font-weight: 700; }
    .conf-bar { width: 100%; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; margin-top: 6px; }
    .conf-fill { height: 100%; transition: width 0.5s ease; border-radius: 4px; }
    .conf-fill.low { background: linear-gradient(90deg, #f87171, #fb923c); }
    .conf-fill.mid { background: linear-gradient(90deg, #fbbf24, #facc15); }
    .conf-fill.high { background: linear-gradient(90deg, #34d399, #38bdf8); }
    .conf-text { font-size: 18px; font-weight: 800; }
    .conf-text.low { color: var(--low); }
    .conf-text.mid { color: var(--mid); }
    .conf-text.high { color: var(--high); }
    .breakdown { font-size: 10px; color: var(--text-muted); margin-top: 4px; font-family: monospace; }
    .table-wrapper { max-width: 800px; margin: 0 auto; padding: 0 16px; }
    .table-container { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 16px; max-height: 60vh; overflow-y: auto; }
    .data-table { width: 100%; border-collapse: separate; border-spacing: 0; }
    .data-table th { background: #111827; color: var(--text-muted); font-size: 11px; font-weight: 700; text-transform: uppercase; padding: 14px 10px; text-align: center; position: sticky; top: 0; z-index: 10; }
    .data-table td { padding: 12px 10px; text-align: center; border-bottom: 1px solid var(--border-color); font-size: 14px; font-weight: 600; }
    .badge { display: inline-block; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; min-width: 60px; }
    .badge-tai { background: rgba(56,189,248,0.15); color: var(--tai-color); border: 1px solid rgba(56,189,248,0.3); }
    .badge-xiu { background: rgba(244,114,182,0.15); color: var(--xiu-color); border: 1px solid rgba(244,114,182,0.3); }
    .dice-text { font-size: 11px; color: var(--text-muted); display: block; margin-top: 4px; }
    .loading { text-align: center; padding: 40px; color: var(--tai-color); font-weight: 600; }
    @media (max-width: 500px) {
        .data-table th, .data-table td { padding: 8px 4px; font-size: 12px; }
        .header-title { font-size: 18px; }
        .time-update { display: none; }
        .stats-bar { grid-template-columns: repeat(2, 1fr); }
        .stat-value { font-size: 18px; }
        .prediction-box { flex-direction: column; text-align: center; }
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
        <div class="col">
            <div class="label">Dự đoán phiên tới</div>
            <div class="value none" id="pred-value">Đang tải...</div>
        </div>
        <div class="col">
            <div class="label">Mẫu 13 phiên</div>
            <div class="pattern" id="pred-pattern">--</div>
        </div>
        <div class="col" style="flex:1;min-width:180px">
            <div class="label">Độ tin cậy</div>
            <div class="conf-text low" id="conf-text">--%</div>
            <div class="conf-bar"><div class="conf-fill low" id="conf-fill" style="width:0%"></div></div>
            <div class="breakdown" id="conf-breakdown"></div>
        </div>
    </div>
</div>

<div class="table-wrapper">
    <div class="table-container">
        <table class="data-table">
            <thead>
                <tr><th>Phiên</th><th>Kết quả</th></tr>
            </thead>
            <tbody id="table-body">
                <tr><td colspan="2" class="loading">Đang kết nối Server...</td></tr>
            </tbody>
        </table>
    </div>
</div>

<script>
let isResetting = false;

function animateNumber(el, target, suffix = '') {
    const start = parseInt(el.innerText.replace(/[^0-9]/g, '')) || 0;
    if (start === target) { el.innerText = target + suffix; return; }
    const startTime = performance.now();
    function update(t) {
        const p = Math.min((t - startTime) / 500, 1);
        const ease = 1 - Math.pow(1 - p, 3);
        el.innerText = Math.floor(start + (target - start) * ease) + suffix;
        if (p < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

function confClass(p) {
    if (p >= 80) return 'high';
    if (p >= 70) return 'mid';
    return 'low';
}

async function fetchPrediction() {
    try {
        const r = await fetch('/lc79md5', { cache: 'no-store' });
        const data = await r.json();
        const predEl = document.getElementById('pred-value');
        const patEl = document.getElementById('pred-pattern');
        const confText = document.getElementById('conf-text');
        const confFill = document.getElementById('conf-fill');
        const breakdown = document.getElementById('conf-breakdown');

        if (data.du_doan) {
            predEl.innerText = data.du_doan;
            predEl.className = 'value ' + (data.du_doan === 'Tài' ? 'tai' : 'xiu');

            const pct = data.do_tin_cay || 0;
            const cls = confClass(pct);
            confText.innerText = pct.toFixed(1) + '%';
            confText.className = 'conf-text ' + cls;
            confFill.className = 'conf-fill ' + cls;
            confFill.style.width = pct + '%';

            if (data.breakdown) {
                const b = data.breakdown;
                const parts = [];
                if (b.backtest_rate !== null) parts.push('BT:' + (b.backtest_rate*100).toFixed(0) + '%(' + b.occurrences + ')');
                parts.push('S:' + b.streak_score);
                parts.push('B:' + b.balance_score);
                breakdown.innerText = parts.join(' | ');
            } else {
                breakdown.innerText = '';
            }
        } else {
            predEl.innerText = data.thong_bao || 'Mẫu chưa có';
            predEl.className = 'value none';
            confText.innerText = '--%';
            confText.className = 'conf-text low';
            confFill.style.width = '0%';
            breakdown.innerText = '';
        }
        patEl.innerText = data.mau_13 || '--';
    } catch (e) { console.error(e); }
}

async function fetchData() {
    if (isResetting) return;
    try {
        const r = await fetch('/api/history', { cache: 'no-store' });
        const data = await r.json();
        document.getElementById('time-update').innerText = new Date().toLocaleTimeString('vi-VN');
        renderTable(data.rows || [], data.stats || {});
        await fetchPrediction();
    } catch (e) { console.error(e); }
}

function renderTable(rows, stats) {
    const tbody = document.getElementById('table-body');
    animateNumber(document.getElementById('stat-total'), stats.total || 0);
    animateNumber(document.getElementById('stat-win'), stats.tai || 0);
    animateNumber(document.getElementById('stat-lose'), stats.xiu || 0);
    const rate = stats.total > 0 ? (stats.tai / stats.total) * 100 : 0;
    animateNumber(document.getElementById('stat-rate'), Math.round(rate), '%');

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="2" class="loading">Không có dữ liệu.</td></tr>';
        return;
    }
    let html = '';
    rows.forEach((row) => {
        const badge = row.result === 'Tài'
            ? '<span class="badge badge-tai">TÀI</span>'
            : '<span class="badge badge-xiu">XỈU</span>';
        let diceDisplay = '';
        if (row.dice && row.dice !== '? + ? + ?') {
            const p = row.dice.split(' + ').map(Number);
            const sum = p.length === 3 && p.every(Number.isFinite) ? ` (${p.reduce((a,b)=>a+b,0)})` : '';
            diceDisplay = `<span class="dice-text">${row.dice}${sum}</span>`;
        }
        html += `<tr><td>#${row.phien}</td><td><div style="display:flex;flex-direction:column;align-items:center">${badge}${diceDisplay}</div></td></tr>`;
    });
    tbody.innerHTML = html;
}

async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', text: "Toàn bộ lịch sử hiển thị sẽ bị xoá!",
        icon: 'warning', background: '#1e293b', color: '#f8fafc',
        showCancelButton: true, confirmButtonColor: '#0ea5e9', cancelButtonColor: '#64748b',
        confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, background: '#1e293b', color: '#f8fafc', didOpen: () => Swal.showLoading() });
            try {
                const res = await fetch('/api/reset', { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}' });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Thành công!', icon: 'success', background: '#1e293b', color: '#f8fafc', confirmButtonColor: '#0ea5e9' });
                    isResetting = false; fetchData();
                } else throw new Error(data.message);
            } catch (error) {
                Swal.fire({ title: 'Lỗi!', text: error.message, icon: 'error', background: '#1e293b', color: '#f8fafc' });
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
# ROUTES
# =====================================================================
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
        rows = [{'phien': i['phien'], 'result': i['result'], 'dice': i['dice']}
                for i in reversed(valid[-200:])]
        tai_count = sum(1 for i in valid if i['result'] == 'Tài')
        xiu_count = sum(1 for i in valid if i['result'] == 'Xỉu')
        return jsonify({
            'rows': rows,
            'stats': {'total': len(valid), 'tai': tai_count, 'xiu': xiu_count},
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

        prediction, pattern, confidence, breakdown = get_prediction(valid)

        return jsonify({
            'id': '@cskhleminh',
            'phien': str(last['phien']),
            'ket_qua': f"{last['result'].lower()} {dice_short}",
            'du_doan': prediction,
            'do_tin_cay': f"{confidence}%" if prediction else None,
            'do_tin_cay_raw': confidence,
            'mau_13': pattern,
            'thuat_toan': 'pattern_13_chars_weighted',
            'breakdown': breakdown,
            'thong_bao': 'Dự đoán dựa trên mẫu 13 kết quả + backtest + streak + balance.'
                         if prediction else 'Mẫu 13 phiên chưa có trong bảng tra cứu.',
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
        prediction, pattern, confidence, breakdown = get_prediction(valid)
        return jsonify({
            'Id': 'le minh',
            'Phien': str(last['phien']),
            'Ket_qua': last['result'].lower(),
            'Du_doan': prediction,
            'Do_tin_cay': f"{confidence}%" if prediction else None,
            'Do_tin_cay_raw': confidence,
            'Mau_13': pattern,
            'Breakdown': breakdown,
            'Thong_bao': 'Dự đoán + backtest + streak + balance.'
                         if prediction else 'Mẫu chưa có trong bảng tra cứu.',
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
        return jsonify({'status': 'error', 'message': 'Lỗi mạng'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
