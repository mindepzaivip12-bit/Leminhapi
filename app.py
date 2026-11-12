import os
import traceback
import time
import json
import hashlib
import math
import threading
import random
from datetime import datetime
from collections import Counter, defaultdict
import requests
from flask import Flask, render_template_string, jsonify, request
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
MAX_LOG_SIZE = 3000
LOG_FILE = "prediction_log.json"

_FETCH_LOCK = threading.Lock()
_LAST_FETCH_TIME = 0.0
_LAST_FETCH_RESULT = ([], False)
_FETCH_CACHE_TTL = 10.0

# ============================================================
# HELPERS
# ============================================================
def _runs(seq):
    if not seq: return []
    out, cur, n = [], seq[0], 1
    for x in seq[1:]:
        if x == cur: n += 1
        else: out.append((cur, n)); cur, n = x, 1
    out.append((cur, n))
    return out


# ============================================================
# 🎯 MATH PREDICTOR V27 — TOÁN HỌC THUẦN
# Bỏ pattern học, chỉ dùng: Markov, Cầu, Trend, Reversal, Momentum, Recovery
# Ưu tiên BẺ khi bệt, đa dạng Tài/Xỉu, trần 88.5%
# ============================================================
class MathPredictorV27:
    MAX_CONF = 88.5

    # -------- MARKOV (thuần toán, dựa tần suất chuyển tiếp) --------
    @staticmethod
    def _markov(seq):
        if len(seq) < 12: return (None, 0.0)
        n = len(seq); scores = []
        for order, min_cnt, w in [(1, 6, 1.0), (2, 5, 1.2), (3, 4, 1.4), (4, 3, 1.6)]:
            if n < order + 4: continue
            trans = defaultdict(lambda: [0, 0])
            for i in range(n - order):
                key = tuple(seq[i:i+order])
                nxt = 0 if seq[i+order] == 'Tài' else 1
                trans[key][nxt] += 1
            cnt = trans.get(tuple(seq[-order:]))
            if cnt and sum(cnt) >= min_cnt:
                t = sum(cnt); p = cnt[0] / t
                if p >= 0.68: scores.append(('Tài', p * 80, w))
                elif p <= 0.32: scores.append(('Xỉu', (1-p) * 80, w))
        if not scores: return (None, 0.0)
        wt = sum(s[1]*s[2] for s in scores if s[0] == 'Tài')
        wx = sum(s[1]*s[2] for s in scores if s[0] == 'Xỉu')
        if wt + wx == 0: return (None, 0.0)
        if wt >= wx: return ('Tài', min(round(wt/(wt+wx)*90, 1), 85.5))
        return ('Xỉu', min(round(wx/(wt+wx)*90, 1), 85.5))

    # -------- CẦU (runs, patterns) — Ưu tiên BẺ khi bệt --------
    @staticmethod
    def _cau(seq):
        if len(seq) < 6: return (None, 0.0)
        runs = _runs(seq)
        cur_val, cur_len = runs[-1]
        opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
        lens = [l for _, l in runs]
        vals = [v for v, _ in runs]

        # Bệt dài → BẺ (không đu bệt)
        if cur_len >= 6: return (opp, 86.5)
        if cur_len >= 4: return (opp, 78.5)
        if cur_len == 3: return (opp, 65.0)

        # Cầu 1-1 (xen kẽ hoàn hảo)
        if len(lens) >= 5 and all(l == 1 for l in lens[-5:]): return (opp, 82.5)
        if len(lens) >= 4 and all(l == 1 for l in lens[-4:]): return (opp, 74.0)
        if len(lens) >= 3 and all(l == 1 for l in lens[-3:]): return (opp, 64.0)

        # Cầu 2-2
        if len(lens) >= 3 and lens[-3:] == [2, 2, 2]:
            return (opp if cur_len >= 2 else cur_val, 72.0)
        if len(lens) >= 2 and lens[-2:] == [2, 2]:
            return (opp if cur_len >= 2 else cur_val, 64.0)

        # Cầu 3-3
        if len(lens) >= 2 and lens[-2:] == [3, 3]:
            return (opp if cur_len >= 3 else cur_val, 66.0)

        # Cầu xen kẽ 1-2
        if len(lens) >= 4:
            p = lens[-4:]
            if p in ([1,2,1,2], [2,1,2,1]):
                return (opp if cur_len == p[-1] else cur_val, 70.5)

        # Cầu nghiêng 6 phiên
        if len(lens) >= 6:
            rv = vals[-6:]
            tc = rv.count('Tài'); xc = rv.count('Xỉu')
            if tc >= 5: return ('Xỉu', 72.0)
            if xc >= 5: return ('Tài', 72.0)

        return (None, 0.0)

    # -------- TREND (tỷ lệ Tài/Xỉu gần đây) --------
    @staticmethod
    def _trend(seq):
        if len(seq) < 14: return (None, 0.0)
        r24 = seq[-24:].count('Tài') / len(seq[-24:])
        if r24 >= 0.87: return ('Xỉu', 80.0)
        if r24 <= 0.13: return ('Tài', 80.0)
        if r24 >= 0.78: return ('Xỉu', 70.0)
        if r24 <= 0.22: return ('Tài', 70.0)
        # Entropy thấp → bẻ
        if 0 < r24 < 1:
            ent = -(r24 * math.log2(r24) + (1-r24) * math.log2(1-r24))
            if ent < 0.85:
                if r24 >= 0.64: return ('Tài', 62.0)
                if r24 <= 0.36: return ('Xỉu', 62.0)
        return (None, 0.0)

    # -------- DATA HISTORY (mẫu 6-8 ký tự trong lịch sử) --------
    @staticmethod
    def _data_history(seq, valid_full):
        if len(seq) < 15: return (None, 0.0)
        hist = [v['result'] for v in valid_full[-1500:]]
        pat6 = seq[-6:]
        t6 = x6 = 0
        for i in range(len(hist) - 7):
            if hist[i:i+6] == pat6:
                if hist[i+6] == 'Tài': t6 += 1
                else: x6 += 1
        tot = t6 + x6
        if tot >= 3:
            if t6/tot >= 0.68: return ('Tài', min(round(t6/tot*90, 1), 85.0))
            if x6/tot >= 0.68: return ('Xỉu', min(round(x6/tot*90, 1), 85.0))
        if len(seq) >= 8:
            pat8 = seq[-8:]
            t8 = x8 = 0
            for i in range(len(hist) - 9):
                if hist[i:i+8] == pat8:
                    if hist[i+8] == 'Tài': t8 += 1
                    else: x8 += 1
            tot8 = t8 + x8
            if tot8 >= 2:
                if t8/tot8 >= 0.72: return ('Tài', min(round(t8/tot8*90, 1), 87.0))
                if x8/tot8 >= 0.72: return ('Xỉu', min(round(x8/tot8*90, 1), 87.0))
        return (None, 0.0)

    # -------- TREND REVERSAL (bắt buộc bẻ khi cực đoan) --------
    @staticmethod
    def _trend_reversal(seq):
        if len(seq) < 10: return (None, 0.0)
        runs = _runs(seq)
        cur_val, cur_len = runs[-1]
        opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
        if cur_len >= 8: return (opp, 88.0)
        if cur_len >= 6: return (opp, 82.0)
        if len(seq) >= 10:
            last10 = seq[-10:]
            if last10.count('Tài') >= 9: return ('Xỉu', 80.0)
            if last10.count('Xỉu') >= 9: return ('Tài', 80.0)
        if len(seq) >= 9:
            last9 = seq[-9:]
            if all(last9[i] != last9[i+1] for i in range(8)): return (opp, 78.0)
        return (None, 0.0)

    # -------- MOMENTUM (5 phiên gần) --------
    @staticmethod
    def _momentum(seq):
        if len(seq) < 5: return (None, 0.0)
        last5 = seq[-5:]
        tc = last5.count('Tài')
        if tc >= 4: return ('Tài', 62.0)
        if tc <= 1: return ('Xỉu', 62.0)
        return (None, 0.0)

    # -------- RECOVERY (bẻ khi sai liên tiếp) --------
    @staticmethod
    def _recovery(log):
        if not log: return (None, 0.0)
        evaluated = [e for _, e in sorted(log.items(), reverse=True) if e.get('actual') is not None][:6]
        if not evaluated: return (None, 0.0)
        wrong = 0
        for e in evaluated:
            if not e.get('correct'): wrong += 1
            else: break
        if wrong >= 2:
            last_pred = evaluated[0]['prediction']
            fix = 'Xỉu' if last_pred == 'Tài' else 'Tài'
            if wrong >= 4: return (fix, 88.0)
            if wrong == 3: return (fix, 82.0)
            return (fix, 74.0)
        return (None, 0.0)

    @classmethod
    def predict(cls, valid, log=None):
        if log is None: log = PREDICTION_LOG
        if not valid: return cls._fallback('Tài', 52.0, 'Random')

        seq = [v['result'] for v in valid]
        if len(seq) < 5:
            opp = 'Xỉu' if seq[-1] == 'Tài' else 'Tài'
            return cls._fallback(opp, 55.5, 'Khởi động')

        raw = [
            ('markov',   cls._markov(seq),                1.6),
            ('cau',      cls._cau(seq),                   2.4),
            ('trend',    cls._trend(seq),                 1.2),
            ('data',     cls._data_history(seq, valid),   2.0),
            ('reversal', cls._trend_reversal(seq),        2.6),
            ('momentum', cls._momentum(seq),              0.9),
            ('recovery', cls._recovery(log),              3.5),
        ]

        signals, log_odds, total_w = [], 0.0, 0.0
        recovery_active = False
        rec_pred, rec_conf = cls._recovery(log)
        if rec_pred: recovery_active = True

        # Dynamic weight theo hiệu suất thuật toán
        recent_log = [e for _, e in sorted(log.items(), reverse=True) if e.get('actual') is not None][:12]
        algo_perf = defaultdict(lambda: {'ok': 1, 'fail': 1})
        for e in recent_log:
            m = e.get('method', '')
            for algo in ['Markov', 'Cầu', 'Trend', 'Data']:
                if algo in m:
                    algo_perf[algo.lower()]['ok' if e['correct'] else 'fail'] += 1

        for name, (pred, conf), base_w in raw:
            if not pred or conf <= 0: continue
            dw = base_w
            key = {'cau': 'cầu'}.get(name, name)
            if key in algo_perf and not recovery_active:
                p = algo_perf[key]
                dw *= (0.5 + p['ok'] / (p['ok'] + p['fail']))

            pn = max(0.51, min(conf / 100.0, 0.95))
            lr = pn / (1 - pn)
            if pred == 'Xỉu': lr = 1.0 / lr
            log_odds += dw * (1.0 if pred == 'Tài' else -1.0) * (lr - 1.0)
            total_w += dw
            signals.append({'name': name, 'prediction': pred, 'confidence': conf, 'weight': round(dw, 2)})

        if len(signals) < 2 or total_w == 0:
            return cls._fallback_final(seq, signals)

        scaled = log_odds / total_w * 3.0
        p_tai = 1.0 / (1.0 + math.exp(-scaled))
        pred = 'Tài' if p_tai >= 0.5 else 'Xỉu'
        raw_conf = (p_tai if pred == 'Tài' else 1 - p_tai) * 100.0

        votes_t = sum(1 for s in signals if s['prediction'] == 'Tài')
        votes_x = len(signals) - votes_t
        agree = max(votes_t, votes_x) / len(signals)
        if agree == 1.0: bonus = 13.0
        elif agree >= 0.85: bonus = 9.0
        elif agree >= 0.75: bonus = 5.0
        elif agree >= 0.65: bonus = 2.0
        else: bonus = 0.0

        final_conf = min(round(raw_conf + bonus, 1), cls.MAX_CONF)

        if recovery_active and rec_pred:
            pred = rec_pred
            final_conf = max(final_conf, rec_conf)

        signals.sort(key=lambda s: s['weight'] * s['confidence'], reverse=True)
        top = [s['name'].upper() for s in signals[:3]]

        return {
            'prediction': pred, 'confidence': round(final_conf, 1),
            'method': ' • '.join(top) if top else 'Tổng hợp',
            'signals': signals, 'top_signals': top,
            'flipped': recovery_active, 'recovery_active': recovery_active,
        }

    @staticmethod
    def _fallback(pred, conf, method):
        return {'prediction': pred, 'confidence': min(conf, 88.5), 'method': method,
                'signals': [], 'top_signals': [], 'flipped': False, 'recovery_active': False}

    @classmethod
    def _fallback_final(cls, seq, signals):
        runs = _runs(seq)
        cur_val, cur_len = runs[-1]
        if cur_len >= 3:
            return {'prediction': cur_val, 'confidence': 58.0, 'method': 'Bệt cơ bản',
                    'signals': signals, 'top_signals': ['Bệt'], 'flipped': False, 'recovery_active': False}
        opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
        return {'prediction': opp, 'confidence': 54.0, 'method': 'Bẻ nhịp',
                'signals': signals, 'top_signals': ['Bẻ nhịp'], 'flipped': False, 'recovery_active': False}


