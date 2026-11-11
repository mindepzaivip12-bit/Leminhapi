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
# BẢNG PATTERN 13 KÝ TỰ
# ============================================================
def _build_pattern_table():
    table = {}
    for i in range(1 << 13):
        pat = ''.join('X' if (i >> b) & 1 else 'T' for b in range(12, -1, -1))
        nT = pat.count('T')
        nX = 13 - nT
        tail = pat[-4:]
        nT_tail = tail.count('T')
        score = (nT - nX) * 0.5 + (nT_tail - 2) * 1.2
        streak = 1
        for k in range(len(pat) - 2, -1, -1):
            if pat[k] == pat[-1]:
                streak += 1
            else:
                break
        if pat[-1] == 'T':
            score += min(streak * 0.5, 3.0)
        else:
            score -= min(streak * 0.5, 3.0)
        if len(pat) >= 6 and all(pat[k] != pat[k + 1] for k in range(len(pat) - 6, len(pat) - 1)):
            score += 2.0 if pat[-1] == 'T' else -2.0
        table[pat] = "Tài" if score >= 0 else "Xỉu"
    return table

TABLE_13 = _build_pattern_table()

def _lookup_pattern(seq_str):
    if len(seq_str) < 13:
        return None, 0
    pat = seq_str[-13:]
    res = TABLE_13.get(pat)
    if res:
        return res, 76
    return None, 0

# ============================================================
# HELPERS
# ============================================================
def _runs(seq):
    if not seq:
        return []
    out, cur, n = [], seq[0], 1
    for x in seq[1:]:
        if x == cur:
            n += 1
        else:
            out.append((cur, n))
            cur, n = x, 1
    out.append((cur, n))
    return out

def _to_seq_str(seq):
    return ''.join('T' if x == 'Tài' else 'X' for x in seq)

