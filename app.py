import os
import traceback
import time
import json
import hashlib
import math
import random
from datetime import datetime
from collections import Counter, defaultdict, deque
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

# Trạng thái Làm Nét
SHARP_FOCUS_MODE = False

SIGNAL_NAMES = {
    'markov': 'Markov', 'streak': 'Bẻ chuỗi', 'pattern': 'Khớp mẫu',
    'trend': 'Xu hướng', 'cycle': 'Chu kỳ', 'entropy': 'Entropy',
    'cau11': 'Cầu 1-1', 'cau22': 'Cầu 2-2', 'cau33': 'Cầu 3-3',
    'breakpoint': 'Điểm gãy', 'dao_cau': 'Đảo cầu', 'meta': 'Meta'
}

# ========== HELPER ==========
def _runs(seq):
    if not seq: return []
    out, cur, n = [], seq[0], 1
    for x in seq[1:]:
        if x == cur: n += 1
        else: out.append((cur, n)); cur, n = x, 1
    out.append((cur, n))
    return out

def _entropy(seq):
    if len(seq) < 5: return 0.0
    c = Counter(seq); total = len(seq); h = 0.0
    for v in c.values():
        p = v / total
        if p > 0: h -= p * math.log2(p)
    return h

def _tai_ratio(seq, win):
    if not seq or win <= 0: return 0.5
    seg = seq[-win:] if len(seq) >= win else seq
    return sum(1 for x in seg if x == 'Tài') / len(seg)

def _opp(x):
    return 'Xỉu' if x == 'Tài' else 'Tài'

def _detect_regime(seq):
    if len(seq) < 12: return 'random', 0.0
    runs = _runs(seq[-26:])
    if not runs: return 'random', 0.0
    L = [l for _, l in runs]; n = len(L)
    ones = sum(1 for l in L if l == 1) / n
    longs = sum(1 for l in L if l >= 4) / n
    twos = sum(1 for l in L if l == 2) / n
    threes = sum(1 for l in L if l == 3) / n
    tr = _tai_ratio(seq, 30)
    h = _entropy(seq[-30:])

    if h > 0.97 and ones < 0.42 and longs < 0.20: return 'chaos', h
    if ones >= 0.55: return 'alternation', ones
    if twos >= 0.55: return 'cau22', twos
    if threes >= 0.45: return 'cau33', threes
    if longs >= 0.35: return 'streak', longs
    if tr >= 0.68 or tr <= 0.32: return 'trend_strong', abs(tr - 0.5) * 2
    return 'short_run', max(ones, twos, threes)

