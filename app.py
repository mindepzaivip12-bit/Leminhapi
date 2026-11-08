import os
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
API_URL_HU = (
    "https://wtx.tele68.com/v1/tx/lite-sessions"
    "?cp=R&cl=R&pf=web&at=4b53d17c817943086def89a78d10a2eb"
)

HISTORY_CACHE = {}
HU_HISTORY_CACHE = {}
RESET_ID = 0
HU_RESET_ID = 0
PREDICTION_LOG = {}
HU_PREDICTION_LOG = {}
MAX_LOG_SIZE = 3000
LOG_FILE = "prediction_log.json"

SIGNAL_NAMES = {
    'markov3':      'Markov bậc 3',
    'markov2':      'Markov bậc 2',
    'markov1':      'Markov bậc 1',
    'streak':       'Bẻ chuỗi',
    'pattern':      'Khớp mẫu',
    'weighted':     'Tần suất',
    'dice':         'Lệch xúc xắc',
    'alternation':  'Cầu 1-1',
    'momentum':     'Đà',
    'recency':      'Gần đây',
    'invert':       'Đảo cầu',
    'trend':        'Xu hướng',
    'bias_run':     'Lệch 12 phiên',
    'follow':       'Theo cầu',
    'exhaust':      'Cầu kiệt',
    'dominance':    'Lệch cực đoan',
    'cycle_1_1':    'Chu kỳ 1-1',
    'cycle_2_2':    'Chu kỳ 2-2',
    'cycle_3_3':    'Chu kỳ 3-3',
    'cycle_1_2':    'Chu kỳ 1-2',
    'cycle_2_1':    'Chu kỳ 2-1',
    'cycle_1_3':    'Chu kỳ 1-3',
    'cycle_3_1':    'Chu kỳ 3-1',
    'cycle_2_3':    'Chu kỳ 2-3',
    'cycle_3_2':    'Chu kỳ 3-2',
    'cycle_123':    'Chu kỳ 1-2-3',
    'cycle_321':    'Chu kỳ 3-2-1',
    'cycle_346':    'Chu kỳ 3-4-6',
    'cycle_112':    'Chu kỳ 1-1-2',
    'cycle_212':    'Chu kỳ 2-1-2',
    'cycle_122':    'Chu kỳ 1-2-2',
    'cycle_221':    'Chu kỳ 2-2-1',
    'auto_cycle':   'Chu kỳ tự động',
    'pattern_sim':  'Tương đồng mẫu',
    'regime':       'Chế độ thị trường',
    'flip_break':   'Bẻ cầu đảo',
    'run_break':    'Bẻ run dài',
    'cross_game':   'Đối chiếu chéo',
    'hu_dice_pattern':   'Hũ · Lệch điểm',
    'hu_streak_predict': 'Hũ · Bẻ ngắn',
    'hu_momentum_boost': 'Hũ · Điểm+chiều',
    'ngram_2':          'N-gram 2',
    'ngram_3':          'N-gram 3',
    'ngram_4':          'N-gram 4',
    'ngram_5':          'N-gram 5',
    'mirror_pattern':   'Đối xứng đảo',
    'reverse_trend':    'Đảo xu hướng',
    'palindrome_check': 'Cầu đối xứng',
    'bayes_recent':     'Bayes gần đây',
    'chi_square':       'Kiểm định lệch',
    'runs_prediction':  'Chuỗi run-length',
    'transition_matrix': 'Ma trận chuyển',
    'cycle_1234':       'Chu kỳ 1-2-3-4',
    'cycle_2341':       'Chu kỳ 2-3-4-1',
    'cycle_3456':       'Chu kỳ 3-4-5-6',
    'cycle_4_4':        'Chu kỳ 4-4',
    'double_break':     'Bẻ đôi',
    'signal_consensus': 'Đồng thuận tín hiệu',
    'signal_dissent':   'Phản biện tín hiệu',
    'entropy_adaptive': 'Entropy thích ứng',
    'streak_maturity':  'Độ chín streak',
    # V6.0 NEW
    'time_pattern':     'Mẫu thời gian',
    'volatility':       'Biến động',
    'cusum':            'CUSUM',
    'kelly_optimal':    'Kelly tối ưu',
    'multi_window':     'Đa cửa sổ',
    'rsi_signal':       'RSI cầu',
    'fibonacci_break':  'Fibonacci bẻ',
    'zscore_extreme':   'Z-Score cực trị',
}


# =====================================================================
# PERSISTENCE
# =====================================================================
def _load_log():
    global PREDICTION_LOG, HU_PREDICTION_LOG, RESET_ID, HU_RESET_ID
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        PREDICTION_LOG = {int(k): v for k, v in data.get('log', {}).items()}
        HU_PREDICTION_LOG = {int(k): v for k, v in data.get('hu_log', {}).items()}
        RESET_ID = int(data.get('reset_id', 0))
        HU_RESET_ID = int(data.get('hu_reset_id', 0))
        print(f"[LOG] Loaded {len(PREDICTION_LOG)} TX + {len(HU_PREDICTION_LOG)} HU")
    except Exception as e:
        print(f"[LOG] Load failed: {e}")