# ============================================================
# 🎯 MATH PREDICTOR V21 — NÂNG CAO + DATA LỊCH SỬ
# ============================================================
class MathPredictorV21:
    """
    V21: Adaptive Weighting + Data History + Advanced Markov
    """

    # ---------- 1) MARKOV (NÂNG CAO) ----------
    @staticmethod
    def _markov(seq):
        if len(seq) < 12:
            return (None, 0)
        n = len(seq)
        scores = []
        
        # Bậc 1 & 2 & 3
        for order, min_cnt, w_mult in [(1, 6, 1.0), (2, 5, 1.2), (3, 4, 1.4), (4, 3, 1.6)]:
            if n < order + 4:
                continue
            trans = defaultdict(lambda: [0, 0])
            for i in range(n - order):
                key = tuple(seq[i:i+order])
                nxt = 0 if seq[i+order] == 'Tài' else 1
                trans[key][nxt] += 1
            
            cur_key = tuple(seq[-order:])
            cnt = trans.get(cur_key)
            if cnt and sum(cnt) >= min_cnt:
                t = sum(cnt)
                p_tai = cnt[0] / t
                if p_tai >= 0.68:
                    scores.append(('Tài', p_tai * 70, w_mult))
                elif p_tai <= 0.32:
                    scores.append(('Xỉu', (1-p_tai) * 70, w_mult))

        if not scores: return (None, 0)
        w_tai = sum(s[1] * s[2] for s in scores if s[0] == 'Tài')
        w_xiu = sum(s[1] * s[2] for s in scores if s[0] == 'Xỉu')
        if w_tai + w_xiu == 0: return (None, 0)
        if w_tai >= w_xiu:
            return ('Tài', min(int(w_tai / (w_tai + w_xiu) * 88), 85))
        return ('Xỉu', min(int(w_xiu / (w_tai + w_xiu) * 88), 85))

    # ---------- 2) PATTERN 13 ----------
    @staticmethod
    def _pattern(seq):
        return _lookup_pattern(_to_seq_str(seq))

    # ---------- 3) CẦU HỌC + CHỐNG BÁM BỆT ẢO ----------
    @staticmethod
    def _cau(seq):
        if len(seq) < 6:
            return (None, 0)
        runs = _runs(seq)
        cur_val, cur_len = runs[-1]
        opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
        lens = [l for _, l in runs]

        # Nếu bệt đạt 6-8 tay (vùng nguy hiểm) -> Bẻ
        if 6 <= cur_len <= 8:
            return (opp, 78)
        # Bệt >= 9 -> Bẻ mạnh
        if cur_len >= 9:
            return (opp, 86)
        # Bệt 3-5 -> Theo
        if 3 <= cur_len <= 5:
            return (cur_val, min(62 + (cur_len - 3) * 3, 75))
        
        # Cầu 1-1
        if len(lens) >= 4 and all(l == 1 for l in lens[-4:]):
            return (opp, 74)
        if len(lens) >= 3 and all(l == 1 for l in lens[-3:]):
            return (opp, 68)
        # Cầu 2-2
        if len(lens) >= 3 and lens[-3:] == [2, 2, 2]:
            return (opp if cur_len == 2 else cur_val, 70)
        # Cầu 3-3
        if len(lens) >= 2 and lens[-2:] == [3, 3]:
            return (cur_val if cur_len < 3 else opp, 68)
        # Zigzag
        if len(lens) >= 3 and lens[-3] == 1 and lens[-2] == 1 and lens[-1] >= 2:
            return (opp, 64)
        return (None, 0)

    # ---------- 4) XU HƯỚNG + ENTROPY ----------
    @staticmethod
    def _trend(seq):
        if len(seq) < 14:
            return (None, 0)
        recent = seq[-24:]
        ratio = recent.count('Tài') / len(recent)
        
        if ratio >= 0.82: return ('Xỉu', min(72 + int((ratio - 0.8) * 80), 88))
        if ratio <= 0.18: return ('Tài', min(72 + int((0.2 - ratio) * 80), 88))
        
        if 0 < ratio < 1:
            entropy = -(ratio * math.log2(ratio) + (1 - ratio) * math.log2(1 - ratio))
            if entropy < 0.85:
                if ratio >= 0.64: return ('Tài', 66)
                if ratio <= 0.36: return ('Xỉu', 66)
        return (None, 0)

    # ---------- 5) DATA LỊCH SỬ (MỚI) ----------
    @staticmethod
    def _data_history(seq, valid_full):
        """Tìm kiếm các đoạn quá khứ giống hiện tại để xem kết quả sau đó."""
        if len(seq) < 15:
            return (None, 0)
        
        current_pat = seq[-6:]  # Xét 6 tay gần nhất
        tai_next = 0
        xiu_next = 0
        
        # Quét toàn bộ lịch sử (tối đa 500 phiên gần nhất để nhẹ máy)
        hist_seq = [v['result'] for v in valid_full[-500:]]
        for i in range(len(hist_seq) - 7):
            if hist_seq[i:i+6] == current_pat:
                if hist_seq[i+6] == 'Tài': tai_next += 1
                else: xiu_next += 1
                
        total = tai_next + xiu_next
        if total >= 3:  # Cần ít nhất 3 lần khớp trong quá khứ
            if tai_next / total >= 0.65:
                return ('Tài', min(int(tai_next / total * 80), 85))
            elif xiu_next / total >= 0.65:
                return ('Xỉu', min(int(xiu_next / total * 80), 85))
        return (None, 0)

    # ---------- 6) RECOVERY ----------
    @staticmethod
    def _recovery(log):
        if not log: return (None, 0)
        evaluated = [e for _, e in sorted(log.items(), reverse=True) if e.get('actual') is not None][:5]
        if len(evaluated) < 2: return (None, 0)
        wrong = sum(1 for e in evaluated if not e.get('correct'))
        
        if wrong >= 3: return ('Xỉu', 82)
        if wrong >= 2: return ('Xỉu', 75)
        return (None, 0)

    # ---------- MAIN ----------
    @classmethod
    def predict(cls, valid, log=None):
        if log is None: log = PREDICTION_LOG
        if not valid: return cls._fallback('Tài', 50, 'Random')

        seq = [v['result'] for v in valid]
        if len(seq) < 5:
            opp = 'Xỉu' if seq[-1] == 'Tài' else 'Tài'
            return cls._fallback(opp, 55, 'Khởi động')

        # Lấy tín hiệu
        raw = [
            ('markov',   cls._markov(seq),                1.8),
            ('pattern',  cls._pattern(seq),               1.6),
            ('cau',      cls._cau(seq),                   1.7),
            ('trend',    cls._trend(seq),                 1.4),
            ('data',     cls._data_history(seq, valid),   1.9), # Trọng số cao cho Data
            ('recovery', cls._recovery(log),              2.2),
        ]

        signals = []
        log_odds = 0.0
        total_w = 0.0
        recovery_active = False

        # ADAPTIVE WEIGHTING (Dựa trên log đúng/sai gần đây)
        recent_log = [e for _, e in sorted(log.items(), reverse=True) if e.get('actual') is not None][:10]
        algo_perf = defaultdict(lambda: {'ok': 1, 'fail': 1})
        for e in recent_log:
            m = e.get('method', '')
            if 'Markov' in m: algo_perf['markov']['ok' if e['correct'] else 'fail'] += 1
            if 'Pattern' in m: algo_perf['pattern']['ok' if e['correct'] else 'fail'] += 1
            if 'Cầu' in m: algo_perf['cau']['ok' if e['correct'] else 'fail'] += 1

        for name, (pred, conf), base_w in raw:
            if not pred or conf <= 0: continue
            
            # Điều chỉnh trọng số theo phong độ
            dynamic_w = base_w
            if name in algo_perf:
                perf = algo_perf[name]
                win_rate = perf['ok'] / (perf['ok'] + perf['fail'])
                dynamic_w *= (0.5 + win_rate)  # Nếu win rate thấp -> giảm mạnh trọng số

            p_norm = max(0.51, min(conf / 100.0, 0.94))
            lr = p_norm / (1 - p_norm)
            if pred == 'Xỉu': lr = 1.0 / lr
            
            log_odds += dynamic_w * (1.0 if pred == 'Tài' else -1.0) * (lr - 1.0)
            total_w += dynamic_w
            signals.append({'name': name, 'prediction': pred, 'confidence': conf, 'weight': round(dynamic_w, 2)})
            if name == 'recovery': recovery_active = True

        if len(signals) < 2 or total_w == 0:
            return cls._fallback_final(seq, signals)

        scaled = log_odds / total_w * 2.5
        p_tai = 1.0 / (1.0 + math.exp(-scaled))
        pred = 'Tài' if p_tai >= 0.5 else 'Xỉu'
        raw_conf = int((p_tai if pred == 'Tài' else 1 - p_tai) * 100)

        votes_tai = sum(1 for s in signals if s['prediction'] == 'Tài')
        votes_xiu = len(signals) - votes_tai
        agreement = max(votes_tai, votes_xiu) / len(signals)
        bonus = 12 if agreement == 1.0 else (6 if agreement >= 0.75 else 0)
        final_conf = max(50, min(raw_conf + bonus, 92))

        if recovery_active and pred != 'Xỉu':
            pred = 'Xỉu'
            final_conf = max(final_conf, 72)

        # Sắp xếp tín hiệu mạnh nhất lên đầu
        signals.sort(key=lambda s: s['weight'] * s['confidence'], reverse=True)
        
        # Chỉ hiển thị 2 tín hiệu chính để giao diện gọn
        top = [s['name'].upper() for s in signals[:2]]

        return {
            'prediction': pred, 'confidence': final_conf,
            'method': ' • '.join(top) if top else 'Tổng hợp',
            'signals': signals, 'top_signals': top,
            'signals_strength': [{'name': s['name'],
                                  'display': s['name'].capitalize(),
                                  'prediction': s['prediction'],
                                  'confidence': s['confidence'],
                                  'weight': s['weight'],
                                  'strength': round(s['weight'] * s['confidence'], 1)}
                                 for s in signals],
            'flipped': recovery_active, 'recovery_active': recovery_active, 'skip': False,
        }

    @staticmethod
    def _fallback(pred, conf, method):
        return {'prediction': pred, 'confidence': conf, 'method': method,
                'signals': [], 'top_signals': [], 'signals_strength': [],
                'flipped': False, 'recovery_active': False, 'skip': False}

    @classmethod
    def _fallback_final(cls, seq, signals):
        runs = _runs(seq)
        cur_val, cur_len = runs[-1]
        if cur_len >= 3:
            return {'prediction': cur_val, 'confidence': 58, 'method': 'Bệt cơ bản',
                    'signals': signals, 'top_signals': ['Bệt'], 'signals_strength': [],
                    'flipped': False, 'recovery_active': False, 'skip': False}
        opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
        return {'prediction': opp, 'confidence': 54, 'method': 'Bẻ nhịp',
                'signals': signals, 'top_signals': ['Bẻ nhịp'], 'signals_strength': [],
                'flipped': False, 'recovery_active': False, 'skip': False}