# ========== PREDICTOR V1 (TÍCH HỢP LÀM NÉT) ==========
class MultiStrategyPredictor:
    _TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0})
    _RECENT = deque(maxlen=15)
    _RECOVERY = {'active': False, 'fail': 0, 'mode': None}

    @staticmethod
    def _sig_dao_cau(seq):
        if len(seq) < 10: return (None, 0, 0)
        runs = _runs(seq[-15:])
        if not runs: return (None, 0, 0)
        cur_val, cur_len = runs[-1]
        if len(runs) >= 6:
            last_6 = [l for _, l in runs[-6:]]
            if all(l == 1 for l in last_6): return (_opp(cur_val), 75, 1.5)
        if cur_len >= 5: return (_opp(cur_val), min(58 + cur_len * 4, 85), 1.45)
        if len(runs) >= 4:
            lens = [l for _, l in runs[-4:]]
            if lens == [2, 2, 2, 2]: return (_opp(cur_val), 72, 1.4)
            if lens == [3, 3, 3, 3]: return (_opp(cur_val), 72, 1.4)
        return (None, 0, 0)

    @staticmethod
    def _sig_streak(seq, regime):
        runs = _runs(seq)
        if not runs: return (None, 0, 0)
        cur_val, cur_len = runs[-1]
        opp = _opp(cur_val)
        if regime == 'streak':
            if cur_len <= 4: return (cur_val, min(58 + cur_len * 3, 75), 1.2)
            if cur_len >= 6: return (opp, min(60 + (cur_len - 5) * 4, 84), 1.35)
        if regime == 'alternation': return (opp, 66, 1.4)
        if cur_len >= 5: return (opp, min(58 + (cur_len - 4) * 3, 78), 1.15)
        return (None, 0, 0)

    @staticmethod
    def _sig_markov(seq):
        best = (None, 0, 0)
        for order in (4, 3, 2):
            if len(seq) < order + 8: continue
            trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
            for i in range(len(seq) - order):
                trans[tuple(seq[i:i + order])][seq[i + order]] += 1
            c = trans[tuple(seq[-order:])]
            t = c['Tài'] + c['Xỉu']
            if t < 3: continue
            p = (c['Tài'] + 1) / (t + 2)
            if p >= 0.66 or p <= 0.34:
                pred = 'Tài' if p >= 0.5 else 'Xỉu'
                base = max(p, 1 - p)
                conf = min(int(base * 100) + order * 2, 86)
                w = 1.30 + order * 0.12
                if conf * w > best[1] * best[2]: best = (pred, conf, w)
        return best

    @staticmethod
    def _sig_pattern(seq):
        if len(seq) < 10: return (None, 0, 0)
        best = (None, 0, 0)
        for plen in (7, 6, 5, 4, 3):
            if len(seq) < plen + 5: continue
            pat = tuple(seq[-plen:])
            matches = [seq[i + plen] for i in range(len(seq) - plen - 1) if tuple(seq[i:i + plen]) == pat]
            if len(matches) < 3: continue
            c = Counter(matches)
            top, cnt = c.most_common(1)[0]
            ratio = cnt / len(matches)
            if ratio >= 0.68:
                conf = min(54 + int(ratio * 28) + plen * 2, 88)
                w = 1.20 + plen * 0.10
                if conf * w > best[1] * best[2]: best = (top, conf, w)
        return best

    @staticmethod
    def _sig_trend(seq):
        if len(seq) < 15: return (None, 0, 0)
        votes = []
        for w in (5, 8, 12, 18, 25):
            if len(seq) < w: continue
            p = _tai_ratio(seq, w)
            if p >= 0.64: votes.append(('Tài', p))
            elif p <= 0.36: votes.append(('Xỉu', p))
        if len(votes) < 3: return (None, 0, 0)
        c = Counter(v[0] for v in votes)
        top, cnt = c.most_common(1)[0]
        if cnt >= 3:
            avg = sum(v[1] if top == 'Tài' else 1 - v[1] for v in votes if v[0] == top) / cnt
            return (top, min(int(avg * 100) + cnt * 2, 84), 1.30)
        return (None, 0, 0)

    @staticmethod
    def _sig_cycle(seq):
        if len(seq) < 14: return (None, 0, 0)
        best = None
        for period in range(2, 10):
            if len(seq) < period * 3: break
            pat = seq[-period:]
            ok = all(seq[-period * (k + 1):-period * k] == pat for k in range(3))
            if not ok: continue
            hits = sum(1 for i in range(period, len(seq)) if seq[i] == seq[i - period])
            total = len(seq) - period
            score = hits / total if total else 0
            if score >= 0.70 and (best is None or score > best[0]):
                best = (score, period, pat)
        if not best: return (None, 0, 0)
        _, period, pat = best
        nxt = pat[len(seq) % period]
        return (nxt, min(58 + int(best[0] * 26), 84), 1.35)

    @staticmethod
    def _sig_entropy(seq):
        if len(seq) < 12: return (None, 0, 0)
        seg = seq[-22:]
        h = _entropy(seg)
        p = _tai_ratio(seg, len(seg))
        if h < 0.72:
            if p >= 0.64: return ('Tài', 66, 1.20)
            if p <= 0.36: return ('Xỉu', 66, 1.20)
        if h > 0.97: return (_opp(seq[-1]), 60, 1.05)
        return (None, 0, 0)

    @classmethod
    def _calibrate(cls, conf, log):
        evaluated = [(p, e) for p, e in log.items() if e.get('actual') is not None]
        if len(evaluated) < 20: return conf
        evaluated.sort(reverse=True)
        recent = evaluated[:50]
        acc = sum(1 for _, e in recent if e.get('correct')) / len(recent)
        if acc < 0.40: return max(50, conf - 14)
        if acc < 0.46: return max(50, conf - 8)
        if acc < 0.52: return max(50, conf - 3)
        if acc > 0.70: return min(90, conf + 6) # Nâng trần lên 90%
        if acc > 0.62: return min(88, conf + 3)
        return conf

    @classmethod
    def _update_recovery(cls, log):
        evaluated = [(p, e) for p, e in sorted(log.items(), reverse=True) if e.get('actual') is not None][:8]
        cls._RECENT.clear()
        for _, e in reversed(evaluated): cls._RECENT.append(bool(e.get('correct')))
        fail = 0
        for _, e in evaluated:
            if e.get('correct') is False: fail += 1
            else: break
        cls._RECOVERY['fail'] = fail
        if fail >= 3: cls._RECOVERY['active'] = True; cls._RECOVERY['mode'] = 'hard_flip'
        elif fail == 2: cls._RECOVERY['active'] = True; cls._RECOVERY['mode'] = 'soft_flip'
        else: cls._RECOVERY['active'] = False; cls._RECOVERY['mode'] = None

    _REGIME_BOOST = {
        'streak': {'streak': 1.3, 'markov': 1.2, 'dao_cau': 1.4},
        'alternation': {'cau11': 1.35, 'dao_cau': 1.4},
        'cau22': {'cau22': 1.4, 'cycle': 1.15, 'dao_cau': 1.3},
        'cau33': {'cau33': 1.4, 'cycle': 1.15, 'dao_cau': 1.3},
        'trend_strong': {'trend': 1.3, 'entropy': 1.15},
        'chaos': {'entropy': 1.25, 'dao_cau': 1.2},
        'short_run': {'cycle': 1.15, 'pattern': 1.1},
        'random': {},
    }

    @classmethod
    def predict(cls, valid, log=None, is_sharp=False):
        if log is None: log = PREDICTION_LOG
        if not valid:
            return cls._empty_result('Tài', 50, 'Chưa có DL', 'Không có dữ liệu')

        cls._update_recovery(log)
        seq = [v['result'] for v in valid]

        if len(seq) < 5:
            run_val, run_len = _runs(seq)[-1]
            return cls._empty_result(_opp(run_val), min(52 + run_len * 2, 68), 'Khởi động', 'Khởi động')

        regime, regime_strength = _detect_regime(seq)

        raw = [
            ('markov', cls._sig_markov(seq)),
            ('streak', cls._sig_streak(seq, regime)),
            ('pattern', cls._sig_pattern(seq)),
            ('trend', cls._sig_trend(seq)),
            ('cycle', cls._sig_cycle(seq)),
            ('entropy', cls._sig_entropy(seq)),
            ('dao_cau', cls._sig_dao_cau(seq)),
        ]

        signals = []
        weighted_votes = {'Tài': 0.0, 'Xỉu': 0.0}
        total_w = 0.0
        regime_boost = cls._REGIME_BOOST.get(regime, {})

        for name, (pred, conf, weight) in raw:
            if not pred or weight <= 0: continue
            
            # --- XỬ LÝ LÀM NÉT ---
            # 1. Lọc nhiễu: Nếu đang Làm Nét mà tín hiệu này winrate < 45%, bỏ qua
            tr = cls._TRACK.get(name)
            if is_sharp and tr and (tr['hit'] + tr['miss']) >= 5:
                acc = tr['hit'] / (tr['hit'] + tr['miss'])
                if acc < 0.45:
                    continue # Bỏ qua tín hiệu rác
                if acc > 0.60:
                    weight *= 1.5 # Boost mạnh tín hiệu tốt
                    
            # 2. Điều chỉnh trọng số cơ bản
            if tr and (tr['hit'] + tr['miss']) >= 6:
                acc = tr['hit'] / (tr['hit'] + tr['miss'])
                weight *= max(0.45, min(0.60 + (acc - 0.5) * 3.0, 1.70))
                
            if name in regime_boost:
                weight *= regime_boost[name]
                
            if is_sharp:
                # Nếu Làm Nét, ưu tiên tuyệt đối các tín hiệu đoán ngược (Bẻ cầu/Đảo cầu)
                if name in ('dao_cau', 'streak', 'breakpoint'):
                    weight *= 1.4
                conf = min(conf + 3, 92) # Cộng thêm 3% tự tin

            weighted_votes[pred] += weight * (conf / 100.0)
            total_w += weight
            signals.append({'name': name, 'prediction': pred, 'confidence': conf, 'weight': round(weight, 2)})

        if not signals or total_w == 0:
            run_val, _ = _runs(seq)[-1]
            return cls._empty_result(_opp(run_val), 52, 'Fallback', 'Không đủ tín hiệu', regime=regime)

        v_tai = weighted_votes['Tài']
        v_xiu = weighted_votes['Xỉu']
        pred = 'Tài' if v_tai >= v_xiu else 'Xỉu'
        raw_conf = int(max(v_tai, v_xiu) / max(v_tai + v_xiu, 1e-6) * 100)

        votes_tai = sum(1 for s in signals if s['prediction'] == 'Tài')
        agreement = max(votes_tai, len(signals) - votes_tai) / len(signals)
        recent_h = _entropy(seq[-22:])
        
        penalty = 0
        bonus = 0
        if recent_h > 0.96: penalty += 7
        elif recent_h > 0.88: penalty += 4
        elif recent_h < 0.70: bonus += 3
        if agreement < 0.60: penalty += 6
        elif agreement < 0.70: penalty += 3
        elif agreement >= 0.88: bonus += 5
        if regime_strength > 0.6: bonus += 3

        # --- LÀM NÉT: Ép xung Confidence ---
        if is_sharp and agreement >= 0.75:
            bonus += 5  # Thưởng thêm nếu các tín hiệu đồng thuận cao

        final_conf = max(50, min(raw_conf - penalty + bonus, 92 if is_sharp else 86))

        flipped = False
        mode = cls._RECOVERY.get('mode')
        if mode == 'hard_flip':
            pred = _opp(pred); final_conf = max(60, min(final_conf + 3, 78)); flipped = True
        elif mode == 'soft_flip' and agreement < 0.70:
            pred = _opp(pred); final_conf = max(58, min(final_conf + 1, 74)); flipped = True

        final_conf = cls._calibrate(final_conf, log)
        signals.sort(key=lambda s: s['weight'] * (s['confidence'] - 50), reverse=True)
        top = [SIGNAL_NAMES.get(s['name'], s['name']) for s in signals[:3]]

        return {
            'prediction': pred,
            'confidence': final_conf,
            'method': ' + '.join(top) if top else 'Tổng hợp',
            'signals': signals,
            'top_signals': top,
            'signals_strength': [{'name': s['name'], 'display': SIGNAL_NAMES.get(s['name'], s['name']), 'prediction': s['prediction'], 'confidence': s['confidence'], 'weight': s['weight'], 'strength': round(s['weight'] * (s['confidence'] - 50), 1)} for s in signals[:8]],
            'reason': f'Regime={regime} · Agreement={agreement:.0%} · Focus={is_sharp}',
            'flipped': flipped,
            'cau': regime,
            'cau_label': cls._cau_label(regime),
            'recovery_active': cls._RECOVERY['active'],
            'fail_streak': cls._RECOVERY['fail'],
            'regime_strength': round(regime_strength, 3),
            'sharp_focus': is_sharp
        }

    @staticmethod
    def _cau_label(regime):
        labels = {'streak': 'Cầu bệt', 'alternation': 'Cầu 1-1', 'cau22': 'Cầu 2-2', 'cau33': 'Cầu 3-3', 'trend_strong': 'Cầu nghiêng', 'chaos': 'Cầu hỗn loạn', 'short_run': 'Cầu ngắn', 'random': 'Ngẫu nhiên'}
        return labels.get(regime, '')

    @staticmethod
    def _empty_result(pred, conf, method, reason, regime='unknown'):
        return {'prediction': pred, 'confidence': conf, 'method': method, 'signals': [], 'top_signals': [], 'signals_strength': [], 'reason': reason, 'flipped': False, 'cau': regime, 'cau_label': '', 'recovery_active': False, 'fail_streak': 0, 'regime_strength': 0.0, 'sharp_focus': False}

