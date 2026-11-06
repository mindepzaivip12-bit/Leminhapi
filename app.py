import os
import random
import traceback
import time
import json
import hashlib
from datetime import datetime
from collections import Counter, defaultdict
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = (
    "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions"
    "?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
)

HISTORY_CACHE = {}
RESET_ID = 0
PREDICTION_LOG = {}
MAX_LOG_SIZE = 2000

LOG_FILE = "prediction_log.json"

# =====================================================================
# PERSISTENCE
# =====================================================================
def _load_log():
    global PREDICTION_LOG, RESET_ID
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        PREDICTION_LOG = {int(k): v for k, v in data.get('log', {}).items()}
        RESET_ID = int(data.get('reset_id', 0))
        print(f"[LOG] Loaded {len(PREDICTION_LOG)} predictions from file")
    except Exception as e:
        print(f"[LOG] Load failed: {e}")


def _save_log():
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'log': PREDICTION_LOG, 'reset_id': RESET_ID}, f)
    except Exception as e:
        print(f"[LOG] Save failed: {e}")


# =====================================================================
# DETERMINISTIC PREDICTOR v7
# =====================================================================
class MultiStrategyPredictor:

    @staticmethod
    def _deterministic_choice(options, seed_str):
        """Chọn deterministic dựa trên hash — cùng input = cùng output."""
        h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
        return options[h % len(options)]

    @staticmethod
    def _markov_order2(valid):
        if len(valid) < 15:
            return None, 0, 0
        trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
        for i in range(len(valid) - 2):
            key = (valid[i]['result'], valid[i + 1]['result'])
            trans[key][valid[i + 2]['result']] += 1
        key = (valid[-2]['result'], valid[-1]['result'])
        counts = trans[key]
        total = counts['Tài'] + counts['Xỉu']
        if total < 3:
            return None, 0, 0
        p_tai = counts['Tài'] / total
        if p_tai > 0.58:
            return 'Tài', int(p_tai * 100), 1.3
        elif p_tai < 0.42:
            return 'Xỉu', int((1 - p_tai) * 100), 1.3
        return None, 0, 0

    @staticmethod
    def _markov_order1(valid):
        if len(valid) < 8:
            return None, 0, 0
        trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
        for i in range(len(valid) - 1):
            trans[valid[i]['result']][valid[i + 1]['result']] += 1
        counts = trans[valid[-1]['result']]
        total = counts['Tài'] + counts['Xỉu']
        if total < 4:
            return None, 0, 0
        p_tai = counts['Tài'] / total
        if p_tai > 0.56:
            return 'Tài', int(p_tai * 100), 1.2
        elif p_tai < 0.44:
            return 'Xỉu', int((1 - p_tai) * 100), 1.2
        return None, 0, 0

    @staticmethod
    def _streak_break(valid):
        if len(valid) < 3:
            return None, 0, 0
        last = valid[-1]['result']
        streak = 1
        for i in range(len(valid) - 2, -1, -1):
            if valid[i]['result'] == last:
                streak += 1
            else:
                break
        if streak >= 3:
            opp = 'Xỉu' if last == 'Tài' else 'Tài'
            return opp, min(55 + streak * 7, 78), 1.0
        return None, 0, 0

    @staticmethod
    def _pattern_match(valid):
        if len(valid) < 15:
            return None, 0, 0
        results = [v['result'] for v in valid]
        best_hit, best_conf = None, 0
        for plen in (6, 5, 4, 3):
            if len(results) < plen + 4:
                continue
            pattern = tuple(results[-plen:])
            matches = []
            for i in range(len(results) - plen):
                if tuple(results[i:i + plen]) == pattern and i + plen < len(results):
                    matches.append(results[i + plen])
            if len(matches) >= 2:
                c = Counter(matches)
                top, count = c.most_common(1)[0]
                conf = int(count / len(matches) * 100)
                if conf > best_conf and conf >= 55:
                    best_hit, best_conf = top, conf
        if best_hit:
            return best_hit, best_conf, 1.5
        return None, 0, 0

    @staticmethod
    def _weighted_freq(valid, window=30):
        recent = valid[-window:]
        if len(recent) < 8:
            return None, 0, 0
        tai, xiu = 0.0, 0.0
        for i, v in enumerate(recent):
            w = (i + 1) / len(recent)
            if v['result'] == 'Tài':
                tai += w
            else:
                xiu += w
        total = tai + xiu
        if total == 0:
            return None, 0, 0
        p = tai / total
        if p > 0.58:
            return 'Tài', int(p * 100), 0.8
        elif p < 0.42:
            return 'Xỉu', int((1 - p) * 100), 0.8
        return None, 0, 0

    @staticmethod
    def _dice_bias(valid, window=50):
        recent = [v for v in valid[-window:] if v.get('total')]
        if len(recent) < 10:
            return None, 0, 0
        tais = sum(1 for v in recent if v['result'] == 'Tài')
        ratio = tais / len(recent)
        if ratio > 0.62:
            return 'Xỉu', int(ratio * 100), 0.6
        elif ratio < 0.38:
            return 'Tài', int((1 - ratio) * 100), 0.6
        return None, 0, 0

    @staticmethod
    def _alternation(valid, window=12):
        recent = [v['result'] for v in valid[-window:]]
        if len(recent) < 6:
            return None, 0, 0
        alt = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i - 1])
        alt_ratio = alt / (len(recent) - 1)
        if alt_ratio >= 0.7:
            last = recent[-1]
            nxt = 'Xỉu' if last == 'Tài' else 'Tài'
            return nxt, int(alt_ratio * 100), 1.4
        return None, 0, 0

    @staticmethod
    def _momentum(valid, window=10):
        recent = [v['result'] for v in valid[-window:]]
        if len(recent) < 6:
            return None, 0, 0
        tai = sum(1 for r in recent if r == 'Tài')
        p = tai / len(recent)
        if p >= 0.7:
            return 'Tài', int(p * 100), 0.9
        elif p <= 0.3:
            return 'Xỉu', int((1 - p) * 100), 0.9
        return None, 0, 0

    @staticmethod
    def _recency_streak(valid):
        if len(valid) < 10:
            return None, 0, 0
        weights = {'Tài': 0.0, 'Xỉu': 0.0}
        for i in range(len(valid) - 10, len(valid)):
            w = (i - (len(valid) - 10) + 1) / 10
            weights[valid[i]['result']] += w
        total = weights['Tài'] + weights['Xỉu']
        if total == 0:
            return None, 0, 0
        p = weights['Tài'] / total
        if p > 0.6:
            return 'Tài', int(p * 100), 1.1
        elif p < 0.4:
            return 'Xỉu', int((1 - p) * 100), 1.1
        return None, 0, 0

    @staticmethod
    def _entropy(results):
        if len(results) < 5:
            return 0.0
        import math
        c = Counter(results)
        total = len(results)
        h = 0.0
        for v in c.values():
            p = v / total
            if p > 0:
                h -= p * math.log2(p)
        return h

    @classmethod
    def predict(cls, valid):
        """DETERMINISTIC — cùng lịch sử → cùng dự đoán."""
        # Seed từ phiên cuối để deterministic
        seed = str(valid[-1]['phien']) if valid else "0"

        if not valid:
            return {'prediction': cls._deterministic_choice(['Tài', 'Xỉu'], seed),
                    'confidence': 50, 'method': 'random', 'signals': [],
                    'reason': 'Chưa có dữ liệu'}

        if len(valid) < 5:
            last = valid[-1]['result']
            streak = 1
            for i in range(len(valid) - 2, -1, -1):
                if valid[i]['result'] == last:
                    streak += 1
                else:
                    break
            opp = 'Xỉu' if last == 'Tài' else 'Tài'
            conf = min(50 + streak * 5, 65)
            return {'prediction': opp, 'confidence': conf, 'method': 'streak_fallback',
                    'signals': [], 'reason': f'Ít dữ liệu — bẻ chuỗi {streak}'}

        strategies = [
            ('markov2', cls._markov_order2(valid)),
            ('markov1', cls._markov_order1(valid)),
            ('streak', cls._streak_break(valid)),
            ('pattern', cls._pattern_match(valid)),
            ('weighted', cls._weighted_freq(valid)),
            ('dice', cls._dice_bias(valid)),
            ('alternation', cls._alternation(valid)),
            ('momentum', cls._momentum(valid)),
            ('recency', cls._recency_streak(valid)),
        ]

        tai_score, xiu_score = 0.0, 0.0
        signals = []
        for name, (pred, conf, weight) in strategies:
            if pred is None or weight == 0:
                continue
            score = (conf / 100.0) * weight
            if pred == 'Tài':
                tai_score += score
            else:
                xiu_score += score
            signals.append({'name': name, 'prediction': pred,
                            'confidence': conf, 'weight': weight})

        recent = [v['result'] for v in valid[-20:]]
        entropy = cls._entropy(recent)

        if not signals or (tai_score == 0 and xiu_score == 0):
            pick = cls._deterministic_choice(['Tài', 'Xỉu'], seed)
            return {'prediction': pick, 'confidence': 50, 'method': 'random',
                    'signals': [], 'reason': 'Không có tín hiệu'}

        total_score = tai_score + xiu_score
        if tai_score > xiu_score:
            pred = 'Tài'
            raw_conf = int((tai_score / total_score) * 100)
        else:
            pred = 'Xỉu'
            raw_conf = int((xiu_score / total_score) * 100)

        if entropy > 0.9:
            final_conf = max(50, raw_conf - 8)
        elif entropy > 0.7:
            final_conf = max(50, raw_conf - 3)
        else:
            final_conf = min(raw_conf, 85)

        method = '+'.join(s['name'] for s in signals) or 'ensemble'
        return {
            'prediction': pred,
            'confidence': final_conf,
            'method': method,
            'signals': signals,
            'reason': f"{len(signals)} tín hiệu · entropy={entropy:.2f}",
        }


