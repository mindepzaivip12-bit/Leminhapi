import json
import os
import time
import hashlib
import threading
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/sessions"
DB_FILE = "/tmp/predictions_db.json" 
LOCK = threading.Lock()

# ============ GIAO DIỆN HTML/CSS GỘP VÀO ĐÂY ============
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SICSUN BOT</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Montserrat', sans-serif; }
    body { background: radial-gradient(circle at top, #1a2332 0%, #0a0f17 100%); color: #e6edf3; min-height: 100vh; padding: 16px; display: flex; justify-content: center; }
    .app { width: 100%; max-width: 520px; }
    .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding: 0 6px; }
    .logo { display: flex; align-items: center; gap: 10px; }
    .logo h2 { font-size: 18px; letter-spacing: 1.5px; color: #58a6ff; }
    .pulse { width: 10px; height: 10px; border-radius: 50%; background: #3fb950; box-shadow: 0 0 10px #3fb950; animation: pulse 1.5s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
    .stats { text-align: right; }
    .stats #winrate { font-size: 18px; font-weight: 800; color: #3fb950; }
    .stats small { display: block; color: #8b949e; font-size: 11px; }
    .status-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding: 8px 12px; background: rgba(255,255,255,0.03); border-radius: 10px; font-size: 12px; color: #8b949e; }
    .badge { padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 11px; }
    .badge.live { background: rgba(63,185,80,0.15); color: #3fb950; }
    .badge.demo { background: rgba(210,153,34,0.15); color: #d29922; }
    .session-list { display: flex; flex-direction: column; gap: 12px; }
    .card { background: linear-gradient(135deg, #161b22 0%, #0d1117 100%); border: 1px solid #21262d; border-radius: 14px; padding: 14px 16px; display: flex; align-items: center; gap: 10px; transition: all 0.3s; position: relative; overflow: hidden; }
    .card::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: transparent; transition: background 0.3s; }
    .card.next { border-color: #58a6ff; box-shadow: 0 0 20px rgba(88,166,255,0.25); background: linear-gradient(135deg, #1a2332 0%, #0d1117 100%); }
    .card.next::before { background: #58a6ff; }
    .col.left { flex: 1.6; min-width: 0; }
    .col.mid { flex: 1; text-align: center; }
    .col.right { flex: 1; text-align: right; }
    .sid { font-size: 15px; font-weight: 800; color: #e6edf3; margin-bottom: 5px; }
    .botline { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 12px; margin-bottom: 4px; }
    .bot-label { color: #8b949e; }
    .bet { padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 800; letter-spacing: 0.3px; }
    .bet.tai { background: #1f6feb; color: #fff; }
    .bet.xiu { background: #d0356c; color: #fff; }
    .amt { color: #8b949e; font-size: 11px; }
    .conf { color: #6e7681; font-size: 11px; font-style: italic; }
    .pred { font-size: 17px; font-weight: 800; letter-spacing: 0.5px; margin-bottom: 3px; }
    .text-tai { color: #58a6ff; }
    .text-xiu { color: #f85149; }
    .dice { font-size: 13px; color: #c9d1d9; font-weight: 600; letter-spacing: 0.5px; }
    .sum { font-size: 11px; color: #6e7681; margin-top: 2px; }
    .stt { font-size: 13px; font-weight: 700; }
    .stt.ok { color: #3fb950; }
    .stt.err { color: #f85149; }
    .stt.waiting { color: #d29922; display: inline-flex; align-items: center; gap: 6px; justify-content: flex-end; }
    .stt.na { color: #6e7681; }
    .spin { width: 11px; height: 11px; border-radius: 50%; border: 2px solid #d29922; border-top-color: transparent; animation: spin 0.8s linear infinite; display: inline-block; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (max-width: 400px) { .pred { font-size: 15px; } .sid { font-size: 14px; } .dice { font-size: 12px; } }
    .loading { text-align: center; color: #8b949e; padding: 40px; }
</style>
</head>
<body>
<div class="app">
  <div class="header">
    <div class="logo">
      <span class="pulse"></span>
      <h2>SICSUN BOT</h2>
    </div>
    <div class="stats" id="stats">
      <span id="winrate">--%</span>
      <small id="total">0 phiên</small>
    </div>
  </div>

  <div class="status-bar">
    <span id="source-badge" class="badge">● LIVE</span>
    <span id="updated">Đang tải...</span>
  </div>

  <div class="session-list" id="session-list">
    <div class="loading">Đang tải dữ liệu phiên...</div>
  </div>
</div>

<script>
async function fetchData() {
  try {
    const r = await fetch('/api/history', { cache: 'no-store' });
    const data = await r.json();
    render(data);
  } catch (e) {
    document.getElementById('updated').textContent = 'Mất kết nối';
  }
}

function render(data) {
  const list = document.getElementById('session-list');
  const rows = data.rows || [];
  if (!rows.length) {
    list.innerHTML = '<div class="loading">Không có dữ liệu</div>';
    return;
  }

  const s = data.stats || {};
  document.getElementById('winrate').textContent = (s.winrate || 0) + '%';
  document.getElementById('total').textContent = (s.total || 0) + ' phiên';
  document.getElementById('winrate').style.color = s.winrate >= 70 ? '#3fb950' : s.winrate >= 50 ? '#d29922' : '#f85149';

  const badge = document.getElementById('source-badge');
  if (data.source === 'live') {
    badge.textContent = '● LIVE';
    badge.className = 'badge live';
  } else {
    badge.textContent = '● DEMO';
    badge.className = 'badge demo';
  }
  document.getElementById('updated').textContent = 'Cập nhật: ' + data.updated_at;

  list.innerHTML = '';
  rows.forEach(row => {
    const isTai = row.prediction === 'Tài';
    const betClass = isTai ? 'tai' : 'xiu';
    const textClass = isTai ? 'text-tai' : 'text-xiu';

    let status = '';
    if (row.is_next) {
      status = `<div class="stt waiting"><span class="spin"></span> Chờ KQ</div>`;
    } else if (row.is_correct === true) {
      status = `<div class="stt ok">Đúng cửa ✅</div>`;
    } else if (row.is_correct === false) {
      status = `<div class="stt err">Sai cửa ❌</div>`;
    } else {
      status = `<div class="stt na">—</div>`;
    }

    const card = document.createElement('div');
    card.className = 'card' + (row.is_next ? ' next' : '');
    card.innerHTML = `
      <div class="col left">
        <div class="sid">#${row.phien}</div>
        <div class="botline">
          <span class="bot-label">Bot:</span>
          <span class="bet ${betClass}">CƯỢC ${row.prediction.toUpperCase()}</span>
          <span class="amt">(${row.bet_amount.toLocaleString('vi-VN')}đ)</span>
        </div>
        <div class="conf">(Tin cậy: ${row.confidence}%)</div>
      </div>
      <div class="col mid">
        <div class="pred ${textClass}">${row.prediction.toUpperCase()}</div>
        <div class="dice">${row.dice}</div>
        <div class="sum">(${row.total})</div>
      </div>
      <div class="col right">${status}</div>
    `;
    list.appendChild(card);
  });
}

fetchData();
setInterval(fetchData, 5000);
</script>
</body>
</html>
"""
# =======================================================

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
    except Exception:
        pass

PREDICTIONS_DB = load_db()

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
        r = requests.get(API_URL, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and 'rows' in data and data['rows']:
                return data['rows'], 'live'
            if isinstance(data, list) and data:
                return data, 'live'
    except Exception as e:
        pass
    return generate_fallback(), 'fallback'

def analyze_pattern(results):
    if not results:
        return "Tài", 72.0, "Khởi đầu"
    scores = {"Tài": 0.0, "Xỉu": 0.0}
    reasons = []
    streak = 1
    last = results[0]
    for r in results[1:]:
        if r == last: streak += 1
        else: break
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

    if len(results) >= 4:
        is_1_1 = all(results[i] != results[i+1] for i in range(min(6, len(results)-1)))
        if is_1_1:
            other = "Xỉu" if results[0] == "Tài" else "Tài"
            scores[other] += 2.0
            reasons.append("Cầu 1-1")

    if len(results) >= 4:
        p = results[:4]
        if p[0] == p[1] and p[2] == p[3] and p[0] != p[2]:
            scores[p[0]] += 1.8
            reasons.append("Cầu 2-2")

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
    conf = 70.0 + (margin / total_score) * 30.0 if total_score > 0 else 75.0
    conf = min(96.0, max(72.0, round(conf, 1)))
    return pred, conf, " + ".join(reasons) if reasons else "Trung tính"

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
    return n1, n2, n3, n1+n2+n3

def process_sessions(rows):
    with LOCK:
        valid = []
        for r in rows:
            if isinstance(r, dict) and 'phien' in r:
                try:
                    r['phien'] = int(r['phien'])
                    valid.append(r)
                except: pass
        valid.sort(key=lambda x: x['phien'], reverse=True)
        if not valid: return []

        running_session = None
        past_sessions = []
        for r in valid:
            res = str(r.get('result', '')).strip()
            if res in ['Tài', 'Xỉu']:
                past_sessions.append(r)
            elif running_session is None:
                running_session = r

        for s in past_sessions:
            sid = str(s['phien'])
            actual = s['result']
            if sid in PREDICTIONS_DB:
                rec = PREDICTIONS_DB[sid]
                if rec.get('actual') != actual:
                    rec['actual'] = actual
                    rec['is_correct'] = (rec['prediction'] == actual)

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

        if running_session is not None:
            sid = str(running_session['phien'])
            if sid not in PREDICTIONS_DB:
                history = [s['result'] for s in past_sessions]
                pred, conf, reason = analyze_pattern(history)
                PREDICTIONS_DB[sid] = {
                    'session_id': sid, 'prediction': pred, 'confidence': conf,
                    'reason': reason, 'actual': None, 'is_correct': None
                }

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

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