# ========== THUẬT TOÁN DỰ ĐOÁN 3 CON XÚC XẮC ==========
def _predict_dice(valid, pred_result):
    if not valid or len(valid) < 5:
        if pred_result == 'Tài': return sorted([random.randint(2, 6), random.randint(2, 6), random.randint(3, 6)], reverse=True)
        else: return sorted([random.randint(1, 4), random.randint(1, 4), random.randint(1, 4)], reverse=True)

    recent = valid[-30:]
    dices_history = []
    for v in recent:
        try:
            parts = v['dice'].split(' + ')
            if len(parts) == 3: dices_history.append([int(p) for p in parts])
        except: continue

    if not dices_history: return sorted([random.randint(1, 6) for _ in range(3)], reverse=True)

    freq = [Counter(), Counter(), Counter()]
    for d in dices_history:
        for i in range(3): freq[i][d[i]] += 1

    predicted = []
    for i in range(3):
        if not freq[i]: 
            predicted.append(random.randint(1, 6))
            continue
        top_2 = freq[i].most_common(2)
        if len(top_2) == 2 and random.random() < 0.7: predicted.append(top_2[0][0])
        elif len(top_2) == 2: predicted.append(top_2[1][0])
        else: predicted.append(top_2[0][0])

    current_sum = sum(predicted)
    if pred_result == 'Tài' and current_sum <= 10:
        diff = 11 - current_sum
        while diff > 0:
            idx = random.randint(0, 2)
            if predicted[idx] < 6: predicted[idx] += 1; diff -= 1
    elif pred_result == 'Xỉu' and current_sum >= 11:
        diff = current_sum - 10
        while diff > 0:
            idx = random.randint(0, 2)
            if predicted[idx] > 1: predicted[idx] -= 1; diff -= 1

    predicted.sort(reverse=True)
    return predicted

