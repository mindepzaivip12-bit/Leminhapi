import os
import traceback
import time
import json
import hashlib
import math
import threading
import requests
from datetime import datetime
from collections import Counter, defaultdict

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# =====================================================================
# INIT
# =====================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'le-minh-v8-secret')
CORS(app)
socketio = SocketIO(
    app,
    cors_allowed_origins='*',
    async_mode='eventlet',
    ping_interval=20,
    ping_timeout=60,
)

# =====================================================================
# API ENDPOINTS
# =====================================================================
API_URL_MD5 = (
    "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions"
    "?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
)
# Endpoint đăng nhập + đặt cược — điền theo game thật
API_URL_LOGIN = os.environ.get('API_URL_LOGIN', '')
API_URL_BET = os.environ.get('API_URL_BET', '')

# =====================================================================
# STATE
# =====================================================================
HISTORY_CACHE = {}
RESET_ID = 0
PREDICTION_LOG = {}
MAX_LOG_SIZE = 3000
LOG_FILE = os.environ.get('LOG_FILE', 'prediction_log.json')

# Per-session state (dùng sid của socket.io làm key)
SESSIONS = {}  # sid -> {username, nickname, balance, token, ...}

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
        print(f"[LOG] Loaded {len(PREDICTION_LOG)} predictions")
    except Exception as e:
        print(f"[LOG] Load failed: {e}")


def _save_log():
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'log': PREDICTION_LOG, 'reset_id': RESET_ID}, f)
    except Exception as e:
        print(f"[LOG] Save failed: {e}")


# =====================================================================
# UTILS
# =====================================================================
def _run_lengths(results):
    if not results:
        return []
    runs = [1]
    for i in range(1, len(results)):
        if results[i] == results[i - 1]:
            runs[-1] += 1
        else:
            runs.append(1)
    return runs


def _entropy(results):
    if len(results) < 5:
        return 0.0
    c = Counter(results)
    total = len(results)
    h = 0.0
    for v in c.values():
        p = v / total
        if p > 0:
            h -= p * math.log2(p)
    return h


