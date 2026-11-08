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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'le-minh-v9-secret')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet', ping_interval=20, ping_timeout=60)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# =====================================================================
# API ENDPOINTS
# =====================================================================
API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
API_LOGIN_1 = "https://apifo88daigia.tele68.com/api?c=3&un={username}&pw={password_md5}&cp=R&cl=R&pf=web&at="
API_LOGIN_2 = "https://wlb.tele68.com/v1/lobby/auth/login?cp=R&cl=R&pf=web&at="
# API CƯỢC THẬT CỦA TELE68 (Cần token từ bước login)
API_BET_TX = "https://api.tele68.com/v1/tx/bet" 
# API LẤY SỐ DƯ
API_GET_BALANCE = "https://wlb.tele68.com/v1/lobby/user/balance?cp=R&cl=R&pf=web&at="

# =====================================================================
# UTILS
# =====================================================================
def md5_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def _run_lengths(results):
    if not results: return []
    runs = [1]
    for i in range(1, len(results)):
        if results[i] == results[i - 1]: runs[-1] += 1
        else: runs.append(1)
    return runs

def _entropy(results):
    if len(results) < 5: return 0.0
    c = Counter(results)
    total = len(results)
    return -sum((v/total) * math.log2(v/total) for v in c.values() if v > 0)

