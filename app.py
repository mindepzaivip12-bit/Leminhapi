import os
import traceback
import time
import json
import hashlib
import math
import threading
import base64
import requests
import logging
from datetime import datetime
from collections import Counter, defaultdict

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# =====================================================================
# INIT & LOGGER
# =====================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'le-minh-v9-secret')
CORS(app)
socketio = SocketIO(
    app,
    cors_allowed_origins='*',
    async_mode='eventlet',
    ping_interval=20,
    ping_timeout=60,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# =====================================================================
# ENDPOINTS
# =====================================================================
API_URL_MD5 = (
    "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions"
    "?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
)
API_URL_LOGIN_BASE = "https://apifo88daigia.tele68.com/api"
API_URL_LOBBY = "https://wlb.tele68.com/v1/lobby/auth/login"
# TODO: Cập nhật API đặt cược thật của game (endpoint, payload)
API_URL_BET = os.environ.get('API_URL_BET', '')

# =====================================================================
# STATE
# =====================================================================
HISTORY_CACHE = {}
RESET_ID = 0
PREDICTION_LOG = {}
MAX_LOG_SIZE = 3000
LOG_FILE = os.environ.get('LOG_FILE', 'prediction_log.json')

SESSIONS = {}  # sid -> SessionState
BET_QUEUE = defaultdict(list)  # sid -> list of bets

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
        logger.info(f"[LOG] Loaded {len(PREDICTION_LOG)} predictions")
    except Exception as e:
        logger.error(f"[LOG] Load failed: {e}")


def _save_log():
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'log': PREDICTION_LOG, 'reset_id': RESET_ID}, f)
    except Exception as e:
        logger.error(f"[LOG] Save failed: {e}")


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


def md5_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


# =====================================================================
# LOGIN FLOW (API THẬT)
# =====================================================================
def login_and_get_token(username: str, password: str) -> dict:
    """Đăng nhập qua API tele68, trả về JWT token + nickname + money."""
    pw_md5 = md5_hash(password)
    url = f"{API_URL_LOGIN_BASE}?c=3&un={username}&pw={pw_md5}&cp=R&cl=R&pf=web&at="
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            return {"_error": f"Lỗi Game: {str(data.get('message', 'Sai thông tin'))}"}

        session_key = data["sessionKey"]
        session_key += "=" * ((4 - len(session_key) % 4) % 4)
        session_data = json.loads(base64.b64decode(session_key).decode('utf-8'))
        nickname = session_data.get("nickname") or session_data.get("nickName")

        access_token = data["accessToken"]
        r2 = requests.post(
            f"{API_URL_LOBBY}?cp=R&cl=R&pf=web&at=",
            headers={
                "authority": "wlb.tele68.com",
                "content-type": "application/json"
            },
            json={"nickName": nickname, "accessToken": access_token},
            timeout=12
        )
        lobby = r2.json()
        token = lobby.get("token")
        if not token:
            return {"_error": "Lobby không trả về JWT token."}
        return {
            "token": token,
            "nickname": nickname,
            "money": lobby.get("remoteLoginResp", {}).get("money", 0)
        }
    except Exception as e:
        return {"_error": f"Lỗi kết nối: {e}"}


