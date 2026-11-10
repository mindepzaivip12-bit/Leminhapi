import os
import traceback
import time
import json
import hashlib
import math
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

SIGNAL_NAMES = {
    'markov': 'Markov', 'streak': 'Bẻ chuỗi', 'pattern': 'Khớp mẫu',
    'trend': 'Xu hướng', 'cycle': 'Chu kỳ', 'entropy': 'Entropy',
    'cau11': 'Cầu 1-1', 'cau22': 'Cầu 2-2', 'cau33': 'Cầu 3-3',
    'bệt_fake': 'Bệt giả', 'breakpoint': 'Điểm gãy', 'meta': 'Meta',
}


# ========== HELPERS ==========
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
    """Phát hiện regime hiện tại - mở rộng 6 loại"""
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

    if h > 0.97 and ones < 0.42 and longs < 0.20:
        return 'chaos', h
    if ones >= 0.55: return 'alternation', ones
    if twos >= 0.55: return 'cau22', twos
    if threes >= 0.45: return 'cau33', threes
    if longs >= 0.35: return 'streak', longs
    if tr >= 0.68 or tr <= 0.32: return 'trend_strong', abs(tr - 0.5) * 2
    return 'short_run', max(ones, twos, threes)


# ========== PREDICTOR V12 ==========
class MultiStrategyPredictor:
    # Tracking per-signal
    _TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0})
    # Tracking per-regime
    _REGIME_TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0})
    # Tracking per-confidence bucket
    _CONF_TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0})
    # Recent outcomes (last 15)
    _RECENT = deque(maxlen=15)
    # Recovery state
    _RECOVERY = {'active': False, 'fail': 0, 'mode': None}
    # Meta learning: accuracy per signal per regime
    _META = defaultdict(lambda: defaultdict(lambda: {'hit': 0, 'miss': 0}))

    # =========================================================
    # SIGNAL 1: MARKOV (n-gram backoff)
    # =========================================================
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
            # Laplace smoothing
            p = (c['Tài'] + 1) / (t + 2)
            if p >= 0.66 or p <= 0.34:
                pred = 'Tài' if p >= 0.5 else 'Xỉu'
                # Higher order = higher base confidence
                base = max(p, 1 - p)
                conf = min(int(base * 100) + order * 2, 86)
                w = 1.30 + order * 0.12
                if conf * w > best[1] * best[2]:
                    best = (pred, conf, w)
        return best

    # =========================================================
    # SIGNAL 2: STREAK / BREAK (cầu bệt + bẻ bệt thông minh)
    # =========================================================
    @staticmethod
    def _sig_streak(seq, regime):
        runs = _runs(seq)
        if not runs: return (None, 0, 0)
        cur_val, cur_len = runs[-1]
        opp = _opp(cur_val)

        # Fake streak: bệt ngắn trong xu hướng dài → không bẻ vội
        is_fake = False
        if cur_len <= 3 and len(runs) >= 4:
            prev_lens = [l for _, l in runs[-5:-1]]
            if prev_lens and sum(prev_lens) / len(prev_lens) >= 3.5:
                is_fake = True

        if regime == 'streak':
            if cur_len <= 4:
                return (cur_val, min(56 + cur_len * 3, 74), 1.20)
            if cur_len >= 7:
                return (opp, min(58 + (cur_len - 6) * 4, 82), 1.45)
            if cur_len >= 5:
                return (opp, min(56 + (cur_len - 4) * 3, 74), 1.30)

        if regime == 'alternation':
            return (opp, 64, 1.40)

        # Bệt giả → đánh tiếp hướng bệt
        if is_fake:
            return (cur_val, 62, 1.15)

        # Bệt dài không thuộc regime streak → cẩn thận bẻ
        if cur_len >= 6:
            return (opp, min(58 + (cur_len - 5) * 3, 78), 1.25)
        if cur_len >= 5:
            return (opp, 60, 1.10)
        return (None, 0, 0)

    # =========================================================
    # SIGNAL 3: PATTERN (fuzzy + exact)
    # =========================================================
    @staticmethod
    def _sig_pattern(seq):
        if len(seq) < 10: return (None, 0, 0)
        best = (None, 0, 0)
        for plen in (7, 6, 5, 4, 3):
            if len(seq) < plen + 5: continue
            pat = tuple(seq[-plen:])
            matches = []
            # Exact suffix match
            for i in range(len(seq) - plen - 1):
                if tuple(seq[i:i + plen]) == pat:
                    matches.append(seq[i + plen])
            # Fuzzy match (chỉ miss 1 vị trí)
            if len(matches) < 2 and plen >= 5:
                for i in range(len(seq) - plen - 1):
                    win = seq[i:i + plen]
                    diffs = sum(1 for a, b in zip(win, pat) if a != b)
                    if diffs == 1:
                        matches.append(seq[i + plen])
            if len(matches) < 3: continue
            c = Counter(matches)
            top, cnt = c.most_common(1)[0]
            ratio = cnt / len(matches)
            if ratio >= 0.68:
                conf = min(54 + int(ratio * 28) + plen * 2, 88)
                w = 1.20 + plen * 0.10
                if conf * w > best[1] * best[2]:
                    best = (top, conf, w)
        return best

    # =========================================================
    # SIGNAL 4: TREND (đa khung)
    # =========================================================
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
            avg = sum(v[1] if top == 'Tài' else 1 - v[1]
                      for v in votes if v[0] == top) / cnt
            conf = min(int(avg * 100) + cnt * 2, 84)
            return (top, conf, 1.30)
        return (None, 0, 0)

    # =========================================================
    # SIGNAL 5: CYCLE (chu kỳ + cầu đặc biệt VN)
    # =========================================================
    @staticmethod
    def _sig_cycle(seq):
        if len(seq) < 14: return (None, 0, 0)
        best = None
        for period in range(2, 10):
            if len(seq) < period * 3: break
            pat = seq[-period:]
            # Kiểm tra 3 chu kỳ gần nhất khớp
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
        conf = min(58 + int(best[0] * 26), 84)
        return (nxt, conf, 1.35)

    # =========================================================
    # SIGNAL 6: CẦU 1-1 (alternation)
    # =========================================================
    @staticmethod
    def _sig_cau11(seq):
        if len(seq) < 10: return (None, 0, 0)
        seg = seq[-10:]
        # Đếm số lần đổi liên tiếp
        changes = sum(1 for i in range(1, len(seg)) if seg[i] != seg[i - 1])
        ratio = changes / (len(seg) - 1)
        if ratio >= 0.80:
            conf = min(58 + int(ratio * 30), 82)
            return (_opp(seq[-1]), conf, 1.30)
        return (None, 0, 0)

    # =========================================================
    # SIGNAL 7: CẦU 2-2 / 3-3
    # =========================================================
    @staticmethod
    def _sig_cau22(seq):
        if len(seq) < 12: return (None, 0, 0)
        runs = _runs(seq[-12:])
        if len(runs) < 4: return (None, 0, 0)
        lens = [l for _, l in runs]
        twos = sum(1 for l in lens if l == 2) / len(lens)
        if twos >= 0.60:
            # Chu kỳ 2-2: đảo sau khi đủ 2
            cur_val, cur_len = runs[-1]
            if cur_len >= 2:
                return (_opp(cur_val), 64, 1.30)
            return (cur_val, 60, 1.10)
        return (None, 0, 0)

    @staticmethod
    def _sig_cau33(seq):
        if len(seq) < 15: return (None, 0, 0)
        runs = _runs(seq[-15:])
        if len(runs) < 4: return (None, 0, 0)
        lens = [l for _, l in runs]
        threes = sum(1 for l in lens if l == 3) / len(lens)
        if threes >= 0.50:
            cur_val, cur_len = runs[-1]
            if cur_len >= 3:
                return (_opp(cur_val), 64, 1.30)
            return (cur_val, 60, 1.10)
        return (None, 0, 0)

    # =========================================================
    # SIGNAL 8: ENTROPY (chaos detection)
    # =========================================================
    @staticmethod
    def _sig_entropy(seq):
        if len(seq) < 12: return (None, 0, 0)
        seg = seq[-22:]
        h = _entropy(seg)
        p = _tai_ratio(seg, len(seg))

        # Low entropy → trend rõ
        if h < 0.72:
            if p >= 0.64: return ('Tài', 66, 1.20)
            if p <= 0.36: return ('Xỉu', 66, 1.20)
        # High entropy → chaos, đánh ngược phiên cuối (mean reversion)
        if h > 0.97:
            return (_opp(seq[-1]), 60, 1.05)
        return (None, 0, 0)

    # =========================================================
    # SIGNAL 9: BREAKPOINT (điểm gãy cầu)
    # =========================================================
    @staticmethod
    def _sig_breakpoint(seq):
        if len(seq) < 20: return (None, 0, 0)
        runs = _runs(seq[-20:])
        if len(runs) < 3: return (None, 0, 0)
        cur_val, cur_len = runs[-1]
        # Điểm gãy: bệt đạt ngưỡng thống kê
        # Trung bình độ dài run trước đó
        prev_lens = [l for _, l in runs[:-1]]
        if not prev_lens: return (None, 0, 0)
        avg_len = sum(prev_lens) / len(prev_lens)
        # Nếu run hiện tại dài gấp 2.2x trung bình → khả năng gãy cao
        if cur_len >= max(5, avg_len * 2.2):
            conf = min(60 + int((cur_len / max(avg_len, 1)) * 6), 82)
            return (_opp(cur_val), conf, 1.40)
        return (None, 0, 0)

    # =========================================================
    # CALIBRATION (dựa trên confidence bucket)
    # =========================================================
    @classmethod
    def _calibrate(cls, conf, log):
        evaluated = [(p, e) for p, e in log.items() if e.get('actual') is not None]
        if len(evaluated) < 20: return conf
        # Global recent accuracy
        evaluated.sort(reverse=True)
        recent = evaluated[:50]
        acc = sum(1 for _, e in recent if e.get('correct')) / len(recent)

        # Confidence bucket accuracy
        bucket = min(conf // 10 * 10, 80)
        cls._CONF_TRACK[bucket]['hit'] += 0
        # Apply global calibration
        if acc < 0.40: return max(50, conf - 14)
        if acc < 0.46: return max(50, conf - 8)
        if acc < 0.52: return max(50, conf - 3)
        if acc > 0.70: return min(86, conf + 6)
        if acc > 0.62: return min(86, conf + 3)
        return conf

    # =========================================================
    # RECOVERY (thông minh hơn V11)
    # =========================================================
    @classmethod
    def _update_recovery(cls, log):
        evaluated = [(p, e) for p, e in sorted(log.items(), reverse=True)
                     if e.get('actual') is not None][:8]
        cls._RECENT.clear()
        for _, e in reversed(evaluated):
            cls._RECENT.append(bool(e.get('correct')))

        # Đếm fail streak từ mới nhất
        fail = 0
        for _, e in evaluated:
            if e.get('correct') is False: fail += 1
            else: break
        cls._RECOVERY['fail'] = fail

        # Recovery levels
        if fail >= 4:
            cls._RECOVERY['active'] = True
            cls._RECOVERY['mode'] = 'hard_flip'
        elif fail == 3:
            cls._RECOVERY['active'] = True
            cls._RECOVERY['mode'] = 'soft_flip'
        elif fail == 2:
            # Chỉ flip nếu agreement thấp
            cls._RECOVERY['active'] = True
            cls._RECOVERY['mode'] = 'conditional'
        else:
            cls._RECOVERY['active'] = False
            cls._RECOVERY['mode'] = None

    # =========================================================
    # REGIME BOOST MAP
    # =========================================================
    _REGIME_BOOST = {
        'streak':        {'streak': 1.30, 'markov': 1.20, 'breakpoint': 1.20},
        'alternation':   {'cau11': 1.35, 'streak': 1.15},
        'cau22':         {'cau22': 1.40, 'cycle': 1.15},
        'cau33':         {'cau33': 1.40, 'cycle': 1.15},
        'trend_strong':  {'trend': 1.30, 'entropy': 1.15},
        'chaos':         {'entropy': 1.25, 'cau11': 1.10},
        'short_run':     {'cycle': 1.15, 'pattern': 1.10},
        'random':        {},
    }

    # =========================================================
    # MAIN PREDICT
    # =========================================================
    @classmethod
    def predict(cls, valid, log=None):
        if log is None: log = PREDICTION_LOG

        if not valid:
            seed = str(int(time.time()) // 60)
            h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
            return cls._empty_result(['Tài', 'Xỉu'][h % 2], 50, 'Chưa có DL', 'Không có dữ liệu')

        cls._update_recovery(log)
        seq = [v['result'] for v in valid]

        # Cold start
        if len(seq) < 5:
            run_val, run_len = _runs(seq)[-1]
            conf = min(52 + run_len * 2, 68)
            return cls._empty_result(_opp(run_val), conf, 'Bẻ nhịp', 'Khởi động')

        regime, regime_strength = _detect_regime(seq)

        # ===== Thu thập tất cả tín hiệu =====
        raw = [
            ('markov',      cls._sig_markov(seq)),
            ('streak',      cls._sig_streak(seq, regime)),
            ('pattern',     cls._sig_pattern(seq)),
            ('trend',       cls._sig_trend(seq)),
            ('cycle',       cls._sig_cycle(seq)),
            ('cau11',       cls._sig_cau11(seq)),
            ('cau22',       cls._sig_cau22(seq)),
            ('cau33',       cls._sig_cau33(seq)),
            ('entropy',     cls._sig_entropy(seq)),
            ('breakpoint',  cls._sig_breakpoint(seq)),
        ]

        signals = []
        weighted_votes = {'Tài': 0.0, 'Xỉu': 0.0}
        total_w = 0.0
        regime_boost = cls._REGIME_BOOST.get(regime, {})

        for name, (pred, conf, weight) in raw:
            if not pred or weight <= 0: continue

            # 1. Adaptive weight từ global tracking
            tr = cls._TRACK.get(name)
            if tr and (tr['hit'] + tr['miss']) >= 6:
                acc = tr['hit'] / (tr['hit'] + tr['miss'])
                factor = max(0.45, min(0.60 + (acc - 0.5) * 3.0, 1.70))
                weight *= factor

            # 2. Meta learning: accuracy per (signal, regime)
            meta = cls._META[regime].get(name)
            if meta and (meta['hit'] + meta['miss']) >= 4:
                macc = meta['hit'] / (meta['hit'] + meta['miss'])
                weight *= max(0.5, min(0.65 + (macc - 0.5) * 2.5, 1.55))

            # 3. Regime boost
            if name in regime_boost:
                weight *= regime_boost[name]

            # 4. Recovery boost cho signal ổn định
            if cls._RECOVERY['active'] and name in ('trend', 'pattern', 'cycle', 'cau11'):
                weight *= 1.35

            # Vote-weighted
            weighted_votes[pred] += weight * (conf / 100.0)
            total_w += weight
            signals.append({'name': name, 'prediction': pred,
                            'confidence': conf, 'weight': round(weight, 2)})

        if not signals or total_w == 0:
            run_val, _ = _runs(seq)[-1]
            return cls._empty_result(_opp(run_val), 52, 'Fallback', 'Không đủ tín hiệu',
                                     regime=regime)

        # ===== Tổng hợp vote =====
        v_tai = weighted_votes['Tài']
        v_xiu = weighted_votes['Xỉu']
        pred = 'Tài' if v_tai >= v_xiu else 'Xỉu'
        win_v = max(v_tai, v_xiu)
        raw_conf = int(win_v / max(v_tai + v_xiu, 1e-6) * 100)

        # ===== Agreement =====
        votes_tai = sum(1 for s in signals if s['prediction'] == 'Tài')
        votes_xiu = len(signals) - votes_tai
        agreement = max(votes_tai, votes_xiu) / len(signals)

        # ===== Entropy penalty =====
        recent_h = _entropy(seq[-22:])
        penalty = 0
        bonus = 0
        if recent_h > 0.96: penalty += 7
        elif recent_h > 0.88: penalty += 4
        elif recent_h < 0.70: bonus += 3

        if agreement < 0.60: penalty += 6
        elif agreement < 0.70: penalty += 3
        elif agreement >= 0.88: bonus += 5

        # Regime strength bonus
        if regime_strength > 0.6: bonus += 3

        final_conf = max(50, min(raw_conf - penalty + bonus, 86))

        # ===== Recovery flip (V12) =====
        flipped = False
        mode = cls._RECOVERY.get('mode')
        if mode == 'hard_flip':
            pred = _opp(pred)
            final_conf = max(60, min(final_conf + 3, 78))
            flipped = True
        elif mode == 'soft_flip':
            pred = _opp(pred)
            final_conf = max(58, min(final_conf + 1, 74))
            flipped = True
        elif mode == 'conditional' and agreement < 0.68 and raw_conf < 68:
            pred = _opp(pred)
            final_conf = max(56, final_conf - 2)
            flipped = True

        # ===== Calibration =====
        final_conf = cls._calibrate(final_conf, log)

        # ===== Sort signals =====
        signals.sort(key=lambda s: s['weight'] * (s['confidence'] - 50), reverse=True)
        top = [SIGNAL_NAMES.get(s['name'], s['name']) for s in signals[:3]]

        return {
            'prediction': pred,
            'confidence': final_conf,
            'method': ' + '.join(top) if top else 'Tổng hợp',
            'signals': signals,
            'top_signals': top,
            'signals_strength': [
                {
                    'name': s['name'],
                    'display': SIGNAL_NAMES.get(s['name'], s['name']),
                    'prediction': s['prediction'],
                    'confidence': s['confidence'],
                    'weight': s['weight'],
                    'strength': round(s['weight'] * (s['confidence'] - 50), 1),
                } for s in signals[:8]
            ],
            'reason': f'Regime={regime} · Agreement={agreement:.0%} · H={recent_h:.2f}',
            'flipped': flipped,
            'cau': regime,
            'cau_label': cls._cau_label(regime, signals),
            'recovery_active': cls._RECOVERY['active'],
            'fail_streak': cls._RECOVERY['fail'],
            'regime_strength': round(regime_strength, 3),
        }

    @staticmethod
    def _cau_label(regime, signals):
        labels = {
            'streak': 'Cầu bệt', 'alternation': 'Cầu 1-1',
            'cau22': 'Cầu 2-2', 'cau33': 'Cầu 3-3',
            'trend_strong': 'Cầu nghiêng', 'chaos': 'Cầu hỗn loạn',
            'short_run': 'Cầu ngắn', 'random': 'Ngẫu nhiên',
        }
        return labels.get(regime, '')

    @staticmethod
    def _empty_result(pred, conf, method, reason, regime='unknown'):
        return {
            'prediction': pred, 'confidence': conf, 'method': method,
            'signals': [], 'top_signals': [], 'signals_strength': [],
            'reason': reason, 'flipped': False,
            'cau': regime, 'cau_label': '',
            'recovery_active': False, 'fail_streak': 0,
            'regime_strength': 0.0,
        }


# ========== FETCH + SYNC ==========
def fetch_sessions():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
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


def _load_log():
    global PREDICTION_LOG, RESET_ID
    if not os.path.exists(LOG_FILE): return
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


def _sync_history():
    raw_rows, success = fetch_sessions()
    if not success and not HISTORY_CACHE: return [], False
    for row in raw_rows:
        HISTORY_CACHE[row['phien']] = row
    if RESET_ID > 0:
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
            del HISTORY_CACHE[k]
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

    # Update tracking sau khi evaluate
    _update_tracking(valid)

    if len(PREDICTION_LOG) > MAX_LOG_SIZE:
        keys = sorted(PREDICTION_LOG.keys())[:len(PREDICTION_LOG) - MAX_LOG_SIZE]
        for k in keys: del PREDICTION_LOG[k]
        changed = True
    if changed: _save_log()


def _update_tracking(valid):
    """Cập nhật tracking per-signal per-regime từ log"""
    if not valid: return
    by_phien = {v['phien']: v for v in valid}
    phien_list = sorted(by_phien.keys())

    # Reset track
    track = defaultdict(lambda: {'hit': 0, 'miss': 0})
    regime_track = defaultdict(lambda: {'hit': 0, 'miss': 0})
    meta = defaultdict(lambda: defaultdict(lambda: {'hit': 0, 'miss': 0}))

    for i, phien in enumerate(phien_list):
        if phien not in PREDICTION_LOG: continue
        entry = PREDICTION_LOG[phien]
        if entry.get('actual') is None: continue
        correct = entry.get('correct')
        if correct is None: continue

        # Regime tại thời điểm dự đoán
        history_before = [by_phien[p] for p in phien_list[:i]]
        if len(history_before) < 5: continue
        seq = [v['result'] for v in history_before]
        regime, _ = _detect_regime(seq)

        regime_track[regime]['hit' if correct else 'miss'] += 1

        # Signal-level: chỉ track method chính (dựa vào log cũ)
        # Do không lưu signals chi tiết → dùng method
        method_key = entry.get('method', 'unknown')
        # Track per-regime accuracy (dùng để boost)
        meta[regime]['__global__']['hit' if correct else 'miss'] += 1

    # Merge vào class tracking (giữ accumulation, không reset)
    for k, v in regime_track.items():
        MultiStrategyPredictor._REGIME_TRACK[k]['hit'] = v['hit']
        MultiStrategyPredictor._REGIME_TRACK[k]['miss'] = v['miss']


def _log_prediction(phien, pred_result):
    if phien in PREDICTION_LOG: return
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


def _log_stats(log=None):
    if log is None: log = PREDICTION_LOG
    evaluated = [e for e in log.values() if e.get('actual') is not None]
    correct = sum(1 for e in evaluated if e.get('correct'))
    wrong = len(evaluated) - correct
    pending = sum(1 for e in log.values() if e.get('actual') is None)

    # Streak analysis
    sorted_items = sorted(log.items(), key=lambda x: x[0], reverse=True)
    recent = [e for _, e in sorted_items if e.get('actual') is not None][:20]
    current_streak = 0
    streak_type = None
    for e in recent:
        c = e.get('correct')
        if c is None: continue
        if streak_type is None:
            streak_type = c
            current_streak = 1
        elif c == streak_type:
            current_streak += 1
        else:
            break

    return {
        'correct': correct, 'wrong': wrong, 'pending': pending,
        'evaluated': len(evaluated),
        'accuracy': round(correct / max(len(evaluated), 1) * 100, 1),
        'current_streak': current_streak,
        'streak_type': 'win' if streak_type else 'lose' if streak_type is False else None,
    }


_load_log()


# ========== HTML TEMPLATE ==========
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>LE MINH MD5 V12</title>
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
.actions{display:flex;gap:8px;align-items:center}
.clock{font-size:11px;color:var(--muted);font-weight:600;font-variant-numeric:tabular-nums}
.btn{background:#fff;color:var(--text-soft);border:1px solid var(--border);padding:7px 12px;border-radius:9px;font-weight:700;font-size:12px;cursor:pointer;transition:.2s}
.btn:hover{background:var(--bg-1);transform:translateY(-1px);border-color:var(--border-strong);color:var(--primary-dark)}
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
.pred-meta{margin-top:10px;font-size:11px;color:var(--text-soft);display:flex;flex-wrap:wrap;gap:8px}
.pred-meta span{background:rgba(14,165,233,.08);padding:3px 8px;border-radius:6px}
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
@media(max-width:520px){th,td{padding:8px 4px;font-size:11px}.clock{display:none}.badge{min-width:44px;font-size:9px}.sc-v{font-size:16px}.pred-value{font-size:26px}}
</style></head><body>
<div class="header"><div class="logo"><span class="logo-text">LE MINH</span><span class="ver">V3</span></div>
<div class="actions"><div class="clock" id="clock">--:--:--</div>
<button class="btn" onclick="manualRefresh(this)">↻</button>
<button class="btn btn-reset" onclick="confirmReset()">Reset</button></div></div>
<div class="wrap">
<div id="loading-screen" class="loading" style="display:none;">🌊 Đang tải dữ liệu...</div>
<div id="main-content">
<div class="pred-box"><div class="pred-row">
<div><div class="pred-label">Dự đoán phiên tiếp theo</div>
<div class="pred-value" id="pred-value">—</div></div>
<div class="pred-conf-badge" id="conf-badge">--%</div></div>
<div class="conf-bar"><div class="conf-bar-fill" id="conf-bar" style="width:0%"></div></div>
<div class="pred-meta" id="pred-meta"></div></div>
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
    const meta=document.getElementById('pred-meta');
    if(!pred){pv.innerText='—';cb.innerText='--%';bar.style.width='0%';meta.innerHTML='';}
    else{
      pv.innerText=pred.prediction;
      pv.className='pred-value '+(pred.prediction==='Tài'?'tai':'xiu');
      cb.innerText=pred.confidence+'%';
      bar.style.width=pred.confidence+'%';
      let metaHtml='';
      if(pred.cau_label) metaHtml+=`<span>📊 ${pred.cau_label}</span>`;
      if(pred.method) metaHtml+=`<span>🎯 ${pred.method}</span>`;
      if(pred.flipped) metaHtml+=`<span style="background:#fef3c7;color:#d97706">🔄 Đã đảo</span>`;
      if(pred.recovery_active) metaHtml+=`<span style="background:#fee2e2;color:#dc2626">⚠ Recovery (${pred.fail_streak})</span>`;
      meta.innerHTML=metaHtml;
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
fetchData();
setInterval(fetchData,5000);
</script></body></html>"""


# ========== ROUTES ==========
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
            return jsonify({'ready': False, 'message': 'Đang tải dữ liệu...',
                            'ai_stats': _log_stats()})
        next_phien = valid[-1]['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        ai_stats = _log_stats()
        out = [{
            'phien': next_phien, 'is_next': True, 'result': 'Chờ...',
            'dice': '? + ? + ?', 'total': None,
            'ai_prediction': pred['prediction'],
            'ai_confidence': pred['confidence'],
            'ai_correct': None,
        }]
        for v in reversed(valid[-200:]):
            if v['phien'] <= RESET_ID: continue
            log = PREDICTION_LOG.get(v['phien'])
            out.append({
                'phien': v['phien'], 'is_next': False,
                'result': v['result'], 'dice': v['dice'], 'total': v['total'],
                'ai_prediction': log['prediction'] if log else None,
                'ai_confidence': log['confidence'] if log else None,
                'ai_correct': log['correct'] if log else None,
            })
        return jsonify({
            'ready': True, 'rows': out, 'ai_stats': ai_stats,
            'prediction': {
                'prediction': pred['prediction'],
                'confidence': pred['confidence'],
                'method': pred['method'],
                'cau_label': pred.get('cau_label', ''),
                'flipped': pred.get('flipped', False),
                'recovery_active': pred.get('recovery_active', False),
                'fail_streak': pred.get('fail_streak', 0),
                'top_signals': pred.get('top_signals', []),
            }
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
            return jsonify({'Id': 'LE MINH V12 MD5', 'Phien': None,
                            'Du_doan': None, 'message': 'Đang tải dữ liệu...'})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        ai_stats = _log_stats(PREDICTION_LOG)
        return jsonify({
            'Id': 'LE MINH V12 MD5',
            'Phien': str(next_phien),
            'Ket_qua_truoc': last['result'].lower(),
            'Xuc_xac_truoc': last['dice'],
            'Diem_truoc': last['total'],
            'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%",
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
            'Chuoi_thang': ai_stats.get('current_streak', 0),
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
            return jsonify({'Id': '@cskhleminh', 'Phien': None,
                            'Du_doan': None, 'Ket_qua': None,
                            'message': 'Đang tải dữ liệu...'})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        dice_str = last['dice'].replace(' + ', '-')
        ket_qua = f"{last['result']} {dice_str}"
        ai_stats = _log_stats(PREDICTION_LOG)
        return jsonify({
            'Id': '@cskhleminh',
            'Phien': str(next_phien),
            'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%",
            'Phuong_phap': pred['method'],
            'Loai_cau': pred.get('cau_label', ''),
            'Ket_qua': ket_qua,
            'Xuc_xac_truoc': last['dice'],
            'Diem_truoc': last['total'],
            'Ket_qua_truoc': last['result'],
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
            'Chuoi_thang': ai_stats.get('current_streak', 0),
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
            return jsonify({'ready': False, 'message': 'Đang tải dữ liệu...',
                            'prediction': None})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        return jsonify({
            'version': 'V12',
            'last_phien': last['phien'],
            'next_phien': next_phien,
            'last_result': last['result'],
            'last_dice': last['dice'],
            'last_total': last['total'],
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'cau': pred.get('cau', 'unknown'),
            'cau_label': pred.get('cau_label', ''),
            'regime_strength': pred.get('regime_strength', 0.0),
            'top_signals': pred.get('top_signals', []),
            'signals_strength': pred.get('signals_strength', []),
            'reason': pred['reason'],
            'signals': pred['signals'],
            'signals_count': len(pred['signals']),
            'flipped': pred.get('flipped', False),
            'recovery_active': pred.get('recovery_active', False),
            'fail_streak': pred.get('fail_streak', 0),
            'ai_stats': _log_stats(),
            'timestamp': datetime.now().isoformat(),
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
        if not valid:
            return jsonify({'ready': False, 'message': 'Đang tải dữ liệu...'})
        last = valid[-1] if valid else None
        return jsonify({
            'ready': True,
            'ai_stats': _log_stats(),
            'recovery': MultiStrategyPredictor._RECOVERY,
            'regime_track': dict(MultiStrategyPredictor._REGIME_TRACK),
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
            return jsonify({'ready': False, 'message': 'Đang tải dữ liệu...'})
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        seq = [v['result'] for v in valid]
        regime, strength = _detect_regime(seq)
        return jsonify({
            'version': 'V12',
            'ready': True,
            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'regime': regime,
            'regime_label': pred.get('cau_label', ''),
            'regime_strength': round(strength, 3),
            'top_signals': pred.get('top_signals', []),
            'signals_strength': pred.get('signals_strength', []),
            'all_signals': pred['signals'],
            'signals_count': len(pred['signals']),
            'flipped': pred.get('flipped', False),
            'recovery_active': pred.get('recovery_active', False),
            'fail_streak': pred.get('fail_streak', 0),
            'recovery_state': MultiStrategyPredictor._RECOVERY,
            'reason': pred['reason'],
            'recent_runs': [{'value': v, 'len': l} for v, l in _runs(seq[-40:])],
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
            'flipped': e.get('flipped', False),
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
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys())
            HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
        else:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 400
        PREDICTION_LOG = {}
        MultiStrategyPredictor._TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0})
        MultiStrategyPredictor._REGIME_TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0})
        MultiStrategyPredictor._CONF_TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0})
        MultiStrategyPredictor._RECENT.clear()
        MultiStrategyPredictor._RECOVERY = {'active': False, 'fail': 0, 'mode': None}
        MultiStrategyPredictor._META.clear()
        _save_log()
        return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