MathPredictor = MathPredictorV27
MultiStrategyPredictor = MathPredictorV27


# ============================================================
# FETCH & SYSTEM
# ============================================================
def fetch_sessions():
    global _LAST_FETCH_TIME, _LAST_FETCH_RESULT
    with _FETCH_LOCK:
        now = time.time()
        if now - _LAST_FETCH_TIME < _FETCH_CACHE_TTL and _LAST_FETCH_RESULT[0]:
            return _LAST_FETCH_RESULT
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        for _ in range(3):
            try:
                r = requests.get(API_URL_MD5, timeout=6, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    if 'list' in data and data['list']:
                        rows = [{
                            'phien': int(i['id']),
                            'result': "Tài" if i['resultTruyenThong'] == "TAI" else "Xỉu",
                            'dice': f"{i.get('dices',[0,0,0])[0]} + {i.get('dices',[0,0,0])[1]} + {i.get('dices',[0,0,0])[2]}",
                            'total': i.get('point', sum(i.get('dices', [0,0,0])))
                        } for i in data['list']]
                        _LAST_FETCH_TIME = now
                        _LAST_FETCH_RESULT = (rows, True)
                        return rows, True
            except Exception:
                time.sleep(1)
        return _LAST_FETCH_RESULT


def _load_log():
    global PREDICTION_LOG, RESET_ID
    if not os.path.exists(LOG_FILE): return
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        PREDICTION_LOG = {int(k): v for k, v in data.get('log', {}).items()}
        RESET_ID = int(data.get('reset_id', 0))
    except Exception: pass


def _save_log():
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'log': PREDICTION_LOG, 'reset_id': RESET_ID}, f)
    except Exception: pass