# ========== FETCH + SYNC ==========
def fetch_sessions():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Accept': 'application/json'}
    for attempt in range(3):
        try:
            r = requests.get(API_URL_MD5, timeout=8, headers=headers)
            if r.status_code == 200:
                data = r.json()
                if 'list' in data and data['list']:
                    rows = []
                    for item in data['list']:
                        res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
                        dices = item.get('dices', [0, 0, 0])
                        rows.append({'phien': int(item['id']), 'result': res, 'dice': f"{dices[0]} + {dices[1]} + {dices[2]}", 'total': item.get('point', sum(dices))})
                    return rows, True
        except Exception: time.sleep(1)
    return [], False

def _load_log():
    global PREDICTION_LOG, RESET_ID, SHARP_FOCUS_MODE
    if not os.path.exists(LOG_FILE): return
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        PREDICTION_LOG = {int(k): v for k, v in data.get('log', {}).items()}
        RESET_ID = int(data.get('reset_id', 0))
        SHARP_FOCUS_MODE = data.get('sharp_focus', False)
    except Exception: pass

def _save_log():
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'log': PREDICTION_LOG, 'reset_id': RESET_ID, 'sharp_focus': SHARP_FOCUS_MODE}, f)
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
        if entry.get('actual') is not None: continue
        if phien in by_phien:
            actual = by_phien[phien]['result']
            entry['actual'] = actual
            entry['correct'] = (entry['prediction'] == actual)
    changed = False
    for i, phien in enumerate(phien_list):
        if phien in PREDICTION_LOG or phien <= RESET_ID: continue
        history_before = [by_phien[p] for p in phien_list[:i]]
        if len(history_before) < 3: continue
        pred = MultiStrategyPredictor.predict(history_before, log=PREDICTION_LOG, is_sharp=SHARP_FOCUS_MODE)
        actual = by_phien[phien]['result']
        PREDICTION_LOG[phien] = {'prediction': pred['prediction'], 'confidence': pred['confidence'], 'method': pred['method'], 'actual': actual, 'correct': (pred['prediction'] == actual), 'logged_at': datetime.now().isoformat(), 'retroactive': True, 'flipped': pred.get('flipped', False)}
        changed = True
    if len(PREDICTION_LOG) > MAX_LOG_SIZE:
        keys = sorted(PREDICTION_LOG.keys())[:len(PREDICTION_LOG) - MAX_LOG_SIZE]
        for k in keys: del PREDICTION_LOG[k]
        changed = True
    if changed: _save_log()