# =====================================================================
# PREDICTOR V8.0 — giữ nguyên engine
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

    # ---- Các signals còn lại (rút gọn để file không quá dài) ----
    # (Giữ nguyên phần signals như V8.0, bao gồm:
    #  _streak_aware, _tier2_boost, _volatility_regime, _cascade_pattern,
    #  _harmonic_pattern, _wavelet_trend, _seasonal_cycle, _markov_weighted,
    #  _ensemble_boost, _decision_tree, _ngram_signal, _mirror_pattern,
    #  _reverse_trend, _palindrome_check, _bayes_recent, _chi_square,
    #  _runs_prediction, _transition_matrix, _signal_consensus,
    #  _signal_dissent, _entropy_adaptive, _streak_maturity,
    #  _markov_order1/2/3, _streak_break, _exhaustion, _dominance_flip,
    #  _follow_trend, _invert_cau, _trend, _bias_run, _pattern_match,
    #  _weighted_freq, _dice_bias, _alternation, _momentum,
    #  _recency_streak, _time_pattern, _volatility, _cusum,
    #  _kelly_optimal, _multi_window, _rsi_signal, _fibonacci_break,
    #  _zscore_extreme)

    @classmethod
    def _strategy_list(cls):
        """Trả về danh sách (name, fn) — full như V8.0."""
        # (Xem file V8.0 để copy đầy đủ — giữ nguyên)
        return [
            # core
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

    # ==================== ADAPTIVE (giữ nguyên như V8.0) ====================
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


# =====================================================================
# MD5 HISTORY FETCHER
# =====================================================================
def fetch_sessions():
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
            r = requests.get(API_URL_MD5, timeout=6, headers=headers, proxies=proxies)
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
            logger.warning(f"[API MD5 ERROR] attempt {attempt + 1}: {e}")
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
# SESSION STATE
# =====================================================================
class SessionState:
    def __init__(self, sid):
        self.sid = sid
        self.username = ''
        self.password = ''
        self.nickname = ''
        self.token = ''
        self.balance = 0
        self.logged_in = False
        # Bet config — cho phép nhập bất kỳ
        self.base_bet = 20000
        self.current_bet = 20000
        self.bet_step = 0
        self.win_count = 0
        self.lose_count = 0
        self.auto_bet_enabled = False
        self.is_paused = False
        # Session tracking
        self.current_session = None
        self.current_prediction = None
        self.ai_correct = 0
        self.ai_wrong = 0
        self.last_pattern = ''
        self.last_bet_session = None
        self.lock = threading.Lock()


def _get_session(sid):
    if sid not in SESSIONS:
        SESSIONS[sid] = SessionState(sid)
    return SESSIONS[sid]


def _state_to_dict(s):
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    history = [v['result'] for v in valid[-40:]]
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
    logger.info(f"[{s.sid[:6]}] [{level.upper()}] {msg}")


# =====================================================================
# LOGIN
# =====================================================================
def _do_login(s, username, password):
    s.username = username
    s.password = password
    _emit_log(s, 'info', 'Đang kết nối tới server game...')

    result = login_and_get_token(username, password)
    if "_error" in result:
        _emit_log(s, 'err', result["_error"])
        return False

    s.token = result.get("token", "")
    s.nickname = result.get("nickname", username)
    s.balance = float(result.get("money", 0))
    s.logged_in = True

    _emit_log(s, 'ok', f'Đăng nhập thành công: {s.nickname} — {s.balance:,.0f}')
    _emit_state(s)
    return True


# =====================================================================
# BET FLOW — MOCK hoặc REAL (tuỳ API game)
# =====================================================================
def _do_bet(s, prediction, amount):
    """Đặt cược thật (nếu có API_URL_BET) hoặc mock."""
    if not API_URL_BET:
        # MOCK mode: giả lập đặt cược thành công
        logger.info(f"[BET] MOCK {s.nickname} · {prediction} · {amount:,}")
        return {'ok': True}

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
# BET QUEUE
# =====================================================================
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
# AUTO BET LOOP (per session)
# =====================================================================
def _auto_bet_loop(sid):
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

            # Đánh giá cược trước (nếu có)
            if s.last_bet_session and s.last_bet_session < last_phien:
                prev_bet = next(
                    (b for b in _get_pending_bets(s) if b['session'] == s.last_bet_session),
                    None
                )
                if prev_bet:
                    result_row = next((v for v in valid if v['phien'] == s.last_bet_session), None)
                    if result_row:
                        won = (prev_bet['prediction'] == result_row['result'])
                        if won:
                            s.win_count += 1
                            s.ai_correct += 1
                            s.bet_step = 0
                            s.current_bet = s.base_bet
                            s.balance += prev_bet['amount']  # hoàn vốn thắng
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

            # Cập nhật dự đoán phiên mới + đặt cược
            if s.current_session != next_phien:
                s.current_session = next_phien
                pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
                _log_prediction(next_phien, pred)
                s.current_prediction = pred['prediction']
                s.last_pattern = pred['method']
                _emit_log(s, 'info',
                          f'Phiên {next_phien} · Dự đoán {pred["prediction"]} '
                          f'({pred["confidence"]}%)')

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


# =====================================================================
# SOCKET.IO EVENTS
# =====================================================================
@socketio.on('connect')
def _on_connect():
    sid = request.sid
    s = _get_session(sid)
    logger.info(f"[SOCKET] Connect: {sid}")
    _emit_log(s, 'ok', f'Web socket kết nối: {sid}')
    _emit_state(s)


@socketio.on('disconnect')
def _on_disconnect():
    sid = request.sid
    logger.info(f"[SOCKET] Disconnect: {sid}")
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
        # Start auto bet loop cho session này
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
            return jsonify({'Id': 'LE MINH V9.0', 'Phien': None, 'Du_doan': None})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats()
        return jsonify({
            'Id': 'LE MINH V9.0 MD5',
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