def _sync_history():
    raw_rows, success = fetch_sessions()
    if not success and not HISTORY_CACHE: return [], False
    for row in raw_rows: HISTORY_CACHE[row['phien']] = row
    if RESET_ID > 0:
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]: del HISTORY_CACHE[k]
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    _update_prediction_log(valid)
    return valid, True


def _update_prediction_log(valid):
    if not valid: return
    by_phien = {v['phien']: v for v in valid}
    phien_list = sorted(by_phien.keys())
    for phien, entry in list(PREDICTION_LOG.items()):
        if entry.get('actual') is None and phien in by_phien:
            entry['actual'] = by_phien[phien]['result']
            entry['correct'] = (entry['prediction'] == entry['actual'])
    changed = False
    for i, phien in enumerate(phien_list):
        if phien in PREDICTION_LOG or phien <= RESET_ID: continue
        hist_before = [by_phien[p] for p in phien_list[:i]]
        if len(hist_before) < 5: continue
        pred = MathPredictorV27.predict(hist_before, log=PREDICTION_LOG)
        actual = by_phien[phien]['result']
        PREDICTION_LOG[phien] = {
            'prediction': pred['prediction'], 'confidence': pred['confidence'],
            'method': pred['method'], 'actual': actual,
            'correct': (pred['prediction'] == actual),
            'logged_at': datetime.now().isoformat(), 'flipped': pred.get('flipped', False)}
        changed = True
    if len(PREDICTION_LOG) > MAX_LOG_SIZE:
        for k in sorted(PREDICTION_LOG.keys())[:len(PREDICTION_LOG) - MAX_LOG_SIZE]: del PREDICTION_LOG[k]
        changed = True
    if changed: _save_log()