def _log_prediction(phien, pred_result):
    if phien in PREDICTION_LOG: return
    PREDICTION_LOG[phien] = {'prediction': pred_result['prediction'], 'confidence': pred_result['confidence'], 'method': pred_result['method'], 'actual': None, 'correct': None, 'logged_at': datetime.now().isoformat(), 'retroactive': False, 'flipped': pred_result.get('flipped', False)}
    _save_log()

def _log_stats(log=None):
    if log is None: log = PREDICTION_LOG
    evaluated = [e for e in log.values() if e.get('actual') is not None]
    correct = sum(1 for e in evaluated if e.get('correct'))
    wrong = len(evaluated) - correct
    pending = sum(1 for e in log.values() if e.get('actual') is None)
    return {'correct': correct, 'wrong': wrong, 'pending': pending, 'evaluated': len(evaluated), 'accuracy': round(correct / max(len(evaluated), 1) * 100, 1)}

_load_log()

# ========== GIAO DIỆN LEMINH V1 (CÓ NÚT LÀM NÉT) ==========
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>LEMINH V1</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
:root{--bg-1:#eff6ff;--bg-2:#f0f9ff;--bg-3:#e0f2fe;--card:#ffffff;--text:#0f172a;--text-soft:#475569;--muted:#94a3b8;--border:#dbeafe;--border-blue:#93c5fd;--border-strong:#60a5fa;--primary:#0ea5e9;--primary-dark:#0284c7;--tai:#0284c7;--tai-bg:#e0f2fe;--xiu:#0891b2;--xiu-bg:#cffafe;--ok:#059669;--ok-bg:#d1fae5;--fail:#dc2626;--fail-bg:#fee2e2;--warn:#d97706;--warn-bg:#fef3c7;--shadow:0 4px 12px rgba(14,165,233,.10);--shadow-lg:0 12px 32px rgba(2,132,199,.15)}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Plus Jakarta Sans',sans-serif}
body{background:linear-gradient(135deg,#eff6ff,#f0f9ff 35%,#e0f2fe 70%,#dbeafe);background-attachment:fixed;color:var(--text);min-height:100vh;padding-bottom:30px;font-size:13px}
.header{background:rgba(255,255,255,.9);backdrop-filter:blur(20px);border-bottom:1px solid var(--border-blue);padding:12px 16px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(14,165,233,.08)}
.logo{font-size:16px;font-weight:800;display:flex;align-items:center;gap:8px}
.logo-text{background:linear-gradient(90deg,#0284c7,#0ea5e9,#38bdf8,#0284c7);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:shine 4s linear infinite}
@keyframes shine{to{background-position:200% center}}
.logo span.ver{font-size:9px;background:linear-gradient(135deg,#0284c7,#0ea5e9);color:#fff;padding:3px 8px;border-radius:20px;font-weight:800}
.actions{display:flex;gap:6px;align-items:center}
.clock{font-size:11px;color:var(--muted);font-weight:600;font-variant-numeric:tabular-nums;margin-right:4px}
.btn{background:#fff;color:var(--text-soft);border:1px solid var(--border);padding:7px 10px;border-radius:9px;font-weight:700;font-size:11px;cursor:pointer;transition:.2s;display:flex;align-items:center;gap:4px}
.btn:hover{background:var(--bg-1);transform:translateY(-1px);border-color:var(--border-strong);color:var(--primary-dark)}
.btn-active{background:linear-gradient(135deg,#e0f2fe,#bae6fd);border-color:var(--primary);color:var(--primary-dark);box-shadow:0 0 10px rgba(14,165,233,0.3)}
.btn-reset{background:linear-gradient(135deg,#fee2e2,#fecaca);color:var(--fail);border-color:#fca5a5}
.spin{animation:spin .5s}@keyframes spin{to{transform:rotate(360deg)}}
.wrap{max-width:780px;margin:0 auto;padding:12px}
.pred-box{background:linear-gradient(135deg,#fff,#eff6ff);border:1px solid var(--border-blue);border-radius:16px;padding:18px;margin-bottom:12px;position:relative;overflow:hidden;box-shadow:var(--shadow-lg)}
.pred-box::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#0284c7,#0ea5e9,#38bdf8,#0284c7);background-size:200% 100%;animation:shine 3s linear infinite}
.pred-row{display:flex;align-items:center;justify-content:space-between}
.pred-label{font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:700;letter-spacing:.5px;margin-bottom:6px}
.pred-value{font-size:34px;font-weight:800;line-height:1}
.pred-value.tai{color:var(--tai)}.pred-value.xiu{color:var(--xiu)}
.pred-conf-badge{background:linear-gradient(135deg,#dbeafe,#bfdbfe);border:1px solid var(--border-strong);color:var(--primary-dark);padding:7px 16px;border-radius:20px;font-weight:800;font-size:15px}
.conf-bar{height:5px;background:var(--bg-1);border-radius:3px;overflow:hidden;margin-top:14px}
.conf-bar-fill{height:100%;background:linear-gradient(90deg,#0284c7,#0ea5e9,#38bdf8);transition:width 1s ease}
.scorebar{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px}
.sc{background:#fff;border:1px solid var(--border);border-radius:11px;padding:12px 8px;text-align:center}
.sc-l{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:700;margin-bottom:4px}
.sc-v{font-size:20px;font-weight:800}
.sc-v.ok{color:var(--ok)}.sc-v.fail{color:var(--fail)}.sc-v.warn{color:var(--warn)}.sc-v.info{color:var(--primary-dark)}
.tbl{background:#fff;border:1px solid var(--border);border-radius:14px;overflow:hidden;max-height:65vh;overflow-y:auto;box-shadow:var(--shadow)}
table{width:100%;border-collapse:separate;border-spacing:0}
th{background:linear-gradient(135deg,#eff6ff,#dbeafe);color:var(--primary-dark);font-size:10px;font-weight:700;padding:12px 6px;text-align:center;border-bottom:1px solid var(--border-blue);position:sticky;top:0;z-index:10}
td{padding:10px 6px;text-align:center;border-bottom:1px solid var(--bg-1);font-size:12px;font-weight:600}
tr:hover td{background:#eff6ff}
.row-next{background:linear-gradient(90deg,#e0f2fe,#fff);border-left:3px solid var(--primary)}
.badge{display:inline-block;padding:3px 10px;border-radius:14px;font-size:10px;font-weight:800;min-width:52px}
.b-tai{background:var(--tai-bg);color:var(--tai);border:1px solid #7dd3fc}
.b-xiu{background:var(--xiu-bg);color:var(--xiu);border:1px solid #67e8f9}
.b-none{background:var(--bg-1);color:var(--muted);border:1px solid var(--border)}
.b-ok{background:var(--ok-bg);color:var(--ok);border:1px solid #6ee7b7}
.b-fail{background:var(--fail-bg);color:var(--fail);border:1px solid #fca5a5}
.b-pending{background:var(--warn-bg);color:var(--warn);border:1px solid #fcd34d}
.dice{font-size:10px;color:var(--muted);display:block;margin-top:2px}
.pred-mini{font-size:11px;font-weight:800}
.pred-mini.tai{color:var(--tai)}.pred-mini.xiu{color:var(--xiu)}
.loading{text-align:center;padding:30px;color:var(--primary);font-weight:600}
@media(max-width:520px){th,td{padding:8px 4px;font-size:11px}.clock{display:none}.badge{min-width:44px;font-size:9px}.sc-v{font-size:16px}.pred-value{font-size:26px}.btn span{display:none}}
</style></head><body>
<div class="header"><div class="logo"><span class="logo-text">LEMINH</span><span class="ver">V1</span></div>
<div class="actions">
  <div class="clock" id="clock">--:--:--</div>
  <button class="btn" id="btn-sharp" onclick="toggleSharp()" title="Làm nét dự đoán"> <span>Làm Nét</span></button>
  <button class="btn" onclick="manualRefresh(this)" title="Tải lại">↻</button>
  <button class="btn btn-reset" onclick="confirmReset()" title="Reset">Reset</button>
</div></div>
<div class="wrap">
<div id="loading-screen" class="loading" style="display:none;">🌊 Đang tải dữ liệu...</div>
<div id="main-content">
<div class="pred-box"><div class="pred-row">
<div><div class="pred-label">Dự đoán phiên tiếp theo</div>
<div class="pred-value" id="pred-value">—</div></div>
<div class="pred-conf-badge" id="conf-badge">--%</div></div>
<div class="conf-bar"><div class="conf-bar-fill" id="conf-bar" style="width:0%"></div></div></div>
<div class="scorebar">
<div class="sc"><div class="sc-l">✓ Đúng</div><div class="sc-v ok" id="sc-correct">0</div></div>
<div class="sc"><div class="sc-l">✗ Sai</div><div class="sc-v fail" id="sc-wrong">0</div></div>
<div class="sc"><div class="sc-l">Chờ</div><div class="sc-v warn" id="sc-pending">0</div></div>
<div class="sc"><div class="sc-l">Tỉ lệ</div><div class="sc-v info" id="sc-acc">0%</div></div>
</div>
<div class="tbl"><table><thead><tr><th>Phiên</th><th>Dự đoán</th><th>Kết quả</th><th>Đúng/Sai</th></tr></thead>
<tbody id="tbody"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody></table></div>
</div></div>
<script>
let isResetting=false;
let sharpMode=false;

async function fetchSharpState() {
    try {
        const r = await fetch('/api/sharp_state');
        const d = await r.json();
        sharpMode = d.sharp;
        updateSharpBtn();
    } catch(e) {}
}
function updateSharpBtn() {
    const btn = document.getElementById('btn-sharp');
    if(sharpMode) btn.classList.add('btn-active');
    else btn.classList.remove('btn-active');
}
async function toggleSharp() {
    try {
        const r = await fetch('/api/sharp', {method: 'POST'});
        const d = await r.json();
        sharpMode = d.sharp;
        updateSharpBtn();
        fetchData();
        Swal.fire({title: sharpMode ? 'Bật Làm Nét' : 'Tắt Làm Nét', text: sharpMode ? 'Đang dùng thuật toán quét sâu!' : 'Đã trở về chế độ thường.', icon: 'success', timer: 1500, showConfirmButton: false});
    } catch(e) {}
}

function manualRefresh(btn){btn.classList.add('spin');setTimeout(()=>btn.classList.remove('spin'),500);fetchData();}
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
    document.getElementById('sc-acc').innerText=(ai.accuracy||0)+'%';
    
    const pred=d.prediction, rows=d.rows||[];
    const pv=document.getElementById('pred-value');
    const cb=document.getElementById('conf-badge');
    const bar=document.getElementById('conf-bar');
    
    if(!pred){pv.innerText='—';cb.innerText='--%';bar.style.width='0%';}
    else{
      pv.innerText=pred.prediction;
      pv.className='pred-value '+(pred.prediction==='Tài'?'tai':'xiu');
      cb.innerText=pred.confidence+'%';
      bar.style.width=pred.confidence+'%';
    }
    
    const tb=document.getElementById('tbody');
    if(!rows.length){tb.innerHTML='<tr><td colspan="4" class="loading">Chưa có dữ liệu</td></tr>';return;}
    let html='';
    rows.forEach(row=>{
      const trCls=row.is_next?'class="row-next"':'';
      let predCell='<span class="badge b-none">—</span>';
      if(row.ai_prediction){
        const cls=row.ai_prediction==='Tài'?'tai':'xiu';
        predCell=`<span class="pred-mini ${cls}">${row.ai_prediction}</span><br><span style="font-size:9px;color:var(--muted)">${row.ai_confidence||0}%</span>`;
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
      html+=`<tr ${trCls}><td>#${row.phien}${row.is_next?'<br><span style="font-size:9px;color:var(--primary)">NEXT</span>':''}</td><td>${predCell}</td><td>${resBadge}${dice}</td><td>${evalCell}</td></tr>`;
    });
    tb.innerHTML=html;
  }catch(e){console.error(e);}
}
async function confirmReset(){
  Swal.fire({title:'Reset?',text:'Xoá toàn bộ cache và log?',icon:'warning',showCancelButton:true,confirmButtonColor:'#0ea5e9',cancelButtonColor:'#94a3b8',confirmButtonText:'Đồng ý',cancelButtonText:'Hủy'}).then(async r=>{
    if(!r.isConfirmed)return;
    isResetting=true;
    try{
      const res=await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      const d=await res.json();
      isResetting=false;
      if(d.status==='success'){fetchData();Swal.fire({title:'OK!',text:'Đã reset.',icon:'success'});}
      else throw new Error(d.message||'Lỗi');
    }catch(e){isResetting=false;Swal.fire({title:'Lỗi!',text:e.message,icon:'error'});}
  });
}
// Khởi chạy
fetchSharpState();
fetchData();
setInterval(fetchData,5000);
</script></body></html>"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# API điều khiển Làm Nét
@app.route('/api/sharp_state')
def sharp_state():
    global SHARP_FOCUS_MODE
    return jsonify({'sharp': SHARP_FOCUS_MODE})

@app.route('/api/sharp', methods=['POST'])
def toggle_sharp():
    global SHARP_FOCUS_MODE
    SHARP_FOCUS_MODE = not SHARP_FOCUS_MODE
    _save_log() # Lưu trạng thái
    return jsonify({'sharp': SHARP_FOCUS_MODE})

@app.route('/api/history')
def history():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid: return jsonify({'ready': False, 'message': 'Đang tải dữ liệu...', 'ai_stats': _log_stats()})
        next_phien = valid[-1]['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG, is_sharp=SHARP_FOCUS_MODE)
        _log_prediction(next_phien, pred)
        ai_stats = _log_stats()
        out = [{'phien': next_phien, 'is_next': True, 'result': 'Chờ...', 'dice': '? + ? + ?', 'total': None, 'ai_prediction': pred['prediction'], 'ai_confidence': pred['confidence'], 'ai_correct': None}]
        for v in reversed(valid[-200:]):
            if v['phien'] <= RESET_ID: continue
            log = PREDICTION_LOG.get(v['phien'])
            out.append({'phien': v['phien'], 'is_next': False, 'result': v['result'], 'dice': v['dice'], 'total': v['total'], 'ai_prediction': log['prediction'] if log else None, 'ai_confidence': log['confidence'] if log else None, 'ai_correct': log['correct'] if log else None})
        return jsonify({
            'ready': True, 'rows': out, 'ai_stats': ai_stats, 
            'prediction': {'prediction': pred['prediction'], 'confidence': pred['confidence'], 'sharp': SHARP_FOCUS_MODE}
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/lc79md5')
def lc79md5():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối MD5 API'}), 500
        if not valid: return jsonify({'Id': 'LEMINH V1', 'Phien': None, 'Du_doan': None, 'message': 'Đang tải dữ liệu...'})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG, is_sharp=SHARP_FOCUS_MODE)
        _log_prediction(next_phien, pred)
        ai_stats = _log_stats(PREDICTION_LOG)
        
        predicted_dice = _predict_dice(valid, pred['prediction'])
        dice_str = "-".join(map(str, predicted_dice))
        du_doan_format = f"{pred['prediction']} {dice_str}"

        return jsonify({
            'Id': 'LEMINH V1',
            'Phien': str(next_phien),
            'Ket_qua_truoc': last['result'].lower(),
            'Xuc_xac_truoc': last['dice'],
            'Diem_truoc': last['total'],
            'Du_doan': du_doan_format,
            'Tai_Xiu': pred['prediction'],
            'Xuc_Xac_Du_Kien': predicted_dice,
            'Do_tin_cay': f"{pred['confidence']}%",
            'Sharp_Focus': SHARP_FOCUS_MODE,
            'Phuong_phap': pred['method'],
            'Loai_cau': pred.get('cau_label', ''),
            'Tin_hieu_chinh': pred.get('top_signals', []),
            'Ly_do': pred['reason'],
            'Da_dao': pred.get('flipped', False),
            'Recovery': pred.get('recovery_active', False),
            'So_tin_hieu': len(pred['signals']),
            'Top_manh': pred.get('signals_strength', [])[:5],
            'AI_dung': ai_stats['correct'],
            'AI_sai': ai_stats['wrong'],
            'AI_cho': ai_stats['pending'],
            'Ti_le_AI': ai_stats['accuracy'],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict')
def predict():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid: return jsonify({'ready': False, 'message': 'Đang tải dữ liệu...', 'prediction': None})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG, is_sharp=SHARP_FOCUS_MODE)
        _log_prediction(next_phien, pred)
        return jsonify({
            'version': 'LEMINH V1', 'last_phien': last['phien'], 'next_phien': next_phien, 'last_result': last['result'],
            'last_dice': last['dice'], 'last_total': last['total'], 'prediction': pred['prediction'], 'confidence': pred['confidence'],
            'method': pred['method'], 'cau': pred.get('cau', 'unknown'), 'cau_label': pred.get('cau_label', ''),
            'regime_strength': pred.get('regime_strength', 0.0), 'top_signals': pred.get('top_signals', []),
            'signals_strength': pred.get('signals_strength', []), 'reason': pred['reason'], 'signals': pred['signals'],
            'signals_count': len(pred['signals']), 'flipped': pred.get('flipped', False), 'recovery_active': pred.get('recovery_active', False),
            'fail_streak': pred.get('fail_streak', 0), 'sharp_focus': SHARP_FOCUS_MODE, 'ai_stats': _log_stats(), 'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def stats_only():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid: return jsonify({'ready': False, 'message': 'Đang tải dữ liệu...'})
        last = valid[-1] if valid else None
        return jsonify({
            'ready': True, 'ai_stats': _log_stats(), 'recovery': MultiStrategyPredictor._RECOVERY,
            'sharp_focus': SHARP_FOCUS_MODE,
            'last_result': last['result'] if last else None, 'last_phien': last['phien'] if last else None,
            'last_dice': last['dice'] if last else None, 'timestamp': datetime.now().isoformat(),
        })
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
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys())
            HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
        else:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 400
        PREDICTION_LOG = {}
        MultiStrategyPredictor._TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0})
        MultiStrategyPredictor._RECENT.clear()
        MultiStrategyPredictor._RECOVERY = {'active': False, 'fail': 0, 'mode': None}
        _save_log()
        return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
