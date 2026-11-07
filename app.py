import os
import random
import traceback
import time
import json
import hashlib
import math
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
# DETERMINISTIC PREDICTOR v10
# =====================================================================
class MultiStrategyPredictor:
    _STRATEGY_TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0, 'last_len': 0})

    @staticmethod
    def _deterministic_choice(options, seed_str):
        h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
        return options[h % len(options)]

    # =================================================================
    # CORE SIGNALS
    # =================================================================
    @staticmethod
    def _markov_order2(valid, window=None):
        if len(valid) < 15:
            return None, 0, 0
        data = valid[-window:] if window and len(valid) > window else valid
        trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
        for i in range(len(data) - 2):
            key = (data[i]['result'], data[i + 1]['result'])
            trans[key][data[i + 2]['result']] += 1
        key = (data[-2]['result'], data[-1]['result'])
        counts = trans[key]
        total = counts['Tài'] + counts['Xỉu']
        if total < 3:
            return None, 0, 0
        p_tai_s = (counts['Tài'] + 1) / (total + 2)
        if p_tai_s > 0.58:
            return 'Tài', int(p_tai_s * 100), 1.35
        elif p_tai_s < 0.42:
            return 'Xỉu', int((1 - p_tai_s) * 100), 1.35
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
            return 'Tài', int(p_tai * 100), 1.20
        elif p_tai < 0.44:
            return 'Xỉu', int((1 - p_tai) * 100), 1.20
        return None, 0, 0

    # =================================================================
    # STREAK ADAPTIVE
    # =================================================================
    @staticmethod
    def _streak_break(valid, window=None):
        if len(valid) < 4:
            return None, 0, 0
        last = valid[-1]['result']
        streak = 1
        for i in range(len(valid) - 2, -1, -1):
            if valid[i]['result'] == last:
                streak += 1
            else:
                break

        opp = 'Xỉu' if last == 'Tài' else 'Tài'

        if streak == 1 and len(valid) >= 6:
            prev = valid[-2]['result']
            prev_run = 1
            for i in range(len(valid) - 3, -1, -1):
                if valid[i]['result'] == prev:
                    prev_run += 1
                else:
                    break
            if prev_run >= 4:
                return last, 62, 1.10

        if streak < 3:
            return None, 0, 0

        if streak >= 8:
            return None, 0, 0

        breaks, continues = 0, 0
        run = 1
        for i in range(1, len(valid)):
            if valid[i]['result'] == valid[i - 1]['result']:
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
            target = opp
            conf = int(p_break * 100)
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

    # =================================================================
    # EXHAUSTION (cầu kiệt)
    # =================================================================
    @staticmethod
    def _exhaustion(valid):
        if len(valid) < 10:
            return None, 0, 0
        last = valid[-1]['result']
        streak = 1
        for i in range(len(valid) - 2, -1, -1):
            if valid[i]['result'] == last:
                streak += 1
            else:
                break

        if streak < 8:
            return None, 0, 0

        opp = 'Xỉu' if last == 'Tài' else 'Tài'

        long_breaks, long_total = 0, 0
        run = 1
        for i in range(1, len(valid) - 1):
            if valid[i]['result'] == valid[i - 1]['result']:
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

        if long_total == 0:
            base -= 8
        else:
            p_break = long_breaks / long_total
            base = int(base * 0.6 + p_break * 100 * 0.4)

        conf = max(55, min(int(base), 80))
        weight = 1.1 + (streak - 8) * 0.08
        return opp, conf, min(weight, 1.5)

    # =================================================================
    # DOMINANCE FLIP (lệch cực đoan)
    # =================================================================
    @staticmethod
    def _dominance_flip(valid):
        if len(valid) < 20:
            return None, 0, 0
        seg = [v['result'] for v in valid[-20:]]
        t = sum(1 for x in seg if x == 'Tài') / 20
        if t >= 0.85:
            conf = min(int((t - 0.75) * 200), 75)
            return 'Xỉu', max(conf, 58), 0.90
        if t <= 0.15:
            conf = min(int((0.25 - t) * 200), 75)
            return 'Tài', max(conf, 58), 0.90
        return None, 0, 0

    # =================================================================
    # FOLLOW TREND
    # =================================================================
    @staticmethod
    def _follow_trend(valid):
        if len(valid) < 8:
            return None, 0, 0

        last = valid[-1]['result']
        streak = 1
        for i in range(len(valid) - 2, -1, -1):
            if valid[i]['result'] == last:
                streak += 1
            else:
                break

        if streak >= 8:
            return None, 0, 0

        if streak >= 5:
            conf = min(58 + (streak - 5) * 4, 72)
            return last, conf, 1.25

        if len(valid) >= 15:
            seg15 = [v['result'] for v in valid[-15:]]
            t15 = sum(1 for x in seg15 if x == 'Tài') / 15
            seg5 = seg15[-5:]
            t5 = sum(1 for x in seg5 if x == 'Tài') / 5
            if 0.70 <= t15 <= 0.80 and t5 >= 0.60:
                conf = min(55 + int((t15 - 0.6) * 100), 72)
                return 'Tài', conf, 1.15
            if 0.20 <= t15 <= 0.30 and t5 <= 0.40:
                conf = min(55 + int((0.4 - t15) * 100), 72)
                return 'Xỉu', conf, 1.15
        return None, 0, 0

    # =================================================================
    # INVERT CAU
    # =================================================================
    @staticmethod
    def _invert_cau(valid):
        if len(valid) < 12:
            return None, 0, 0
        r = [v['result'] for v in valid[-16:]]

        alt = sum(1 for i in range(1, len(r)) if r[i] != r[i - 1])
        alt_ratio = alt / (len(r) - 1)
        if alt_ratio >= 0.65:
            nxt = 'Xỉu' if r[-1] == 'Tài' else 'Tài'
            conf = min(56 + int(alt_ratio * 30), 82)
            return nxt, conf, 1.30

        block2_hits = 0
        block2_total = 0
        for i in range(2, len(r)):
            if r[i] == r[i - 2] and r[i] != r[i - 1]:
                block2_hits += 1
            if r[i] != r[i - 1]:
                block2_total += 1
        if block2_total >= 4 and block2_hits / block2_total >= 0.7:
            tail_run = 1
            for i in range(len(r) - 2, -1, -1):
                if r[i] == r[-1]:
                    tail_run += 1
                else:
                    break
            nxt = r[-2] if tail_run == 1 else ('Xỉu' if r[-1] == 'Tài' else 'Tài')
            return nxt, 68, 1.25

        run = 1
        for i in range(len(r) - 2, -1, -1):
            if r[i] == r[-1]:
                run += 1
            else:
                break
        if run == 1 and len(r) >= 6:
            prev = r[-2]
            prev_run = 1
            for i in range(len(r) - 3, -1, -1):
                if r[i] == prev:
                    prev_run += 1
                else:
                    break
            if prev_run >= 4:
                return r[-1], 62, 1.15
        return None, 0, 0

    # =================================================================
    # TREND
    # =================================================================
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
            conf = min(int((p10 - 0.5) * 200 + 52), 78)
            return 'Tài', conf, 1.20
        if p10 < 0.45 and p20 < 0.48 and p10 <= p20 + 0.05 and p40 - p10 >= 0.05:
            conf = min(int((0.5 - p10) * 200 + 52), 78)
            return 'Xỉu', conf, 1.20
        return None, 0, 0

    # =================================================================
    # BIAS RUN
    # =================================================================
    @staticmethod
    def _bias_run(valid):
        if len(valid) < 24:
            return None, 0, 0
        r = [v['result'] for v in valid[-24:]]
        first = r[:12]
        second = r[12:]

        r_first = sum(1 for x in first if x == 'Tài') / 12
        r_second = sum(1 for x in second if x == 'Tài') / 12

        if r_second - r_first >= 0.25 and r_second >= 0.60:
            conf = min(int((r_second - 0.5) * 180 + 55), 80)
            return 'Tài', conf, 1.15
        if r_first - r_second >= 0.25 and (1 - r_second) >= 0.60:
            conf = min(int((0.5 - r_second) * -180 + 55), 80)
            return 'Xỉu', conf, 1.15
        if r_second >= 0.75:
            return 'Tài', 65, 1.00
        if r_second <= 0.25:
            return 'Xỉu', 65, 1.00
        return None, 0, 0

    # =================================================================
    # OTHERS
    # =================================================================
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
                bonus = min(plen * 2, 10)
                conf_adj = min(conf + bonus, 88)
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
            w = (i + 1) / len(recent)
            w = w ** 1.5
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
        elif p < 0.42:
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
            conf = int(min((ratio - 0.5) * 200, 75))
            return 'Xỉu', max(conf, 55), 0.65
        elif ratio < 0.38:
            conf = int(min((0.5 - ratio) * 200, 75))
            return 'Tài', max(conf, 55), 0.65
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
            conf = min(int(alt_ratio * 100) + 5, 85)
            return nxt, conf, 1.45
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
        elif p <= 0.3:
            return 'Xỉu', int((1 - p) * 100), 0.95
        return None, 0, 0

    @staticmethod
    def _recency_streak(valid):
        if len(valid) < 10:
            return None, 0, 0
        weights = {'Tài': 0.0, 'Xỉu': 0.0}
        n = 10
        for i in range(len(valid) - n, len(valid)):
            w = (i - (len(valid) - n) + 1) / n
            w = w ** 2
            weights[valid[i]['result']] += w
        total = weights['Tài'] + weights['Xỉu']
        if total == 0:
            return None, 0, 0
        p = weights['Tài'] / total
        if p > 0.6:
            return 'Tài', int(p * 100), 1.15
        elif p < 0.4:
            return 'Xỉu', int((1 - p) * 100), 1.15
        return None, 0, 0

    @staticmethod
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

    # =================================================================
    # ADAPTIVE WEIGHTS
    # =================================================================
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
        factor = max(0.45, min(factor, 1.6))
        return base_weight * factor

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
            for fname, fn in (
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
            ):
                try:
                    p, c, w = fn(history)
                    if p is not None:
                        cls._update_track(fname, p, actual)
                except Exception:
                    pass
        cls._STRATEGY_TRACK['__len__'] = {'last_len': cur_len}

    # =================================================================
    # MAIN PREDICT
    # =================================================================
    @classmethod
    def predict(cls, valid):
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
            return {'prediction': opp, 'confidence': conf,
                    'method': 'streak_fallback', 'signals': [],
                    'reason': f'Ít dữ liệu — bẻ chuỗi {streak}'}

        cls._sync_track_from_history(valid)

        strategy_defs = [
            ('markov2',     lambda v: cls._markov_order2(v)),
            ('markov1',     lambda v: cls._markov_order1(v)),
            ('streak',      lambda v: cls._streak_break(v)),
            ('pattern',     lambda v: cls._pattern_match(v)),
            ('weighted',    lambda v: cls._weighted_freq(v)),
            ('dice',        lambda v: cls._dice_bias(v)),
            ('alternation', lambda v: cls._alternation(v)),
            ('momentum',    lambda v: cls._momentum(v)),
            ('recency',     lambda v: cls._recency_streak(v)),
            ('invert',      lambda v: cls._invert_cau(v)),
            ('trend',       lambda v: cls._trend(v)),
            ('bias_run',    lambda v: cls._bias_run(v)),
            ('follow',      lambda v: cls._follow_trend(v)),
            ('exhaust',     lambda v: cls._exhaustion(v)),
            ('dominance',   lambda v: cls._dominance_flip(v)),
        ]

        log_odds = 0.0
        signals = []
        total_weight = 0.0

        for name, fn in strategy_defs:
            try:
                pred, conf, weight = fn(valid)
            except Exception:
                continue
            if pred is None or weight == 0:
                continue

            weight = cls._get_adaptive_weight(name, weight)

            p = max(0.51, min(conf / 100.0, 0.92))
            lr = p / (1 - p)
            if pred == 'Xỉu':
                lr = 1.0 / lr

            contrib = weight * (1.0 if pred == 'Tài' else -1.0) * (lr - 1.0)
            log_odds += contrib
            total_weight += weight
            signals.append({
                'name': name, 'prediction': pred,
                'confidence': conf, 'weight': round(weight, 2),
            })

        if not signals or total_weight == 0:
            pick = cls._deterministic_choice(['Tài', 'Xỉu'], seed)
            return {'prediction': pick, 'confidence': 50, 'method': 'random',
                    'signals': [], 'reason': 'Không có tín hiệu'}

        scaled = log_odds / max(total_weight, 1.0) * 1.8
        p_tai = 1.0 / (1.0 + math.exp(-scaled))
        if p_tai >= 0.5:
            pred = 'Tài'
            raw_conf = int(p_tai * 100)
        else:
            pred = 'Xỉu'
            raw_conf = int((1 - p_tai) * 100)

        recent = [v['result'] for v in valid[-20:]]
        entropy = cls._entropy(recent)

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

        final_conf = raw_conf - penalty + bonus
        final_conf = max(50, min(final_conf, 88))

        method = '+'.join(s['name'] for s in signals[:4]) or 'ensemble'
        if len(signals) > 4:
            method += f'+{len(signals) - 4}'

        return {
            'prediction': pred,
            'confidence': final_conf,
            'method': method,
            'signals': signals,
            'reason': (f"{len(signals)} tín hiệu · entropy={entropy:.2f} · "
                       f"đồng thuận={agreement:.0%}"),
        }


