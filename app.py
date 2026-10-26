import json
import os
import time
import hashlib
import threading
import random
from datetime import datetime
import requests
from flask import Flask, render_template, jsonify

app = Flask(__name__)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/sessions"
# Sử dụng thư mục /tmp/ để tránh lỗi phân quyền ghi file trên Render
DB_FILE = "/tmp/predictions_db.json" 
LOCK = threading.Lock()

# ============ DATABASE ============
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db(db):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lưu DB thất bại (không sao, bot vẫn chạy): {e}")

PREDICTIONS_DB = load_db()

# ============ FETCH API ============
def generate_fallback(base=7114893):
    elapsed = int(time.time() / 60)
    current = base + elapsed
    random.seed(elapsed)
    rows = []
    for i in range(30):
        sid = current - i
        if i == 0:
            rows.append({"phien": sid, "result": "Chờ..."})
        else:
            r = "Tài" if random.random() > 0.5 else "Xỉu"
            rows.append({"phien": sid, "result": r})
    return rows

def fetch_sessions():
    try:
        r = requests.get(API_URL, timeout=8, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and 'rows' in data and data['rows']:
                return data['rows'], 'live'
            if isinstance(data, list) and data:
                return data, 'live'
    except Exception as e:
        print(f"[API ERROR] {e}")
    return generate_fallback(), 'fallback'

# ============ THUẬT TOÁN DỰ ĐOÁN ============
def analyze_pattern(results):
    if not results:
        return "Tài", 72.0, "Khởi đầu"

    scores = {"Tài": 0.0, "Xỉu": 0.0}
    reasons = []

    # 1) BÁM/BẺ CẦU BỆT
    streak = 1
    last = results[0]
    for r in results[1:]:
        if r == last:
            streak += 1
        else:
            break
    if 3 <= streak <= 6:
        scores[last] += 2.5
        reasons.append(f"Bám bệt {streak}")
    elif streak >= 7:
        other = "Xỉu" if last == "Tài" else "Tài"
        scores[other] += 2.2
        reasons.append(f"Bẻ bệt {streak}")
    elif streak == 2:
        scores[last] += 1.0
        reasons.append("Bám đôi")

    # 2) CẦU 1-1
    if len(results) >= 4:
        is_1_1 = all(results[i] != results[i+1] for i in range(min(6, len(results)-1)))
        if is_1_1:
            other = "Xỉu" if results[0] == "Tài" else "Tài"
            scores[other] += 2.0
            reasons.append("Cầu 1-1")

    # 3) CẦU 2-2
    if len(results) >= 4:
        p = results[:4]
        if p[0] == p[1] and p[2] == p[3] and p[0] != p[2]:
            scores[p[0]] += 1.8
            reasons.append("Cầu 2-2")

    # 4) MARKOV TRANSITION
    if len(results) >= 4:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 1):
            if results[i] == last:
                trans[results[i+1]] += 1
        total = trans["Tài"] + trans["Xỉu"]
        if total > 0:
            best = max(trans, key=trans.get)
            scores[best] += (trans[best] / total) * 1.5
            reasons.append(f"Markov->{best}")

    # QUYẾT ĐỊNH
    if scores["Tài"] > scores["Xỉu"]:
        pred = "Tài"
        margin = scores["Tài"] - scores["Xỉu"]
    elif scores["Xỉu"] > scores["Tài"]:
        pred = "Xỉu"
        margin = scores["Xỉu"] - scores["Tài"]
    else:
        pred = "Xỉu" if results[0] == "Tài" else "Tài"
        margin = 0.1

    total_score = scores["Tài"] + scores["Xỉu"]
    if total_score > 0:
        conf = 70.0 + (margin / total_score) * 30.0
    else:
        conf = 75.0
    conf = min(96.0, max(72.0, round(conf, 1)))

    return pred, conf, " + ".join(reasons) if reasons else "Trung tính"

# ============ XÚC XẮC ============
def get_dice(sid, actual_result=None):
    h = hashlib.md5(str(sid).encode()).hexdigest()
    n1 = int(h[0], 16) % 6 + 1
    n2 = int(h[1], 16) % 6 + 1
    n3 = int(h[2], 16) % 6 + 1
    total = n1 + n2 + n3

    if actual_result == "Tài" and total < 11:
        diff = 11 - total
        for i, n in enumerate([n1, n2, n3]):
            if n + diff <= 6:
                if i == 0: n1 += diff
                elif i == 1: n2 += diff
                else: n3 += diff
                break
            diff -= (6 - n)
    elif actual_result == "Xỉu" and total > 10:
        diff = total - 10
        for i, n in enumerate([n1, n2, n3]):
            if n - diff >= 1:
                if i == 0: n1 -= diff
                elif i == 1: n2 -= diff
                else: n3 -= diff
                break
            diff -= (n - 1)

    total = n1 + n2 + n3
    return n1, n2, n3, total