def _log_prediction(phien, pred_result):
    if phien in PREDICTION_LOG: return
    PREDICTION_LOG[phien] = {
        'prediction': pred_result['prediction'], 'confidence': pred_result['confidence'],
        'method': pred_result['method'], 'actual': None, 'correct': None,
        'logged_at': datetime.now().isoformat(), 'flipped': pred_result.get('flipped', False)}
    _save_log()


def _log_stats(log=None):
    if log is None: log = PREDICTION_LOG
    evaluated = [e for e in log.values() if e.get('actual') is not None]
    correct = sum(1 for e in evaluated if e.get('correct'))
    wrong = len(evaluated) - correct
    pending = sum(1 for e in log.values() if e.get('actual') is None)
    rate = round(correct / max(len(evaluated), 1) * 100, 1)
    return {'correct': correct, 'wrong': wrong, 'pending': pending,
            'evaluated': len(evaluated), 'rate': rate}


_load_log()

# ============================================================
# GIAO DIỆN
# ============================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>LE MINH BON MD5</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
:root{
  --bg-1:#f0f9ff;--bg-2:#e0f2fe;
  --text:#0c1421;--text-soft:#475569;--muted:#94a3b8;
  --border:#dbeafe;--border-blue:#93c5fd;--border-strong:#60a5fa;
  --primary:#0ea5e9;--primary-dark:#0284c7;--primary-light:#38bdf8;
  --tai:#0284c7;--tai-bg:#e0f2fe;--tai-border:#7dd3fc;
  --xiu:#0891b2;--xiu-bg:#cffafe;--xiu-border:#67e8f9;
  --ok:#059669;--ok-bg:#d1fae5;--ok-border:#6ee7b7;
  --fail:#dc2626;--fail-bg:#fee2e2;--fail-border:#fca5a5;
  --warn:#d97706;--warn-bg:#fef3c7;--warn-border:#fcd34d;
  --shadow-sm:0 2px 6px rgba(14,165,233,.08);
  --shadow:0 4px 14px rgba(14,165,233,.12);
  --shadow-lg:0 12px 36px rgba(2,132,199,.18);
}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Plus Jakarta Sans',sans-serif;-webkit-tap-highlight-color:transparent}
body{background:radial-gradient(ellipse 80% 60% at 50% 0%,#dbeafe 0%,transparent 60%),radial-gradient(ellipse 60% 50% at 100% 100%,#cffafe 0%,transparent 70%),linear-gradient(180deg,#f8fafc,#eff6ff 50%,#e0f2fe);background-attachment:fixed;color:var(--text);min-height:100vh;padding-bottom:40px;font-size:13px}
.header{background:rgba(255,255,255,.85);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-bottom:1px solid var(--border-blue);padding:14px 18px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;box-shadow:var(--shadow-sm)}
.brand{display:flex;align-items:center;gap:10px}
.brand-icon{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,#0284c7,#0ea5e9,#38bdf8);display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 6px 16px rgba(2,132,199,.35);animation:pulse 3s ease-in-out infinite}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}
.brand-text{display:flex;flex-direction:column;line-height:1.1}
.brand-title{font-size:15px;font-weight:800;letter-spacing:.3px;background:linear-gradient(90deg,#0284c7,#0ea5e9,#38bdf8,#0284c7);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:shine 4s linear infinite}
@keyframes shine{to{background-position:200% center}}
.brand-sub{font-size:9px;color:var(--muted);font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-top:2px}
.brand-ver{font-size:9px;background:linear-gradient(135deg,#059669,#10b981);color:#fff;padding:3px 8px;border-radius:20px;font-weight:800;margin-left:6px;letter-spacing:.3px}
.header-right{display:flex;gap:8px;align-items:center}
.clock{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--primary-dark);font-weight:700;background:#fff;padding:7px 12px;border-radius:9px;border:1px solid var(--border)}
.btn{background:#fff;color:var(--text-soft);border:1px solid var(--border);padding:8px 14px;border-radius:9px;font-weight:700;font-size:12px;cursor:pointer;transition:all .2s;display:inline-flex;align-items:center;gap:5px}
.btn:hover{background:var(--bg-1);border-color:var(--border-strong);color:var(--primary-dark);transform:translateY(-1px)}
.btn:active{transform:translateY(0)}
.btn-reset{background:linear-gradient(135deg,#fee2e2,#fecaca);color:var(--fail);border-color:var(--fail-border)}
.btn-reset:hover{background:linear-gradient(135deg,#fecaca,#fca5a5);color:#b91c1c}
.spin{animation:spin .6s ease}@keyframes spin{to{transform:rotate(360deg)}}
.wrap{max-width:820px;margin:0 auto;padding:16px}
.pred-card{background:linear-gradient(135deg,#fff 0%,#f0f9ff 100%);border:1px solid var(--border-blue);border-radius:20px;padding:22px;margin-bottom:14px;position:relative;overflow:hidden;box-shadow:var(--shadow-lg)}
.pred-card::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#0284c7,#0ea5e9,#38bdf8,#7c3aed,#0284c7);background-size:200% 100%;animation:shine 3s linear infinite}
.pred-card::after{content:'';position:absolute;top:-40px;right:-40px;width:120px;height:120px;background:radial-gradient(circle,rgba(14,165,233,.15),transparent 70%);border-radius:50%;pointer-events:none}
.pred-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
.pred-label{font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:800;letter-spacing:1.2px;margin-bottom:8px;display:flex;align-items:center;gap:5px}
.pred-label::before{content:'';width:6px;height:6px;background:var(--primary);border-radius:50%;animation:blink 1.5s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.pred-value{font-size:44px;font-weight:800;line-height:1;letter-spacing:-1px}
.pred-value.tai{color:var(--tai);text-shadow:0 2px 12px rgba(2,132,199,.2)}
.pred-value.xiu{color:var(--xiu);text-shadow:0 2px 12px rgba(8,145,178,.2)}
.conf-badge{background:linear-gradient(135deg,#dbeafe,#bfdbfe);border:1.5px solid var(--border-strong);color:var(--primary-dark);padding:9px 18px;border-radius:24px;font-weight:800;font-size:17px;box-shadow:0 4px 12px rgba(14,165,233,.2);font-family:'JetBrains Mono',monospace}
.conf-bar{height:6px;background:#e0f2fe;border-radius:3px;overflow:hidden;margin-top:4px}
.conf-bar-fill{height:100%;background:linear-gradient(90deg,#0284c7,#0ea5e9,#38bdf8);transition:width 1.2s cubic-bezier(.4,0,.2,1);border-radius:3px;box-shadow:0 0 8px rgba(14,165,233,.5)}
.method-row{margin-top:12px;display:flex;flex-wrap:wrap;gap:6px;min-height:24px}
.method-tag{font-size:10px;background:linear-gradient(135deg,#ede9fe,#ddd6fe);color:#6d28d9;border:1px solid #c4b5fd;padding:4px 10px;border-radius:12px;font-weight:700}
.method-tag.fixing{background:linear-gradient(135deg,#fee2e2,#fecaca);color:#b91c1c;border-color:#fca5a5;animation:pulse 1.5s infinite}
.scorebar{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px}
.sc{background:#fff;border:1px solid var(--border);border-radius:12px;padding:12px 6px;text-align:center;box-shadow:var(--shadow-sm);position:relative;overflow:hidden}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.sc-ok::before{background:var(--ok)}.sc-fail::before{background:var(--fail)}.sc-pending::before{background:var(--warn)}.sc-rate::before{background:var(--primary)}
.sc-l{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:800;letter-spacing:.5px;margin-bottom:4px}
.sc-v{font-size:22px;font-weight:800;font-family:'JetBrains Mono',monospace}
.sc-v.ok{color:var(--ok)}.sc-v.fail{color:var(--fail)}.sc-v.warn{color:var(--warn)}.sc-v.primary{color:var(--primary-dark)}
.tbl-card{background:#fff;border:1px solid var(--border);border-radius:14px;overflow:hidden;box-shadow:var(--shadow);max-height:62vh;overflow-y:auto}
table{width:100%;border-collapse:separate;border-spacing:0}
th{background:linear-gradient(135deg,#eff6ff,#dbeafe);color:var(--primary-dark);font-size:10px;font-weight:800;padding:13px 8px;text-align:center;border-bottom:1px solid var(--border-blue);position:sticky;top:0;z-index:10;text-transform:uppercase;letter-spacing:.5px}
td{padding:11px 8px;text-align:center;border-bottom:1px solid var(--bg-1);font-size:12px;font-weight:600}
tr:hover td{background:#f0f9ff}
.row-next{background:linear-gradient(90deg,#e0f2fe,#fff 60%);border-left:3px solid var(--primary);animation:nextPulse 2s infinite}
@keyframes nextPulse{0%,100%{background:linear-gradient(90deg,#e0f2fe,#fff 60%)}50%{background:linear-gradient(90deg,#bfdbfe,#e0f2fe 60%)}}
.badge{display:inline-block;padding:4px 11px;border-radius:14px;font-size:10px;font-weight:800;min-width:56px;letter-spacing:.3px}
.b-tai{background:var(--tai-bg);color:var(--tai);border:1px solid var(--tai-border)}
.b-xiu{background:var(--xiu-bg);color:var(--xiu);border:1px solid var(--xiu-border)}
.b-none{background:var(--bg-1);color:var(--muted);border:1px solid var(--border)}
.b-ok{background:var(--ok-bg);color:var(--ok);border:1px solid var(--ok-border)}
.b-fail{background:var(--fail-bg);color:var(--fail);border:1px solid var(--fail-border)}
.b-pending{background:var(--warn-bg);color:var(--warn);border:1px solid var(--warn-border)}
.dice{font-size:10px;color:var(--muted);display:block;margin-top:3px;font-family:'JetBrains Mono',monospace}
.pred-mini{font-size:12px;font-weight:800;font-family:'JetBrains Mono',monospace}
.pred-mini.tai{color:var(--tai)}.pred-mini.xiu{color:var(--xiu)}
.pred-conf-mini{font-size:9px;color:var(--muted);font-weight:700}
.loading{text-align:center;padding:40px 20px;color:var(--primary);font-weight:700;font-size:14px}
.loading::before{content:'';display:inline-block;width:16px;height:16px;border:2px solid var(--border-blue);border-top-color:var(--primary);border-radius:50%;animation:spin .8s linear infinite;margin-right:8px;vertical-align:middle}
.toast{position:fixed;bottom:24px;right:24px;z-index:200;background:linear-gradient(135deg,#0284c7,#0ea5e9);color:#fff;padding:14px 20px;border-radius:12px;font-weight:700;font-size:13px;box-shadow:0 12px 32px rgba(2,132,199,.4);transform:translateY(100px);opacity:0;transition:all .4s cubic-bezier(.4,0,.2,1);display:flex;align-items:center;gap:8px;max-width:320px}
.toast.show{transform:translateY(0);opacity:1}
@media(max-width:540px){
  .wrap{padding:12px}.pred-value{font-size:36px}.conf-badge{font-size:14px;padding:7px 14px}.clock{display:none}
  .scorebar{grid-template-columns:repeat(2,1fr)}th,td{padding:8px 4px;font-size:11px}
  .badge{min-width:44px;font-size:9px;padding:3px 8px}.brand-sub{display:none}
  .btn{padding:7px 10px;font-size:11px}
}
</style></head><body>

<div class="header">
  <div class="brand">
    <div class="brand-icon">🎲</div>
    <div class="brand-text">
      <div class="brand-title">LE MINH BON<span class="brand-ver">🐼 </span></div>
      <div class="brand-sub">THUẬT TOÁN VIP</div>
    </div>
  </div>
  <div class="header-right">
    <div class="clock" id="clock">--:--:--</div>
    <button class="btn" onclick="manualRefresh(this)">↻</button>
    <button class="btn btn-reset" onclick="confirmReset()">Reset</button>
  </div>
</div>

<div class="wrap">
  <div id="loading-screen" class="loading" style="display:none;">Đang tải dữ liệu...</div>
  <div id="main-content">
    <div class="pred-card">
      <div class="pred-top">
        <div>
          <div class="pred-label">Dự đoán phiên tiếp theo</div>
          <div class="pred-value" id="pred-value">—</div>
          <div class="method-row" id="method-row"></div>
        </div>
        <div class="conf-badge" id="conf-badge">--%</div>
      </div>
      <div class="conf-bar"><div class="conf-bar-fill" id="conf-bar" style="width:0%"></div></div>
    </div>

    <div class="scorebar">
      <div class="sc sc-ok"><div class="sc-l">✓ Đúng</div><div class="sc-v ok" id="sc-correct">0</div></div>
      <div class="sc sc-fail"><div class="sc-l">✗ Sai</div><div class="sc-v fail" id="sc-wrong">0</div></div>
      <div class="sc sc-pending"><div class="sc-l">⏳ Chờ</div><div class="sc-v warn" id="sc-pending">0</div></div>
      <div class="sc sc-rate"><div class="sc-l">📊 Tỷ lệ</div><div class="sc-v primary" id="sc-rate">0.0%</div></div>
    </div>

    <div class="tbl-card">
      <table>
        <thead><tr><th>Phiên</th><th>Dự đoán</th><th>Kết quả</th><th>Đánh giá</th></tr></thead>
        <tbody id="tbody"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody>
      </table>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
let isResetting=false,lastPred=null,lastRecovery=false;
function showToast(msg,isDanger=false){
  const t=document.getElementById('toast');
  t.style.background=isDanger?'linear-gradient(135deg,#dc2626,#ef4444)':'linear-gradient(135deg,#0284c7,#0ea5e9)';
  t.style.boxShadow=isDanger?'0 12px 32px rgba(220,38,38,.4)':'0 12px 32px rgba(2,132,199,.4)';
  t.innerText=msg;t.classList.add('show');
  clearTimeout(t._tm);t._tm=setTimeout(()=>t.classList.remove('show'),4000);
}
function manualRefresh(b){b.classList.add('spin');setTimeout(()=>b.classList.remove('spin'),600);fetchData();}
async function fetchData(){
  if(isResetting)return;
  document.getElementById('clock').innerText=new Date().toLocaleTimeString('vi-VN');
  try{
    const r=await fetch('/api/history',{cache:'no-store'});
    const d=await r.json();
    if(!d.ready){
      document.getElementById('loading-screen').style.display='block';
      document.getElementById('main-content').style.display='none';return;
    }
    document.getElementById('loading-screen').style.display='none';
    document.getElementById('main-content').style.display='block';
    const ai=d.ai_stats||{};
    document.getElementById('sc-correct').innerText=ai.correct||0;
    document.getElementById('sc-wrong').innerText=ai.wrong||0;
    document.getElementById('sc-pending').innerText=ai.pending||0;
    document.getElementById('sc-rate').innerText=(ai.rate||0).toFixed(1)+'%';
    const pred=d.prediction,rows=d.rows||[];
    const pv=document.getElementById('pred-value'),cb=document.getElementById('conf-badge');
    const bar=document.getElementById('conf-bar'),mr=document.getElementById('method-row');
    if(!pred){pv.innerText='—';cb.innerText='--%';bar.style.width='0%';mr.innerHTML='';}
    else{
      pv.innerText=pred.prediction;
      pv.className='pred-value '+(pred.prediction==='Tài'?'tai':'xiu');
      const cs=parseFloat(pred.confidence).toFixed(1)+'%';
      cb.innerText=cs;bar.style.width=pred.confidence+'%';
      mr.innerHTML='';
      if(pred.flipped){
        const tag=document.createElement('span');
        tag.className='method-tag fixing';tag.innerText='ĐẢO CHIỀU';
        mr.appendChild(tag);
        if(!lastRecovery)showToast('Tự động đảo chiều!',true);
      }else{
        (pred.top_signals||[]).slice(0,2).forEach(s=>{
          const tag=document.createElement('span');
          tag.className='method-tag';tag.innerText=s;mr.appendChild(tag);
        });
      }
      lastRecovery=pred.flipped;
      if(lastPred&&lastPred!==pred.prediction&&!pred.flipped)
        showToast('🎯 Dự đoán đổi → '+pred.prediction+' ('+cs+')');
      lastPred=pred.prediction;
    }
    const tb=document.getElementById('tbody');
    if(!rows.length){tb.innerHTML='<tr><td colspan="4" class="loading">Chưa có dữ liệu</td></tr>';return;}
    let html='';
    rows.forEach(row=>{
      const trCls=row.is_next?'class="row-next"':'';
      let pc='<span class="badge b-none">—</span>';
      if(row.ai_prediction){
        const c=row.ai_prediction==='Tài'?'tai':'xiu';
        pc=`<span class="pred-mini ${c}">${row.ai_prediction}</span><br><span class="pred-conf-mini">${parseFloat(row.ai_confidence||0).toFixed(1)}%</span>`;
      }
      let rb='<span class="badge b-none">—</span>';
      if(row.result==='Tài')rb='<span class="badge b-tai">TÀI</span>';
      if(row.result==='Xỉu')rb='<span class="badge b-xiu">XỈU</span>';
      let dice='';
      if(row.dice&&row.dice!=='? + ? + ?')dice=`<span class="dice">${row.dice} · ${row.total}</span>`;
      let ec='<span class="badge b-none">—</span>';
      if(row.ai_correct===true)ec='<span class="badge b-ok">✓ ĐÚNG</span>';
      else if(row.ai_correct===false)ec='<span class="badge b-fail">✗ SAI</span>';
      else if(row.ai_prediction&&row.ai_correct===null)ec='<span class="badge b-pending">⏳ CHỜ</span>';
      html+=`<tr ${trCls}><td>#${row.phien}${row.is_next?'<br><span style="font-size:9px;color:var(--primary);font-weight:800">NEXT</span>':''}</td><td>${pc}</td><td>${rb}${dice}</td><td>${ec}</td></tr>`;
    });
    tb.innerHTML=html;
  }catch(e){console.error(e);}
}
async function confirmReset(){
  Swal.fire({title:'Reset toàn bộ?',text:'Xoá cache và log?',icon:'warning',showCancelButton:true,confirmButtonColor:'#0ea5e9',cancelButtonColor:'#94a3b8',confirmButtonText:'Đồng ý',cancelButtonText:'Hủy'}).then(async r=>{
    if(!r.isConfirmed)return;
    isResetting=true;
    try{
      const res=await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      const d=await res.json();isResetting=false;
      if(d.status==='success'){
        lastPred=null;lastRecovery=false;fetchData();showToast('✅ Đã reset thành công');
      }else throw new Error(d.message||'Lỗi');
    }catch(e){isResetting=false;Swal.fire({title:'Lỗi!',text:e.message,icon:'error'});}
  });
}
fetchData();setInterval(fetchData,5000);
</script></body></html>"""

# ============================================================
# ROUTES
# ============================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid: return jsonify({'ready': False, 'message': 'Đang tải dữ liệu...', 'ai_stats': _log_stats()})
        next_phien = valid[-1]['phien'] + 1
        pred = MathPredictorV27.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        out = [{'phien': next_phien, 'is_next': True, 'result': 'Chờ...', 'dice': '? + ? + ?',
                'total': None, 'ai_prediction': pred['prediction'], 'ai_confidence': pred['confidence'],
                'ai_correct': None}]
        for v in reversed(valid[-200:]):
            if v['phien'] <= RESET_ID: continue
            log = PREDICTION_LOG.get(v['phien'])
            out.append({'phien': v['phien'], 'is_next': False, 'result': v['result'],
                        'dice': v['dice'], 'total': v['total'],
                        'ai_prediction': log['prediction'] if log else None,
                        'ai_confidence': log['confidence'] if log else None,
                        'ai_correct': log['correct'] if log else None})
        return jsonify({
            'ready': True, 'rows': out, 'ai_stats': _log_stats(),
            'prediction': {
                'prediction': pred['prediction'], 'confidence': pred['confidence'],
                'method': pred['method'], 'top_signals': pred.get('top_signals', []),
                'flipped': pred.get('flipped', False)
            }
        })
    except Exception as e:
        traceback.print_exc(); return jsonify({'error': str(e)}), 500


@app.route('/lc79md5')
def lc79md5():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối MD5 API'}), 500
        if not valid:
            return jsonify({'Id': '@cskhleminh', 'Phien': None, 'Du_doan': None, 'Xuc_xac': None,
                            'Do_tin_cay': None, 'Ket_qua_du_doan': None, 'message': 'Đang tải dữ liệu...'})
        last = valid[-1]; next_phien = last['phien'] + 1
        pred = MathPredictorV27.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        h = int(hashlib.md5(f"v27_{next_phien}_{last['phien']}".encode()).hexdigest(), 16)
        rng = random.Random(h)
        target = rng.randint(12, 17) if pred['prediction'] == 'Tài' else rng.randint(4, 9)
        dice = [1, 1, 1]
        for _ in range(60):
            d1, d2 = rng.randint(1, 6), rng.randint(1, 6)
            d3 = target - d1 - d2
            if 1 <= d3 <= 6: dice = [d1, d2, d3]; break
        return jsonify({
            'Id': '@cskhleminh', 'Phien': str(next_phien), 'Du_doan': pred['prediction'],
            'Xuc_xac': f"{dice[0]}-{dice[1]}-{dice[2]}", 'Do_tin_cay': f"{pred['confidence']}%",
            'Ket_qua_du_doan': pred['prediction'],
        })
    except Exception as e:
        traceback.print_exc(); return jsonify({'error': str(e)}), 500


@app.route('/lc79')
def lc79():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'Id': '@cskhleminh', 'Phien': None, 'Du_doan': None, 'Ket_qua': None,
                            'message': 'Đang tải dữ liệu...'})
        last = valid[-1]; next_phien = last['phien'] + 1
        pred = MathPredictorV27.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        ai_stats = _log_stats(PREDICTION_LOG)
        return jsonify({
            'Id': '@cskhleminh', 'Phien': str(next_phien), 'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%", 'Phuong_phap': pred['method'],
            'Ket_qua': f"{last['result']} {last['dice'].replace(' + ', '-')}",
            'Tin_hieu_chinh': pred.get('top_signals', []), 'Da_dao': pred.get('flipped', False),
            'AI_dung': ai_stats['correct'], 'AI_sai': ai_stats['wrong'], 'AI_cho': ai_stats['pending'],
            'Ti_le_AI': ai_stats['rate']
        })
    except Exception as e:
        traceback.print_exc(); return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid: return jsonify({'ready': False, 'prediction': None})
        last = valid[-1]; next_phien = last['phien'] + 1
        pred = MathPredictorV27.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        return jsonify({
            'version': 'V27-MathOnly', 'next_phien': next_phien, 'last_result': last['result'],
            'prediction': pred['prediction'], 'confidence': pred['confidence'],
            'method': pred['method'], 'top_signals': pred.get('top_signals', []),
            'flipped': pred.get('flipped', False), 'ai_stats': _log_stats()
        })
    except Exception as e:
        traceback.print_exc(); return jsonify({'error': str(e)}), 500


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
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys())
            HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
        else:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 400
        PREDICTION_LOG = {}
        _save_log()
        return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