# =====================================================================
# 80 MẪU TEST PATTERN
# =====================================================================
TEST_PATTERNS = [
    {"name": "1-1_clean", "seq": "T X T X T X T X T X T X T X T X T X", "expect_note": "bẻ theo nhịp"},
    {"name": "1-1_start_X", "seq": "X T X T X T X T X T X T X T X T X T", "expect_note": "bẻ theo nhịp"},
    {"name": "1-1_mixed_short", "seq": "T X T X T X T X T", "expect_note": "bẻ"},
    {"name": "1-1_long", "seq": "T X " * 12, "expect_note": "theo nhịp"},
    {"name": "1-1_with_noise", "seq": "T X T X T X T T X T X T X T X T X", "expect_note": "bẻ"},
    {"name": "2-2_clean", "seq": "T T X X T T X X T T X X T T X X", "expect_note": "đảo block"},
    {"name": "2-2_start_X", "seq": "X X T T X X T T X X T T X X T T", "expect_note": "đảo block"},
    {"name": "2-2_mixed", "seq": "T T X X T T X X T T X T T X X", "expect_note": "đảo"},
    {"name": "2-2_long", "seq": "T T X X " * 6, "expect_note": "đảo block"},
    {"name": "3-3_clean", "seq": "T T T X X X T T T X X X T T T", "expect_note": "đảo block"},
    {"name": "3-3_short", "seq": "T T T X X X T T T", "expect_note": "đảo block"},
    {"name": "3-3_start_X", "seq": "X X X T T T X X X T T T", "expect_note": "đảo block"},
    {"name": "all_tai_3", "seq": "T T T", "expect_note": "bẻ nhẹ"},
    {"name": "all_tai_4", "seq": "T T T T", "expect_note": "bẻ"},
    {"name": "all_tai_5", "seq": "T T T T T", "expect_note": "theo cầu"},
    {"name": "all_tai_6", "seq": "T T T T T T", "expect_note": "theo cầu"},
    {"name": "all_tai_7", "seq": "T T T T T T T", "expect_note": "trung tính"},
    {"name": "all_tai_8", "seq": "T T T T T T T T", "expect_note": "kiệt — bẻ"},
    {"name": "all_tai_10", "seq": "T T T T T T T T T T", "expect_note": "kiệt — bẻ mạnh"},
    {"name": "all_tai_12", "seq": "T " * 12, "expect_note": "kiệt cực mạnh"},
    {"name": "all_tai_15", "seq": "T " * 15, "expect_note": "siêu kiệt"},
    {"name": "all_tai_20", "seq": "T " * 20, "expect_note": "dominance flip"},
    {"name": "all_xiu_3", "seq": "X X X", "expect_note": "bẻ nhẹ"},
    {"name": "all_xiu_5", "seq": "X X X X X", "expect_note": "theo cầu"},
    {"name": "all_xiu_8", "seq": "X X X X X X X X", "expect_note": "kiệt — bẻ"},
    {"name": "all_xiu_10", "seq": "X " * 10, "expect_note": "kiệt"},
    {"name": "all_xiu_12", "seq": "X " * 12, "expect_note": "kiệt mạnh"},
    {"name": "all_xiu_20", "seq": "X " * 20, "expect_note": "dominance flip"},
    {"name": "85pct_tai", "seq": "T " * 17 + "X X X", "expect_note": "lệch — bẻ"},
    {"name": "85pct_xiu", "seq": "X " * 17 + "T T T", "expect_note": "lệch — bẻ"},
    {"name": "75pct_tai", "seq": "T T T X " * 5, "expect_note": "nghiêng Tài"},
    {"name": "75pct_xiu", "seq": "X X X T " * 5, "expect_note": "nghiêng Xỉu"},
    {"name": "trend_up", "seq": "X X X X X T T T T T T T T T T", "expect_note": "theo Tài"},
    {"name": "trend_up_recent", "seq": "X X T X T T T T T T T", "expect_note": "theo Tài"},
    {"name": "trend_down", "seq": "T T T T T X X X X X X X X X X", "expect_note": "theo Xỉu"},
    {"name": "trend_down_recent", "seq": "T T X T X X X X X X X", "expect_note": "theo Xỉu"},
    {"name": "break_after_5tai", "seq": "T T T T T X", "expect_note": "đảo lại Tài"},
    {"name": "break_after_5xiu", "seq": "X X X X X T", "expect_note": "đảo lại Xỉu"},
    {"name": "break_after_6tai", "seq": "T T T T T T X", "expect_note": "đảo lại Tài"},
    {"name": "break_after_7xiu", "seq": "X X X X X X X T", "expect_note": "đảo lại Xỉu"},
    {"name": "zigzag_1", "seq": "T X X T T X X T T X", "expect_note": "theo nhịp"},
    {"name": "zigzag_2", "seq": "T T X T T X T T X", "expect_note": "theo nhịp"},
    {"name": "zigzag_3", "seq": "X T T X T T X T", "expect_note": "theo nhịp"},
    {"name": "1-2_clean", "seq": "T X X T X X T X X T X X", "expect_note": "đảo block"},
    {"name": "1-2_start_X", "seq": "X T T X T T X T T X T T", "expect_note": "đảo block"},
    {"name": "2-1_clean", "seq": "T T X T T X T T X T T X", "expect_note": "đảo block"},
    {"name": "2-1_start_X", "seq": "X X T X X T X X T X X T", "expect_note": "đảo block"},
    {"name": "1-3_clean", "seq": "T X X X T X X X T X X X", "expect_note": "đảo block"},
    {"name": "3-1_clean", "seq": "T T T X T T T X T T T X", "expect_note": "đảo block"},
    {"name": "2-2-1", "seq": "T T X X T T T X X T T T X X", "expect_note": "pattern"},
    {"name": "noisy_1", "seq": "T X T T X X T X X T T X T X", "expect_note": "không chắc"},
    {"name": "noisy_2", "seq": "T T X T X T T X X T X T X X", "expect_note": "không chắc"},
    {"name": "noisy_3", "seq": "X T X X T T X T X X T X T T", "expect_note": "không chắc"},
    {"name": "random", "seq": "T X X T T X T T X X T X T T X X T", "expect_note": "không chắc"},
    {"name": "symmetry", "seq": "T T T X X X X X X T T T", "expect_note": "đảo block"},
    {"name": "reverse_symmetry", "seq": "X X X T T T T T T X X X", "expect_note": "đảo block"},
    {"name": "sandwich", "seq": "T X X T T X X T T X X T", "expect_note": "theo nhịp"},
    {"name": "double_sandwich", "seq": "T T X X X X T T T T X X X X", "expect_note": "đảo block"},
    {"name": "trend_to_exhaust", "seq": "X T T T T T T T T T", "expect_note": "kiệt Tài"},
    {"name": "trend_to_exhaust_xiu", "seq": "T X X X X X X X X X", "expect_note": "kiệt Xỉu"},
    {"name": "fast_flip", "seq": "T T T X X X T T T X X X T", "expect_note": "đảo block"},
    {"name": "slow_flip", "seq": "T T T T T X X X X X T T T T", "expect_note": "đảo block"},
    {"name": "classic_break", "seq": "T T T X", "expect_note": "vừa bẻ"},
    {"name": "classic_break_xiu", "seq": "X X X T", "expect_note": "vừa bẻ"},
    {"name": "mix_1", "seq": "T T X X T T T X X X T T T T", "expect_note": "tăng dần block"},
    {"name": "mix_2", "seq": "X X T T X X X T T T X X X X", "expect_note": "tăng dần block"},
    {"name": "mix_3", "seq": "T X X T T T X X X X T T T T T", "expect_note": "tăng dần block"},
    {"name": "4-4", "seq": "T T T T X X X X T T T T X X X X", "expect_note": "đảo block"},
    {"name": "5-5", "seq": "T T T T T X X X X X T T T T T", "expect_note": "đảo block"},
    {"name": "tail_dai_break", "seq": "X X T T T T T T X", "expect_note": "đảo lại Tài"},
    {"name": "tail_dai_break_xiu", "seq": "T T X X X X X X T", "expect_note": "đảo lại Xỉu"},
    {"name": "high_entropy", "seq": "T X T T X X T X X T T X X T X T", "expect_note": "không chắc"},
    {"name": "low_entropy", "seq": "T T T T T T T T T T T T T T T", "expect_note": "kiệt"},
]