# =====================================================================
# DATA FETCHER
# =====================================================================
def fetch_sessions():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
    for attempt in range(3):
        try:
            r = requests.get(API_URL_MD5, timeout=6, headers=headers)
            if r.status_code == 200:
                data = r.json()
                if 'list' in data and data['list']:
                    rows = []
                    for item in data['list']:
                        res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
                        dices = item.get('dices', [0, 0, 0])
                        rows.append({
                            'phien': int(item['id']),
                            'result': res,
                            'dice': f"{dices[0]} + {dices[1]} + {dices[2]}",
                            'total': item.get('point', sum(dices)),
                        })
                    return rows, True
        except Exception as e:
            print(f"[API ERROR] Lần {attempt + 1}: {e}")
            time.sleep(1)
    return [], False


def _sync_history():
    raw_rows, success = fetch_sessions()
    if not success and not HISTORY_CACHE:
        return [], False
    for row in raw_rows:
        HISTORY_CACHE[row['phien']] = row
    if RESET_ID > 0:
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
            del HISTORY_CACHE[k]
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    _update_prediction_log(valid)
    return valid, True


def _update_prediction_log(valid):
    """
    1. Điền actual/correct cho log đã có.
    2. Retroactive: phiên chưa có log → dự đoán lại từ dữ liệu TRƯỚC nó.
    """
    if not valid:
        return

    by_phien = {v['phien']: v for v in valid}
    phien_list = sorted(by_phien.keys())

    # Bước 1: cập nhật actual cho log đã có
    for phien, entry in list(PREDICTION_LOG.items()):
        if entry.get('actual') is not None:
            continue
        if phien in by_phien:
            actual = by_phien[phien]['result']
            entry['actual'] = actual
            entry['correct'] = (entry['prediction'] == actual)

    # Bước 2: retroactive prediction cho phiên chưa có log
    changed = False
    for i, phien in enumerate(phien_list):
        if phien in PREDICTION_LOG:
            continue
        if phien <= RESET_ID:
            continue

        history_before = [by_phien[p] for p in phien_list[:i]]
        if len(history_before) < 3:
            continue

        pred = MultiStrategyPredictor.predict(history_before)
        actual = by_phien[phien]['result']
        PREDICTION_LOG[phien] = {
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'actual': actual,
            'correct': (pred['prediction'] == actual),
            'logged_at': datetime.now().isoformat(),
            'retroactive': True,
        }
        changed = True

    # Bước 3: giới hạn kích thước
    if len(PREDICTION_LOG) > MAX_LOG_SIZE:
        keys = sorted(PREDICTION_LOG.keys())[:len(PREDICTION_LOG) - MAX_LOG_SIZE]
        for k in keys:
            del PREDICTION_LOG[k]
        changed = True

    if changed:
        _save_log()