def _save_log():
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'log': PREDICTION_LOG,
                'hu_log': HU_PREDICTION_LOG,
                'reset_id': RESET_ID,
                'hu_reset_id': HU_RESET_ID,
            }, f)
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
# PREDICTOR V6.0
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

    # ==================== CYCLE ====================
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

    # ==================== V6.0 NEW SIGNALS ====================
    @classmethod
    def _time_pattern(cls, valid):
        """Phát hiện pattern theo chu kỳ thời gian (mỗi N phiên lặp)."""
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid]
        # Kiểm tra chu kỳ 5, 6, 7, 8, 9, 10
        for period in (5, 6, 7, 8, 9, 10):
            if len(r) < period * 3:
                continue
            # Đếm khớp vị trí modulo
            hits = 0
            total = 0
            target_pos = (len(r) % period)
            for i in range(len(r) - period):
                if i % period == target_pos:
                    total += 1
                    if r[i] == r[-period:][0]:
                        hits += 1
            # Thay vào dự đoán: kết quả tại vị trí modulo tương ứng
            matching_pos = [r[i] for i in range(len(r)) if i % period == target_pos and i < len(r) - 1]
            if len(matching_pos) >= 3:
                c = Counter(matching_pos)
                top, cnt = c.most_common(1)[0]
                ratio = cnt / len(matching_pos)
                if ratio >= 0.65:
                    conf = min(55 + int(ratio * 25), 75)
                    return top, conf, 1.05
        return None, 0, 0

    @classmethod
    def _volatility(cls, valid):
        """Đo biến động - khi quá ổn định thì bẻ."""
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        # Đếm số lần đổi trong 20 phiên
        flips = sum(1 for i in range(1, len(r)) if r[i] != r[i - 1])
        flip_ratio = flips / (len(r) - 1)
        # Nếu flip_ratio rất cao hoặc rất thấp → tín hiệu mạnh
        if flip_ratio >= 0.85:
            # Rất nhiều đảo → đảo tiếp
            return ('Xỉu' if r[-1] == 'Tài' else 'Tài'), 64, 1.15
        if flip_ratio <= 0.15:
            # Rất ổn định → bẻ sau khi đủ dài
            cur_len, cur_val = cls._tail_run(r)
            if cur_len >= 4:
                return ('Xỉu' if cur_val == 'Tài' else 'Tài'), 62, 1.10
        return None, 0, 0

    @classmethod
    def _cusum(cls, valid):
        """CUSUM - Cumulative Sum để phát hiện drift."""
        if len(valid) < 15:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        # Map Tài = +1, Xỉu = -1
        vals = [1 if x == 'Tài' else -1 for x in r]
        mean = sum(vals) / len(vals)
        s_pos, s_neg = 0.0, 0.0
        threshold = 1.5
        # CUSUM
        for v in vals:
            s_pos = max(0, s_pos + (v - mean))
            s_neg = max(0, s_neg - (v - mean))
        # Nếu s_pos > threshold → trend tăng → dự đoán đảo (mean revert)
        if s_pos > threshold and mean > 0:
            return 'Xỉu', 62, 1.05
        if s_neg > threshold and mean < 0:
            return 'Tài', 62, 1.05
        return None, 0, 0

    @classmethod
    def _kelly_optimal(cls, valid):
        """Kelly Criterion để đánh giá cầu hiện tại."""
        if len(valid) < 15:
            return None, 0, 0
        recent = [v['result'] for v in valid[-15:]]
        tai = sum(1 for x in recent if x == 'Tài')
        p = tai / len(recent)
        # Kelly: f = p - (1-p)/b với b=1 (fair)
        # f = 2p - 1
        kelly = 2 * p - 1
        if kelly >= 0.30:
            return 'Tài', min(55 + int(kelly * 40), 80), 1.10
        if kelly <= -0.30:
            return 'Xỉu', min(55 + int(-kelly * 40), 80), 1.10
        return None, 0, 0

    @classmethod
    def _multi_window(cls, valid):
        """Đa cửa sổ - vote giữa 5/10/15/20."""
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
            # Đa số đồng thuận
            c = Counter(votes)
            top, cnt = c.most_common(1)[0]
            if cnt >= 3:
                conf = min(55 + cnt * 5, 75)
                return top, conf, 1.15
        return None, 0, 0

    @classmethod
    def _rsi_signal(cls, valid, period=14):
        """RSI cho cầu (overbought/oversold)."""
        if len(valid) < period + 5:
            return None, 0, 0
        r = [v['result'] for v in valid]
        # Tính change
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
        # RSI > 70: overbought → đảo
        if rsi >= 75:
            return 'Xỉu', min(55 + int((rsi - 70)), 78), 1.10
        if rsi <= 25:
            return 'Tài', min(55 + int((30 - rsi)), 78), 1.10
        return None, 0, 0

    @classmethod
    def _fibonacci_break(cls, valid):
        """Fibonacci - streak dài dựa trên dãy Fibonacci."""
        if len(valid) < 15:
            return None, 0, 0
        r = [v['result'] for v in valid]
        cur_len, cur_val = cls._tail_run(r)
        # Fibonacci levels: 3, 5, 8, 13
        fibs = [3, 5, 8, 13]
        # Nếu streak đạt gần Fibonacci → bẻ
        for fib in fibs:
            if cur_len == fib or cur_len == fib + 1:
                opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
                conf = min(58 + fib, 75)
                return opp, conf, 1.10
        return None, 0, 0

    @classmethod
    def _zscore_extreme(cls, valid):
        """Z-Score - phát hiện cực trị."""
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        vals = [1 if x == 'Tài' else 0 for x in r]
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        std = variance ** 0.5
        if std < 0.01:
            return None, 0, 0
        # Z-score của phiên cuối
        z = (vals[-1] - mean) / std
        # Z-score > 1.5: lệch cao → có thể đảo
        if z >= 1.5:
            return 'Xỉu', 62, 0.95
        if z <= -1.5:
            return 'Tài', 62, 0.95
        return None, 0, 0

    # ==================== N-GRAM ====================
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
        base_conf = 55 + min(n * 3, 15) + int((ratio - 0.6) * 40)
        conf = min(base_conf, 85)
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

    # ==================== STATISTICAL ====================
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

    # ==================== META ====================
    @classmethod
    def _signal_consensus(cls, valid):
        if len(valid) < 10:
            return None, 0, 0
        key_signals = [
            cls._markov_order2(valid),
            cls._streak_break(valid),
            cls._trend(valid),
            cls._invert_cau(valid),
            cls._alternation(valid),
            cls._momentum(valid),
        ]
        votes = {'Tài': 0, 'Xỉu': 0}
        count = 0
        for p, c, w in key_signals:
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
        key_signals = [
            cls._markov_order2(valid),
            cls._streak_break(valid),
            cls._trend(valid),
            cls._invert_cau(valid),
            cls._alternation(valid),
        ]
        votes = {'Tài': 0, 'Xỉu': 0}
        for p, c, w in key_signals:
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

    # ==================== HU SPECIFIC ====================
    @classmethod
    def _hu_dice_pattern(cls, valid):
        if len(valid) < 10:
            return None, 0, 0
        points = [v['total'] for v in valid[-30:] if v.get('total')]
        if len(points) < 10:
            return None, 0, 0
        recent_10 = points[-10:]
        avg_10 = sum(recent_10) / 10
        avg_30 = sum(points) / len(points)
        if avg_10 > 12.5 and avg_10 - avg_30 >= 1.0:
            if avg_10 >= 13.5:
                return 'Xỉu', 65, 1.20
            return 'Tài', 60, 1.05
        if avg_10 < 9.5 and avg_30 - avg_10 >= 1.0:
            if avg_10 <= 8.5:
                return 'Tài', 65, 1.20
            return 'Xỉu', 60, 1.05
        if len(points) >= 6:
            last6 = points[-6:]
            last3 = points[-3:]
            if len(valid) >= 3:
                last3_res = [v['result'] for v in valid[-3:]]
                if all(x == 'Tài' for x in last3_res):
                    if sum(last3) / 3 > sum(last6) / 6 + 1.5:
                        return 'Xỉu', 62, 1.10
                if all(x == 'Xỉu' for x in last3_res):
                    if sum(last3) / 3 < sum(last6) / 6 - 1.5:
                        return 'Tài', 62, 1.10
        return None, 0, 0

    @classmethod
    def _hu_streak_predict(cls, valid):
        if len(valid) < 12:
            return None, 0, 0
        r = [v['result'] for v in valid]
        cur_len, cur_val = cls._tail_run(r)
        if cur_len < 2 or cur_len > 6:
            return None, 0, 0
        runs = _run_lengths(r)
        breaks, totals = 0, 0
        pos = 0
        for rlen in runs[:-1]:
            if rlen == cur_len:
                totals += 1
                if pos + rlen < len(r):
                    breaks += 1
            pos += rlen
        if totals < 2:
            return None, 0, 0
        p_break = breaks / totals
        if p_break >= 0.60:
            opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
            conf = min(58 + int(p_break * 25), 76)
            return opp, conf, 1.15
        if p_break <= 0.40:
            conf = min(58 + int((1 - p_break) * 25), 76)
            return cur_val, conf, 1.15
        return None, 0, 0

    @classmethod
    def _hu_momentum_boost(cls, valid):
        if len(valid) < 8:
            return None, 0, 0
        last5 = valid[-5:]
        if any(not v.get('total') for v in last5):
            return None, 0, 0
        results_5 = [v['result'] for v in last5]
        points_5 = [v['total'] for v in last5]
        t_count = sum(1 for x in results_5 if x == 'Tài')
        point_slope = points_5[-1] - points_5[0]
        if t_count >= 4 and point_slope <= -3:
            return 'Xỉu', 64, 1.10
        if t_count <= 1 and point_slope >= 3:
            return 'Tài', 64, 1.10
        if t_count == 5:
            return 'Tài', 60, 0.95
        if t_count == 0:
            return 'Xỉu', 60, 0.95
        return None, 0, 0

    # ==================== CROSS GAME ====================
    @classmethod
    def _cross_game_signal(cls, valid_tx, valid_hu):
        if not valid_hu or len(valid_hu) < 8:
            return None, 0, 0
        r_tx = [v['result'] for v in valid_tx] if valid_tx else []
        r_hu = [v['result'] for v in valid_hu]
        cyc_tx = cls._detect_cycle(r_tx, max_period=5, min_repeats=2) if len(r_tx) >= 10 else None
        cyc_hu = cls._detect_cycle(r_hu, max_period=5, min_repeats=2) if len(r_hu) >= 10 else None
        if cyc_tx and cyc_hu:
            if cyc_tx['next'] == cyc_hu['next']:
                return cyc_hu['next'], 72, 1.35
            e_tx = _entropy(r_tx[-20:])
            e_hu = _entropy(r_hu[-20:])
            if e_hu < e_tx - 0.15:
                return cyc_hu['next'], 62, 1.10
            elif e_tx < e_hu - 0.15:
                return cyc_tx['next'], 62, 1.10
        if len(r_hu) >= 10:
            hu_last5 = r_hu[-5:]
            t5 = sum(1 for x in hu_last5 if x == 'Tài') / 5
            hu_tail_len, hu_tail_val = cls._tail_run(r_hu)
            if t5 >= 0.8 and hu_tail_len <= 3:
                return 'Tài', 60, 1.05
            if t5 <= 0.2 and hu_tail_len <= 3:
                return 'Xỉu', 60, 1.05
            if hu_tail_len >= 5:
                opp = 'Xỉu' if hu_tail_val == 'Tài' else 'Tài'
                return opp, 58, 0.95
        return None, 0, 0

    # ==================== ORIGINAL ====================
    @staticmethod
    def _markov_order3(valid):
        if len(valid) < 25:
            return None, 0, 0
        trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
        for i in range(len(valid) - 3):
            key = (valid[i]['result'], valid[i + 1]['result'], valid[i + 2]['result'])
            trans[key][valid[i + 3]['result']] += 1
        key = (valid[-3]['result'], valid[-2]['result'], valid[-1]['result'])
        counts = trans[key]
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
            key = (data[i]['result'], data[i + 1]['result'])
            trans[key][data[i + 2]['result']] += 1
        key = (data[-2]['result'], data[-1]['result'])
        counts = trans[key]
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
            for fname, fn in cls._strategy_list(include_cross=False, include_hu_specific=False):
                try:
                    p, c, w = fn(history, None)
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
        recent = sorted(
            [(p, e) for p, e in log.items() if e.get('actual') is not None],
            reverse=True
        )[:30]
        if not recent:
            return raw_conf
        acc = sum(1 for _, e in recent if e.get('correct')) / len(recent)
        if acc < 0.45:
            return max(50, raw_conf - 10)
        if acc < 0.50:
            return max(50, raw_conf - 5)
        if acc > 0.65:
            return min(88, raw_conf + 3)
        return raw_conf

    # ==================== STRATEGY LIST (V6.0) ====================
    @classmethod
    def _strategy_list(cls, include_cross=False, include_hu_specific=False):
        base = [
            # Core
            ('markov3',      lambda v, hu: cls._markov_order3(v)),
            ('markov2',      lambda v, hu: cls._markov_order2(v)),
            ('markov1',      lambda v, hu: cls._markov_order1(v)),
            ('streak',       lambda v, hu: cls._streak_break(v)),
            ('pattern',      lambda v, hu: cls._pattern_match(v)),
            ('weighted',     lambda v, hu: cls._weighted_freq(v)),
            ('dice',         lambda v, hu: cls._dice_bias(v)),
            ('alternation',  lambda v, hu: cls._alternation(v)),
            ('momentum',     lambda v, hu: cls._momentum(v)),
            ('recency',      lambda v, hu: cls._recency_streak(v)),
            ('invert',       lambda v, hu: cls._invert_cau(v)),
            ('trend',        lambda v, hu: cls._trend(v)),
            ('bias_run',     lambda v, hu: cls._bias_run(v)),
            ('follow',       lambda v, hu: cls._follow_trend(v)),
            ('exhaust',      lambda v, hu: cls._exhaustion(v)),
            ('dominance',    lambda v, hu: cls._dominance_flip(v)),
            # Cycle
            ('cycle_1_1',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [1, 1])),
            ('cycle_2_2',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [2, 2])),
            ('cycle_3_3',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [3, 3])),
            ('cycle_1_2',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [1, 2])),
            ('cycle_2_1',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [2, 1])),
            ('cycle_1_3',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [1, 3])),
            ('cycle_3_1',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [3, 1])),
            ('cycle_2_3',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [2, 3])),
            ('cycle_3_2',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [3, 2])),
            ('cycle_123',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [1, 2, 3])),
            ('cycle_321',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [3, 2, 1])),
            ('cycle_346',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [3, 4, 6])),
            ('cycle_112',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [1, 1, 2])),
            ('cycle_212',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [2, 1, 2])),
            ('cycle_122',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [1, 2, 2])),
            ('cycle_221',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [2, 2, 1])),
            ('cycle_1234',   lambda v, hu: cls._cycle_signal([x['result'] for x in v], [1, 2, 3, 4])),
            ('cycle_2341',   lambda v, hu: cls._cycle_signal([x['result'] for x in v], [2, 3, 4, 1])),
            ('cycle_3456',   lambda v, hu: cls._cycle_signal([x['result'] for x in v], [3, 4, 5, 6])),
            ('cycle_4_4',    lambda v, hu: cls._cycle_signal([x['result'] for x in v], [4, 4])),
            ('auto_cycle',   lambda v, hu: cls._auto_cycle_signal([x['result'] for x in v])),
            ('pattern_sim',  lambda v, hu: cls._pattern_similarity([x['result'] for x in v])),
            ('regime',       lambda v, hu: cls._regime_signal(v)),
            ('flip_break',   lambda v, hu: cls._flip_break(v)),
            ('run_break',    lambda v, hu: cls._run_break(v)),
            # N-gram
            ('ngram_2',      lambda v, hu: cls._ngram_signal([x['result'] for x in v], 2)),
            ('ngram_3',      lambda v, hu: cls._ngram_signal([x['result'] for x in v], 3)),
            ('ngram_4',      lambda v, hu: cls._ngram_signal([x['result'] for x in v], 4)),
            ('ngram_5',      lambda v, hu: cls._ngram_signal([x['result'] for x in v], 5)),
            # Mirror
            ('mirror_pattern',  lambda v, hu: cls._mirror_pattern([x['result'] for x in v])),
            ('reverse_trend',   lambda v, hu: cls._reverse_trend(v)),
            ('palindrome_check', lambda v, hu: cls._palindrome_check([x['result'] for x in v])),
            # Statistical
            ('bayes_recent',      lambda v, hu: cls._bayes_recent(v)),
            ('chi_square',        lambda v, hu: cls._chi_square(v)),
            ('runs_prediction',   lambda v, hu: cls._runs_prediction(v)),
            ('transition_matrix', lambda v, hu: cls._transition_matrix(v)),
            ('double_break',      lambda v, hu: cls._cycle_signal([x['result'] for x in v], [2, 2])),
            # Meta
            ('signal_consensus',  lambda v, hu: cls._signal_consensus(v)),
            ('signal_dissent',    lambda v, hu: cls._signal_dissent(v)),
            ('entropy_adaptive',  lambda v, hu: cls._entropy_adaptive(v)),
            ('streak_maturity',   lambda v, hu: cls._streak_maturity(v)),
            # V6.0 NEW
            ('time_pattern',      lambda v, hu: cls._time_pattern(v)),
            ('volatility',        lambda v, hu: cls._volatility(v)),
            ('cusum',             lambda v, hu: cls._cusum(v)),
            ('kelly_optimal',     lambda v, hu: cls._kelly_optimal(v)),
            ('multi_window',      lambda v, hu: cls._multi_window(v)),
            ('rsi_signal',        lambda v, hu: cls._rsi_signal(v)),
            ('fibonacci_break',   lambda v, hu: cls._fibonacci_break(v)),
            ('zscore_extreme',    lambda v, hu: cls._zscore_extreme(v)),
        ]
        if include_hu_specific:
            base.extend([
                ('hu_dice_pattern',   lambda v, hu: cls._hu_dice_pattern(v)),
                ('hu_streak_predict', lambda v, hu: cls._hu_streak_predict(v)),
                ('hu_momentum_boost', lambda v, hu: cls._hu_momentum_boost(v)),
            ])
        if include_cross:
            base.append(('cross_game', lambda v, hu: cls._cross_game_signal(v, hu)))
        return base

    # ==================== MAIN PREDICT ====================
    @classmethod
    def predict(cls, valid, valid_hu=None, use_cross=False, log=None, is_hu=False):
        if log is None:
            log = PREDICTION_LOG
        if valid_hu is None:
            valid_hu = []
        if not use_cross:
            valid_hu = []

        if not valid:
            if use_cross and valid_hu and len(valid_hu) >= 3:
                pred_hu = cls.predict(valid_hu, [], use_cross=False,
                                      log=log, is_hu=is_hu)
                return {
                    'prediction': pred_hu['prediction'],
                    'confidence': max(50, pred_hu['confidence'] - 10),
                    'method': 'Fallback Hũ (cross)',
                    'signals': pred_hu.get('signals', []),
                    'top_signals': ['Fallback Hũ'],
                    'reason': 'Không có data → dùng Hũ',
                    'flipped': False,
                }
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
                reason = f'1 phiên {last}'
                conf = 52
            elif streak <= 3:
                method = f'Bẻ {last}×{streak}'
                reason = f'{streak} phiên {last}'
                conf = 52 + streak * 2
            else:
                method = f'Bẻ {last}×{streak}'
                reason = f'{streak} phiên {last}'
                conf = min(60 + (streak - 3) * 3, 70)
            if use_cross and valid_hu and len(valid_hu) >= 3:
                hu_streak, hu_last = cls._tail_run([v['result'] for v in valid_hu])
                if hu_last == last and hu_streak >= 2:
                    return {
                        'prediction': last, 'confidence': 62,
                        'method': f'Đồng thuận Hũ {last}',
                        'signals': [], 'top_signals': [f'Đồng thuận Hũ'],
                        'reason': f'2 bàn cùng {last}', 'flipped': False,
                    }
            return {
                'prediction': opp, 'confidence': conf,
                'method': method, 'signals': [],
                'top_signals': [method],
                'reason': reason, 'flipped': False,
            }

        cls._sync_track_from_history(valid)

        log_odds = 0.0
        signals = []
        total_weight = 0.0

        for name, fn in cls._strategy_list(
                include_cross=use_cross, include_hu_specific=is_hu):
            try:
                p, conf, weight = fn(valid, valid_hu)
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
        top_signals = [SIGNAL_NAMES.get(s['name'], s['name'])
                       for s in signals_sorted[:5]]

        result = {
            'prediction': pred, 'confidence': final_conf,
            'method': ' + '.join(top_signals[:3]) if top_signals else 'Tổng hợp',
            'signals': signals, 'top_signals': top_signals,
            'signals_strength': [
                {
                    'name': s['name'],
                    'display': SIGNAL_NAMES.get(s['name'], s['name']),
                    'prediction': s['prediction'],
                    'confidence': s['confidence'],
                    'weight': s['weight'],
                    'strength': round(s['weight'] * (s['confidence'] - 50), 1),
                }
                for s in signals_sorted[:8]
            ],
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
# DATA FETCHERS
# =====================================================================
def _fetch_endpoint(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=6, headers=headers)
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


def fetch_hu_sessions():
    return _fetch_endpoint(API_URL_HU)


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


def _sync_hu_history():
    raw_rows, success = fetch_hu_sessions()
    if not success and not HU_HISTORY_CACHE:
        return [], False
    for row in raw_rows:
        HU_HISTORY_CACHE[row['phien']] = row
    if HU_RESET_ID > 0:
        for k in [k for k in HU_HISTORY_CACHE if k < HU_RESET_ID]:
            del HU_HISTORY_CACHE[k]
    valid_hu = sorted(HU_HISTORY_CACHE.values(), key=lambda x: x['phien'])
    _update_hu_log(valid_hu)
    return valid_hu, True


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
        pred = MultiStrategyPredictor.predict(
            history_before, [], use_cross=False, log=PREDICTION_LOG, is_hu=False)
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


def _update_hu_log(valid_hu):
    if not valid_hu:
        return
    by_phien = {v['phien']: v for v in valid_hu}
    phien_list = sorted(by_phien.keys())
    for phien, entry in list(HU_PREDICTION_LOG.items()):
        if entry.get('actual') is not None:
            continue
        if phien in by_phien:
            actual = by_phien[phien]['result']
            entry['actual'] = actual
            entry['correct'] = (entry['prediction'] == actual)
    changed = False
    for i, phien in enumerate(phien_list):
        if phien in HU_PREDICTION_LOG or phien <= HU_RESET_ID:
            continue
        history_before = [by_phien[p] for p in phien_list[:i]]
        if len(history_before) < 3:
            continue
        pred = MultiStrategyPredictor.predict(
            history_before, [], use_cross=False, log=HU_PREDICTION_LOG, is_hu=True)
        actual = by_phien[phien]['result']
        HU_PREDICTION_LOG[phien] = {
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
    if len(HU_PREDICTION_LOG) > MAX_LOG_SIZE:
        keys = sorted(HU_PREDICTION_LOG.keys())[:len(HU_PREDICTION_LOG) - MAX_LOG_SIZE]
        for k in keys:
            del HU_PREDICTION_LOG[k]
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


def _log_hu_prediction(phien, pred_result):
    if phien in HU_PREDICTION_LOG:
        return
    HU_PREDICTION_LOG[phien] = {
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
# HTML - V6.0 (ĐỘNG + HIỆU ỨNG)
# =====================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH </title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
:root{--bg:#0f172a;--card:#1e293b;--card2:#111827;--text:#f8fafc;--muted:#94a3b8;--border:#334155;--tai:#38bdf8;--xiu:#f472b6;--ok:#22c55e;--fail:#ef4444;--warn:#fbbf24;--hu:#a855f7}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Plus Jakarta Sans',sans-serif}
body{background:linear-gradient(135deg,#0f172a,#1e1b4b,#0f172a);background-size:200% 200%;animation:bgShift 15s ease infinite;color:var(--text);min-height:100vh;padding-bottom:30px;font-size:13px}
@keyframes bgShift{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}

/* HEADER */
.header{background:rgba(30,41,59,.85);backdrop-filter:blur(16px);border-bottom:1px solid var(--border);padding:12px 16px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;box-shadow:0 4px 20px rgba(0,0,0,.3)}
.logo{font-size:16px;font-weight:800;color:var(--tai);display:flex;align-items:center;gap:8px}
.logo-text{background:linear-gradient(90deg,#38bdf8,#a855f7,#f472b6);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:shine 3s linear infinite}
@keyframes shine{to{background-position:200% center}}
.logo span{font-size:9px;background:linear-gradient(135deg,#a855f7,#ec4899);color:#fff;padding:3px 8px;border-radius:20px;font-weight:800;letter-spacing:.5px}
.actions{display:flex;gap:8px;align-items:center}
.clock{font-size:11px;color:var(--muted);font-weight:600;font-variant-numeric:tabular-nums}
.btn{background:var(--card);color:var(--text);border:1px solid var(--border);padding:7px 12px;border-radius:9px;font-weight:700;font-size:12px;cursor:pointer;transition:.2s}
.btn:hover{background:var(--card2);transform:translateY(-1px)}
.btn:active{transform:scale(.95)}
.btn-reset{background:rgba(248,113,113,.15);color:#f87171;border-color:rgba(248,113,113,.4)}
.btn-reset:hover{background:rgba(248,113,113,.25)}
.spin{animation:spin .5s}
@keyframes spin{to{transform:rotate(360deg)}}

.wrap{max-width:780px;margin:0 auto;padding:12px}

/* TABS */
.tabs{display:flex;gap:6px;margin-bottom:12px;background:var(--card);padding:5px;border-radius:11px;border:1px solid var(--border);position:relative}
.tab{flex:1;padding:10px;text-align:center;border-radius:8px;font-weight:700;font-size:12px;cursor:pointer;color:var(--muted);transition:.3s;position:relative;z-index:1}
.tab.active{background:linear-gradient(135deg,#0ea5e9,#3b82f6);color:#fff;box-shadow:0 4px 15px rgba(14,165,233,.4)}
.tab.hu.active{background:linear-gradient(135deg,#a855f7,#ec4899);box-shadow:0 4px 15px rgba(168,85,247,.4)}

.panel{display:none}.panel.active{display:block;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}

/* PREDICTION BOX */
.pred-box{background:linear-gradient(135deg,rgba(30,41,59,.9),rgba(17,24,39,.9));border:1px solid var(--border);border-radius:14px;padding:16px;margin-bottom:12px;position:relative;overflow:hidden}
.pred-box::before{content:'';position:absolute;inset:0;background:linear-gradient(45deg,transparent 30%,rgba(56,189,248,.05) 50%,transparent 70%);animation:sweep 3s linear infinite}
@keyframes sweep{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.pred-row{display:flex;align-items:center;justify-content:space-between;position:relative;z-index:1}
.pred-label{font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:700;letter-spacing:.5px;margin-bottom:6px}
.pred-value{font-size:32px;font-weight:800;line-height:1;letter-spacing:-.5px}
.pred-value.tai{color:var(--tai);text-shadow:0 0 20px rgba(56,189,248,.5)}
.pred-value.xiu{color:var(--xiu);text-shadow:0 0 20px rgba(244,114,182,.5)}
.pred-conf-badge{background:rgba(56,189,248,.15);border:1px solid rgba(56,189,248,.3);color:var(--tai);padding:6px 14px;border-radius:20px;font-weight:800;font-size:14px;font-variant-numeric:tabular-nums}

/* CONFIDENCE BAR */
.conf-bar{height:4px;background:rgba(255,255,255,.05);border-radius:2px;overflow:hidden;margin-top:12px}
.conf-bar-fill{height:100%;background:linear-gradient(90deg,#38bdf8,#a855f7);border-radius:2px;transition:width 1s ease;box-shadow:0 0 10px rgba(56,189,248,.5)}

/* TOP SIGNALS */
.signals-wrap{margin-top:12px;position:relative;z-index:1}
.signals-title{font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:700;margin-bottom:6px;letter-spacing:.5px}
.signals-list{display:flex;flex-wrap:wrap;gap:5px}
.signal-badge{padding:4px 9px;border-radius:12px;font-size:10px;font-weight:700;display:inline-flex;align-items:center;gap:4px;animation:pop .3s ease backwards}
@keyframes pop{from{opacity:0;transform:scale(.8)}to{opacity:1;transform:scale(1)}}
.signal-badge.t{background:rgba(56,189,248,.15);color:var(--tai);border:1px solid rgba(56,189,248,.3)}
.signal-badge.x{background:rgba(244,114,182,.15);color:var(--xiu);border:1px solid rgba(244,114,182,.3)}
.signal-badge .strength{opacity:.7;font-size:9px}

/* SCORE BAR */
.scorebar{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}
.sc{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 8px;text-align:center;transition:.2s;position:relative;overflow:hidden}
.sc:hover{transform:translateY(-2px);border-color:rgba(56,189,248,.3)}
.sc-l{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:700;margin-bottom:4px;letter-spacing:.5px}
.sc-v{font-size:22px;font-weight:800;font-variant-numeric:tabular-nums;transition:.3s}
.sc-v.ok{color:var(--ok);text-shadow:0 0 15px rgba(34,197,94,.3)}
.sc-v.fail{color:var(--fail);text-shadow:0 0 15px rgba(239,68,68,.3)}
.sc-v.warn{color:var(--warn);text-shadow:0 0 15px rgba(251,191,36,.3)}
.sc-v.pulse{animation:pulse .4s}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.15)}}

/* TABLE */
.tbl{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;max-height:60vh;overflow-y:auto}
table{width:100%;border-collapse:separate;border-spacing:0}
th{background:var(--card2);color:var(--muted);font-size:10px;font-weight:700;padding:11px 6px;text-align:center;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10;text-transform:uppercase}
td{padding:10px 6px;text-align:center;border-bottom:1px solid var(--border);font-size:12px;font-weight:600;transition:.15s}
tr:hover td{background:rgba(56,189,248,.03)}
.row-next{background:linear-gradient(90deg,rgba(56,189,248,.12),rgba(56,189,248,.02));border-left:3px solid var(--tai);animation:glow 2s ease infinite}
@keyframes glow{0%,100%{box-shadow:inset 0 0 20px rgba(56,189,248,.1)}50%{box-shadow:inset 0 0 20px rgba(56,189,248,.25)}}
.row-next.hu{background:linear-gradient(90deg,rgba(168,85,247,.12),rgba(168,85,247,.02));border-left:3px solid var(--hu)}
.badge{display:inline-block;padding:3px 10px;border-radius:14px;font-size:10px;font-weight:800;min-width:52px;text-align:center}
.b-tai{background:rgba(56,189,248,.18);color:var(--tai);border:1px solid rgba(56,189,248,.3)}
.b-xiu{background:rgba(244,114,182,.18);color:var(--xiu);border:1px solid rgba(244,114,182,.3)}
.b-none{background:rgba(255,255,255,.05);color:var(--muted)}
.b-ok{background:rgba(34,197,94,.2);color:var(--ok);border:1px solid rgba(34,197,94,.4);font-size:10px;padding:4px 10px;font-weight:800;animation:checkIn .3s}
@keyframes checkIn{from{transform:scale(0)}to{transform:scale(1)}}
.b-fail{background:rgba(239,68,68,.2);color:var(--fail);border:1px solid rgba(239,68,68,.4);font-size:10px;padding:4px 10px;font-weight:800}
.b-pending{background:rgba(251,191,36,.2);color:var(--warn);border:1px solid rgba(251,191,36,.4);font-size:10px;padding:4px 10px;font-weight:800;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.6}}
.dice{font-size:10px;color:var(--muted);display:block;margin-top:2px;font-variant-numeric:tabular-nums}
.pred-mini{font-size:11px;font-weight:800}
.pred-mini.tai{color:var(--tai)}.pred-mini.xiu{color:var(--xiu)}
.hu-pred{font-size:11px;font-weight:800;color:var(--hu)}
.loading{text-align:center;padding:30px;color:var(--tai);font-weight:600}

/* HU PRED BOX */
.hu-pred-box{background:linear-gradient(135deg,rgba(168,85,247,.1),rgba(236,72,153,.05));border:1px solid rgba(168,85,247,.3);border-radius:14px;padding:16px;margin-bottom:12px;position:relative;overflow:hidden}
.hu-pred-box::before{content:'';position:absolute;inset:0;background:linear-gradient(45deg,transparent 30%,rgba(168,85,247,.1) 50%,transparent 70%);animation:sweep 3s linear infinite}
.hu-value{font-size:32px;font-weight:800;line-height:1;color:var(--hu);text-shadow:0 0 20px rgba(168,85,247,.5);position:relative;z-index:1}

@media(max-width:520px){
    th,td{padding:8px 4px;font-size:11px}
    .clock{display:none}
    .badge{min-width:44px;font-size:9px}
    .sc-v{font-size:17px}
    .tab{font-size:11px;padding:8px}
    .pred-value,.hu-value{font-size:26px}
}
</style>
</head>
<body>
<div class="header">
    <div class="logo"><span class="logo-text">LE MINH</span> <span>V2</span></div>
    <div class="actions">
        <div class="clock" id="clock">--:--:--</div>
        <button class="btn" onclick="manualRefresh(this)">↻</button>
        <button class="btn btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>
<div class="wrap">
    <div class="tabs">
        <div class="tab active" data-tab="tx" onclick="switchTab('tx')">MD5</div>
        <div class="tab hu" data-tab="hu" onclick="switchTab('hu')">HŨ</div>
    </div>
    
    <div class="panel active" id="panel-tx">
        <!-- PREDICTION DISPLAY -->
        <div class="pred-box" id="tx-pred-box">
            <div class="pred-row">
                <div>
                    <div class="pred-label">Dự đoán phiên tiếp theo</div>
                    <div class="pred-value" id="tx-pred-value">Đang tải...</div>
                </div>
                <div class="pred-conf-badge" id="tx-conf-badge">--%</div>
            </div>
            <div class="conf-bar">
                <div class="conf-bar-fill" id="tx-conf-bar" style="width:0%"></div>
            </div>
            <div class="signals-wrap" id="tx-signals-wrap">
                <div class="signals-title">Top tín hiệu</div>
                <div class="signals-list" id="tx-signals-list">
                    <span class="signal-badge" style="opacity:.5">Đang tải...</span>
                </div>
            </div>
        </div>
        
        <!-- STATS -->
        <div class="scorebar">
            <div class="sc"><div class="sc-l">✓ Đúng</div><div class="sc-v ok" id="sc-correct">0</div></div>
            <div class="sc"><div class="sc-l">✗ Sai</div><div class="sc-v fail" id="sc-wrong">0</div></div>
            <div class="sc"><div class="sc-l">⏳ Chờ</div><div class="sc-v warn" id="sc-pending">0</div></div>
        </div>
        
        <div class="tbl">
            <table>
                <thead><tr><th>Phiên</th><th>Dự đoán</th><th>Kết quả</th><th>Đúng/Sai</th></tr></thead>
                <tbody id="tbody-tx"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody>
            </table>
        </div>
    </div>
    
    <div class="panel" id="panel-hu">
        <div class="hu-pred-box">
            <div class="pred-row">
                <div>
                    <div class="pred-label">Hũ dự đoán phiên tiếp theo</div>
                    <div class="hu-value" id="hu-pred-value">Đang tải...</div>
                </div>
                <div class="pred-conf-badge" id="hu-conf-badge" style="background:rgba(168,85,247,.15);border-color:rgba(168,85,247,.3);color:var(--hu)">--%</div>
            </div>
            <div class="conf-bar">
                <div class="conf-bar-fill" id="hu-conf-bar" style="width:0%;background:linear-gradient(90deg,#a855f7,#ec4899)"></div>
            </div>
            <div class="signals-wrap">
                <div class="signals-title">Top tín hiệu Hũ</div>
                <div class="signals-list" id="hu-signals-list">
                    <span class="signal-badge" style="opacity:.5">Đang tải...</span>
                </div>
            </div>
        </div>
        
        <div class="tbl">
            <table>
                <thead><tr><th>Phiên</th><th>Dự đoán</th><th>Kết quả</th><th>Điểm</th></tr></thead>
                <tbody id="tbody-hu"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody>
            </table>
        </div>
    </div>
</div>
<script>
let isResetting=false;
let lastTxPred=null, lastHuPred=null;

function switchTab(t){
    document.querySelectorAll('.tab').forEach(el=>el.classList.toggle('active',el.dataset.tab===t));
    document.querySelectorAll('.panel').forEach(el=>el.classList.remove('active'));
    document.getElementById('panel-'+t).classList.add('active');
}

function manualRefresh(btn){
    btn.classList.add('spin');
    setTimeout(()=>btn.classList.remove('spin'),500);
    fetchAll();
}

async function fetchAll(){
    if(isResetting)return;
    document.getElementById('clock').innerText=new Date().toLocaleTimeString('vi-VN');
    try{
        const r=await fetch('/api/history',{cache:'no-store'});
        const d=await r.json();
        renderScore(d.ai_stats||{});
        renderTxPred(d.prediction,d.rows||[]);
    }catch(e){console.error(e);}
    try{
        const r=await fetch('/api/hu_history',{cache:'no-store'});
        const d=await r.json();
        renderHuPred(d);
    }catch(e){console.error(e);}
}

function renderScore(ai){
    const cv=document.getElementById('sc-correct');
    const wv=document.getElementById('sc-wrong');
    const pv=document.getElementById('sc-pending');
    const newC=ai.correct||0, newW=ai.wrong||0, newP=ai.pending||0;
    if(parseInt(cv.innerText)!==newC && cv.innerText!=='0'){cv.classList.add('pulse');setTimeout(()=>cv.classList.remove('pulse'),400);}
    cv.innerText=newC;wv.innerText=newW;pv.innerText=newP;
}

function renderTxPred(pred, rows){
    const pv=document.getElementById('tx-pred-value');
    const cb=document.getElementById('tx-conf-badge');
    const bar=document.getElementById('tx-conf-bar');
    const sl=document.getElementById('tx-signals-list');
    
    if(!pred){
        pv.innerText='—';pv.className='pred-value';
        cb.innerText='--%';bar.style.width='0%';
        sl.innerHTML='<span class="signal-badge" style="opacity:.5">Không có tín hiệu</span>';
    } else {
        const p=pred.prediction, c=pred.confidence||0;
        pv.innerText=p;
        pv.className='pred-value '+(p==='Tài'?'tai':'xiu');
        cb.innerText=c+'%';
        bar.style.width=c+'%';
        
        // Render top signals
        const sigs=pred.signals_strength||[];
        if(sigs.length){
            sl.innerHTML=sigs.map((s,i)=>{
                const cls=s.prediction==='Tài'?'t':'x';
                return `<span class="signal-badge ${cls}" style="animation-delay:${i*0.05}s" title="${s.prediction} · ${s.confidence}% · weight ${s.weight}">${s.display}<span class="strength">${s.strength}</span></span>`;
            }).join('');
        } else {
            sl.innerHTML='<span class="signal-badge" style="opacity:.5">Không có tín hiệu</span>';
        }
    }
    renderTableTX(rows);
}

function renderTableTX(rows){
    const tb=document.getElementById('tbody-tx');
    if(!rows.length){tb.innerHTML='<tr><td colspan="4" class="loading">Chưa có dữ liệu.</td></tr>';return;}
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
        html+=`<tr ${trCls}><td>#${row.phien}${row.is_next?'<br><span style="font-size:9px;color:var(--tai)">NEXT</span>':''}</td><td>${predCell}</td><td>${resBadge}${dice}</td><td>${evalCell}</td></tr>`;
    });
    tb.innerHTML=html;
}

function renderHuPred(d){
    const pred=d.prediction||{};
    const pv=document.getElementById('hu-pred-value');
    const cb=document.getElementById('hu-conf-badge');
    const bar=document.getElementById('hu-conf-bar');
    const sl=document.getElementById('hu-signals-list');
    
    pv.innerText=pred.prediction||'—';
    cb.innerText=(pred.confidence||0)+'%';
    bar.style.width=(pred.confidence||0)+'%';
    
    const sigs=pred.signals_strength||[];
    if(sigs.length){
        sl.innerHTML=sigs.map((s,i)=>{
            const cls=s.prediction==='Tài'?'t':'x';
            return `<span class="signal-badge ${cls}" style="animation-delay:${i*0.05}s">${s.display}<span class="strength">${s.strength}</span></span>`;
        }).join('');
    } else {
        sl.innerHTML='<span class="signal-badge" style="opacity:.5">Đang tải...</span>';
    }
    renderTableHu(d.rows||[]);
}

function renderTableHu(rows){
    const tb=document.getElementById('tbody-hu');
    if(!rows.length){tb.innerHTML='<tr><td colspan="4" class="loading">Chưa có dữ liệu Hũ.</td></tr>';return;}
    let html='';
    rows.forEach(row=>{
        const trCls=row.is_next?'class="row-next hu"':'';
        let predCell='<span class="badge b-none">—</span>';
        if(row.ai_prediction){
            predCell=`<span class="hu-pred">${row.ai_prediction}</span><br><span style="font-size:9px;color:var(--muted)">${row.ai_confidence||0}%</span>`;
        }
        let resBadge='<span class="badge b-none">—</span>';
        if(row.result==='Tài')resBadge='<span class="badge b-tai">TÀI</span>';
        if(row.result==='Xỉu')resBadge='<span class="badge b-xiu">XỈU</span>';
        let dice='';
        if(row.dice&&row.dice!=='? + ? + ?')dice=`<span class="dice">${row.dice}</span>`;
        let point='';
        if(row.total!==null&&row.total!==undefined)point=`<span style="font-weight:800;color:var(--hu)">${row.total}</span>`;
        html+=`<tr ${trCls}><td>#${row.phien}${row.is_next?'<br><span style="font-size:9px;color:var(--hu)">NEXT</span>':''}</td><td>${predCell}</td><td>${resBadge}${dice}</td><td>${point}</td></tr>`;
    });
    tb.innerHTML=html;
}

async function confirmReset(){
    Swal.fire({title:'Reset?',text:'Xoá toàn bộ cache và log?',icon:'warning',background:'#1e293b',color:'#f8fafc',showCancelButton:true,confirmButtonColor:'#0ea5e9',cancelButtonColor:'#64748b',confirmButtonText:'Đồng ý',cancelButtonText:'Hủy'}).then(async r=>{
        if(!r.isConfirmed)return;
        isResetting=true;
        try{
            const res=await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
            const d=await res.json();
            isResetting=false;
            if(d.status==='success'){
                fetchAll();
                Swal.fire({title:'OK!',text:'Đã reset.',icon:'success',background:'#1e293b',color:'#f8fafc',confirmButtonColor:'#0ea5e9'});
            } else throw new Error(d.message||'Lỗi');
        }catch(e){
            isResetting=false;
            Swal.fire({title:'Lỗi!',text:e.message,icon:'error',background:'#1e293b',color:'#f8fafc'});
        }
    });
}

fetchAll();
setInterval(fetchAll,5000);
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
                            'ai_stats': _log_stats(), 'prediction': None})
        next_phien = valid[-1]['phien'] + 1
        pred = MultiStrategyPredictor.predict(
            valid, [], use_cross=False, log=PREDICTION_LOG, is_hu=False)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats()
        out = [{
            'phien': next_phien, 'is_next': True, 'result': 'Chờ...',
            'dice': '? + ? + ?', 'total': None,
            'ai_prediction': pred['prediction'],
            'ai_confidence': pred['confidence'],
            'ai_correct': None,
        }]
        for v in reversed(valid[-200:]):
            if v['phien'] <= RESET_ID:
                continue
            log = PREDICTION_LOG.get(v['phien'])
            out.append({
                'phien': v['phien'], 'is_next': False,
                'result': v['result'], 'dice': v['dice'], 'total': v['total'],
                'ai_prediction': log['prediction'] if log else None,
                'ai_confidence': log['confidence'] if log else None,
                'ai_correct': log['correct'] if log else None,
            })
        return jsonify({
            'rows': out, 'stats': stats, 'ai_stats': ai_stats,
            'prediction': {
                'prediction': pred['prediction'],
                'confidence': pred['confidence'],
                'method': pred['method'],
                'signals_strength': pred.get('signals_strength', []),
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/hu_history')
def hu_history():
    try:
        valid_hu, success = _sync_hu_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối Hũ API'}), 500
        if not valid_hu:
            return jsonify({'rows': [], 'prediction': None, 'next_phien': None})
        next_phien = valid_hu[-1]['phien'] + 1
        pred = MultiStrategyPredictor.predict(
            valid_hu, [], use_cross=False, log=HU_PREDICTION_LOG, is_hu=True)
        _log_hu_prediction(next_phien, pred)
        out = [{
            'phien': next_phien, 'is_next': True, 'result': 'Chờ...',
            'dice': '? + ? + ?', 'total': None,
            'ai_prediction': pred['prediction'],
            'ai_confidence': pred['confidence'],
        }]
        for v in reversed(valid_hu[-60:]):
            if v['phien'] <= HU_RESET_ID:
                continue
            log = HU_PREDICTION_LOG.get(v['phien'])
            out.append({
                'phien': v['phien'], 'is_next': False,
                'result': v['result'], 'dice': v['dice'], 'total': v['total'],
                'ai_prediction': log['prediction'] if log else None,
                'ai_confidence': log['confidence'] if log else None,
                'ai_correct': log['correct'] if log else None,
            })
        return jsonify({
            'rows': out, 'next_phien': next_phien,
            'prediction': {
                'prediction': pred['prediction'],
                'confidence': pred['confidence'],
                'method': pred['method'],
                'signals_strength': pred.get('signals_strength', []),
            },
            'stats': _honest_stats(valid_hu),
            'ai_stats': _log_stats(HU_PREDICTION_LOG),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lc79md5')
def lc79md5():
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối MD5 API'}), 500
        if not valid:
            return jsonify({'Id': 'LE MINH V6.0 MD5', 'Phien': None,
                            'Du_doan': None, 'message': 'Chưa có dữ liệu'})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(
            valid, [], use_cross=False, log=PREDICTION_LOG, is_hu=False)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats(PREDICTION_LOG)
        return jsonify({
            'Id': 'LE MINH V6.0 MD5',
            'Phien': str(next_phien),
            'Ket_qua_truoc': last['result'].lower(),
            'Xuc_xac_truoc': last['dice'],
            'Diem_truoc': last['total'],
            'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%",
            'Phuong_phap': pred['method'],
            'Tin_hieu_chinh': pred.get('top_signals', []),
            'Ly_do': pred['reason'],
            'Da_dao': pred.get('flipped', False),
            'So_tin_hieu': len(pred['signals']),
            'Top_manh': pred.get('signals_strength', [])[:5],
            'Tong_phien': stats['total'],
            'So_Tai': stats['tai'],
            'So_Xiu': stats['xiu'],
            'AI_dung': ai_stats['correct'],
            'AI_sai': ai_stats['wrong'],
            'AI_cho': ai_stats['pending'],
            'Ti_le_AI': round(
                ai_stats['correct'] / max(ai_stats['evaluated'], 1) * 100, 1),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lc79hu')
def lc79hu():
    try:
        valid_hu, success = _sync_hu_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối Hũ API'}), 500
        if not valid_hu:
            return jsonify({'Id': 'LE MINH V6.0 HU', 'Phien': None,
                            'Du_doan': None, 'message': 'Chưa có dữ liệu Hũ'})
        last_hu = valid_hu[-1]
        next_phien = last_hu['phien'] + 1
        pred = MultiStrategyPredictor.predict(
            valid_hu, [], use_cross=False, log=HU_PREDICTION_LOG, is_hu=True)
        _log_hu_prediction(next_phien, pred)
        stats = _honest_stats(valid_hu)
        ai_stats = _log_stats(HU_PREDICTION_LOG)
        return jsonify({
            'Id': 'LE MINH V6.0 HU',
            'Phien': str(next_phien),
            'Ket_qua_truoc': last_hu['result'].lower(),
            'Xuc_xac_truoc': last_hu['dice'],
            'Diem_truoc': last_hu['total'],
            'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%",
            'Phuong_phap': pred['method'],
            'Tin_hieu_chinh': pred.get('top_signals', []),
            'Ly_do': pred['reason'],
            'Da_dao': pred.get('flipped', False),
            'So_tin_hieu': len(pred['signals']),
            'Top_manh': pred.get('signals_strength', [])[:5],
            'Tong_phien': stats['total'],
            'So_Tai': stats['tai'],
            'So_Xiu': stats['xiu'],
            'AI_dung': ai_stats['correct'],
            'AI_sai': ai_stats['wrong'],
            'AI_cho': ai_stats['pending'],
            'Ti_le_AI': round(
                ai_stats['correct'] / max(ai_stats['evaluated'], 1) * 100, 1),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lc79')
def lc79():
    try:
        valid, success = _sync_history()
        valid_hu, _ = _sync_hu_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'Id': 'LE MINH V6.0', 'Phien': None, 'Du_doan': None})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(
            valid, valid_hu, use_cross=True, log=PREDICTION_LOG, is_hu=False)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats(PREDICTION_LOG)
        return jsonify({
            'Id': 'LE MINH V6.0 COMBINED',
            'Phien': str(next_phien),
            'Ket_qua_truoc': last['result'].lower(),
            'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%",
            'Phuong_phap': pred['method'],
            'Tin_hieu_chinh': pred.get('top_signals', []),
            'Ly_do': pred['reason'],
            'Da_dao': pred.get('flipped', False),
            'So_tin_hieu': len(pred['signals']),
            'Top_manh': pred.get('signals_strength', [])[:5],
            'Tong_phien': stats['total'],
            'So_Tai': stats['tai'],
            'So_Xiu': stats['xiu'],
            'AI_dung': ai_stats['correct'],
            'AI_sai': ai_stats['wrong'],
            'AI_cho': ai_stats['pending'],
            'Ti_le_AI': round(
                ai_stats['correct'] / max(ai_stats['evaluated'], 1) * 100, 1),
            'Hu_context': {
                'total': len(valid_hu),
                'last_result': valid_hu[-1]['result'] if valid_hu else None,
            },
        })
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
        pred = MultiStrategyPredictor.predict(
            valid, [], use_cross=False, log=PREDICTION_LOG, is_hu=False)
        _log_prediction(next_phien, pred)
        return jsonify({
            'version': 'V6.0',
            'last_phien': last['phien'],
            'next_phien': next_phien,
            'last_result': last['result'],
            'last_dice': last['dice'],
            'last_total': last['total'],
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'top_signals': pred.get('top_signals', []),
            'signals_strength': pred.get('signals_strength', []),
            'reason': pred['reason'],
            'signals': pred['signals'],
            'signals_count': len(pred['signals']),
            'flipped': pred.get('flipped', False),
            'stats': _honest_stats(valid),
            'ai_stats': _log_stats(),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/hu_predict')
def hu_predict():
    try:
        valid_hu, success = _sync_hu_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối Hũ API'}), 500
        if not valid_hu:
            return jsonify({'prediction': None})
        last_hu = valid_hu[-1]
        next_phien = last_hu['phien'] + 1
        pred = MultiStrategyPredictor.predict(
            valid_hu, [], use_cross=False, log=HU_PREDICTION_LOG, is_hu=True)
        _log_hu_prediction(next_phien, pred)
        return jsonify({
            'version': 'V6.0', 'game': 'Hũ',
            'last_phien': last_hu['phien'],
            'next_phien': next_phien,
            'last_result': last_hu['result'],
            'last_dice': last_hu['dice'],
            'last_total': last_hu['total'],
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'top_signals': pred.get('top_signals', []),
            'signals_strength': pred.get('signals_strength', []),
            'reason': pred['reason'],
            'signals': pred['signals'],
            'signals_count': len(pred['signals']),
            'flipped': pred.get('flipped', False),
            'stats': _honest_stats(valid_hu),
            'ai_stats': _log_stats(HU_PREDICTION_LOG),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def stats_only():
    try:
        valid, success = _sync_history()
        valid_hu, _ = _sync_hu_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        last = valid[-1] if valid else None
        last_hu = valid_hu[-1] if valid_hu else None
        return jsonify({
            'tx': {
                'stats': _honest_stats(valid),
                'last_result': last['result'] if last else None,
                'last_phien': last['phien'] if last else None,
            },
            'hu': {
                'stats': _honest_stats(valid_hu),
                'last_result': last_hu['result'] if last_hu else None,
                'last_phien': last_hu['phien'] if last_hu else None,
                'last_total': last_hu['total'] if last_hu else None,
            },
            'ai_stats_tx': _log_stats(PREDICTION_LOG),
            'ai_stats_hu': _log_stats(HU_PREDICTION_LOG),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/algo_info')
def algo_info():
    try:
        valid, success = _sync_history()
        valid_hu, _ = _sync_hu_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'}), 400
        pred = MultiStrategyPredictor.predict(
            valid, [], use_cross=False, log=PREDICTION_LOG, is_hu=False)
        results = [v['result'] for v in valid]
        cyc = MultiStrategyPredictor._detect_cycle(results, max_period=6, min_repeats=2)
        cyc_hu = None
        if valid_hu:
            cyc_hu = MultiStrategyPredictor._detect_cycle(
                [v['result'] for v in valid_hu], max_period=6, min_repeats=2)
        return jsonify({
            'version': 'V6.0',
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'top_signals': pred.get('top_signals', []),
            'signals_strength': pred.get('signals_strength', []),
            'all_signals': pred['signals'],
            'signals_count': len(pred['signals']),
            'flipped': pred.get('flipped', False),
            'reason': pred['reason'],
            'recent_runs': _run_lengths(results[-40:]),
            'entropy': round(_entropy(results[-20:]), 3),
            'detected_cycle': {
                'period': cyc['period'], 'pattern': cyc['pattern'], 'next': cyc['next'],
            } if cyc else None,
            'hu_detected_cycle': {
                'period': cyc_hu['period'], 'pattern': cyc_hu['pattern'], 'next': cyc_hu['next'],
            } if cyc_hu else None,
            'num_phien': len(valid),
            'num_phien_hu': len(valid_hu),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/prediction_log')
def prediction_log():
    try:
        _sync_history()
        _sync_hu_history()
        items = sorted(PREDICTION_LOG.items(), key=lambda x: x[0], reverse=True)[:100]
        hu_items = sorted(HU_PREDICTION_LOG.items(), key=lambda x: x[0], reverse=True)[:100]
        out = [{
            'phien': p, 'prediction': e['prediction'], 'confidence': e['confidence'],
            'method': e['method'], 'actual': e.get('actual'),
            'correct': e.get('correct'), 'retroactive': e.get('retroactive', False),
            'logged_at': e.get('logged_at'),
        } for p, e in items]
        hu_out = [{
            'phien': p, 'prediction': e['prediction'], 'confidence': e['confidence'],
            'method': e['method'], 'actual': e.get('actual'),
            'correct': e.get('correct'),
        } for p, e in hu_items]
        return jsonify({
            'tx_stats': _log_stats(PREDICTION_LOG),
            'hu_stats': _log_stats(HU_PREDICTION_LOG),
            'tx_predictions': out,
            'hu_predictions': hu_out,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HU_RESET_ID, HISTORY_CACHE, HU_HISTORY_CACHE
    global PREDICTION_LOG, HU_PREDICTION_LOG
    try:
        raw_rows, success = fetch_sessions()
        raw_hu, success_hu = fetch_hu_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
        if success_hu and raw_hu:
            valid_hu = sorted(raw_hu, key=lambda x: x['phien'])
            if valid_hu:
                HU_RESET_ID = valid_hu[-1]['phien']
                HU_HISTORY_CACHE = {valid_hu[-1]['phien']: valid_hu[-1]}
        PREDICTION_LOG = {}
        HU_PREDICTION_LOG = {}
        MultiStrategyPredictor._STRATEGY_TRACK = defaultdict(
            lambda: {'hit': 0, 'miss': 0, 'last_len': 0})
        _save_log()
        return jsonify({
            'status': 'success',
            'reset_tx_to': RESET_ID + 1 if RESET_ID else None,
            'reset_hu_to': HU_RESET_ID + 1 if HU_RESET_ID else None,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