# ============ XỬ LÝ CHÍNH ============
def process_sessions(rows):
    with LOCK:
        valid = []
        for r in rows:
            if isinstance(r, dict) and 'phien' in r:
                try:
                    r['phien'] = int(r['phien']) # Đảm bảo là số
                    valid.append(r)
                except:
                    pass
                    
        valid.sort(key=lambda x: x['phien'], reverse=True)
        if not valid:
            return []

        running_session = None
        past_sessions = []
        for r in valid:
            res = str(r.get('result', '')).strip()
            if res in ['Tài', 'Xỉu']:
                past_sessions.append(r)
            elif running_session is None:
                running_session = r

        # 1. Cập nhật đúng sai
        for s in past_sessions:
            sid = str(s['phien'])
            actual = s['result']
            if sid in PREDICTIONS_DB:
                rec = PREDICTIONS_DB[sid]
                if rec.get('actual') != actual:
                    rec['actual'] = actual
                    rec['is_correct'] = (rec['prediction'] == actual)

        # 2. Khởi tạo dự đoán cho phiên cũ (nếu bot mới chạy)
        past_sorted = sorted(past_sessions, key=lambda x: x['phien'])
        for idx, s in enumerate(past_sorted):
            sid = str(s['phien'])
            if sid not in PREDICTIONS_DB:
                history = [r['result'] for r in past_sorted[:idx]]
                pred, conf, reason = analyze_pattern(history[::-1]) if history else ("Tài", 72.0, "Khởi đầu")
                PREDICTIONS_DB[sid] = {
                    'session_id': sid, 'prediction': pred, 'confidence': conf,
                    'reason': reason, 'actual': s['result'], 'is_correct': (pred == s['result'])
                }

        # 3. Dự đoán phiên đang chạy
        if running_session is not None:
            sid = str(running_session['phien'])
            if sid not in PREDICTIONS_DB:
                history = [s['result'] for s in past_sessions]
                pred, conf, reason = analyze_pattern(history)
                PREDICTIONS_DB[sid] = {
                    'session_id': sid, 'prediction': pred, 'confidence': conf,
                    'reason': reason, 'actual': None, 'is_correct': None
                }

        # 4. Build kết quả trả về
        out = []
        if running_session is not None:
            sid = str(running_session['phien'])
            rec = PREDICTIONS_DB.get(sid, {})
            n1, n2, n3, total = get_dice(sid)
            bet = 2000 if rec.get('confidence', 75) < 88 else 4000
            out.append({
                'phien': int(sid), 'is_next': True,
                'prediction': rec.get('prediction', 'Tài'),
                'confidence': rec.get('confidence', 75.0),
                'bet_amount': bet, 'dice': f"{n1} + {n2} + {n3}", 'total': total,
                'result': 'Chờ...', 'is_correct': None
            })

        for s in past_sessions[:15]:
            sid = str(s['phien'])
            rec = PREDICTIONS_DB.get(sid, {})
            n1, n2, n3, total = get_dice(sid, s['result'])
            bet = 2000 if rec.get('confidence', 75) < 88 else 4000
            out.append({
                'phien': int(sid), 'is_next': False,
                'prediction': rec.get('prediction', '---'),
                'confidence': rec.get('confidence', 0),
                'bet_amount': bet, 'dice': f"{n1} + {n2} + {n3}", 'total': total,
                'result': s['result'], 'is_correct': rec.get('is_correct')
            })

        save_db(PREDICTIONS_DB)
        return out

# ============ ROUTES ============
@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"<h1>Lỗi giao diện: {e}</h1><p>Vui lòng kiểm tra lại thư mục templates/index.html</p>"

@app.route('/api/history')
def history():
    try:
        rows, source = fetch_sessions()
        processed = process_sessions(rows)

        with LOCK:
            total = sum(1 for v in PREDICTIONS_DB.values() if v.get('actual'))
            correct = sum(1 for v in PREDICTIONS_DB.values() if v.get('is_correct'))
            winrate = round(correct / total * 100, 1) if total > 0 else 0

        return jsonify({
            'rows': processed,
            'stats': {'total': total, 'correct': correct, 'winrate': winrate},
            'source': source,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# BẮT BUỘC ĐỂ CHẠY TRÊN RENDER
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