def _log_prediction(phien, pred_result):
    """Log dự đoán cho phiên tới — không ghi đè retroactive nếu đã có."""
    if phien in PREDICTION_LOG:
        return
    PREDICTION_LOG[phien] = {
        'prediction': pred_result['prediction'],
        'confidence': pred_result['confidence'],
        'method': pred_result['method'],
        'actual': None,
        'correct': None,
        'logged_at': datetime.now().isoformat(),
        'retroactive': False,
    }
    _save_log()


def _honest_stats(valid):
    total = len(valid)
    tai = sum(1 for v in valid if v['result'] == 'Tài')
    return {'total': total, 'tai': tai, 'xiu': total - tai,
            'ratio_tai': round(tai / total, 3) if total else 0}


def _log_stats():
    evaluated = [e for e in PREDICTION_LOG.values() if e.get('actual') is not None]
    correct = sum(1 for e in evaluated if e.get('correct'))
    wrong = len(evaluated) - correct
    pending = sum(1 for e in PREDICTION_LOG.values() if e.get('actual') is None)
    return {'correct': correct, 'wrong': wrong, 'pending': pending,
            'evaluated': len(evaluated)}


# Load log khi khởi động
_load_log()


# =====================================================================
# HTML
# =====================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 </title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
:root{--bg:#0f172a;--card:#1e293b;--card2:#111827;--text:#f8fafc;--muted:#94a3b8;--border:#334155;--tai:#38bdf8;--xiu:#f472b6;--ok:#22c55e;--fail:#ef4444;--warn:#fbbf24}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Plus Jakarta Sans',sans-serif}
body{background:linear-gradient(135deg,#0f172a,#1e1b4b);color:var(--text);min-height:100vh;padding-bottom:30px;font-size:13px}
.header{background:rgba(30,41,59,.9);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:12px 16px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
.logo{font-size:16px;font-weight:800;color:var(--tai);display:flex;align-items:center;gap:8px}
.logo span{font-size:9px;background:#334155;color:#cbd5e1;padding:3px 8px;border-radius:20px;font-weight:800;letter-spacing:.5px}
.actions{display:flex;gap:8px;align-items:center}
.clock{font-size:11px;color:var(--muted);font-weight:600}
.btn{background:var(--card);color:var(--text);border:1px solid var(--border);padding:7px 12px;border-radius:9px;font-weight:700;font-size:12px;cursor:pointer}
.btn-reset{background:rgba(248,113,113,.15);color:#f87171;border-color:rgba(248,113,113,.4)}

.wrap{max-width:760px;margin:0 auto;padding:12px}

.scorebar{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}
.sc{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 8px;text-align:center}
.sc-l{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:700;margin-bottom:4px;letter-spacing:.5px}
.sc-v{font-size:22px;font-weight:800}
.sc-v.ok{color:var(--ok)}.sc-v.fail{color:var(--fail)}.sc-v.warn{color:var(--warn)}

.tbl{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;max-height:74vh;overflow-y:auto}
table{width:100%;border-collapse:separate;border-spacing:0}
th{background:var(--card2);color:var(--muted);font-size:10px;font-weight:700;padding:11px 6px;text-align:center;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10;text-transform:uppercase}
td{padding:10px 6px;text-align:center;border-bottom:1px solid var(--border);font-size:12px;font-weight:600}
.row-next{background:rgba(56,189,248,.08);border-left:3px solid var(--tai)}
.badge{display:inline-block;padding:3px 10px;border-radius:14px;font-size:10px;font-weight:800;min-width:52px;text-align:center}
.b-tai{background:rgba(56,189,248,.18);color:var(--tai);border:1px solid rgba(56,189,248,.3)}
.b-xiu{background:rgba(244,114,182,.18);color:var(--xiu);border:1px solid rgba(244,114,182,.3)}
.b-none{background:rgba(255,255,255,.05);color:var(--muted)}
.b-ok{background:rgba(34,197,94,.2);color:var(--ok);border:1px solid rgba(34,197,94,.4);font-size:10px;padding:4px 10px;font-weight:800}
.b-fail{background:rgba(239,68,68,.2);color:var(--fail);border:1px solid rgba(239,68,68,.4);font-size:10px;padding:4px 10px;font-weight:800}
.b-pending{background:rgba(251,191,36,.2);color:var(--warn);border:1px solid rgba(251,191,36,.4);font-size:10px;padding:4px 10px;font-weight:800}
.dice{font-size:10px;color:var(--muted);display:block;margin-top:2px}
.pred-mini{font-size:11px;font-weight:800}
.pred-mini.tai{color:var(--tai)}.pred-mini.xiu{color:var(--xiu)}
.loading{text-align:center;padding:30px;color:var(--tai);font-weight:600}
@media(max-width:520px){
  th,td{padding:8px 4px;font-size:11px}
  .clock{display:none}
  .badge{min-width:44px;font-size:9px}
  .b-ok,.b-fail,.b-pending{font-size:9px;padding:3px 7px}
  .sc-v{font-size:18px}
}
</style>
</head>
<body>
<div class="header">
    <div class="logo">LE MINH <span>v1</span></div>
    <div class="actions">
        <div class="clock" id="clock">--:--:--</div>
        <button class="btn" onclick="fetchData()">↻</button>
        <button class="btn btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>

<div class="wrap">
    <div class="scorebar">
        <div class="sc"><div class="sc-l">✓ Đúng</div><div class="sc-v ok" id="sc-correct">0</div></div>
        <div class="sc"><div class="sc-l">✗ Sai</div><div class="sc-v fail" id="sc-wrong">0</div></div>
        <div class="sc"><div class="sc-l"> Chờ</div><div class="sc-v warn" id="sc-pending">0</div></div>
    </div>

    <div class="tbl">
        <table>
            <thead>
                <tr>
                    <th>Phiên</th>
                    <th>Dự đoán</th>
                    <th>Kết quả</th>
                    <th>Đúng / Sai</th>
                </tr>
            </thead>
            <tbody id="tbody"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody>
        </table>
    </div>
</div>

<script>
let isResetting = false;

async function fetchData(){
    if(isResetting) return;
    try{
        const r = await fetch('/api/history', {cache:'no-store'});
        const data = await r.json();
        document.getElementById('clock').innerText = new Date().toLocaleTimeString('vi-VN');
        renderScore(data.ai_stats || {});
        renderTable(data.rows || []);
    }catch(e){ console.error(e); }
}

function renderScore(ai){
    document.getElementById('sc-correct').innerText = ai.correct || 0;
    document.getElementById('sc-wrong').innerText = ai.wrong || 0;
    document.getElementById('sc-pending').innerText = ai.pending || 0;
}

function renderTable(rows){
    const tb = document.getElementById('tbody');
    if(!rows.length){ tb.innerHTML = '<tr><td colspan="4" class="loading">Chưa có dữ liệu.</td></tr>'; return; }
    let html = '';
    rows.forEach(row => {
        const trCls = row.is_next ? 'class="row-next"' : '';

        let predCell = '<span class="badge b-none">—</span>';
        if(row.ai_prediction){
            const cls = row.ai_prediction === 'Tài' ? 'tai' : 'xiu';
            predCell = `<span class="pred-mini ${cls}">${row.ai_prediction}</span>
                        <br><span style="font-size:9px;color:var(--muted)">${row.ai_confidence||0}%</span>`;
        }

        let resBadge = '<span class="badge b-none">—</span>';
        if(row.result === 'Tài') resBadge = '<span class="badge b-tai">TÀI</span>';
        if(row.result === 'Xỉu') resBadge = '<span class="badge b-xiu">XỈU</span>';
        let dice = '';
        if(row.dice && row.dice !== '? + ? + ?') dice = `<span class="dice">${row.dice} · ${row.total}</span>`;

        let evalCell = '<span class="badge b-none">—</span>';
        if(row.ai_correct === true) evalCell = '<span class="badge b-ok">✓ ĐÚNG</span>';
        else if(row.ai_correct === false) evalCell = '<span class="badge b-fail">✗ SAI</span>';
        else if(row.ai_prediction && row.ai_correct === null) evalCell = '<span class="badge b-pending">⏳ CHỜ</span>';

        html += `<tr ${trCls}>
            <td>#${row.phien}${row.is_next ? '<br><span style="font-size:9px;color:var(--tai)">NEXT</span>' : ''}</td>
            <td>${predCell}</td>
            <td>${resBadge}${dice}</td>
            <td>${evalCell}</td>
        </tr>`;
    });
    tb.innerHTML = html;
}

async function confirmReset(){
    Swal.fire({
        title:'Reset?', text:'Xoá toàn bộ cache và log dự đoán?', icon:'warning',
        background:'#1e293b', color:'#f8fafc', showCancelButton:true,
        confirmButtonColor:'#0ea5e9', cancelButtonColor:'#64748b',
        confirmButtonText:'Đồng ý', cancelButtonText:'Hủy'
    }).then(async r => {
        if(!r.isConfirmed) return;
        isResetting = true;
        try{
            const res = await fetch('/api/reset', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
            const d = await res.json();
            isResetting = false;
            if(d.status === 'success'){
                fetchData();
                Swal.fire({title:'OK!', text:'Đã reset.', icon:'success', background:'#1e293b', color:'#f8fafc', confirmButtonColor:'#0ea5e9'});
            } else throw new Error(d.message || 'Lỗi');
        }catch(e){
            isResetting = false;
            Swal.fire({title:'Lỗi!', text:e.message, icon:'error', background:'#1e293b', color:'#f8fafc'});
        }
    });
}

fetchData();
setInterval(fetchData, 5000);
</script>
</body>
</html>"""


# =====================================================================
# ROUTES
# =====================================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500

        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'tai': 0, 'xiu': 0},
                            'ai_stats': _log_stats()})

        next_phien = valid[-1]['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats()

        out = [{
            'phien': next_phien,
            'is_next': True,
            'result': 'Chờ...',
            'dice': '? + ? + ?',
            'total': None,
            'ai_prediction': pred['prediction'],
            'ai_confidence': pred['confidence'],
            'ai_correct': None,
        }]

        for v in reversed(valid[-200:]):
            if v['phien'] <= RESET_ID:
                continue
            log = PREDICTION_LOG.get(v['phien'])
            out.append({
                'phien': v['phien'],
                'is_next': False,
                'result': v['result'],
                'dice': v['dice'],
                'total': v['total'],
                'ai_prediction': log['prediction'] if log else None,
                'ai_confidence': log['confidence'] if log else None,
                'ai_correct': log['correct'] if log else None,
            })

        return jsonify({'rows': out, 'stats': stats, 'ai_stats': ai_stats})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict():
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'prediction': None, 'ai_stats': _log_stats()})

        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid)
        _log_prediction(next_phien, pred)

        return jsonify({
            'last_phien': last['phien'],
            'next_phien': next_phien,
            'last_result': last['result'],
            'last_dice': last['dice'],
            'last_total': last['total'],
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'reason': pred['reason'],
            'signals': pred['signals'],
            'stats': _honest_stats(valid),
            'ai_stats': _log_stats(),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lc79')
def lc79():
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'Id': 'le minh ai v7', 'Phien': None, 'Du_doan': None})

        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats()

        return jsonify({
            'Id': 'le minh ai v7',
            'Phien': str(next_phien),
            'Ket_qua_truoc': last['result'].lower(),
            'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%",
            'Phuong_phap': pred['method'],
            'Tong_phien': stats['total'],
            'So_Tai': stats['tai'],
            'So_Xiu': stats['xiu'],
            'AI_dung': ai_stats['correct'],
            'AI_sai': ai_stats['wrong'],
            'AI_cho': ai_stats['pending'],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def stats_only():
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        last = valid[-1] if valid else None
        return jsonify({
            'stats': _honest_stats(valid),
            'ai_stats': _log_stats(),
            'last_result': last['result'] if last else None,
            'last_phien': last['phien'] if last else None,
            'last_dice': last['dice'] if last else None,
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/prediction_log')
def prediction_log():
    try:
        _sync_history()
        items = sorted(PREDICTION_LOG.items(), key=lambda x: x[0], reverse=True)[:100]
        out = [{
            'phien': p, 'prediction': e['prediction'], 'confidence': e['confidence'],
            'method': e['method'], 'actual': e.get('actual'),
            'correct': e.get('correct'), 'retroactive': e.get('retroactive', False),
            'logged_at': e.get('logged_at'),
        } for p, e in items]
        return jsonify({'stats': _log_stats(), 'predictions': out})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE, PREDICTION_LOG
    try:
        raw_rows, success = fetch_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                PREDICTION_LOG = {}
                _save_log()
                return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys())
            HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
            PREDICTION_LOG = {}
            _save_log()
            return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        return jsonify({'status': 'error', 'message': 'Không có dữ liệu để reset'}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