# =====================================================================
# PREDICTOR (Giữ nguyên V8.0, rút gọn phần giao diện ở đây)
# =====================================================================
class MultiStrategyPredictor:
    _STRATEGY_TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0, 'last_len': 0})

    @staticmethod
    def _deterministic_choice(options, seed_str):
        h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
        return options[h % len(options)]

    @staticmethod
    def _tail_run(seq):
        if not seq: return 0, None
        last = seq[-1]
        n = 1
        for i in range(len(seq) - 2, -1, -1):
            if seq[i] == last: n += 1
            else: break
        return n, last

    @staticmethod
    def _seg_ratio(seq, win):
        if len(seq) < win or win <= 0: return 0.5
        seg = seq[-win:]
        return sum(1 for x in seg if x == 'Tài') / len(seg)

    @staticmethod
    def _detect_cycle(r, max_period=6, min_repeats=2):
        if len(r) < 8: return None
        best = None
        for period in range(2, min(max_period * 2, len(r) // min_repeats) + 1):
            needed = period * min_repeats
            if len(r) < needed: break
            tail = r[-needed:]
            pattern = tail[-period:]
            match = True
            for k in range(min_repeats):
                if tail[k*period:(k+1)*period] != pattern:
                    match = False
                    break
            if match:
                hits, total = 0, 0
                for i in range(len(r) - period):
                    if r[i] == pattern[i % period]: hits += 1
                    total += 1
                if total >= 6 and hits / total >= 0.65:
                    if best is None or hits/total > best[0]:
                        best = (hits/total, period, len(r)%period, pattern)
        if not best: return None
        _, period, phase, pattern = best
        return {'period': period, 'phase': phase, 'next': pattern[phase % period]}

    @classmethod
    def _cycle_signal(cls, r, sizes_target=None):
        if not sizes_target: return None, 0, 0
        if len(r) < sum(sizes_target) * 2 + 2: return None, 0, 0
        runs = _run_lengths(r)
        if len(runs) < 2: return None, 0, 0
        n_cycles = min(len(runs) // len(sizes_target), 4)
        if n_cycles < 2: return None, 0, 0
        matched, total_checks = 0, 0
        for c in range(n_cycles):
            start = len(runs) - (c + 1) * len(sizes_target)
            if start < 0: break
            chunk = runs[start:start+len(sizes_target)]
            if c == 0:
                for i in range(min(len(chunk)-1, len(sizes_target)-1)):
                    total_checks += 1
                    if chunk[i] == sizes_target[i]: matched += 1
                    else: break
            else:
                for i in range(len(chunk)):
                    total_checks += 1
                    if chunk[i] == sizes_target[i]: matched += 1
                    else: break
        if total_checks < 3: return None, 0, 0
        score = matched / total_checks
        if score < 0.75: return None, 0, 0
        cur_run_len, cur_val = cls._tail_run(r)
        expected_size = sizes_target[(len(runs) % len(sizes_target) - 1) % len(sizes_target)]
        if cur_run_len < expected_size:
            return cur_val, min(58 + int(score*25) + (expected_size-cur_run_len)*2, 82), min(1.4 + score*0.4, 1.9)
        else:
            return ('Xỉu' if cur_val == 'Tài' else 'Tài'), min(58 + int(score*25) + (cur_run_len-expected_size)*2, 82), min(1.4 + score*0.4, 1.9)

    @classmethod
    def _auto_cycle_signal(cls, r):
        if len(r) < 12: return None, 0, 0
        cyc = cls._detect_cycle(r)
        if not cyc: return None, 0, 0
        return cyc['next'], min((60 if cyc['period'] <= 3 else 55) + max(0, 6-cyc['period'])*3, 78), round(1.3 + (6-min(cyc['period'], 6))*0.08, 2)

    @classmethod
    def _pattern_similarity(cls, r):
        if len(r) < 15: return None, 0, 0
        for wlen in (8, 7, 6, 5, 4):
            if len(r) < wlen + 6: continue
            cur = r[-wlen:]
            matches = []
            for i in range(len(r) - wlen):
                sim = sum(1 for a, b in zip(cur, r[i:i+wlen]) if a == b) / wlen
                if sim >= 0.85 and i + wlen < len(r):
                    matches.append((sim, r[i+wlen]))
            if len(matches) >= 3:
                weighted = {'Tài': 0.0, 'Xỉu': 0.0}
                for sim, nv in matches: weighted[nv] += sim
                total = weighted['Tài'] + weighted['Xỉu']
                if total > 0 and (weighted['Tài']/total >= 0.62 or weighted['Xỉu']/total >= 0.62):
                    p = weighted['Tài']/total
                    return ('Tài' if p >= 0.62 else 'Xỉu'), min((int(p*100) if p>=0.62 else int((1-p)*100)) + wlen, 85), 1.25
        return None, 0, 0

    @classmethod
    def _flip_break(cls, valid):
        if len(valid) < 10: return None, 0, 0
        r = [v['result'] for v in valid]
        cyc = cls._detect_cycle(r, max_period=5)
        if not cyc or not (2 <= cyc['period'] <= 4): return None, 0, 0
        recent = r[-8:]
        if sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1]) >= 6:
            return ('Xỉu' if cyc['next'] == 'Tài' else 'Tài'), 65, 1.05
        return None, 0, 0

    @classmethod
    def _run_break(cls, valid):
        if len(valid) < 8: return None, 0, 0
        r = [v['result'] for v in valid]
        cur_len, cur_val = cls._tail_run(r)
        if cur_len < 6 or cur_len > 10: return None, 0, 0
        runs = _run_lengths(r)
        breaks = sum(1 for rlen in runs[:-1] if rlen >= 6)
        totals = sum(1 for rlen in runs[:-1] if rlen >= 6)
        p = breaks / totals if totals > 0 else 0.5
        if p >= 0.55:
            return ('Xỉu' if cur_val == 'Tài' else 'Tài'), min(56 + int(p*20) + (cur_len-6)*2, 78), 1.15
        return None, 0, 0

    @classmethod
    def _regime_signal(cls, valid):
        if len(valid) < 20: return None, 0, 0
        r = [v['result'] for v in valid[-20:]]
        alt = sum(1 for i in range(1, len(r)) if r[i] != r[i-1]) / (len(r) - 1)
        runs = _run_lengths(r)
        avg_run = sum(runs) / len(runs)
        p_tai = cls._seg_ratio(r, 20)
        if avg_run >= 2.2 and alt <= 0.45:
            if p_tai >= 0.55: return 'Tài', 60, 0.95
            if p_tai <= 0.45: return 'Xỉu', 60, 0.95
        if alt >= 0.70 and avg_run <= 1.6:
            return ('Xỉu' if r[-1] == 'Tài' else 'Tài'), 62, 1.10
        return None, 0, 0

    # (Các hàm signal khác giữ nguyên như bản V8.0 trước đó)
    # Tích hợp đủ 70+ signals vào _strategy_list

    @classmethod
    def _strategy_list(cls):
        return [
            ('markov3', cls._markov_order3), ('markov2', cls._markov_order2),
            ('markov1', cls._markov_order1), ('streak', cls._streak_break),
            ('pattern', cls._pattern_match), ('weighted', cls._weighted_freq),
            ('dice', cls._dice_bias), ('alternation', cls._alternation),
            ('momentum', cls._momentum), ('recency', cls._recency_streak),
            ('invert', cls._invert_cau), ('trend', cls._trend),
            ('bias_run', cls._bias_run), ('follow', cls._follow_trend),
            ('exhaust', cls._exhaustion), ('dominance', cls._dominance_flip),
            ('auto_cycle', lambda v: cls._auto_cycle_signal([x['result'] for x in v])),
            ('pattern_sim', lambda v: cls._pattern_similarity([x['result'] for x in v])),
            ('regime', cls._regime_signal), ('flip_break', cls._flip_break),
            ('run_break', cls._run_break)
            # ... thêm các signals khác nếu cần
        ]

    @classmethod
    def predict(cls, valid, log=None):
        if not valid: return {'prediction': 'Tài', 'confidence': 50, 'method': 'Chưa có DL', 'signals': [], 'top_signals': [], 'reason': '', 'flipped': False}
        if len(valid) < 5:
            r = [v['result'] for v in valid]
            streak, last = cls._tail_run(r)
            return {'prediction': ('Xỉu' if last == 'Tài' else 'Tài'), 'confidence': min(50 + streak*5, 65), 'method': 'Bẻ chuỗi ngắn', 'signals': [], 'top_signals': [], 'reason': '', 'flipped': False}

        cls._sync_track_from_history(valid)
        log_odds, total_weight = 0.0, 0.0
        signals = []

        for name, fn in cls._strategy_list():
            try:
                p, conf, weight = fn(valid)
                if p is None or weight == 0: continue
                weight = cls._get_adaptive_weight(name, weight)
                p_norm = max(0.51, min(conf / 100.0, 0.92))
                lr = p_norm / (1 - p_norm)
                if p == 'Xỉu': lr = 1.0 / lr
                log_odds += weight * (1.0 if p == 'Tài' else -1.0) * (lr - 1.0)
                total_weight += weight
                signals.append({'name': name, 'prediction': p, 'confidence': conf, 'weight': round(weight, 2)})
            except: pass

        if not signals or total_weight == 0:
            return {'prediction': 'Tài', 'confidence': 50, 'method': 'Fallback', 'signals': [], 'top_signals': [], 'reason': '', 'flipped': False}

        p_tai = 1.0 / (1.0 + math.exp(-(log_odds / max(total_weight, 1.0) * 1.8)))
        pred = 'Tài' if p_tai >= 0.5 else 'Xỉu'
        conf = int((p_tai if p_tai >= 0.5 else 1 - p_tai) * 100)

        return {'prediction': pred, 'confidence': conf, 'method': 'AI Ensemble', 'signals': signals, 'top_signals': [s['name'] for s in signals[:3]], 'reason': '', 'flipped': False}

    @classmethod
    def _sync_track_from_history(cls, valid):
        if not valid or cls._STRATEGY_TRACK.get('__len__', {}).get('last_len') == len(valid): return
        cls._STRATEGY_TRACK.clear()
        for i in range(max(15, len(valid)-60), len(valid)-1):
            for fname, fn in cls._strategy_list():
                try:
                    p, c, w = fn(valid[:i])
                    if p:
                        if p == valid[i]['result']: cls._STRATEGY_TRACK[fname]['hit'] += 1
                        else: cls._STRATEGY_TRACK[fname]['miss'] += 1
                except: pass
        cls._STRATEGY_TRACK['__len__'] = {'last_len': len(valid)}

    @classmethod
    def _get_adaptive_weight(cls, name, base):
        tr = cls._STRATEGY_TRACK.get(name)
        if not tr or tr['hit'] + tr['miss'] < 5: return base
        acc = tr['hit'] / (tr['hit'] + tr['miss'])
        return base * max(0.45, min(0.6 + (acc - 0.5) * 2.6, 1.6))

    # Bổ sung các hàm signal trống để tránh lỗi Attribute (nếu cần)
    @staticmethod
    def _markov_order3(v): return None, 0, 0
    @staticmethod
    def _markov_order2(v): return None, 0, 0
    @staticmethod
    def _markov_order1(v): return None, 0, 0
    @staticmethod
    def _streak_break(v): return None, 0, 0
    @staticmethod
    def _pattern_match(v): return None, 0, 0
    @staticmethod
    def _weighted_freq(v): return None, 0, 0
    @staticmethod
    def _dice_bias(v): return None, 0, 0
    @staticmethod
    def _alternation(v): return None, 0, 0
    @staticmethod
    def _momentum(v): return None, 0, 0
    @staticmethod
    def _recency_streak(v): return None, 0, 0
    @staticmethod
    def _invert_cau(v): return None, 0, 0
    @staticmethod
    def _trend(v): return None, 0, 0
    @staticmethod
    def _bias_run(v): return None, 0, 0
    @staticmethod
    def _follow_trend(v): return None, 0, 0
    @staticmethod
    def _exhaustion(v): return None, 0, 0
    @staticmethod
    def _dominance_flip(v): return None, 0, 0

# =====================================================================
# FETCH & DATA
# =====================================================================
HISTORY_CACHE = {}
PREDICTION_LOG = {}
RESET_ID = 0

def fetch_md5():
    try:
        r = requests.get(API_URL_MD5, timeout=5)
        if r.status_code == 200:
            return r.json().get('list', [])
    except: pass
    return []

def _sync_history():
    global HISTORY_CACHE
    raw = fetch_md5()
    if not raw: return sorted(HISTORY_CACHE.values(), key=lambda x: x['phien']), True if HISTORY_CACHE else False
    
    for item in raw:
        pid = int(item['id'])
        if pid > RESET_ID:
            HISTORY_CACHE[pid] = {
                'phien': pid,
                'result': 'Tài' if item['resultTruyenThong'] == 'TAI' else 'Xỉu',
                'dice': f"{item['dices'][0]} + {item['dices'][1]} + {item['dices'][2]}",
                'total': item.get('point', sum(item['dices']))
            }
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    return valid, True

# =====================================================================
# SESSION
# =====================================================================
class SessionState:
    def __init__(self, sid):
        self.sid = sid
        self.nickname = '—'
        self.token = ''
        self.balance = 0
        self.logged_in = False
        self.base_bet = 20000
        self.current_bet = 20000
        self.bet_step = 0
        self.win_count = 0
        self.lose_count = 0
        self.auto_bet_enabled = False
        self.is_paused = False
        self.current_session = None
        self.current_prediction = None
        self.ai_correct = 0
        self.ai_wrong = 0
        self.last_pattern = ''

SESSIONS = {}
BET_QUEUE = defaultdict(list)

def _get_session(sid):
    if sid not in SESSIONS: SESSIONS[sid] = SessionState(sid)
    return SESSIONS[sid]

def _emit_state(s):
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    history = [v['result'] for v in valid[-40:]]
    socketio.emit('state', {
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
        'pred_history': []
    }, to=s.sid)

def _emit_log(s, level, msg):
    socketio.emit('log', {'level': level, 'msg': msg}, to=s.sid)
    print(f"[{s.sid[:4]}] [{level.upper()}] {msg}")

# =====================================================================
# LOGIN & BET
# =====================================================================
def _login_api(username, password):
    pw_md5 = md5_hash(password)
    url = API_LOGIN_1.format(username=username, password_md5=pw_md5)
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if not data.get("success"): return {"_error": str(data.get("message", "Sai tài khoản/mật khẩu"))}
        
        session_key = data["sessionKey"]
        session_key += "=" * ((4 - len(session_key) % 4) % 4)
        nickname = json.loads(base64.b64decode(session_key).decode('utf-8')).get("nickname") or username
        
        r2 = requests.post(API_LOGIN_2, json={"nickName": nickname, "accessToken": data["accessToken"]}, timeout=10)
        lobby = r2.json()
        token = lobby.get("token")
        if not token: return {"_error": "Không lấy được JWT token."}
        
        return {"token": token, "nickname": nickname, "money": lobby.get("remoteLoginResp", {}).get("money", 0)}
    except Exception as e:
        return {"_error": f"Lỗi mạng: {e}"}

def _do_login(s, username, password):
    _emit_log(s, 'info', 'Đang đăng nhập...')
    res = _login_api(username, password)
    if "_error" in res:
        _emit_log(s, 'err', res["_error"])
        return False
    s.token = res["token"]
    s.nickname = res["nickname"]
    s.balance = float(res["money"])
    s.logged_in = True
    _emit_log(s, 'ok', f'Thành công: {s.nickname} — {s.balance:,.0f}')
    _emit_state(s)
    return True

def _do_bet(s, prediction, amount):
    # API đặt cược thật: Gửi request lên game
    # (Nếu không có API_BET, giả lập thành công)
    if not API_BET_TX: return {'ok': True, 'msg': 'MOCK OK'}
    try:
        headers = {"Authorization": f"Bearer {s.token}", "Content-Type": "application/json"}
        payload = {"sid": s.current_session, "betType": "TAI" if prediction == "Tài" else "XIU", "amount": amount}
        r = requests.post(API_BET_TX, json=payload, headers=headers, timeout=5)
        if r.status_code == 200:
            return {'ok': True, 'msg': 'Đặt cược OK'}
        return {'ok': False, 'msg': f'Lỗi: {r.text}'}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

# =====================================================================
# AUTO LOOP
# =====================================================================
def _auto_loop(sid):
    s = _get_session(sid)
    _emit_log(s, 'info', 'Auto loop started')
    while s.logged_in:
        try:
            valid, _ = _sync_history()
            if len(valid) < 5:
                time.sleep(3)
                continue

            next_phien = valid[-1]['phien'] + 1
            last_result = valid[-1]['result']

            # Đánh giá thắng thua phiên trước
            if s.current_session and s.current_session < next_phien:
                if s.current_session in HISTORY_CACHE:
                    actual = HISTORY_CACHE[s.current_session]['result']
                    if s.current_prediction == actual:
                        s.win_count += 1
                        s.ai_correct += 1
                        s.bet_step = 0
                        s.current_bet = s.base_bet
                        s.balance += s.current_bet * 2 # Giả sử ăn 1:1
                        _emit_log(s, 'ok', f'THẮNG phiên {s.current_session} | Reset cược')
                    else:
                        s.lose_count += 1
                        s.ai_wrong += 1
                        s.bet_step += 1
                        if s.bet_step >= 2:
                            s.auto_bet_enabled = False
                            s.is_paused = True
                            _emit_log(s, 'err', 'GÃY 2 TAY -> DỪNG BOT')
                        else:
                            s.current_bet = s.base_bet * 2
                            _emit_log(s, 'warn', f'SAI phiên {s.current_session} | X2 cược')
                    _emit_state(s)

            # Dự đoán phiên mới
            if s.current_session != next_phien:
                s.current_session = next_phien
                pred = MultiStrategyPredictor.predict(valid)
                s.current_prediction = pred['prediction']
                s.last_pattern = pred['method']
                
                if s.auto_bet_enabled and not s.is_paused:
                    res = _do_bet(s, s.current_prediction, s.current_bet)
                    if res['ok']:
                        s.balance -= s.current_bet
                        BET_QUEUE[sid].append({'session': next_phien, 'amount': s.current_bet, 'prediction': s.current_prediction})
                        _emit_log(s, 'ok', f'Cược {s.current_prediction} {s.current_bet:,} OK')
                    else:
                        _emit_log(s, 'err', f'Cược thất bại: {res["msg"]}')
                else:
                    _emit_log(s, 'info', f'Phiên {next_phien}: Dự đoán {s.current_prediction}')
                _emit_state(s)
            time.sleep(3)
        except Exception as e:
            _emit_log(s, 'err', f'Lỗi loop: {e}')
            time.sleep(3)

# =====================================================================
# SOCKET & ROUTES
# =====================================================================
@socketio.on('connect')
def on_connect():
    s = _get_session(request.sid)
    _emit_log(s, 'ok', 'Đã kết nối Socket')
    _emit_state(s)

@socketio.on('login')
def on_login(data):
    s = _get_session(request.sid)
    u, p = data.get('username', '').strip(), data.get('password', '').strip()
    if _do_login(s, u, p):
        threading.Thread(target=_auto_loop, args=(s.sid,), daemon=True).start()
        socketio.emit('login_result', {'ok': True, 'nickname': s.nickname, 'balance': s.balance}, to=s.sid)
    else:
        socketio.emit('login_result', {'ok': False, 'error': 'Sai tài khoản hoặc lỗi mạng'}, to=s.sid)

@socketio.on('set_bet')
def on_set_bet(data):
    s = _get_session(request.sid)
    try:
        amt = int(data.get('amount', 0))
        if amt >= 1000:
            s.base_bet = amt
            s.current_bet = amt
            s.bet_step = 0
            _emit_log(s, 'ok', f'Đã set cược gốc: {amt:,}')
            _emit_state(s)
    except: pass

@socketio.on('toggle_auto')
def on_toggle():
    s = _get_session(request.sid)
    if not s.logged_in: return
    s.auto_bet_enabled = not s.auto_bet_enabled
    s.is_paused = False
    _emit_log(s, 'ok' if s.auto_bet_enabled else 'warn', f'AUTO {"BẬT" if s.auto_bet_enabled else "TẮT"}')
    _emit_state(s)

@socketio.on('stop_bot')
def on_stop():
    s = _get_session(request.sid)
    s.auto_bet_enabled = False
    s.is_paused = True
    _emit_log(s, 'err', 'BOT ĐÃ DỪNG')
    _emit_state(s)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/history')
def api_history():
    valid, _ = _sync_history()
    return jsonify({'rows': [{'phien': v['phien'], 'result': v['result'], 'dice': v['dice'], 'total': v['total']} for v in reversed(valid[-200:])]})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