def _seq_to_valid(seq_str, start_phien=1000):
    """Chuyển chuỗi 'T X T ...' thành valid list"""
    tokens = seq_str.split()
    valid = []
    for i, tok in enumerate(tokens):
        valid.append({
            'phien': start_phien + i,
            'result': 'Tài' if tok.upper() == 'T' else 'Xỉu',
            'dice': '0 + 0 + 0',
            'total': 0,
        })
    return valid


# =====================================================================
# BỘ MẪU CẦU TEST ALL — KHÔNG RANDOM
# =====================================================================
def _build_all_cau_tests():
    """
    Sinh mẫu cầu quy luật rõ ràng để test.
    Trả list dict: {name, history, actual, expect}
    """
    tests = []

    def add(name, history_str, actual_char, expect_char):
        h = _seq_to_valid(history_str)
        if len(h) < 4:
            return
        actual = 'Tài' if actual_char.upper() == 'T' else 'Xỉu'
        expect = 'Tài' if expect_char.upper() == 'T' else 'Xỉu'
        tests.append({
            'name': name,
            'history': history_str,
            'actual': actual,
            'expect': expect,
        })

    # ---- CẦU 1-1 ----
    for i in range(6, 15):
        seq = ' '.join(['T' if j % 2 == 0 else 'X' for j in range(i)])
        nxt = 'T' if i % 2 == 0 else 'X'
        add(f'1-1_len{i}', seq, nxt, nxt)

    # ---- CẦU 2-2 ----
    for i in range(6, 15):
        seq = ' '.join(['T' if (j // 2) % 2 == 0 else 'X' for j in range(i)])
        nxt = 'T' if (i // 2) % 2 == 0 else 'X'
        add(f'2-2_len{i}', seq, nxt, nxt)

    # ---- CẦU 3-3 ----
    for i in range(6, 15):
        seq = ' '.join(['T' if (j // 3) % 2 == 0 else 'X' for j in range(i)])
        nxt = 'T' if (i // 3) % 2 == 0 else 'X'
        add(f'3-3_len{i}', seq, nxt, nxt)

    # ---- CẦU BỆT TÀI (test bẻ) ----
    for n in (3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 18, 20):
        add(f'bet_tai_{n}', ' '.join(['T'] * n), 'X', 'X')

    # ---- CẦU BỆT XỈU ----
    for n in (3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 18, 20):
        add(f'bet_xiu_{n}', ' '.join(['X'] * n), 'T', 'T')

    # ---- CẦU 1-2 ----
    for i in range(6, 15):
        seq = []
        j = 0
        toggle = True
        while len(seq) < i:
            if toggle:
                seq.append('T')
            else:
                seq.extend(['X', 'X'])
            toggle = not toggle
        seq = seq[:i]
        j = i
        toggle = True
        cnt = 0
        phase = 0
        while cnt < j:
            size = 1 if phase % 2 == 0 else 2
            cnt += size
            phase += 1
        nxt = 'T' if (phase - 1) % 2 == 0 else 'X'
        add(f'1-2_len{i}', ' '.join(seq), nxt, nxt)

    # ---- CẦU 2-1 ----
    for i in range(6, 15):
        seq = []
        toggle = True
        while len(seq) < i:
            if toggle:
                seq.extend(['T', 'T'])
            else:
                seq.append('X')
            toggle = not toggle
        seq = seq[:i]
        phase = 0
        cnt = 0
        while cnt < i:
            size = 2 if phase % 2 == 0 else 1
            cnt += size
            phase += 1
        nxt = 'T' if (phase - 1) % 2 == 0 else 'X'
        add(f'2-1_len{i}', ' '.join(seq), nxt, nxt)

    # ---- CẦU 4-4 ----
    for i in range(8, 15):
        seq = ' '.join(['T' if (j // 4) % 2 == 0 else 'X' for j in range(i)])
        nxt = 'T' if (i // 4) % 2 == 0 else 'X'
        add(f'4-4_len{i}', seq, nxt, nxt)

    # ---- CẦU 5-5 ----
    for i in range(10, 16):
        seq = ' '.join(['T' if (j // 5) % 2 == 0 else 'X' for j in range(i)])
        nxt = 'T' if (i // 5) % 2 == 0 else 'X'
        add(f'5-5_len{i}', seq, nxt, nxt)

    # ---- XU HƯỚNG TĂNG ----
    add('trend_up', 'X X X X X T T T T T T T T T T', 'T', 'T')
    add('trend_down', 'T T T T T X X X X X X X X X X', 'X', 'X')
    add('trend_up_short', 'X X X T T T T T T', 'T', 'T')
    add('trend_down_short', 'T T T X X X X X X', 'X', 'X')

    # ---- ĐẢO CẦU SAU CHUỖI DÀI ----
    add('break_5tai', 'T T T T T X', 'T', 'T')
    add('break_5xiu', 'X X X X X T', 'X', 'X')
    add('break_6tai', 'T T T T T T X', 'T', 'T')
    add('break_6xiu', 'X X X X X X T', 'X', 'X')
    add('break_7tai', 'T T T T T T T X', 'T', 'T')
    add('break_7xiu', 'X X X X X X X T', 'X', 'X')

    # ---- CẦU GẤP KHÚC ----
    add('zigzag_1', 'T X X T T X X T T X', 'T', 'T')
    add('zigzag_2', 'T T X T T X T T X', 'T', 'T')

    # ---- 2-2-1 ----
    add('2-2-1_1', 'T T X X T T X X T', 'T', 'T')
    add('2-2-1_2', 'T T X X T T T X X T T T X X', 'T', 'T')

    # ---- SYMMETRY ----
    add('symmetry', 'T T T X X X X X X T T T', 'X', 'X')
    add('reverse_symmetry', 'X X X T T T T T T X X X', 'T', 'T')

    # ---- TĂNG DẦN BLOCK ----
    add('mix_1', 'T T X X T T T X X X T T T T', 'X', 'X')
    add('mix_2', 'X X T T X X X T T T X X X X', 'T', 'T')

    # ---- CLASSIC BREAK ----
    add('classic_break', 'T T T X', 'X', 'X')
    add('classic_break_xiu', 'X X X T', 'T', 'T')

    return tests


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
    <div class="logo">LE MINH <span>Bon</span></div>
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
            return jsonify({'Id': 'le minh ai v10', 'Phien': None, 'Du_doan': None})

        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats()

        return jsonify({
            'Id': 'le minh ai v10',
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
                MultiStrategyPredictor._STRATEGY_TRACK = defaultdict(
                    lambda: {'hit': 0, 'miss': 0, 'last_len': 0}
                )
                _save_log()
                return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys())
            HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
            PREDICTION_LOG = {}
            MultiStrategyPredictor._STRATEGY_TRACK = defaultdict(
                lambda: {'hit': 0, 'miss': 0, 'last_len': 0}
            )
            _save_log()
            return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        return jsonify({'status': 'error', 'message': 'Không có dữ liệu để reset'}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# =====================================================================
# API TEST 80 MẪU PATTERN
# =====================================================================
@app.route('/api/test_patterns')
def test_patterns():
    """
    Chạy toàn bộ 80 mẫu pattern qua predictor v10.
    GET /api/test_patterns           → trả JSON
    GET /api/test_patterns?format=txt → trả text
    """
    try:
        results = []
        correct = 0
        total = 0

        for pattern in TEST_PATTERNS:
            seq = pattern['seq'].strip()
            tokens = seq.split()
            if len(tokens) < 5:
                continue

            history_tokens = tokens[:-1]
            actual_tok = tokens[-1].upper()
            actual = 'Tài' if actual_tok == 'T' else 'Xỉu'

            valid = _seq_to_valid(' '.join(history_tokens))
            if len(valid) < 4:
                continue

            pred = MultiStrategyPredictor.predict(valid)
            is_correct = (pred['prediction'] == actual)
            if is_correct:
                correct += 1
            total += 1

            results.append({
                'name': pattern['name'],
                'seq': seq,
                'history_len': len(valid),
                'prediction': pred['prediction'],
                'confidence': pred['confidence'],
                'actual': actual,
                'correct': is_correct,
                'method': pred['method'],
                'reason': pred['reason'],
                'note': pattern.get('expect_note', ''),
            })

        acc = round(correct / total * 100, 2) if total > 0 else 0

        fmt = request.args.get('format', 'json').lower()
        if fmt == 'txt':
            lines = []
            lines.append(f"=== TEST {total} MẪU PATTERN v10 ===")
            lines.append(f"Đúng: {correct}/{total} ({acc}%)")
            lines.append("")
            for r in results:
                mark = '✓' if r['correct'] else '✗'
                lines.append(
                    f"{mark} {r['name']:<22} | seq={r['seq']:<40} | "
                    f"pred={r['prediction']:<5} ({r['confidence']}%) | "
                    f"actual={r['actual']:<5} | {r['note']}"
                )
            return '\n'.join(lines), 200, {'Content-Type': 'text/plain; charset=utf-8'}

        return jsonify({
            'version': 'v10',
            'total': total,
            'correct': correct,
            'accuracy': acc,
            'results': results,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =====================================================================
# API TEST TẤT CẢ CẦU — KHÔNG RANDOM
# =====================================================================
@app.route('/api/test_all_cau')
def test_all_cau():
    """
    Test exhaustive qua TẤT CẢ mẫu cầu deterministic.
    - Không random
    - So sánh prediction vs expect (kỳ vọng của pattern)
    - Trả thống kê theo từng nhóm cầu

    GET /api/test_all_cau            → JSON
    GET /api/test_all_cau?format=txt → text
    """
    try:
        tests = _build_all_cau_tests()
        results = []
        correct = 0
        total = 0
        by_group = defaultdict(lambda: {'correct': 0, 'total': 0})

        for t in tests:
            valid = _seq_to_valid(t['history'])
            if len(valid) < 4:
                continue

            pred = MultiStrategyPredictor.predict(valid)
            is_correct = (pred['prediction'] == t['expect'])
            total += 1
            if is_correct:
                correct += 1

            group = t['name'].split('_')[0]
            by_group[group]['total'] += 1
            if is_correct:
                by_group[group]['correct'] += 1

            results.append({
                'name': t['name'],
                'history_len': len(valid),
                'history_tail': ' '.join(
                    ['T' if v['result'] == 'Tài' else 'X' for v in valid[-8:]]
                ),
                'prediction': pred['prediction'],
                'confidence': pred['confidence'],
                'expect': t['expect'],
                'actual_result': t['actual'],
                'correct_vs_expect': is_correct,
                'correct_vs_actual': (pred['prediction'] == t['actual']),
                'method': pred['method'],
                'flipped': pred.get('flipped', False),
            })

        acc = round(correct / total * 100, 2) if total > 0 else 0
        group_stats = {
            k: {'correct': v['correct'], 'total': v['total'],
                'accuracy': round(v['correct'] / v['total'] * 100, 2) if v['total'] else 0}
            for k, v in sorted(by_group.items())
        }

        fmt = request.args.get('format', 'json').lower()
        if fmt == 'txt':
            lines = [f"=== TEST ALL CẦU v10 (NO RANDOM) ===",
                     f"Tổng: {total} mẫu | Đúng kỳ vọng: {correct} ({acc}%)", ""]
            lines.append("--- THEO NHÓM ---")
            for k, v in group_stats.items():
                lines.append(f"  {k:<15} {v['correct']}/{v['total']} ({v['accuracy']}%)")
            lines.append("")
            lines.append("--- CHI TIẾT ---")
            for r in results:
                mark = '✓' if r['correct_vs_expect'] else '✗'
                flip = ' [FLIP]' if r['flipped'] else ''
                lines.append(
                    f"{mark} {r['name']:<20} hist={r['history_tail']:<24} "
                    f"pred={r['prediction']:<5}({r['confidence']}%) "
                    f"expect={r['expect']:<5} actual={r['actual_result']:<5}{flip}"
                )
            return '\n'.join(lines), 200, {'Content-Type': 'text/plain; charset=utf-8'}

        return jsonify({
            'version': 'v10',
            'total': total,
            'correct': correct,
            'accuracy': acc,
            'group_stats': group_stats,
            'results': results,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