MathPredictor = MathPredictorV21
MultiStrategyPredictor = MathPredictorV21

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
                            'dice': f"{i.get('dices', [0,0,0])[0]} + {i.get('dices', [0,0,0])[1]} + {i.get('dices', [0,0,0])[2]}",
                            'total': i.get('point', sum(i.get('dices', [0, 0, 0])))
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
        history_before = [by_phien[p] for p in phien_list[:i]]
        if len(history_before) < 5: continue
        pred = MathPredictorV21.predict(history_before, log=PREDICTION_LOG)
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
    return {'correct': correct, 'wrong': wrong, 'pending': pending, 'evaluated': len(evaluated), 'rate': rate}

_load_log()

# ============================================================
# GIAO DIỆN LE MINH BON — V21 (Ẩn bớt tag, gọn gàng)
# ============================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>LE MINH BON SECH</title>
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
.brand-ver{font-size:9px;background:linear-gradient(135deg,#7c3aed,#0ea5e9);color:#fff;padding:3px 8px;border-radius:20px;font-weight:800;margin-left:6px;letter-spacing:.3px}
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

/* ẨN BỚT TAG: Chỉ hiển thị gọn gàng */
.method-row{margin-top:12px;display:flex;flex-wrap:wrap;gap:6px; min-height: 24px;}
.method-tag{font-size:10px;background:linear-gradient(135deg,#ede9fe,#ddd6fe);color:#6d28d9;border:1px solid #c4b5fd;padding:4px 10px;border-radius:12px;font-weight:700}

/* Bảng tín hiệu */
.signals-card{background:#fff;border:1px solid var(--border);border-radius:14px;padding:14px;margin-bottom:14px;box-shadow:var(--shadow-sm)}
.signals-title{font-size:11px;font-weight:800;color:var(--text-soft);text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.signals-title::before{content:'⚡';font-size:14px}
.signal-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px}
.signal{background:linear-gradient(135deg,#f0f9ff,#fff);border:1px solid var(--border);border-radius:10px;padding:9px 11px;transition:all .2s}
.signal-name{font-size:10px;color:var(--muted);font-weight:700;margin-bottom:3px;text-transform:capitalize}
.signal-val{font-size:14px;font-weight:800;display:flex;justify-content:space-between;align-items:center}
.signal-val.tai{color:var(--tai)}
.signal-val.xiu{color:var(--xiu)}
.signal-conf{font-size:10px;color:var(--muted);font-weight:700;font-family:'JetBrains Mono',monospace}

.scorebar{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px}
.sc{background:#fff;border:1px solid var(--border);border-radius:12px;padding:12px 6px;text-align:center;box-shadow:var(--shadow-sm);transition:all .2s;position:relative;overflow:hidden}
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
  .signal-grid{grid-template-columns:repeat(2,1fr)}.btn{padding:7px 10px;font-size:11px}
}
</style></head><body>

<div class="header">
  <div class="brand">
    <div class="brand-icon">🎲</div>
    <div class="brand-text">
      <div class="brand-title">LE MINH BON<span class="brand-ver">DZ</span></div>
      <div class="brand-sub">Pro Prediction Tool</div>
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
          <!-- Ẩn bớt tag chỉ hiển thị 2 tag chính -->
          <div class="method-row" id="method-row"></div>
        </div>
        <div class="conf-badge" id="conf-badge">--%</div>
      </div>
      <div class="conf-bar"><div class="conf-bar-fill" id="conf-bar" style="width:0%"></div></div>
    </div>

    <div class="signals-card">
      <div class="signals-title">Tín hiệu đang hoạt động</div>
      <div class="signal-grid" id="signal-grid"></div>
    </div>

    <div class="scorebar">
      <div class="sc sc-ok"><div class="sc-l">✓ Đúng</div><div class="sc-v ok" id="sc-correct">0</div></div>
      <div class="sc sc-fail"><div class="sc-l">✗ Sai</div><div class="sc-v fail" id="sc-wrong">0</div></div>
      <div class="sc sc-pending"><div class="sc-l">⏳ Chờ</div><div class="sc-v warn" id="sc-pending">0</div></div>
      <div class="sc sc-rate"><div class="sc-l">📊 Tỷ lệ</div><div class="sc-v primary" id="sc-rate">0%</div></div>
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
let isResetting=false;
let lastPred=null;

function showToast(msg){
  const t=document.getElementById('toast');
  t.innerText=msg;t.classList.add('show');
  clearTimeout(t._tm);t._tm=setTimeout(()=>t.classList.remove('show'),3000);
}

function manualRefresh(btn){
  btn.classList.add('spin');setTimeout(()=>btn.classList.remove('spin'),600);fetchData();
}

async function fetchData(){
  if(isResetting)return;
  document.getElementById('clock').innerText=new Date().toLocaleTimeString('vi-VN');
  try{
    const r=await fetch('/api/history',{cache:'no-store'});
    const d=await r.json();
    if(!d.ready){
      document.getElementById('loading-screen').style.display='block';
      document.getElementById('main-content').style.display='none';
      return;
    }
    document.getElementById('loading-screen').style.display='none';
    document.getElementById('main-content').style.display='block';

    const ai=d.ai_stats||{};
    document.getElementById('sc-correct').innerText=ai.correct||0;
    document.getElementById('sc-wrong').innerText=ai.wrong||0;
    document.getElementById('sc-pending').innerText=ai.pending||0;
    document.getElementById('sc-rate').innerText=(ai.rate||0)+'%';

    const pred=d.prediction, rows=d.rows||[];
    const pv=document.getElementById('pred-value');
    const cb=document.getElementById('conf-badge');
    const bar=document.getElementById('conf-bar');
    const mr=document.getElementById('method-row');

    if(!pred){
      pv.innerText='—';cb.innerText='--%';bar.style.width='0%';mr.innerHTML='';
    } else {
      pv.innerText=pred.prediction;
      pv.className='pred-value '+(pred.prediction==='Tài'?'tai':'xiu');
      cb.innerText=pred.confidence+'%';
      bar.style.width=pred.confidence+'%';

      // Chỉ hiển thị 2 tag chính
      mr.innerHTML='';
      (pred.top_signals||[]).slice(0, 2).forEach(s=>{
        const tag=document.createElement('span');
        tag.className='method-tag';tag.innerText=s;
        mr.appendChild(tag);
      });

      if(lastPred && lastPred!==pred.prediction){
        showToast('🎯 Dự đoán đổi → '+pred.prediction+' ('+pred.confidence+'%)');
      }
      lastPred=pred.prediction;
    }

    // Render bảng tín hiệu (chỉ hiển thị 3-4 cái chính)
    const sg=document.getElementById('signal-grid');
    if(pred && pred.signals_strength && pred.signals_strength.length){
      sg.innerHTML=pred.signals_strength.slice(0, 4).map(s=>{
        const cls=s.prediction==='Tài'?'tai':'xiu';
        return `<div class="signal">
          <div class="signal-name">${s.display}</div>
          <div class="signal-val ${cls}">
            <span>${s.prediction}</span>
            <span class="signal-conf">${s.confidence}%</span>
          </div>
        </div>`;
      }).join('');
    } else {
      sg.innerHTML='<div class="signal"><div class="signal-name">Chưa có tín hiệu</div></div>';
    }

    const tb=document.getElementById('tbody');
    if(!rows.length){
      tb.innerHTML='<tr><td colspan="4" class="loading">Chưa có dữ liệu</td></tr>';return;
    }
    let html='';
    rows.forEach(row=>{
      const trCls=row.is_next?'class="row-next"':'';
      let predCell='<span class="badge b-none">—</span>';
      if(row.ai_prediction){
        const cls=row.ai_prediction==='Tài'?'tai':'xiu';
        predCell=`<span class="pred-mini ${cls}">${row.ai_prediction}</span><br><span class="pred-conf-mini">${row.ai_confidence||0}%</span>`;
      }
      let resBadge='<span class="badge b-none">—</span>';
      if(row.result==='Tài')resBadge='<span class="badge b-tai">TÀI</span>';
      if(row.result==='Xỉu')resBadge='<span class="badge b-xiu">XỈU</span>';
      let dice='';
      if(row.dice&&row.dice!=='? + ? + ?')dice=`<span class="dice">${row.dice} · ${row.total}</span>`;
      let evalCell='<span class="badge b-none">—</span>';
      if(row.ai_correct===true)evalCell='<span class="badge b-ok">✓ ĐÚNG</span>';
      else if(row.ai_correct===false)evalCell='<span class="badge b-fail">✗ SAI</span>';
      else if(row.ai_prediction&&row.ai_correct===null)evalCell='<span class="badge b-pending">⏳ CHỜ</span>';
      html+=`<tr ${trCls}>
        <td>#${row.phien}${row.is_next?'<br><span style="font-size:9px;color:var(--primary);font-weight:800">NEXT</span>':''}</td>
        <td>${predCell}</td>
        <td>${resBadge}${dice}</td>
        <td>${evalCell}</td>
      </tr>`;
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
      const d=await res.json();
      isResetting=false;
      if(d.status==='success'){
        lastPred=null;fetchData();showToast('✅ Đã reset thành công');
      } else throw new Error(d.message||'Lỗi');
    }catch(e){isResetting=false;Swal.fire({title:'Lỗi!',text:e.message,icon:'error'});}
  });
}

fetchData();
setInterval(fetchData,5000);
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
        pred = MathPredictorV21.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)

        out = [{'phien': next_phien, 'is_next': True, 'result': 'Chờ...', 'dice': '? + ? + ?', 'total': None, 'ai_prediction': pred['prediction'], 'ai_confidence': pred['confidence'], 'ai_correct': None}]
        for v in reversed(valid[-200:]):
            if v['phien'] <= RESET_ID: continue
            log = PREDICTION_LOG.get(v['phien'])
            out.append({'phien': v['phien'], 'is_next': False, 'result': v['result'], 'dice': v['dice'], 'total': v['total'], 'ai_prediction': log['prediction'] if log else None, 'ai_confidence': log['confidence'] if log else None, 'ai_correct': log['correct'] if log else None})
        
        return jsonify({
            'ready': True, 'rows': out, 'ai_stats': _log_stats(),
            'prediction': {
                'prediction': pred['prediction'], 'confidence': pred['confidence'],
                'method': pred['method'], 'top_signals': pred.get('top_signals', []),
                'signals_strength': pred.get('signals_strength', []),
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
        if not valid: return jsonify({'Id': '@cskhleminh', 'Phien': None, 'Du_doan': None, 'Xuc_xac': None, 'Do_tin_cay': None, 'Ket_qua_du_doan': None, 'message': 'Đang tải dữ liệu...'})
        last = valid[-1]; next_phien = last['phien'] + 1
        pred = MathPredictorV21.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        
        h = int(hashlib.md5(f"v21_{next_phien}_{last['phien']}".encode()).hexdigest(), 16)
        rng = random.Random(h)
        target = rng.randint(12, 17) if pred['prediction'] == 'Tài' else rng.randint(4, 9)
        dice = [1,1,1]
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
        if not valid: return jsonify({'Id': '@cskhleminh', 'Phien': None, 'Du_doan': None, 'Ket_qua': None, 'message': 'Đang tải dữ liệu...'})
        last = valid[-1]; next_phien = last['phien'] + 1
        pred = MathPredictorV21.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        ai_stats = _log_stats(PREDICTION_LOG)
        return jsonify({
            'Id': '@cskhleminh', 'Phien': str(next_phien), 'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%", 'Phuong_phap': pred['method'],
            'Ket_qua': f"{last['result']} {last['dice'].replace(' + ', '-')}",
            'Tin_hieu_chinh': pred.get('top_signals', []), 'Da_dao': pred.get('flipped', False),
            'AI_dung': ai_stats['correct'], 'AI_sai': ai_stats['wrong'], 'AI_cho': ai_stats['pending'], 'Ti_le_AI': ai_stats['rate'],
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
        pred = MathPredictorV21.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        return jsonify({
            'version': 'V21-Pro', 'next_phien': next_phien, 'last_result': last['result'],
            'prediction': pred['prediction'], 'confidence': pred['confidence'],
            'method': pred['method'], 'top_signals': pred.get('top_signals', []),
            'signals_strength': pred.get('signals_strength', []), 'ai_stats': _log_stats(),
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
                RESET_ID = valid[-1]['phien']; HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys()); HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
        else: return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 400
        PREDICTION_LOG = {}; _save_log()
        return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
