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

HISTORY_CACHE = {}
RESET_ID = 0
PREDICTION_LOG = {}
MAX_LOG_SIZE = 3000
LOG_FILE = "prediction_log.json"

SIGNAL_NAMES = {
    'markov2':      'Markov bậc 2',
    'markov3':      'Markov bậc 3',
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
    # NEW V3
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
}


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
# PREDICTOR V3 - FULL CẦU ENGINE
# =====================================================================
class MultiStrategyPredictor:
    _STRATEGY_TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0, 'last_len': 0})

    # ==================== HELPERS ====================
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

    # ==================== CYCLE DETECTOR (NEW V3) ====================
    @staticmethod
    def _runs_to_signature(runs, val_first):
        """Chuyển runs -> chuỗi đặc trưng (T/X, độ dài)."""
        sig = []
        val = val_first
        for n in runs:
            sig.append((val, n))
            val = 'Xỉu' if val == 'Tài' else 'Tài'
        return sig

    @staticmethod
    def _detect_cycle(r, max_period=6, min_repeats=2):
        """
        Phát hiện chu kỳ tự động trong dãy kết quả.
        Trả về (period_len, phase_in_cycle, cycle_data) hoặc None.
        cycle_data = list kết quả trong 1 chu kỳ.
        """
        if len(r) < 8:
            return None
        best = None
        for period in range(2, min(max_period * 2, len(r) // min_repeats) + 1):
            # Kiểm tra period cuối cùng có lặp lại min_repeats lần
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
                # Xác nhận thêm: phần lớn lịch sử phải tuân pattern
                hits = 0
                total = 0
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
    def _cycle_signal(cls, r, sizes_target=None, name=None):
        """
        Bắt 1 dạng chu kỳ cụ thể (vd [1,1], [1,2,3], [3,4,6]).
        sizes_target: list các run-length lặp lại
        """
        if sizes_target is None:
            return None, 0, 0
        period_len = sum(sizes_target)
        if len(r) < period_len * 2 + 2:
            return None, 0, 0

        # Xây 2 chu kỳ gần nhất từ runs
        runs = _run_lengths(r)
        if len(runs) < 2:
            return None, 0, 0

        # Kiểm tra N chu kỳ cuối có khớp pattern sizes_target không
        n_cycles = min(len(runs) // len(sizes_target), 4)
        if n_cycles < 2:
            return None, 0, 0

        matched = 0
        total_checks = 0
        # Lấy runs của các chu kỳ cuối
        for c in range(n_cycles):
            start = len(runs) - (c + 1) * len(sizes_target)
            end = start + len(sizes_target)
            if start < 0:
                break
            chunk = runs[start:end]
            # So sánh độ dài (bỏ qua run cuối vì có thể đang mở)
            if c == 0:
                # Chu kỳ đang chạy — chỉ so sánh phần đã đóng
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

        # Xác định vị trí hiện tại trong chu kỳ
        cycle_pos = len(runs) % len(sizes_target)
        # Tìm run hiện tại (run cuối)
        cur_run_len, cur_val = cls._tail_run(r)
        expected_size = sizes_target[(cycle_pos - 1) % len(sizes_target)]

        # Nếu run hiện tại chưa đủ size → theo cầu (giữ val)
        if cur_run_len < expected_size:
            conf = min(58 + int(score * 25) + (expected_size - cur_run_len) * 2, 82)
            weight = 1.4 + score * 0.4
            return cur_val, conf, min(weight, 1.9)
        # Nếu vừa đủ hoặc vượt → bẻ (đổi val)
        else:
            next_val = 'Xỉu' if cur_val == 'Tài' else 'Tài'
            conf = min(58 + int(score * 25) + (cur_run_len - expected_size) * 2, 82)
            weight = 1.4 + score * 0.4
            return next_val, conf, min(weight, 1.9)

    @classmethod
    def _auto_cycle_signal(cls, r):
        """Tự động phát hiện chu kỳ bất kỳ đang chạy."""
        if len(r) < 12:
            return None, 0, 0
        cyc = cls._detect_cycle(r, max_period=6, min_repeats=2)
        if not cyc:
            return None, 0, 0
        next_val = cyc['next']
        pattern = cyc['pattern']
        # Độ tin cậy dựa trên độ dài chu kỳ (ngắn → tin hơn)
        base = 60 if cyc['period'] <= 3 else 55
        conf = min(base + max(0, (6 - cyc['period'])) * 3, 78)
        weight = 1.3 + (6 - min(cyc['period'], 6)) * 0.08
        return next_val, conf, round(weight, 2)

    @classmethod
    def _pattern_similarity(cls, r):
        """So cửa sổ hiện tại với toàn lịch sử — tìm mẫu giống nhất."""
        if len(r) < 15:
            return None, 0, 0
        for wlen in (8, 7, 6, 5, 4):
            if len(r) < wlen + 6:
                continue
            cur = r[-wlen:]
            matches = []
            for i in range(len(r) - wlen):
                window = r[i:i + wlen]
                # Đếm số vị trí khớp
                sim = sum(1 for a, b in zip(cur, window) if a == b) / wlen
                if sim >= 0.85 and i + wlen < len(r):
                    matches.append((sim, r[i + wlen]))
            if len(matches) >= 3:
                # Vote có trọng số theo similarity
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
        """
        Bẻ cầu / Đảo cầu thông minh:
        - Nếu phát hiện 1 cầu đang chạy (1-1, 2-2, 1-2, ...), đảo lại xem có bẻ không.
        - Nếu streak cuối = 1 vừa đổi từ chuỗi dài → theo cầu.
        - Nếu streak cuối = 1 sau chuỗi ngắn → có thể đảo.
        """
        if len(valid) < 10:
            return None, 0, 0
        r = [v['result'] for v in valid]
        cyc = cls._detect_cycle(r, max_period=5, min_repeats=2)
        if not cyc:
            return None, 0, 0
        # Cầu đang chạy → đảo ngược để "bẻ"
        # Nhưng chỉ khi mẫu có độ bền vừa phải (không quá dài, không quá ngắn)
        if 2 <= cyc['period'] <= 4:
            # Kiểm tra flip: dãy thực tế có xu hướng đảo gần đây không
            recent = r[-8:]
            flips = sum(1 for i in range(1, len(recent))
                        if recent[i] != recent[i - 1])
            if flips >= 6:
                # Nhiều đảo → xác suất đảo tiếp cao
                next_val = 'Xỉu' if cyc['next'] == 'Tài' else 'Tài'
                return next_val, 65, 1.05
        return None, 0, 0

    @classmethod
    def _run_break(cls, valid):
        """Bẻ run rất dài (≥6) nhưng không quá 8."""
        if len(valid) < 8:
            return None, 0, 0
        r = [v['result'] for v in valid]
        cur_len, cur_val = cls._tail_run(r)
        if cur_len < 6 or cur_len > 10:
            return None, 0, 0
        # Đếm trong lịch sử: run dài ≥6 có hay bị bẻ ở lần kế?
        runs = _run_lengths(r)
        breaks, totals = 0, 0
        idx = 0
        for rlen in runs[:-1]:
            if rlen >= 6:
                totals += 1
                # Sau run này, kết quả có đổi không?
                if idx + rlen < len(r):
                    breaks += 1
            idx += rlen
        if totals == 0:
            p = 0.5
        else:
            p = breaks / totals
        if p >= 0.55:
            next_val = 'Xỉu' if cur_val == 'Tài' else 'Tài'
            conf = min(56 + int(p * 20) + (cur_len - 6) * 2, 78)
            return next_val, conf, 1.15
        return None, 0, 0

    @classmethod
    def _regime_signal(cls, valid):
        """Phát hiện chế độ thị trường hiện tại và chọn hướng."""
        if len(valid) < 20:
            return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        alt = sum(1 for i in range(1, len(r)) if r[i] != r[i - 1]) / (len(r) - 1)
        runs = _run_lengths(r)
        avg_run = sum(runs) / len(runs)
        p_tai = cls._seg_ratio(r, 20)

        # Regime STRICKY (runs dài): theo hướng majority
        if avg_run >= 2.2 and alt <= 0.45:
            # Hướng majority đang áp đảo
            if p_tai >= 0.55:
                return 'Tài', 60, 0.95
            if p_tai <= 0.45:
                return 'Xỉu', 60, 0.95
        # Regime ALTERNATING (rất nhiều đảo): dự đoán đảo tiếp
        if alt >= 0.70 and avg_run <= 1.6:
            return ('Xỉu' if r[-1] == 'Tài' else 'Tài'), 62, 1.10
        return None, 0, 0

    # ==================== EXISTING SIGNALS ====================
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
            conf = min(56 + int(alt_ratio * 30), 82)
            return nxt, conf, 1.30

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
            for fname, fn in cls._strategy_list():
                try:
                    p, c, w = fn(history)
                    if p is not None:
                        cls._update_track(fname, p, actual)
                except Exception:
                    pass
        cls._STRATEGY_TRACK['__len__'] = {'last_len': cur_len}

    # ==================== FAILURE STREAK ====================
    @classmethod
    def _check_failure_streak(cls):
        evaluated = [
            (p, e) for p, e in sorted(PREDICTION_LOG.items(), reverse=True)
            if e.get('actual') is not None
        ]
        if len(evaluated) < 2:
            return 0
        return sum(1 for _, e in evaluated[:2] if e.get('correct') is False)

    @classmethod
    def _was_flipped_last(cls):
        evaluated = [
            e for p, e in sorted(PREDICTION_LOG.items(), reverse=True)
            if e.get('actual') is not None
        ]
        return evaluated[0].get('flipped', False) if evaluated else False

    @staticmethod
    def _calibrate_confidence(raw_conf):
        evaluated = [e for e in PREDICTION_LOG.values() if e.get('actual') is not None]
        if len(evaluated) < 20:
            return raw_conf
        recent = sorted(
            [(p, e) for p, e in PREDICTION_LOG.items() if e.get('actual') is not None],
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

    # ==================== STRATEGY LIST ====================
    @classmethod
    def _strategy_list(cls):
        return [
            # Original
            ('markov3',      lambda v: cls._markov_order3(v)),
            ('markov2',      lambda v: cls._markov_order2(v)),
            ('markov1',      lambda v: cls._markov_order1(v)),
            ('streak',       lambda v: cls._streak_break(v)),
            ('pattern',      lambda v: cls._pattern_match(v)),
            ('weighted',     lambda v: cls._weighted_freq(v)),
            ('dice',         lambda v: cls._dice_bias(v)),
            ('alternation',  lambda v: cls._alternation(v)),
            ('momentum',     lambda v: cls._momentum(v)),
            ('recency',      lambda v: cls._recency_streak(v)),
            ('invert',       lambda v: cls._invert_cau(v)),
            ('trend',        lambda v: cls._trend(v)),
            ('bias_run',     lambda v: cls._bias_run(v)),
            ('follow',       lambda v: cls._follow_trend(v)),
            ('exhaust',      lambda v: cls._exhaustion(v)),
            ('dominance',    lambda v: cls._dominance_flip(v)),
            # NEW V3 - Cycle detectors
            ('cycle_1_1',    lambda v: cls._cycle_signal([x['result'] for x in v], [1, 1])),
            ('cycle_2_2',    lambda v: cls._cycle_signal([x['result'] for x in v], [2, 2])),
            ('cycle_3_3',    lambda v: cls._cycle_signal([x['result'] for x in v], [3, 3])),
            ('cycle_1_2',    lambda v: cls._cycle_signal([x['result'] for x in v], [1, 2])),
            ('cycle_2_1',    lambda v: cls._cycle_signal([x['result'] for x in v], [2, 1])),
            ('cycle_1_3',    lambda v: cls._cycle_signal([x['result'] for x in v], [1, 3])),
            ('cycle_3_1',    lambda v: cls._cycle_signal([x['result'] for x in v], [3, 1])),
            ('cycle_2_3',    lambda v: cls._cycle_signal([x['result'] for x in v], [2, 3])),
            ('cycle_3_2',    lambda v: cls._cycle_signal([x['result'] for x in v], [3, 2])),
            ('cycle_123',    lambda v: cls._cycle_signal([x['result'] for x in v], [1, 2, 3])),
            ('cycle_321',    lambda v: cls._cycle_signal([x['result'] for x in v], [3, 2, 1])),
            ('cycle_346',    lambda v: cls._cycle_signal([x['result'] for x in v], [3, 4, 6])),
            ('cycle_112',    lambda v: cls._cycle_signal([x['result'] for x in v], [1, 1, 2])),
            ('cycle_212',    lambda v: cls._cycle_signal([x['result'] for x in v], [2, 1, 2])),
            ('cycle_122',    lambda v: cls._cycle_signal([x['result'] for x in v], [1, 2, 2])),
            ('cycle_221',    lambda v: cls._cycle_signal([x['result'] for x in v], [2, 2, 1])),
            ('auto_cycle',   lambda v: cls._auto_cycle_signal([x['result'] for x in v])),
            ('pattern_sim',  lambda v: cls._pattern_similarity([x['result'] for x in v])),
            ('regime',       lambda v: cls._regime_signal(v)),
            ('flip_break',   lambda v: cls._flip_break(v)),
            ('run_break',    lambda v: cls._run_break(v)),
        ]

    # ==================== MAIN PREDICT ====================
    @classmethod
    def predict(cls, valid):
        seed = str(valid[-1]['phien']) if valid else "0"

        if not valid:
            return {'prediction': cls._deterministic_choice(['Tài', 'Xỉu'], seed),
                    'confidence': 50, 'method': 'Ngẫu nhiên', 'signals': [],
                    'top_signals': [], 'reason': 'Chưa có dữ liệu', 'flipped': False}

        if len(valid) < 5:
            last = valid[-1]['result']
            streak, _ = cls._tail_run([v['result'] for v in valid])
            opp = 'Xỉu' if last == 'Tài' else 'Tài'
            return {'prediction': opp, 'confidence': min(50 + streak * 5, 65),
                    'method': 'Bẻ chuỗi (ít DL)', 'signals': [],
                    'top_signals': ['Bẻ chuỗi (ít DL)'],
                    'reason': f'Ít DL — bẻ chuỗi {streak}', 'flipped': False}

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
            pick = cls._deterministic_choice(['Tài', 'Xỉu'], seed)
            return {'prediction': pick, 'confidence': 50, 'method': 'Ngẫu nhiên',
                    'signals': [], 'top_signals': ['Ngẫu nhiên'],
                    'reason': 'Không có tín hiệu', 'flipped': False}

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
                       for s in signals_sorted[:3]]

        result = {
            'prediction': pred,
            'confidence': final_conf,
            'method': ' + '.join(top_signals) if top_signals else 'Tổng hợp',
            'signals': signals,
            'top_signals': top_signals,
            'reason': (f"{len(signals)} tín hiệu · entropy={entropy:.2f} · "
                       f"đồng thuận={agreement:.0%}"),
            'flipped': False,
        }

        fail_streak = cls._check_failure_streak()
        if fail_streak >= 2 and not cls._was_flipped_last():
            result['prediction'] = 'Xỉu' if result['prediction'] == 'Tài' else 'Tài'
            result['confidence'] = max(55, min(result['confidence'], 72))
            result['method'] = '⚠ ĐẢO (' + result['method'] + ')'
            result['reason'] += f" · SAI {fail_streak} TAY → ĐẢO"
            result['flipped'] = True

        result['confidence'] = cls._calibrate_confidence(result['confidence'])
        return result


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
        if phien in PREDICTION_LOG or phien <= RESET_ID:
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
        'actual': None,
        'correct': None,
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


def _log_stats():
    evaluated = [e for e in PREDICTION_LOG.values() if e.get('actual') is not None]
    correct = sum(1 for e in evaluated if e.get('correct'))
    wrong = len(evaluated) - correct
    pending = sum(1 for e in PREDICTION_LOG.values() if e.get('actual') is None)
    return {'correct': correct, 'wrong': wrong, 'pending': pending,
            'evaluated': len(evaluated)}


_load_log()


# =====================================================================
# HTML (unchanged)
# =====================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH V3</title>
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
.sc-v{font-size:20px;font-weight:800}
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
@media(max-width:520px){th,td{padding:8px 4px;font-size:11px}.clock{display:none}.badge{min-width:44px;font-size:9px}.b-ok,.b-fail,.b-pending{font-size:9px;padding:3px 7px}.sc-v{font-size:17px}}
</style>
</head>
<body>
<div class="header">
    <div class="logo">LE MINH <span>V3</span></div>
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
        <div class="sc"><div class="sc-l">⏳ Chờ</div><div class="sc-v warn" id="sc-pending">0</div></div>
    </div>
    <div class="tbl">
        <table>
            <thead><tr><th>Phiên</th><th>Dự đoán</th><th>Kết quả</th><th>Đúng / Sai</th></tr></thead>
            <tbody id="tbody"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody>
        </table>
    </div>
</div>
<script>
let isResetting=false;
async function fetchData(){
    if(isResetting)return;
    try{
        const r=await fetch('/api/history',{cache:'no-store'});
        const data=await r.json();
        document.getElementById('clock').innerText=new Date().toLocaleTimeString('vi-VN');
        renderScore(data.ai_stats||{});
        renderTable(data.rows||[]);
    }catch(e){console.error(e);}
}
function renderScore(ai){
    document.getElementById('sc-correct').innerText=ai.correct||0;
    document.getElementById('sc-wrong').innerText=ai.wrong||0;
    document.getElementById('sc-pending').innerText=ai.pending||0;
}
function renderTable(rows){
    const tb=document.getElementById('tbody');
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
async function confirmReset(){
    Swal.fire({title:'Reset?',text:'Xoá toàn bộ cache và log dự đoán?',icon:'warning',background:'#1e293b',color:'#f8fafc',showCancelButton:true,confirmButtonColor:'#0ea5e9',cancelButtonColor:'#64748b',confirmButtonText:'Đồng ý',cancelButtonText:'Hủy'}).then(async r=>{
        if(!r.isConfirmed)return;
        isResetting=true;
        try{
            const res=await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
            const d=await res.json();
            isResetting=false;
            if(d.status==='success'){
                fetchData();
                Swal.fire({title:'OK!',text:'Đã reset.',icon:'success',background:'#1e293b',color:'#f8fafc',confirmButtonColor:'#0ea5e9'});
            } else throw new Error(d.message||'Lỗi');
        }catch(e){
            isResetting=false;
            Swal.fire({title:'Lỗi!',text:e.message,icon:'error',background:'#1e293b',color:'#f8fafc'});
        }
    });
}
fetchData();
setInterval(fetchData,5000);
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
            'version': 'V3',
            'last_phien': last['phien'],
            'next_phien': next_phien,
            'last_result': last['result'],
            'last_dice': last['dice'],
            'last_total': last['total'],
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'top_signals': pred.get('top_signals', []),
            'reason': pred['reason'],
            'signals': pred['signals'],
            'flipped': pred.get('flipped', False),
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
            return jsonify({'Id': 'LE MINH V3', 'Phien': None, 'Du_doan': None})

        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats()

        return jsonify({
            'Id': 'LE MINH V3',
            'Phien': str(next_phien),
            'Ket_qua_truoc': last['result'].lower(),
            'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%",
            'Phuong_phap': pred['method'],
            'Tin_hieu_chinh': pred.get('top_signals', []),
            'Ly_do': pred['reason'],
            'Da_dao': pred.get('flipped', False),
            'Tong_phien': stats['total'],
            'So_Tai': stats['tai'],
            'So_Xiu': stats['xiu'],
            'AI_dung': ai_stats['correct'],
            'AI_sai': ai_stats['wrong'],
            'AI_cho': ai_stats['pending'],
            'Ti_le_AI': round(ai_stats['correct'] / max(ai_stats['evaluated'], 1) * 100, 1),
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


@app.route('/api/algo_info')
def algo_info():
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'}), 400

        pred = MultiStrategyPredictor.predict(valid)
        results = [v['result'] for v in valid]
        cyc = MultiStrategyPredictor._detect_cycle(results, max_period=6, min_repeats=2)

        return jsonify({
            'version': 'V3',
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'top_signals': pred.get('top_signals', []),
            'all_signals': pred['signals'],
            'flipped': pred.get('flipped', False),
            'reason': pred['reason'],
            'recent_runs': _run_lengths(results[-40:]),
            'entropy': round(_entropy(results[-20:]), 3),
            'detected_cycle': {
                'period': cyc['period'],
                'pattern': cyc['pattern'],
                'next': cyc['next'],
            } if cyc else None,
            'num_phien': len(valid),
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
                    lambda: {'hit': 0, 'miss': 0, 'last_len': 0})
                _save_log()
                return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys())
            HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
            PREDICTION_LOG = {}
            MultiStrategyPredictor._STRATEGY_TRACK = defaultdict(
                lambda: {'hit': 0, 'miss': 0, 'last_len': 0})
            _save_log()
            return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        return jsonify({'status': 'error', 'message': 'Không có dữ liệu để reset'}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# =====================================================================
# TEST API
# =====================================================================
def _seq_to_valid(seq_str, start_phien=1000):
    tokens = seq_str.split()
    return [{
        'phien': start_phien + i,
        'result': 'Tài' if tok.upper() == 'T' else 'Xỉu',
        'dice': '0 + 0 + 0', 'total': 0,
    } for i, tok in enumerate(tokens)]


def _build_all_cau_tests():
    tests = []

    def add(name, history_str, actual_char, expect_char):
        if len(history_str.split()) < 4:
            return
        actual = 'Tài' if actual_char.upper() == 'T' else 'Xỉu'
        expect = 'Tài' if expect_char.upper() == 'T' else 'Xỉu'
        tests.append({'name': name, 'history': history_str,
                      'actual': actual, 'expect': expect})

    cycle_sets = [
        ('1-1', [1, 1]), ('2-2', [2, 2]), ('3-3', [3, 3]),
        ('4-4', [4, 4]), ('5-5', [5, 5]),
        ('1-2', [1, 2]), ('2-1', [2, 1]),
        ('1-3', [1, 3]), ('3-1', [3, 1]),
        ('2-3', [2, 3]), ('3-2', [3, 2]),
        ('1-2-3', [1, 2, 3]), ('3-2-1', [3, 2, 1]),
        ('3-4-6', [3, 4, 6]), ('6-4-3', [6, 4, 3]),
        ('1-1-2', [1, 1, 2]), ('2-1-2', [2, 1, 2]),
        ('1-2-2', [1, 2, 2]), ('2-2-1', [2, 2, 1]),
        ('1-1-1-1', [1, 1, 1, 1]),
    ]

    for cycle_name, sizes in cycle_sets:
        for n_phien in (10, 12, 15, 18, 21, 24, 27, 30):
            seq, phase = [], 0
            while len(seq) < n_phien:
                size = sizes[phase % len(sizes)]
                val = 'T' if phase % 2 == 0 else 'X'
                seq.extend([val] * size)
                phase += 1
            seq = seq[:n_phien]
            next_val = 'T' if phase % 2 == 0 else 'X'
            add(f'{cycle_name}_len{n_phien}', ' '.join(seq), next_val, next_val)

    for n in (5, 6, 7, 8, 9, 10, 12, 15, 18, 20):
        add(f'bet_tai_{n}', ' '.join(['T'] * n), 'X', 'X')
        add(f'bet_xiu_{n}', ' '.join(['X'] * n), 'T', 'T')

    add('trend_up', 'X X X X X T T T T T T T T T T', 'T', 'T')
    add('trend_down', 'T T T T T X X X X X X X X X X', 'X', 'X')
    add('break_5tai', 'T T T T T X', 'T', 'T')
    add('break_5xiu', 'X X X X X T', 'X', 'X')

    return tests


@app.route('/api/test_all_cau')
def test_all_cau():
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
            saved_log = dict(PREDICTION_LOG)
            PREDICTION_LOG.clear()
            pred = MultiStrategyPredictor.predict(valid)
            PREDICTION_LOG.clear()
            PREDICTION_LOG.update(saved_log)

            is_correct = (pred['prediction'] == t['expect'])
            total += 1
            if is_correct:
                correct += 1

            group = t['name'].rsplit('_len', 1)[0] if '_len' in t['name'] else t['name'].split('_')[0]
            by_group[group]['total'] += 1
            if is_correct:
                by_group[group]['correct'] += 1

            results.append({
                'name': t['name'], 'history_len': len(valid),
                'prediction': pred['prediction'],
                'confidence': pred['confidence'],
                'expect': t['expect'],
                'correct': is_correct,
                'method': pred['method'],
                'top_signals': pred.get('top_signals', []),
            })

        acc = round(correct / total * 100, 2) if total > 0 else 0
        group_stats = {
            k: {'correct': v['correct'], 'total': v['total'],
                'accuracy': round(v['correct'] / v['total'] * 100, 2) if v['total'] else 0}
            for k, v in sorted(by_group.items())
        }

        fmt = request.args.get('format', 'json').lower()
        if fmt == 'txt':
            lines = [f"=== TEST ALL CẦU LE MINH V3 ===",
                     f"Tổng: {total} | Đúng: {correct} ({acc}%)", ""]
            lines.append("--- THEO NHÓM ---")
            for k, v in group_stats.items():
                lines.append(f"  {k:<15} {v['correct']}/{v['total']} ({v['accuracy']}%)")
            lines.append("")
            lines.append("--- CHI TIẾT ---")
            for r in results:
                mark = '✓' if r['correct'] else '✗'
                sig = f" [{' + '.join(r['top_signals'][:2])}]" if r['top_signals'] else ''
                lines.append(
                    f"{mark} {r['name']:<22} pred={r['prediction']:<5}"
                    f"({r['confidence']}%) expect={r['expect']:<5}{sig}")
            return '\n'.join(lines), 200, {'Content-Type': 'text/plain; charset=utf-8'}

        return jsonify({
            'version': 'V3',
            'total': total,
            'correct': correct,
            'accuracy': acc,
            'group_stats': group_stats,
            'results': results,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/detect_cycle')
def detect_cycle():
    """Phát hiện chu kỳ cầu đang chạy từ dữ liệu thật."""
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'}), 400

        r = [v['result'] for v in valid]
        cyc = MultiStrategyPredictor._detect_cycle(r, max_period=8, min_repeats=2)
        runs = _run_lengths(r[-60:])

        return jsonify({
            'version': 'V3',
            'current_cycle': {
                'period': cyc['period'],
                'pattern': cyc['pattern'],
                'phase': cyc['phase'],
                'next_prediction': cyc['next'],
            } if cyc else None,
            'recent_runs': runs,
            'last_30_results': r[-30:],
            'entropy': round(_entropy(r[-20:]), 3),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