# =====================================================================
# PREDICTOR V8.0 (giữ nguyên engine — rút gọn phần hiển thị)
# =====================================================================
class MultiStrategyPredictor:
    _STRATEGY_TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0, 'last_len': 0})

    @staticmethod
    def _deterministic_choice(options, seed_str):
        h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
        return options[h % len(options)]

    @staticmethod
    def _tail_run(seq):
        if not seq:
            return 0, None
        last = seq[-1]
        n = 1
        for i in range(len(seq) - 2, -1, -1):
            if seq[i] == last:
                n += 1
            else:
                break
        return n, last

    @staticmethod
    def _seg_ratio(seq, win):
        if len(seq) < win or win <= 0:
            return 0.5
        seg = seq[-win:]
        return sum(1 for x in seg if x == 'Tài') / len(seg)

    @staticmethod
    def _detect_cycle(r, max_period=6, min_repeats=2):
        if len(r) < 8:
            return None
        best = None
        for period in range(2, min(max_period * 2, len(r) // min_repeats) + 1):
            needed = period * min_repeats
            if len(r) < needed:
                break
            tail = r[-needed:]
            pattern = tail[-period:]
            match = True
            for k in range(min_repeats):
                chunk = tail[k * period:(k + 1) * period]
                if chunk != pattern:
                    match = False
                    break
            if match:
                hits, total = 0, 0
                for i in range(len(r) - period):
                    if r[i] == pattern[i % period]:
                        hits += 1
                    total += 1
                if total >= 6 and hits / total >= 0.65:
                    phase = len(r) % period
                    score = hits / total
                    if best is None or score > best[0]:
                        best = (score, period, phase, pattern)
        if not best:
            return None
        _, period, phase, pattern = best
        return {'period': period, 'phase': phase, 'pattern': pattern,
                'next': pattern[phase % period]}

    @classmethod
    def _cycle_signal(cls, r, sizes_target=None):
        if sizes_target is None:
            return None, 0, 0
        period_len = sum(sizes_target)
        if len(r) < period_len * 2 + 2:
            return None, 0, 0
        runs = _run_lengths(r)
        if len(runs) < 2:
            return None, 0, 0
        n_cycles = min(len(runs) // len(sizes_target), 4)
        if n_cycles < 2:
            return None, 0, 0
        matched, total_checks = 0, 0
        for c in range(n_cycles):
            start = len(runs) - (c + 1) * len(sizes_target)
            end = start + len(sizes_target)
            if start < 0:
                break
            chunk = runs[start:end]
            if c == 0:
                for i in range(min(len(chunk) - 1, len(sizes_target) - 1)):
                    total_checks += 1
                    if chunk[i] == sizes_target[i]:
                        matched += 1
                    else:
                        break
            else:
                for i in range(len(chunk)):
                    total_checks += 1
                    if chunk[i] == sizes_target[i]:
                        matched += 1
                    else:
                        break
        if total_checks < 3:
            return None, 0, 0
        score = matched / total_checks
        if score < 0.75:
            return None, 0, 0
        cycle_pos = len(runs) % len(sizes_target)
        cur_run_len, cur_val = cls._tail_run(r)
        expected_size = sizes_target[(cycle_pos - 1) % len(sizes_target)]
        if cur_run_len < expected_size:
            conf = min(58 + int(score * 25) + (expected_size - cur_run_len) * 2, 82)
            weight = 1.4 + score * 0.4
            return cur_val, conf, min(weight, 1.9)
        else:
            next_val = 'Xỉu' if cur_val == 'Tài' else 'Tài'
            conf = min(58 + int(score * 25) + (cur_run_len - expected_size) * 2, 82)
            weight = 1.4 + score * 0.4
            return next_val, conf, min(weight, 1.9)

    @classmethod
    def _auto_cycle_signal(cls, r):
        if len(r) < 12:
            return None, 0, 0
        cyc = cls._detect_cycle(r, max_period=6, min_repeats=2)
        if not cyc:
            return None, 0, 0
        next_val = cyc['next']
        base = 60 if cyc['period'] <= 3 else 55
        conf = min(base + max(0, (6 - cyc['period'])) * 3, 78)
        weight = 1.3 + (6 - min(cyc['period'], 6)) * 0.08
        return next_val, conf, round(weight, 2)

    @classmethod
    def _pattern_similarity(cls, r):
        if len(r) < 15:
            return None, 0, 0
        for wlen in (8, 7, 6, 5, 4):
            if len(r) < wlen + 6:
                continue
            cur = r[-wlen:]
            matches = []
            for i in range(len(r) - wlen):
                window = r[i:i + wlen]
                sim = sum(1 for a, b in zip(cur, window) if a == b) / wlen
                if sim >= 0.85 and i + wlen < len(r):
                    matches.append((sim, r[i + wlen]))
            if len(matches) >= 3:
                weighted = {'Tài': 0.0, 'Xỉu': 0.0}
                for sim, nv in matches:
                    weighted[nv] += sim
                total = weighted['Tài'] + weighted['Xỉu']
                if total == 0:
                    continue
                p_tai = weighted['Tài'] / total
                if p_tai >= 0.62:
                    return 'Tài', min(int(p_tai * 100) + wlen, 85), 1.25
                if p_tai <= 0.38:
                    return 'Xỉu', min(int((1 - p_tai) * 100) + wlen, 85), 1.25
        return None, 0, 0

    @classmethod
    def _flip_break(cls, valid):
        if len(valid) < 10:
            return None, 0, 0
        r = [v['result'] for v in valid]
        cyc = cls._detect_cycle(r, max_period=5, min_repeats=2)
        if not cyc:
            return None, 0, 0
        if 2 <= cyc['period'] <= 4:
            recent = r[-8:]
            flips = sum(1 for i in range(1, len(recent))
                        if recent[i] != recent[i - 1])
            if flips >= 6:
                next_val = 'Xỉu' if cyc['next'] == 'Tài' else 'Tài'
                return next_val, 65, 1.05
        return None, 0, 0

    @classmethod
    def _run_break(cls, valid):
        if len(valid) < 8:
            return None, 0, 0
        r = [v['result'] for v in valid]
        cur_len, cur_val = cls._tail_run(r)
        if cur_len < 6 or cur_len > 10:
            return None, 0, 0
        runs = _run_lengths(r)
        breaks, totals = 0, 0
        idx = 0
        for rlen in runs[:-1]:
            if rlen >= 6:
                totals += 1
                if idx + rlen < len(r):
                    breaks += 1
            idx += rlen
        p = breaks / totals if totals > 0 else 0.5
        if p >= 0.55:
            next_val = 'Xỉu' if cur_val == 'Tài' else 'Tài'
            conf = min(56 + int(p * 20) + (cur_len - 6) * 2, 78)
            return next_val, conf, 1.15
        return None, 0, 0

    @classmethod
    def _regime_signal(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        alt = sum(1 for i in range(1, len(r)) if r[i] != r[i - 1]) / (len(r) - 1)
        runs = _run_lengths(r)
        avg_run = sum(runs) / len(runs)
        p_tai = cls._seg_ratio(r, 20)
        if avg_run >= 2.2 and alt <= 0.45:
            if p_tai >= 0.55:
                return 'Tài', 60, 0.95
            if p_tai <= 0.45:
                return 'Xỉu', 60, 0.95
        if alt >= 0.70 and avg_run <= 1.6:
            return ('Xỉu' if r[-1] == 'Tài' else 'Tài'), 62, 1.10
        return None, 0, 0

    @classmethod
    def _streak_aware(cls, valid):
        if len(valid) < 15:
            return None, 0, 0
        r = [v['result'] for v in valid]
        cur_len, cur_val = cls._tail_run(r)
        if cur_len == 1:
            prev_run, prev_val = cls._tail_run(r[:-1])
            if prev_run >= 3:
                return cur_val, 62, 1.10
            return None, 0, 0
        if cur_len == 2:
            return cur_val, 58, 0.95
        if cur_len >= 7:
            opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
            return opp, 70, 1.20
        return None, 0, 0

    @classmethod
    def _tier2_boost(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        t2 = [
            cls._markov_order1(valid),
            cls._weighted_freq(valid),
            cls._recency_streak(valid),
            cls._momentum(valid),
        ]
        votes = {'Tài': 0.0, 'Xỉu': 0.0}
        count = 0
        for p, c, w in t2:
            if p:
                votes[p] += c * w
                count += 1
        if count < 3:
            return None, 0, 0
        total = votes['Tài'] + votes['Xỉu']
        if total == 0:
            return None, 0, 0
        if votes['Tài'] / total >= 0.68:
            return 'Tài', min(int(votes['Tài'] / total * 100), 76), 0.90
        if votes['Xỉu'] / total >= 0.68:
            return 'Xỉu', min(int(votes['Xỉu'] / total * 100), 76), 0.90
        return None, 0, 0

    @classmethod
    def _volatility_regime(cls, valid):
        if len(valid) < 25:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        flips = sum(1 for i in range(1, len(r)) if r[i] != r[i - 1])
        flip_ratio = flips / (len(r) - 1)
        runs = _run_lengths(r)
        avg_run = sum(runs) / len(runs)
        p_tai = cls._seg_ratio(r, 20)
        if flip_ratio >= 0.75:
            return ('Xỉu' if r[-1] == 'Tài' else 'Tài'), 66, 1.15
        if flip_ratio <= 0.25:
            cur_len, cur_val = cls._tail_run(r)
            if cur_len <= 3:
                return cur_val, 60, 0.95
            if cur_len >= 5:
                opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
                return opp, 64, 1.10
        if 0.40 <= flip_ratio <= 0.60:
            if p_tai >= 0.60:
                return 'Tài', 58, 0.95
            if p_tai <= 0.40:
                return 'Xỉu', 58, 0.95
        return None, 0, 0

    @classmethod
    def _cascade_pattern(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid]
        results = []
        for scale in (2, 3, 5, 8):
            if len(r) < scale + 5:
                continue
            pat = tuple(r[-scale:])
            matches = []
            for i in range(len(r) - scale):
                if tuple(r[i:i + scale]) == pat and i + scale < len(r):
                    matches.append(r[i + scale])
            if len(matches) >= 2:
                c = Counter(matches)
                top, cnt = c.most_common(1)[0]
                ratio = cnt / len(matches)
                if ratio >= 0.70:
                    results.append((scale, top, ratio))
        if not results:
            return None, 0, 0
        results.sort(key=lambda x: x[0], reverse=True)
        scale, top, ratio = results[0]
        conf = min(55 + int(ratio * 25) + scale * 2, 82)
        weight = 1.05 + (scale / 10)
        return top, conf, min(weight, 1.6)

    @classmethod
    def _harmonic_pattern(cls, r):
        if len(r) < 12:
            return None, 0, 0
        trans = defaultdict(lambda: {'Tài': 0.0, 'Xỉu': 0.0})
        for i in range(len(r) - 2):
            key = (r[i], r[i + 1])
            w = 1.0 + (i / len(r)) * 0.5
            trans[key][r[i + 2]] += w
        key = (r[-2], r[-1])
        counts = trans[key]
        total = counts['Tài'] + counts['Xỉu']
        if total < 3:
            return None, 0, 0
        p_tai = counts['Tài'] / total
        if p_tai >= 0.65:
            return 'Tài', min(int(p_tai * 100), 82), 1.20
        if p_tai <= 0.35:
            return 'Xỉu', min(int((1 - p_tai) * 100), 82), 1.20
        return None, 0, 0

    @classmethod
    def _wavelet_trend(cls, valid):
        if len(valid) < 30:
            return None, 0, 0
        r = [v['result'] for v in valid]
        p_short = cls._seg_ratio(r, 5)
        p_medium = cls._seg_ratio(r, 15)
        p_long = cls._seg_ratio(r, 30)
        if p_short > 0.65 and p_medium > 0.58 and p_long > 0.52:
            conf = min(60 + int((p_short - 0.6) * 100), 80)
            return 'Tài', conf, 1.15
        if p_short < 0.35 and p_medium < 0.42 and p_long < 0.48:
            conf = min(60 + int((0.4 - p_short) * 100), 80)
            return 'Xỉu', conf, 1.15
        if p_short > 0.7 and p_long < 0.45:
            return 'Xỉu', 63, 1.10
        if p_short < 0.3 and p_long > 0.55:
            return 'Tài', 63, 1.10
        return None, 0, 0

    @classmethod
    def _seasonal_cycle(cls, r):
        if len(r) < 40:
            return None, 0, 0
        for period in (12, 10, 14, 15, 11, 13):
            if len(r) < period * 3:
                continue
            matches = []
            target_pos = len(r) % period
            for i in range(len(r) - period):
                if i % period == target_pos and i < len(r) - 1:
                    matches.append(r[i])
            if len(matches) >= 3:
                c = Counter(matches)
                top, cnt = c.most_common(1)[0]
                ratio = cnt / len(matches)
                if ratio >= 0.70:
                    conf = min(55 + int(ratio * 20), 78)
                    return top, conf, 1.05
        return None, 0, 0

    @classmethod
    def _markov_weighted(cls, valid):
        if len(valid) < 25:
            return None, 0, 0
        r = [v['result'] for v in valid]
        trans = defaultdict(lambda: {'Tài': 0.0, 'Xỉu': 0.0})
        for i in range(len(r) - 2):
            key = (r[i], r[i + 1])
            w = 0.95 ** (len(r) - i - 2)
            trans[key][r[i + 2]] += w
        key = (r[-2], r[-1])
        counts = trans[key]
        total = counts['Tài'] + counts['Xỉu']
        if total < 2:
            return None, 0, 0
        p_tai = (counts['Tài'] + 0.5) / (total + 1.0)
        if p_tai >= 0.62:
            return 'Tài', min(int(p_tai * 100) + 2, 82), 1.25
        if p_tai <= 0.38:
            return 'Xỉu', min(int((1 - p_tai) * 100) + 2, 82), 1.25
        return None, 0, 0

    @classmethod
    def _ensemble_boost(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        stable = [
            cls._markov_order2(valid),
            cls._trend(valid),
            cls._transition_matrix(valid),
        ]
        votes = {'Tài': 0.0, 'Xỉu': 0.0}
        count = 0
        for p, c, w in stable:
            if p:
                votes[p] += c
                count += 1
        if count < 2:
            return None, 0, 0
        total = votes['Tài'] + votes['Xỉu']
        if total == 0:
            return None, 0, 0
        if votes['Tài'] >= 0.75 * total:
            return 'Tài', min(int(votes['Tài'] / total * 100), 85), 1.15
        if votes['Xỉu'] >= 0.75 * total:
            return 'Xỉu', min(int(votes['Xỉu'] / total * 100), 85), 1.15
        return None, 0, 0

    @classmethod
    def _decision_tree(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid]
        tail_len, tail_val = cls._tail_run(r)
        if tail_len >= 5:
            opp = 'Xỉu' if tail_val == 'Tài' else 'Tài'
            return opp, 68, 1.15
        if 3 <= tail_len <= 4:
            p10 = cls._seg_ratio(r, 10)
            if p10 > 0.65 and tail_val == 'Tài':
                return tail_val, 62, 1.05
            if p10 < 0.35 and tail_val == 'Xỉu':
                return tail_val, 62, 1.05
            opp = 'Xỉu' if tail_val == 'Tài' else 'Tài'
            return opp, 58, 1.00
        if tail_len <= 2:
            p_alt = sum(1 for i in range(1, len(r[-10:]))
                        if r[-10:][i] != r[-10:][i - 1]) / 9
            if p_alt >= 0.65:
                opp = 'Xỉu' if tail_val == 'Tài' else 'Tài'
                return opp, 64, 1.10
        return None, 0, 0

    @classmethod
    def _ngram_signal(cls, r, n):
        if len(r) < n + 6:
            return None, 0, 0
        pattern = tuple(r[-n:])
        matches = []
        for i in range(len(r) - n):
            if tuple(r[i:i + n]) == pattern and i + n < len(r):
                matches.append(r[i + n])
        if len(matches) < 3:
            return None, 0, 0
        c = Counter(matches)
        top, count = c.most_common(1)[0]
        ratio = count / len(matches)
        if ratio < 0.60:
            return None, 0, 0
        conf = min(55 + min(n * 3, 15) + int((ratio - 0.6) * 40), 85)
        weight = 1.1 + n * 0.10
        return top, conf, min(weight, 1.7)

    @classmethod
    def _mirror_pattern(cls, r):
        if len(r) < 10:
            return None, 0, 0
        n = 6
        if len(r) < n * 2:
            return None, 0, 0
        recent = r[-n:]
        mirrored = tuple('Xỉu' if x == 'Tài' else 'Tài' for x in reversed(recent))
        matches = []
        for i in range(len(r) - n):
            if tuple(r[i:i + n]) == mirrored and i + n < len(r):
                nxt = r[i + n]
                matches.append('Xỉu' if nxt == 'Tài' else 'Tài')
        if len(matches) >= 2:
            c = Counter(matches)
            top, count = c.most_common(1)[0]
            ratio = count / len(matches)
            if ratio >= 0.65:
                conf = min(55 + int(ratio * 30), 78)
                return top, conf, 1.10
        return None, 0, 0

    @classmethod
    def _reverse_trend(cls, valid):
        if len(valid) < 24:
            return None, 0, 0
        r = [v['result'] for v in valid]
        first = r[-20:-10]
        second = r[-10:]
        t_first = sum(1 for x in first if x == 'Tài') / 10
        t_second = sum(1 for x in second if x == 'Tài') / 10
        if t_first >= 0.7 and t_second <= 0.3:
            return 'Xỉu', 62, 1.15
        if t_first <= 0.3 and t_second >= 0.7:
            return 'Tài', 62, 1.15
        return None, 0, 0

    @classmethod
    def _palindrome_check(cls, r):
        if len(r) < 8:
            return None, 0, 0
        for plen in (5, 4, 3):
            if len(r) < plen * 2:
                continue
            tail = r[-plen:]
            if tail == tail[::-1]:
                for i in range(len(r) - plen * 2 - 1, -1, -1):
                    if r[i:i + plen] == tail and i + plen < len(r):
                        nxt = r[i + plen]
                        conf = 58 + plen * 2
                        return nxt, min(conf, 72), 1.05
        return None, 0, 0

    @classmethod
    def _bayes_recent(cls, valid, prior_strength=4.0):
        if len(valid) < 10:
            return None, 0, 0
        recent = [v['result'] for v in valid[-25:]]
        tai = sum(1 for x in recent if x == 'Tài')
        n = len(recent)
        a = tai + prior_strength / 2
        b = (n - tai) + prior_strength / 2
        p_tai = a / (a + b)
        if p_tai >= 0.60:
            return 'Tài', min(int(p_tai * 100) + 3, 78), 1.05
        if p_tai <= 0.40:
            return 'Xỉu', min(int((1 - p_tai) * 100) + 3, 78), 1.05
        return None, 0, 0

    @classmethod
    def _chi_square(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        recent = [v['result'] for v in valid[-30:]]
        n = len(recent)
        tai = sum(1 for x in recent if x == 'Tài')
        xiu = n - tai
        expected = n / 2
        chi2 = ((tai - expected) ** 2 + (xiu - expected) ** 2) / expected
        if chi2 >= 3.84:
            if tai > xiu:
                return 'Xỉu', min(55 + int((chi2 - 3.84) * 3), 75), 0.85
            else:
                return 'Tài', min(55 + int((chi2 - 3.84) * 3), 75), 0.85
        return None, 0, 0

    @classmethod
    def _runs_prediction(cls, valid):
        if len(valid) < 15:
            return None, 0, 0
        r = [v['result'] for v in valid]
        runs = _run_lengths(r)
        if len(runs) < 5:
            return None, 0, 0
        cur_len, cur_val = cls._tail_run(r)
        run_dist = Counter(runs[:-1])
        total_runs = sum(run_dist.values())
        if total_runs < 5:
            return None, 0, 0
        end_count = sum(c for l, c in run_dist.items() if l <= cur_len)
        p_end = end_count / total_runs
        if p_end >= 0.65:
            opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
            return opp, min(55 + int(p_end * 25), 75), 1.10
        if p_end <= 0.35:
            return cur_val, min(55 + int((1 - p_end) * 25), 75), 1.00
        return None, 0, 0

    @classmethod
    def _transition_matrix(cls, valid, window=40):
        if len(valid) < 15:
            return None, 0, 0
        data = valid[-window:] if len(valid) > window else valid
        r = [v['result'] for v in data]
        trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
        for i in range(len(r) - 2):
            key = (r[i], r[i + 1])
            trans[key][r[i + 2]] += 1
        key = (r[-2], r[-1])
        counts = trans[key]
        total = counts['Tài'] + counts['Xỉu']
        if total < 4:
            return None, 0, 0
        p_tai = (counts['Tài'] + 1) / (total + 2)
        if p_tai >= 0.62:
            return 'Tài', min(int(p_tai * 100) + 3, 80), 1.15
        if p_tai <= 0.38:
            return 'Xỉu', min(int((1 - p_tai) * 100) + 3, 80), 1.15
        return None, 0, 0

    @classmethod
    def _signal_consensus(cls, valid):
        if len(valid) < 10:
            return None, 0, 0
        key = [
            cls._markov_order2(valid),
            cls._streak_break(valid),
            cls._trend(valid),
            cls._invert_cau(valid),
            cls._alternation(valid),
            cls._momentum(valid),
        ]
        votes = {'Tài': 0, 'Xỉu': 0}
        count = 0
        for p, c, w in key:
            if p:
                votes[p] += c * w
                count += 1
        if count < 4:
            return None, 0, 0
        if votes['Tài'] > votes['Xỉu'] * 1.3:
            return 'Tài', min(int(votes['Tài'] / (votes['Tài'] + votes['Xỉu']) * 100), 80), 1.10
        if votes['Xỉu'] > votes['Tài'] * 1.3:
            return 'Xỉu', min(int(votes['Xỉu'] / (votes['Tài'] + votes['Xỉu']) * 100), 80), 1.10
        return None, 0, 0

    @classmethod
    def _signal_dissent(cls, valid):
        if len(valid) < 15:
            return None, 0, 0
        key = [
            cls._markov_order2(valid),
            cls._streak_break(valid),
            cls._trend(valid),
            cls._invert_cau(valid),
            cls._alternation(valid),
        ]
        votes = {'Tài': 0, 'Xỉu': 0}
        for p, c, w in key:
            if p:
                votes[p] += 1
        total = votes['Tài'] + votes['Xỉu']
        if total < 4:
            return None, 0, 0
        if abs(votes['Tài'] - votes['Xỉu']) <= 1:
            r = [v['result'] for v in valid[-8:]]
            t_count = sum(1 for x in r if x == 'Tài')
            if t_count >= 5:
                return 'Tài', 55, 0.85
            if t_count <= 3:
                return 'Xỉu', 55, 0.85
        return None, 0, 0

    @classmethod
    def _entropy_adaptive(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        entropy = _entropy(r)
        p_tai = cls._seg_ratio(r, 20)
        if entropy < 0.7:
            if p_tai >= 0.6:
                return 'Tài', 62, 1.05
            if p_tai <= 0.4:
                return 'Xỉu', 62, 1.05
        elif entropy > 0.95:
            return ('Xỉu' if r[-1] == 'Tài' else 'Tài'), 58, 0.95
        return None, 0, 0

    @classmethod
    def _streak_maturity(cls, valid):
        if len(valid) < 12:
            return None, 0, 0
        r = [v['result'] for v in valid]
        cur_len, cur_val = cls._tail_run(r)
        if cur_len < 3:
            return None, 0, 0
        runs = _run_lengths(r)
        max_run = max(runs)
        if max_run < 3:
            return None, 0, 0
        maturity = cur_len / max_run
        if maturity >= 0.8 and cur_len >= 4:
            opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
            conf = min(55 + int(maturity * 20), 75)
            return opp, conf, 1.10
        return None, 0, 0

    # ==================== ORIGINAL SIGNALS ====================
    @staticmethod
    def _markov_order3(valid):
        if len(valid) < 25:
            return None, 0, 0
        trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
        for i in range(len(valid) - 3):
            k = (valid[i]['result'], valid[i + 1]['result'], valid[i + 2]['result'])
            trans[k][valid[i + 3]['result']] += 1
        k = (valid[-3]['result'], valid[-2]['result'], valid[-1]['result'])
        counts = trans[k]
        total = counts['Tài'] + counts['Xỉu']
        if total < 3:
            return None, 0, 0
        p_tai = (counts['Tài'] + 1) / (total + 2)
        if p_tai > 0.65:
            return 'Tài', int(p_tai * 100), 1.45
        if p_tai < 0.35:
            return 'Xỉu', int((1 - p_tai) * 100), 1.45
        return None, 0, 0

    @staticmethod
    def _markov_order2(valid, window=None):
        if len(valid) < 15:
            return None, 0, 0
        data = valid[-window:] if window and len(valid) > window else valid
        trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
        for i in range(len(data) - 2):
            k = (data[i]['result'], data[i + 1]['result'])
            trans[k][data[i + 2]['result']] += 1
        k = (data[-2]['result'], data[-1]['result'])
        counts = trans[k]
        total = counts['Tài'] + counts['Xỉu']
        if total < 3:
            return None, 0, 0
        p_tai = (counts['Tài'] + 1) / (total + 2)
        if p_tai > 0.58:
            return 'Tài', int(p_tai * 100), 1.30
        if p_tai < 0.42:
            return 'Xỉu', int((1 - p_tai) * 100), 1.30
        return None, 0, 0

    @staticmethod
    def _markov_order1(valid, window=None):
        if len(valid) < 8:
            return None, 0, 0
        data = valid[-window:] if window and len(valid) > window else valid
        trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
        for i in range(len(data) - 1):
            trans[data[i]['result']][data[i + 1]['result']] += 1
        counts = trans[data[-1]['result']]
        total = counts['Tài'] + counts['Xỉu']
        if total < 4:
            return None, 0, 0
        p_tai = (counts['Tài'] + 1) / (total + 2)
        if p_tai > 0.56:
            return 'Tài', int(p_tai * 100), 1.15
        if p_tai < 0.44:
            return 'Xỉu', int((1 - p_tai) * 100), 1.15
        return None, 0, 0

    @staticmethod
    def _streak_break(valid, window=None):
        if len(valid) < 4:
            return None, 0, 0
        r = [v['result'] for v in valid]
        streak, last = MultiStrategyPredictor._tail_run(r)
        opp = 'Xỉu' if last == 'Tài' else 'Tài'
        if streak == 1 and len(r) >= 6:
            prev_run, _ = MultiStrategyPredictor._tail_run(r[:-1])
            if prev_run >= 4:
                return last, 62, 1.10
        if streak < 3 or streak >= 8:
            return None, 0, 0
        breaks, continues = 0, 0
        run = 1
        for i in range(1, len(r)):
            if r[i] == r[i - 1]:
                run += 1
            else:
                if run >= 3:
                    breaks += 1
                run = 1
        if run >= 3:
            continues += 1
        total_obs = breaks + continues
        if streak <= 4:
            if total_obs >= 3:
                p_break = breaks / total_obs
                p_break = 0.5 * p_break + 0.5 * min(0.52 + streak * 0.03, 0.65)
            else:
                p_break = min(0.55 + streak * 0.02, 0.65)
            target, conf = opp, int(p_break * 100)
        elif streak <= 7:
            if total_obs < 2:
                return None, 0, 0
            p_break = breaks / total_obs
            if p_break >= 0.55:
                target, conf = opp, int(p_break * 100)
            elif p_break <= 0.45:
                target, conf = last, int((1 - p_break) * 100)
            else:
                return None, 0, 0
        else:
            return None, 0, 0
        if conf < 55:
            return None, 0, 0
        weight = 1.0 + (streak - 3) * 0.10
        return target, conf, min(weight, 1.6)

    @staticmethod
    def _exhaustion(valid):
        if len(valid) < 10:
            return None, 0, 0
        r = [v['result'] for v in valid]
        streak, last = MultiStrategyPredictor._tail_run(r)
        if streak < 8:
            return None, 0, 0
        opp = 'Xỉu' if last == 'Tài' else 'Tài'
        long_breaks, long_total = 0, 0
        run = 1
        for i in range(1, len(r) - 1):
            if r[i] == r[i - 1]:
                run += 1
            else:
                if run >= 8:
                    long_total += 1
                    long_breaks += 1
                run = 1
        if run >= 8:
            long_total += 1
        if streak <= 9:
            base = 55 + (streak - 8) * 2
        elif streak <= 12:
            base = 60 + (streak - 10) * 2
        else:
            base = 70 + min((streak - 13) * 2, 8)
        if long_total > 0:
            p_break = long_breaks / long_total
            base = int(base * 0.6 + p_break * 100 * 0.4)
        else:
            base -= 8
        conf = max(55, min(int(base), 80))
        weight = 1.1 + (streak - 8) * 0.08
        return opp, conf, min(weight, 1.5)

    @staticmethod
    def _dominance_flip(valid):
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        t = sum(1 for x in r if x == 'Tài') / 20
        if t >= 0.85:
            return 'Xỉu', max(min(int((t - 0.75) * 200), 75), 58), 0.90
        if t <= 0.15:
            return 'Tài', max(min(int((0.25 - t) * 200), 75), 58), 0.90
        return None, 0, 0

    @staticmethod
    def _follow_trend(valid):
        if len(valid) < 8:
            return None, 0, 0
        r = [v['result'] for v in valid]
        streak, last = MultiStrategyPredictor._tail_run(r)
        if streak >= 8:
            return None, 0, 0
        if streak >= 5:
            return last, min(58 + (streak - 5) * 4, 72), 1.20
        if len(r) >= 15:
            p15 = MultiStrategyPredictor._seg_ratio(r, 15)
            p5 = MultiStrategyPredictor._seg_ratio(r, 5)
            if 0.70 <= p15 <= 0.80 and p5 >= 0.60:
                return 'Tài', min(55 + int((p15 - 0.6) * 100), 72), 1.10
            if 0.20 <= p15 <= 0.30 and p5 <= 0.40:
                return 'Xỉu', min(55 + int((0.4 - p15) * 100), 72), 1.10
        return None, 0, 0

    @staticmethod
    def _invert_cau(valid):
        if len(valid) < 12:
            return None, 0, 0
        r = [v['result'] for v in valid[-16:]]
        alt = sum(1 for i in range(1, len(r)) if r[i] != r[i - 1])
        alt_ratio = alt / (len(r) - 1)
        if alt_ratio >= 0.65:
            nxt = 'Xỉu' if r[-1] == 'Tài' else 'Tài'
            return nxt, min(56 + int(alt_ratio * 30), 82), 1.30
        block2_hits, block2_total = 0, 0
        for i in range(2, len(r)):
            if r[i] == r[i - 2] and r[i] != r[i - 1]:
                block2_hits += 1
            if r[i] != r[i - 1]:
                block2_total += 1
        if block2_total >= 4 and block2_hits / block2_total >= 0.7:
            tail_run, _ = MultiStrategyPredictor._tail_run(r)
            nxt = r[-2] if tail_run == 1 else ('Xỉu' if r[-1] == 'Tài' else 'Tài')
            return nxt, 68, 1.25
        return None, 0, 0

    @staticmethod
    def _trend(valid):
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid]

        def tai_ratio(win):
            seg = r[-win:]
            return sum(1 for x in seg if x == 'Tài') / len(seg)

        p10 = tai_ratio(10)
        p20 = tai_ratio(20) if len(r) >= 20 else p10
        p40 = tai_ratio(40) if len(r) >= 40 else p20
        if p10 > 0.55 and p20 > 0.52 and p10 >= p20 - 0.05 and p10 - p40 >= 0.05:
            return 'Tài', min(int((p10 - 0.5) * 200 + 52), 78), 1.20
        if p10 < 0.45 and p20 < 0.48 and p10 <= p20 + 0.05 and p40 - p10 >= 0.05:
            return 'Xỉu', min(int((0.5 - p10) * 200 + 52), 78), 1.20
        return None, 0, 0

    @staticmethod
    def _bias_run(valid):
        if len(valid) < 24:
            return None, 0, 0
        r = [v['result'] for v in valid[-24:]]
        first, second = r[:12], r[12:]
        r_first = sum(1 for x in first if x == 'Tài') / 12
        r_second = sum(1 for x in second if x == 'Tài') / 12
        if r_second - r_first >= 0.25 and r_second >= 0.60:
            return 'Tài', min(int((r_second - 0.5) * 180 + 55), 80), 1.15
        if r_first - r_second >= 0.25 and (1 - r_second) >= 0.60:
            return 'Xỉu', min(int((0.5 - r_second) * -180 + 55), 80), 1.15
        if r_second >= 0.75:
            return 'Tài', 65, 1.00
        if r_second <= 0.25:
            return 'Xỉu', 65, 1.00
        return None, 0, 0

    @staticmethod
    def _pattern_match(valid, window=None):
        if len(valid) < 15:
            return None, 0, 0
        results = [v['result'] for v in valid]
        best_hit, best_conf, best_len = None, 0, 0
        for plen in (7, 6, 5, 4, 3):
            if len(results) < plen + 5:
                continue
            pattern = tuple(results[-plen:])
            matches = []
            for i in range(len(results) - plen):
                if tuple(results[i:i + plen]) == pattern and i + plen < len(results):
                    matches.append(results[i + plen])
            if len(matches) >= 3:
                c = Counter(matches)
                top, count = c.most_common(1)[0]
                conf = int(count / len(matches) * 100)
                conf_adj = min(conf + min(plen * 2, 10), 88)
                if conf_adj > best_conf and conf >= 55:
                    best_hit, best_conf, best_len = top, conf_adj, plen
        if best_hit:
            weight = 1.2 + best_len * 0.08
            return best_hit, best_conf, min(weight, 1.8)
        return None, 0, 0

    @staticmethod
    def _weighted_freq(valid, window=30):
        recent = valid[-window:]
        if len(recent) < 8:
            return None, 0, 0
        tai, xiu = 0.0, 0.0
        for i, v in enumerate(recent):
            w = ((i + 1) / len(recent)) ** 1.5
            if v['result'] == 'Tài':
                tai += w
            else:
                xiu += w
        total = tai + xiu
        if total == 0:
            return None, 0, 0
        p = tai / total
        if p > 0.58:
            return 'Tài', int(p * 100), 0.85
        if p < 0.42:
            return 'Xỉu', int((1 - p) * 100), 0.85
        return None, 0, 0

    @staticmethod
    def _dice_bias(valid, window=50):
        recent = [v for v in valid[-window:] if v.get('total')]
        if len(recent) < 10:
            return None, 0, 0
        tais = sum(1 for v in recent if v['result'] == 'Tài')
        ratio = tais / len(recent)
        if ratio > 0.62:
            return 'Xỉu', max(int(min((ratio - 0.5) * 200, 75)), 55), 0.65
        if ratio < 0.38:
            return 'Tài', max(int(min((0.5 - ratio) * 200, 75)), 55), 0.65
        return None, 0, 0

    @staticmethod
    def _alternation(valid, window=12):
        recent = [v['result'] for v in valid[-window:]]
        if len(recent) < 6:
            return None, 0, 0
        alt = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i - 1])
        alt_ratio = alt / (len(recent) - 1)
        if alt_ratio >= 0.7:
            nxt = 'Xỉu' if recent[-1] == 'Tài' else 'Tài'
            return nxt, min(int(alt_ratio * 100) + 5, 85), 1.45
        return None, 0, 0

    @staticmethod
    def _momentum(valid, window=10):
        recent = [v['result'] for v in valid[-window:]]
        if len(recent) < 6:
            return None, 0, 0
        tai = sum(1 for r in recent if r == 'Tài')
        p = tai / len(recent)
        if p >= 0.7:
            return 'Tài', int(p * 100), 0.95
        if p <= 0.3:
            return 'Xỉu', int((1 - p) * 100), 0.95
        return None, 0, 0

    @staticmethod
    def _recency_streak(valid):
        if len(valid) < 10:
            return None, 0, 0
        weights = {'Tài': 0.0, 'Xỉu': 0.0}
        n = 10
        for i in range(len(valid) - n, len(valid)):
            w = ((i - (len(valid) - n) + 1) / n) ** 2
            weights[valid[i]['result']] += w
        total = weights['Tài'] + weights['Xỉu']
        if total == 0:
            return None, 0, 0
        p = weights['Tài'] / total
        if p > 0.6:
            return 'Tài', int(p * 100), 1.15
        if p < 0.4:
            return 'Xỉu', int((1 - p) * 100), 1.15
        return None, 0, 0

    @classmethod
    def _time_pattern(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid]
        for period in (5, 6, 7, 8, 9, 10):
            if len(r) < period * 3:
                continue
            target_pos = (len(r) % period)
            matching = [r[i] for i in range(len(r)) if i % period == target_pos and i < len(r) - 1]
            if len(matching) >= 3:
                c = Counter(matching)
                top, cnt = c.most_common(1)[0]
                ratio = cnt / len(matching)
                if ratio >= 0.65:
                    conf = min(55 + int(ratio * 25), 75)
                    return top, conf, 1.05
        return None, 0, 0

    @classmethod
    def _volatility(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        flips = sum(1 for i in range(1, len(r)) if r[i] != r[i - 1])
        flip_ratio = flips / (len(r) - 1)
        if flip_ratio >= 0.85:
            return ('Xỉu' if r[-1] == 'Tài' else 'Tài'), 64, 1.15
        if flip_ratio <= 0.15:
            cur_len, cur_val = cls._tail_run(r)
            if cur_len >= 4:
                return ('Xỉu' if cur_val == 'Tài' else 'Tài'), 62, 1.10
        return None, 0, 0

    @classmethod
    def _cusum(cls, valid):
        if len(valid) < 15:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        vals = [1 if x == 'Tài' else -1 for x in r]
        mean = sum(vals) / len(vals)
        s_pos, s_neg = 0.0, 0.0
        threshold = 1.5
        for v in vals:
            s_pos = max(0, s_pos + (v - mean))
            s_neg = max(0, s_neg - (v - mean))
        if s_pos > threshold and mean > 0:
            return 'Xỉu', 62, 1.05
        if s_neg > threshold and mean < 0:
            return 'Tài', 62, 1.05
        return None, 0, 0

    @classmethod
    def _kelly_optimal(cls, valid):
        if len(valid) < 15:
            return None, 0, 0
        recent = [v['result'] for v in valid[-15:]]
        tai = sum(1 for x in recent if x == 'Tài')
        p = tai / len(recent)
        kelly = 2 * p - 1
        if kelly >= 0.30:
            return 'Tài', min(55 + int(kelly * 40), 80), 1.10
        if kelly <= -0.30:
            return 'Xỉu', min(55 + int(-kelly * 40), 80), 1.10
        return None, 0, 0

    @classmethod
    def _multi_window(cls, valid):
        if len(valid) < 25:
            return None, 0, 0
        r = [v['result'] for v in valid]
        windows = [5, 10, 15, 20]
        votes = []
        for w in windows:
            seg = r[-w:]
            t = sum(1 for x in seg if x == 'Tài') / w
            if t >= 0.60:
                votes.append('Tài')
            elif t <= 0.40:
                votes.append('Xỉu')
        if len(votes) >= 3:
            c = Counter(votes)
            top, cnt = c.most_common(1)[0]
            if cnt >= 3:
                conf = min(55 + cnt * 5, 75)
                return top, conf, 1.15
        return None, 0, 0

    @classmethod
    def _rsi_signal(cls, valid, period=14):
        if len(valid) < period + 5:
            return None, 0, 0
        r = [v['result'] for v in valid]
        changes = []
        for i in range(1, len(r)):
            if r[i] == r[i - 1]:
                changes.append(0)
            elif r[i] == 'Tài':
                changes.append(1)
            else:
                changes.append(-1)
        recent = changes[-period:]
        gains = sum(c for c in recent if c > 0)
        losses = sum(-c for c in recent if c < 0)
        if gains + losses == 0:
            return None, 0, 0
        rs = gains / (losses + 0.01)
        rsi = 100 - 100 / (1 + rs)
        if rsi >= 75:
            return 'Xỉu', min(55 + int((rsi - 70)), 78), 1.10
        if rsi <= 25:
            return 'Tài', min(55 + int((30 - rsi)), 78), 1.10
        return None, 0, 0

    @classmethod
    def _fibonacci_break(cls, valid):
        if len(valid) < 15:
            return None, 0, 0
        r = [v['result'] for v in valid]
        cur_len, cur_val = cls._tail_run(r)
        fibs = [3, 5, 8, 13]
        for fib in fibs:
            if cur_len == fib or cur_len == fib + 1:
                opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
                conf = min(58 + fib, 75)
                return opp, conf, 1.10
        return None, 0, 0

    @classmethod
    def _zscore_extreme(cls, valid):
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        vals = [1 if x == 'Tài' else 0 for x in r]
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        std = variance ** 0.5
        if std < 0.01:
            return None, 0, 0
        z = (vals[-1] - mean) / std
        if z >= 1.5:
            return 'Xỉu', 62, 0.95
        if z <= -1.5:
            return 'Tài', 62, 0.95
        return None, 0, 0

    # ==================== ADAPTIVE ====================
    @classmethod
    def _get_adaptive_weight(cls, name, base_weight):
        tr = cls._STRATEGY_TRACK.get(name)
        if not tr:
            return base_weight
        n = tr['hit'] + tr['miss']
        if n < 5:
            return base_weight
        acc = tr['hit'] / n
        factor = 0.6 + (acc - 0.5) * 2.6
        return base_weight * max(0.45, min(factor, 1.6))

    @classmethod
    def _update_track(cls, name, pred, actual):
        if pred is None:
            return
        tr = cls._STRATEGY_TRACK[name]
        if pred == actual:
            tr['hit'] += 1
        else:
            tr['miss'] += 1

    @classmethod
    def _sync_track_from_history(cls, valid):
        if not valid:
            return
        cur_len = len(valid)
        if cls._STRATEGY_TRACK.get('__len__', {}).get('last_len') == cur_len:
            return
        cls._STRATEGY_TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0, 'last_len': 0})
        start = max(15, len(valid) - 60)
        for i in range(start, len(valid) - 1):
            history = valid[:i]
            actual = valid[i]['result']
            for fname, fn in cls._strategy_list():
                try:
                    p, c, w = fn(history)
                    if p is not None:
                        cls._update_track(fname, p, actual)
                except Exception:
                    pass
        cls._STRATEGY_TRACK['__len__'] = {'last_len': cur_len}

    @classmethod
    def _check_failure_streak(cls, log=None):
        if log is None:
            log = PREDICTION_LOG
        evaluated = [
            (p, e) for p, e in sorted(log.items(), reverse=True)
            if e.get('actual') is not None
        ]
        if len(evaluated) < 2:
            return 0
        return sum(1 for _, e in evaluated[:2] if e.get('correct') is False)

    @classmethod
    def _was_flipped_last(cls, log=None):
        if log is None:
            log = PREDICTION_LOG
        evaluated = [
            e for p, e in sorted(log.items(), reverse=True)
            if e.get('actual') is not None
        ]
        return evaluated[0].get('flipped', False) if evaluated else False

    @staticmethod
    def _calibrate_confidence(raw_conf, log=None):
        if log is None:
            log = PREDICTION_LOG
        evaluated = [e for e in log.values() if e.get('actual') is not None]
        if len(evaluated) < 20:
            return raw_conf
        recent30 = sorted(
            [(p, e) for p, e in log.items() if e.get('actual') is not None],
            reverse=True
        )[:30]
        if not recent30:
            return raw_conf
        acc30 = sum(1 for _, e in recent30 if e.get('correct')) / len(recent30)
        recent100 = sorted(
            [(p, e) for p, e in log.items() if e.get('actual') is not None],
            reverse=True
        )[:100]
        acc100 = sum(1 for _, e in recent100 if e.get('correct')) / len(recent100) if recent100 else acc30
        acc_blend = acc30 * 0.6 + acc100 * 0.4
        if acc_blend < 0.45:
            return max(50, raw_conf - 12)
        if acc_blend < 0.50:
            return max(50, raw_conf - 6)
        if acc_blend > 0.68:
            return min(88, raw_conf + 4)
        if acc_blend > 0.60:
            return min(88, raw_conf + 2)
        return raw_conf

    @classmethod
    def _strategy_list(cls):
        return [
            ('markov3', cls._markov_order3),
            ('markov2', cls._markov_order2),
            ('markov1', cls._markov_order1),
            ('streak', cls._streak_break),
            ('pattern', cls._pattern_match),
            ('weighted', cls._weighted_freq),
            ('dice', cls._dice_bias),
            ('alternation', cls._alternation),
            ('momentum', cls._momentum),
            ('recency', cls._recency_streak),
            ('invert', cls._invert_cau),
            ('trend', cls._trend),
            ('bias_run', cls._bias_run),
            ('follow', cls._follow_trend),
            ('exhaust', cls._exhaustion),
            ('dominance', cls._dominance_flip),
            ('cycle_1_1', lambda v: cls._cycle_signal([x['result'] for x in v], [1, 1])),
            ('cycle_2_2', lambda v: cls._cycle_signal([x['result'] for x in v], [2, 2])),
            ('cycle_3_3', lambda v: cls._cycle_signal([x['result'] for x in v], [3, 3])),
            ('cycle_1_2', lambda v: cls._cycle_signal([x['result'] for x in v], [1, 2])),
            ('cycle_2_1', lambda v: cls._cycle_signal([x['result'] for x in v], [2, 1])),
            ('cycle_1_3', lambda v: cls._cycle_signal([x['result'] for x in v], [1, 3])),
            ('cycle_3_1', lambda v: cls._cycle_signal([x['result'] for x in v], [3, 1])),
            ('cycle_2_3', lambda v: cls._cycle_signal([x['result'] for x in v], [2, 3])),
            ('cycle_3_2', lambda v: cls._cycle_signal([x['result'] for x in v], [3, 2])),
            ('cycle_123', lambda v: cls._cycle_signal([x['result'] for x in v], [1, 2, 3])),
            ('cycle_321', lambda v: cls._cycle_signal([x['result'] for x in v], [3, 2, 1])),
            ('cycle_346', lambda v: cls._cycle_signal([x['result'] for x in v], [3, 4, 6])),
            ('cycle_112', lambda v: cls._cycle_signal([x['result'] for x in v], [1, 1, 2])),
            ('cycle_212', lambda v: cls._cycle_signal([x['result'] for x in v], [2, 1, 2])),
            ('cycle_122', lambda v: cls._cycle_signal([x['result'] for x in v], [1, 2, 2])),
            ('cycle_221', lambda v: cls._cycle_signal([x['result'] for x in v], [2, 2, 1])),
            ('cycle_1234', lambda v: cls._cycle_signal([x['result'] for x in v], [1, 2, 3, 4])),
            ('cycle_2341', lambda v: cls._cycle_signal([x['result'] for x in v], [2, 3, 4, 1])),
            ('cycle_3456', lambda v: cls._cycle_signal([x['result'] for x in v], [3, 4, 5, 6])),
            ('cycle_4_4', lambda v: cls._cycle_signal([x['result'] for x in v], [4, 4])),
            ('auto_cycle', lambda v: cls._auto_cycle_signal([x['result'] for x in v])),
            ('pattern_sim', lambda v: cls._pattern_similarity([x['result'] for x in v])),
            ('regime', cls._regime_signal),
            ('flip_break', cls._flip_break),
            ('run_break', cls._run_break),
            ('ngram_2', lambda v: cls._ngram_signal([x['result'] for x in v], 2)),
            ('ngram_3', lambda v: cls._ngram_signal([x['result'] for x in v], 3)),
            ('ngram_4', lambda v: cls._ngram_signal([x['result'] for x in v], 4)),
            ('ngram_5', lambda v: cls._ngram_signal([x['result'] for x in v], 5)),
            ('mirror_pattern', lambda v: cls._mirror_pattern([x['result'] for x in v])),
            ('reverse_trend', cls._reverse_trend),
            ('palindrome_check', lambda v: cls._palindrome_check([x['result'] for x in v])),
            ('bayes_recent', cls._bayes_recent),
            ('chi_square', cls._chi_square),
            ('runs_prediction', cls._runs_prediction),
            ('transition_matrix', cls._transition_matrix),
            ('double_break', lambda v: cls._cycle_signal([x['result'] for x in v], [2, 2])),
            ('signal_consensus', cls._signal_consensus),
            ('signal_dissent', cls._signal_dissent),
            ('entropy_adaptive', cls._entropy_adaptive),
            ('streak_maturity', cls._streak_maturity),
            ('time_pattern', cls._time_pattern),
            ('volatility', cls._volatility),
            ('cusum', cls._cusum),
            ('kelly_optimal', cls._kelly_optimal),
            ('multi_window', cls._multi_window),
            ('rsi_signal', cls._rsi_signal),
            ('fibonacci_break', cls._fibonacci_break),
            ('zscore_extreme', cls._zscore_extreme),
            ('harmonic_pattern', lambda v: cls._harmonic_pattern([x['result'] for x in v])),
            ('wavelet_trend', cls._wavelet_trend),
            ('seasonal_cycle', lambda v: cls._seasonal_cycle([x['result'] for x in v])),
            ('markov_weighted', cls._markov_weighted),
            ('ensemble_boost', cls._ensemble_boost),
            ('decision_tree', cls._decision_tree),
            ('streak_aware', cls._streak_aware),
            ('tier2_boost', cls._tier2_boost),
            ('volatility_regime', cls._volatility_regime),
            ('cascade_pattern', cls._cascade_pattern),
        ]

    @classmethod
    def predict(cls, valid, log=None):
        if log is None:
            log = PREDICTION_LOG

        if not valid:
            seed = str(int(time.time()) // 60)
            return {
                'prediction': cls._deterministic_choice(['Tài', 'Xỉu'], seed),
                'confidence': 50, 'method': 'Chưa có DL',
                'signals': [], 'top_signals': ['Chưa có DL'],
                'reason': 'Không có dữ liệu', 'flipped': False,
            }

        if len(valid) < 5:
            r = [v['result'] for v in valid]
            streak, last = cls._tail_run(r)
            opp = 'Xỉu' if last == 'Tài' else 'Tài'
            if streak == 1:
                method = f'Đảo {last}'
                conf = 52
            elif streak <= 3:
                method = f'Bẻ {last}×{streak}'
                conf = 52 + streak * 2
            else:
                method = f'Bẻ {last}×{streak}'
                conf = min(60 + (streak - 3) * 3, 70)
            return {
                'prediction': opp, 'confidence': conf,
                'method': method, 'signals': [],
                'top_signals': [method],
                'reason': f'{streak} phiên {last}',
                'flipped': False,
            }

        cls._sync_track_from_history(valid)

        log_odds = 0.0
        signals = []
        total_weight = 0.0

        for name, fn in cls._strategy_list():
            try:
                p, conf, weight = fn(valid)
            except Exception:
                continue
            if p is None or weight == 0:
                continue
            weight = cls._get_adaptive_weight(name, weight)
            p_norm = max(0.51, min(conf / 100.0, 0.92))
            lr = p_norm / (1 - p_norm)
            if p == 'Xỉu':
                lr = 1.0 / lr
            contrib = weight * (1.0 if p == 'Tài' else -1.0) * (lr - 1.0)
            log_odds += contrib
            total_weight += weight
            signals.append({'name': name, 'prediction': p,
                            'confidence': conf, 'weight': round(weight, 2)})

        if not signals or total_weight == 0:
            r = [v['result'] for v in valid]
            cyc = cls._detect_cycle(r, max_period=6, min_repeats=2)
            if cyc:
                return {
                    'prediction': cyc['next'], 'confidence': 55,
                    'method': f"Chu kỳ {cyc['period']}",
                    'signals': [], 'top_signals': [f"Chu kỳ {cyc['period']}"],
                    'reason': f"Phát hiện chu kỳ {cyc['period']}",
                    'flipped': False,
                }
            streak, last = cls._tail_run(r)
            opp = 'Xỉu' if last == 'Tài' else 'Tài'
            return {
                'prediction': opp, 'confidence': 52,
                'method': f'Bẻ {last}×{streak}',
                'signals': [], 'top_signals': [f'Bẻ {last}×{streak}'],
                'reason': f'Bẻ streak {streak}',
                'flipped': False,
            }

        scaled = log_odds / max(total_weight, 1.0) * 1.8
        p_tai = 1.0 / (1.0 + math.exp(-scaled))
        if p_tai >= 0.5:
            pred = 'Tài'
            raw_conf = int(p_tai * 100)
        else:
            pred = 'Xỉu'
            raw_conf = int((1 - p_tai) * 100)

        recent = [v['result'] for v in valid[-20:]]
        entropy = _entropy(recent)
        votes_tai = sum(1 for s in signals if s['prediction'] == 'Tài')
        votes_xiu = len(signals) - votes_tai
        agreement = max(votes_tai, votes_xiu) / len(signals)

        penalty = 0
        if entropy > 0.95:
            penalty += 10
        elif entropy > 0.85:
            penalty += 6
        elif entropy > 0.70:
            penalty += 3
        if agreement < 0.6:
            penalty += 8
        elif agreement < 0.75:
            penalty += 4
        bonus = 4 if agreement >= 0.9 and entropy < 0.6 else 0
        final_conf = max(50, min(raw_conf - penalty + bonus, 88))

        signals_sorted = sorted(
            signals,
            key=lambda s: s['weight'] * (s['confidence'] - 50),
            reverse=True
        )
        top_signals = [s['name'] for s in signals_sorted[:5]]

        result = {
            'prediction': pred, 'confidence': final_conf,
            'method': ' + '.join(top_signals[:3]) if top_signals else 'Tổng hợp',
            'signals': signals, 'top_signals': top_signals,
            'reason': (f"{len(signals)} tín hiệu · entropy={entropy:.2f} · "
                       f"đồng thuận={agreement:.0%}"),
            'flipped': False,
        }

        fail_streak = cls._check_failure_streak(log)
        if fail_streak >= 2 and not cls._was_flipped_last(log):
            result['prediction'] = 'Xỉu' if result['prediction'] == 'Tài' else 'Tài'
            result['confidence'] = max(55, min(result['confidence'], 72))
            result['method'] = '⚠ ' + result['method']
            result['reason'] += f" · SAI {fail_streak} → ĐẢO"
            result['flipped'] = True

        result['confidence'] = cls._calibrate_confidence(result['confidence'], log)
        return result


# =====================================================================
# DATA FETCHER (MD5)
# =====================================================================
def _fetch_endpoint(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
    proxies = None
    proxy_url = os.environ.get('PROXY_URL')
    if proxy_url:
        proxies = {'http': proxy_url, 'https': proxy_url}

    for attempt in range(3):
        try:
            r = requests.get(url, timeout=6, headers=headers, proxies=proxies)
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
            print(f"[API ERROR] attempt {attempt + 1}: {e}")
            time.sleep(1)
    return [], False


def fetch_sessions():
    return _fetch_endpoint(API_URL_MD5)


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
    if not valid:
        return
    by_phien = {v['phien']: v for v in valid}
    phien_list = sorted(by_phien.keys())
    for phien, entry in list(PREDICTION_LOG.items()):
        if entry.get('actual') is not None:
            continue
        if phien in by_phien:
            actual = by_phien[phien]['result']
            entry['actual'] = actual
            entry['correct'] = (entry['prediction'] == actual)
    changed = False
    for i, phien in enumerate(phien_list):
        if phien in PREDICTION_LOG or phien <= RESET_ID:
            continue
        history_before = [by_phien[p] for p in phien_list[:i]]
        if len(history_before) < 3:
            continue
        pred = MultiStrategyPredictor.predict(history_before, log=PREDICTION_LOG)
        actual = by_phien[phien]['result']
        PREDICTION_LOG[phien] = {
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'actual': actual,
            'correct': (pred['prediction'] == actual),
            'logged_at': datetime.now().isoformat(),
            'retroactive': True,
            'flipped': pred.get('flipped', False),
        }
        changed = True
    if len(PREDICTION_LOG) > MAX_LOG_SIZE:
        keys = sorted(PREDICTION_LOG.keys())[:len(PREDICTION_LOG) - MAX_LOG_SIZE]
        for k in keys:
            del PREDICTION_LOG[k]
        changed = True
    if changed:
        _save_log()


def _log_prediction(phien, pred_result):
    if phien in PREDICTION_LOG:
        return
    PREDICTION_LOG[phien] = {
        'prediction': pred_result['prediction'],
        'confidence': pred_result['confidence'],
        'method': pred_result['method'],
        'actual': None, 'correct': None,
        'logged_at': datetime.now().isoformat(),
        'retroactive': False,
        'flipped': pred_result.get('flipped', False),
    }
    _save_log()


def _honest_stats(valid):
    total = len(valid)
    tai = sum(1 for v in valid if v['result'] == 'Tài')
    return {'total': total, 'tai': tai, 'xiu': total - tai,
            'ratio_tai': round(tai / total, 3) if total else 0}


def _log_stats(log=None):
    if log is None:
        log = PREDICTION_LOG
    evaluated = [e for e in log.values() if e.get('actual') is not None]
    correct = sum(1 for e in evaluated if e.get('correct'))
    wrong = len(evaluated) - correct
    pending = sum(1 for e in log.values() if e.get('actual') is None)
    return {'correct': correct, 'wrong': wrong, 'pending': pending,
            'evaluated': len(evaluated)}


_load_log()


# =====================================================================
# SESSION STATE + AUTO BET ENGINE
# =====================================================================
class SessionState:
    """State cho mỗi user kết nối."""
    def __init__(self, sid):
        self.sid = sid
        self.username = ''
        self.password = ''
        self.nickname = ''
        self.token = ''
        self.balance = 0
        self.logged_in = False
        # Bet config
        self.base_bet = 10000
        self.current_bet = 10000
        self.bet_step = 0  # 0=gốc, 1=x2, ...
        self.win_count = 0
        self.lose_count = 0
        self.auto_bet_enabled = False
        self.is_paused = False
        # Session tracking
        self.current_session = None
        self.current_prediction = None
        self.pred_history = []
        self.ai_correct = 0
        self.ai_wrong = 0
        self.last_pattern = ''
        self.last_bet_session = None
        # Threading
        self.lock = threading.Lock()


def _get_session(sid):
    if sid not in SESSIONS:
        SESSIONS[sid] = SessionState(sid)
    return SESSIONS[sid]


def _state_to_dict(s):
    """Chuyển state thành dict để emit qua socket."""
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    history = [v['result'] for v in valid[-40:]]
    hist = PREDICTION_LOG.get(s.current_session) if s.current_session else None
    return {
        'logged_in': s.logged_in,
        'nickname': s.nickname,
        'balance': s.balance,
        'current_bet': s.current_bet,
        'base_bet': s.base_bet,
        'bet_step': s.bet_step,
        'win_count': s.win_count,
        'lose_count': s.lose_count,
        'auto_bet_enabled': s.auto_bet_enabled,
        'is_paused': s.is_paused,
        'current_prediction': s.current_prediction,
        'session_id': s.current_session,
        'last_pattern': s.last_pattern,
        'ai_correct': s.ai_correct,
        'ai_wrong': s.ai_wrong,
        'history': history,
        'pred_history': [
            {
                'session': p.get('phien'),
                'pred': p['prediction'].upper() if p['prediction'] else None,
                'actual': p['actual'].upper() if p.get('actual') else None,
                'correct': p.get('correct'),
                'confidence': p.get('confidence', 0),
                'dices': None,
            }
            for p in sorted(PREDICTION_LOG.values(),
                            key=lambda x: x.get('logged_at', ''),
                            reverse=False)[-50:]
            if p.get('actual')
        ],
    }


def _emit_state(s):
    socketio.emit('state', _state_to_dict(s), to=s.sid)


def _emit_log(s, level, msg):
    socketio.emit('log', {'level': level, 'msg': msg}, to=s.sid)
    print(f"[{s.sid[:6]}] [{level.upper()}] {msg}")


def _notify(s, msg):
    _emit_log(s, 'info', msg)
    _emit_state(s)


# =====================================================================
# LOGIN FLOW
# =====================================================================
def _do_login(s, username, password):
    """Đăng nhập game thật — dùng API thật hoặc mock để demo."""
    s.username = username
    s.password = password

    if not API_URL_LOGIN:
        # MOCK MODE — dùng để test auto flow mà không cần API
        print(f"[LOGIN] Mock login: {username}")
        s.nickname = username
        s.balance = 1000000
        s.logged_in = True
        _emit_log(s, 'warn', 'Chế độ MOCK — không có API đăng nhập thật')
        _emit_log(s, 'ok', f'Đăng nhập thành công: {s.nickname} — {s.balance:,}')
        _emit_state(s)
        return True

    # LOGIN THẬT — cần điều chỉnh theo API game
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Content-Type': 'application/json',
        }
        payload = {'username': username, 'password': password}
        r = requests.post(API_URL_LOGIN, json=payload, headers=headers, timeout=10)
        data = r.json()
        if data.get('code') == 0 or data.get('success'):
            s.token = data.get('token', '')
            s.nickname = data.get('nickname', username)
            s.balance = float(data.get('balance', 0))
            s.logged_in = True
            _emit_log(s, 'ok', f'Đăng nhập thành công: {s.nickname} — {s.balance:,.0f}')
            _emit_state(s)
            return True
        else:
            _emit_log(s, 'err', f'Đăng nhập thất bại: {data.get("message", "unknown")}')
            return False
    except Exception as e:
        _emit_log(s, 'err', f'Lỗi đăng nhập: {e}')
        return False


# =====================================================================
# BET FLOW
# =====================================================================
def _do_bet(s, prediction, amount):
    """Đặt cược — mock hoặc thật."""
    if not API_URL_BET:
        # MOCK MODE
        return {'ok': True, 'session': s.current_session}
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {s.token}',
        }
        payload = {
            'sid': s.current_session,
            'type': 'TAI' if prediction == 'Tài' else 'XIU',
            'amount': int(amount),
        }
        r = requests.post(API_URL_BET, json=payload, headers=headers, timeout=10)
        data = r.json()
        return {'ok': data.get('code') == 0 or data.get('success', False),
                'message': data.get('message')}
    except Exception as e:
        return {'ok': False, 'message': str(e)}


# =====================================================================
# AUTO BET LOOP (background thread per session)
# =====================================================================
def _auto_bet_loop(sid):
    """Chạy nền cho mỗi session, kiểm tra phiên mới & đặt cược."""
    s = _get_session(sid)
    _emit_log(s, 'info', 'Auto bet loop started')

    while s.sid in SESSIONS and s.logged_in:
        try:
            valid, ok = _sync_history()
            if not ok or len(valid) < 5:
                time.sleep(3)
                continue

            next_phien = valid[-1]['phien'] + 1
            last_phien = valid[-1]['phien']

            # Có kết quả mới → đánh giá cược trước
            if s.last_bet_session and s.last_bet_session < last_phien:
                prev_bet = next(
                    (b for b in _get_pending_bets(s) if b['session'] == s.last_bet_session),
                    None
                )
                if prev_bet:
                    # Tìm kết quả
                    result_row = next((v for v in valid if v['phien'] == s.last_bet_session), None)
                    if result_row:
                        won = (prev_bet['prediction'] == result_row['result'])
                        if won:
                            s.win_count += 1
                            s.ai_correct += 1
                            s.bet_step = 0
                            s.current_bet = s.base_bet
                            _emit_log(s, 'ok',
                                      f'✓ THẮNG phiên {s.last_bet_session} · '
                                      f'reset về gốc {s.base_bet:,}')
                        else:
                            s.lose_count += 1
                            s.ai_wrong += 1
                            s.bet_step += 1
                            if s.bet_step >= 2:
                                s.is_paused = True
                                s.auto_bet_enabled = False
                                _emit_log(s, 'err',
                                          f'✗ Gãy 2 tay — DỪNG BOT')
                            else:
                                s.current_bet = s.base_bet * 2
                                _emit_log(s, 'warn',
                                          f'✗ SAI phiên {s.last_bet_session} · '
                                          f'X2 → {s.current_bet:,}')
                        _emit_state(s)

            # Cập nhật dự đoán phiên mới
            if s.current_session != next_phien:
                s.current_session = next_phien
                pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
                _log_prediction(next_phien, pred)
                s.current_prediction = pred['prediction']
                s.last_pattern = pred['method']
                _emit_log(s, 'info',
                          f'Phiên {next_phien} · Dự đoán {pred["prediction"]} '
                          f'({pred["confidence"]}%)')

                # Đặt cược nếu auto bật
                if s.auto_bet_enabled and not s.is_paused:
                    if s.current_bet > s.balance:
                        s.is_paused = True
                        s.auto_bet_enabled = False
                        _emit_log(s, 'err', 'Hết tiền — DỪNG BOT')
                    else:
                        bet_res = _do_bet(s, pred['prediction'], s.current_bet)
                        if bet_res['ok']:
                            s.last_bet_session = next_phien
                            _register_bet(s, next_phien, pred['prediction'], s.current_bet)
                            s.balance -= s.current_bet
                            _emit_log(s, 'ok',
                                      f'💰 Cược {pred["prediction"]} · {s.current_bet:,}')
                        else:
                            _emit_log(s, 'err',
                                      f'Đặt cược lỗi: {bet_res.get("message", "?")}')
                _emit_state(s)

            time.sleep(3)
        except Exception as e:
            traceback.print_exc()
            _emit_log(s, 'err', f'Loop error: {e}')
            time.sleep(3)

    _emit_log(s, 'info', 'Auto bet loop stopped')


# Bet queue per session
BET_QUEUE = defaultdict(list)  # sid -> [{session, prediction, amount}]

def _register_bet(s, session, prediction, amount):
    BET_QUEUE[s.sid].append({
        'session': session,
        'prediction': prediction,
        'amount': amount,
        'ts': time.time(),
    })
    if len(BET_QUEUE[s.sid]) > 100:
        BET_QUEUE[s.sid] = BET_QUEUE[s.sid][-50:]


def _get_pending_bets(s):
    return BET_QUEUE.get(s.sid, [])


# =====================================================================
# SOCKET.IO EVENTS
# =====================================================================
@socketio.on('connect')
def _on_connect():
    sid = request.sid
    s = _get_session(sid)
    print(f"[SOCKET] Connect: {sid}")
    _emit_log(s, 'ok', f'Web socket kết nối: {sid}')
    _emit_state(s)


@socketio.on('disconnect')
def _on_disconnect():
    sid = request.sid
    print(f"[SOCKET] Disconnect: {sid}")
    if sid in SESSIONS:
        SESSIONS[sid].logged_in = False


@socketio.on('login')
def _on_login(data):
    sid = request.sid
    s = _get_session(sid)
    username = (data or {}).get('username', '').strip()
    password = (data or {}).get('password', '').strip()
    if not username or not password:
        _emit_log(s, 'err', 'Thiếu tài khoản hoặc mật khẩu')
        return
    ok = _do_login(s, username, password)
    if ok:
        # Start auto bet loop
        threading.Thread(target=_auto_bet_loop, args=(sid,), daemon=True).start()
        socketio.emit('login_result',
                      {'ok': True, 'nickname': s.nickname, 'balance': s.balance},
                      to=sid)
    else:
        socketio.emit('login_result',
                      {'ok': False, 'error': 'Đăng nhập thất bại'},
                      to=sid)


@socketio.on('set_bet')
def _on_set_bet(data):
    sid = request.sid
    s = _get_session(sid)
    try:
        amount = int((data or {}).get('amount', 0))
    except (TypeError, ValueError):
        _emit_log(s, 'err', 'Số tiền không hợp lệ')
        return
    if amount < 1000:
        _emit_log(s, 'err', 'Cược tối thiểu 1.000')
        return
    s.base_bet = amount
    s.current_bet = amount
    s.bet_step = 0
    _emit_log(s, 'ok', f'Đã set cược gốc: {amount:,}')
    _emit_state(s)


@socketio.on('toggle_auto')
def _on_toggle_auto():
    sid = request.sid
    s = _get_session(sid)
    if not s.logged_in:
        _emit_log(s, 'err', 'Chưa đăng nhập')
        return
    s.auto_bet_enabled = not s.auto_bet_enabled
    s.is_paused = False
    _emit_log(s, 'ok' if s.auto_bet_enabled else 'warn',
              f'AUTO {"ON" if s.auto_bet_enabled else "OFF"}')
    _emit_state(s)


@socketio.on('stop_bot')
def _on_stop():
    sid = request.sid
    s = _get_session(sid)
    s.auto_bet_enabled = False
    s.is_paused = True
    _emit_log(s, 'warn', 'BOT đã dừng')
    _emit_state(s)


@socketio.on('ping_keepalive')
def _on_ping(data):
    socketio.emit('pong_keepalive', {'ts': time.time()}, to=request.sid)


# =====================================================================
# HTTP ROUTES
# =====================================================================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/lc79md5')
def lc79md5():
    try:
        valid, ok = _sync_history()
        if not ok:
            return jsonify({'error': 'Không kết nối API'}), 500
        if not valid:
            return jsonify({'Id': 'LE MINH V8.1', 'Phien': None, 'Du_doan': None})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats()
        return jsonify({
            'Id': 'LE MINH V8.1 MD5',
            'Phien': str(next_phien),
            'Ket_qua_truoc': last['result'].lower(),
            'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%",
            'Phuong_phap': pred['method'],
            'Ly_do': pred['reason'],
            'Da_dao': pred.get('flipped', False),
            'Tong_phien': stats['total'],
            'AI_dung': ai_stats['correct'],
            'AI_sai': ai_stats['wrong'],
            'AI_cho': ai_stats['pending'],
            'Ti_le_AI': round(
                ai_stats['correct'] / max(ai_stats['evaluated'], 1) * 100, 1),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/history')
def history():
    try:
        valid, ok = _sync_history()
        if not ok:
            return jsonify({'error': 'Không kết nối API'}), 500
        if not valid:
            return jsonify({'rows': [], 'stats': {}, 'ai_stats': _log_stats()})
        out = []
        for v in reversed(valid[-200:]):
            log = PREDICTION_LOG.get(v['phien'])
            out.append({
                'phien': v['phien'],
                'result': v['result'],
                'dice': v['dice'],
                'total': v['total'],
                'ai_prediction': log['prediction'] if log else None,
                'ai_confidence': log['confidence'] if log else None,
                'ai_correct': log['correct'] if log else None,
            })
        return jsonify({
            'rows': out,
            'stats': _honest_stats(valid),
            'ai_stats': _log_stats(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def stats_only():
    try:
        valid, _ = _sync_history()
        return jsonify({
            'stats': _honest_stats(valid),
            'ai_stats': _log_stats(),
        })
    except Exception as e:
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
                MultiStrategyPredictor._STRATEGY_TRACK = defaultdict(
                    lambda: {'hit': 0, 'miss': 0, 'last_len': 0})
                _save_log()
                return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# =====================================================================
# RUN
# =====================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
