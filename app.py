import os
import time
import json
import hashlib
import base64
import threading
import requests
import logging
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'leminh_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# API ENDPOINTS
# ==========================================
API_LOGIN_1 = "https://apifo88daigia.tele68.com/api?c=3&un={username}&pw={password_md5}&cp=R&cl=R&pf=web&at="
API_LOGIN_2 = "https://wlb.tele68.com/v1/lobby/auth/login?cp=R&cl=R&pf=web&at="
# API để đặt cược (Dựa trên cấu trúc của tele68)
API_BET = "https://wtxmd52.tele68.com/v1/txmd5/bet?cp=R&cl=R&pf=web&at="

# ==========================================
# QUẢN LÝ PHIÊN (SESSION)
# ==========================================
class UserSession:
    def __init__(self, sid):
        self.sid = sid
        self.token = None
        self.nickname = ""
        self.balance = 0
        self.logged_in = False
        
        self.base_bet = 20000
        self.current_bet = 20000
        self.auto_bet = False
        
        self.ai_correct = 0
        self.ai_wrong = 0
        self.win_streak = 0
        self.last_prediction = None

sessions = {}

def get_session(sid):
    if sid not in sessions:
        sessions[sid] = UserSession(sid)
    return sessions[sid]

# ==========================================
# THUẬT TOÁN DỰ ĐOÁN (CƠ BẢN)
# ==========================================
def predict_result(history):
    # Logic giả lập dựa trên 3 phiên gần nhất
    if not history or len(history) < 3:
        return "TAI", 65
    
    last3 = [h['result'] for h in history[-3:]]
    if len(set(last3)) == 1:
        # Bẻ cầu bệt
        return ("XIU" if last3[0] == "TAI" else "TAI"), 75
    else:
        # Theo cầu 1-1
        return ("TAI" if last3[-1] == "XIU" else "XIU"), 60

# ==========================================
# LOGIC AUTO CƯỢC (CHẠY NGẦM)
# ==========================================
def auto_bet_worker(sid):
    sess = get_session(sid)
    if not sess.logged_in:
        return

    logger.info(f"[{sid}] Bắt đầu Auto Bet")
    session_id = 1000000 # Fake ID để test
    
    while sess.auto_bet and sess.logged_in:
        try:
            # 1. Dự đoán
            # (Thực tế sẽ lấy lịch sử từ API, ở đây giả lập)
            pred, conf = predict_result([])
            sess.last_prediction = pred
            
            # Tính tiền cược (X2 nếu thua)
            if sess.win_streak < 0:
                sess.current_bet = sess.base_bet * 2
            else:
                sess.current_bet = sess.base_bet
            
            # 2. Gửi tín hiệu xuống giao diện
            socketio.emit('log', {'msg': f"Phiên mới #{session_id} | Dự đoán: {pred} ({conf}%)", 'type': 'info'}, to=sid)
            
            if sess.current_bet > sess.balance:
                socketio.emit('log', {'msg': "Số dư không đủ! Tắt Auto.", 'type': 'error'}, to=sid)
                sess.auto_bet = False
                break

            # 3. Tiến hành đặt cược (Gọi API)
            socketio.emit('log', {'msg': f"Đang cược {pred} - {sess.current_bet:,} Win...", 'type': 'warn'}, to=sid)
            
            # --- MOCK ĐẶT CƯỢC THÀNH CÔNG ---
            # (Nếu có API thật, thay bằng requests.post)
            time.sleep(2) 
            is_win = (hashlib.md5(str(session_id).encode()).hexdigest()[0] in '0123456') # Random thắng 70%
            
            if is_win:
                sess.balance += sess.current_bet * 0.98
                sess.ai_correct += 1
                sess.win_streak = 0
                socketio.emit('log', {'msg': f"✅ THẮNG! +{int(sess.current_bet*0.98):,} Win", 'type': 'success'}, to=sid)
            else:
                sess.balance -= sess.current_bet
                sess.ai_wrong += 1
                sess.win_streak -= 1
                socketio.emit('log', {'msg': f"❌ THUA! -{sess.current_bet:,} Win", 'type': 'error'}, to=sid)
                
                if sess.win_streak <= -2:
                    sess.auto_bet = False
                    socketio.emit('log', {'msg': "Gãy 2 tay! Tự động dừng.", 'type': 'error'}, to=sid)

            # 4. Cập nhật UI
            socketio.emit('state', {
                'balance': sess.balance,
                'ai_correct': sess.ai_correct,
                'ai_wrong': sess.ai_wrong,
                'auto_bet': sess.auto_bet
            }, to=sid)
            
            session_id += 1
            time.sleep(5) # Chờ phiên tiếp theo
            
        except Exception as e:
            logger.error(f"Lỗi Auto Bet: {e}")
            time.sleep(2)

# ==========================================
# SOCKET EVENTS
# ==========================================
@socketio.on('connect')
def on_connect():
    sid = request.sid
    logger.info(f"Client connected: {sid}")
    get_session(sid)

@socketio.on('login')
def handle_login(data):
    sid = request.sid
    sess = get_session(sid)
    
    username = data.get('username')
    password = data.get('password')
    
    socketio.emit('log', {'msg': "Đang kết nối server game...", 'type': 'info'}, to=sid)
    
    pw_md5 = hashlib.md5(password.encode('utf-8')).hexdigest()
    url = API_LOGIN_1.format(username=username, password_md5=pw_md5)
    
    try:
        r = requests.get(url, timeout=10)
        res = r.json()
        if not res.get("success"):
            socketio.emit('log', {'msg': f"Lỗi: {res.get('message')}", 'type': 'error'}, to=sid)
            socketio.emit('login_failed', to=sid)
            return
            
        session_key = res["sessionKey"]
        session_key += "=" * ((4 - len(session_key) % 4) % 4)
        nick = json.loads(base64.b64decode(session_key).decode('utf-8')).get("nickname")
        
        r2 = requests.post(API_LOGIN_2, json={"nickName": nick, "accessToken": res["accessToken"]}, timeout=10)
        lobby = r2.json()
        
        sess.token = lobby.get("token")
        sess.nickname = nick
        sess.balance = lobby.get("remoteLoginResp", {}).get("money", 0)
        sess.logged_in = True
        
        socketio.emit('log', {'msg': f"Đăng nhập OK: {nick} | Dư: {sess.balance:,} Win", 'type': 'success'}, to=sid)
        socketio.emit('login_success', {'nickname': nick, 'balance': sess.balance}, to=sid)
        
    except Exception as e:
        socketio.emit('log', {'msg': f"Lỗi mạng: {e}", 'type': 'error'}, to=sid)
        socketio.emit('login_failed', to=sid)

@socketio.on('start_auto')
def handle_start_auto(data):
    sid = request.sid
    sess = get_session(sid)
    if not sess.logged_in: return
    
    sess.base_bet = int(data.get('amount', 20000))
    sess.current_bet = sess.base_bet
    sess.auto_bet = True
    sess.win_streak = 0
    
    socketio.emit('log', {'msg': f"BẬT AUTO CƯỢC ({sess.base_bet:,} Win)", 'type': 'info'}, to=sid)
    # Chạy luồng auto bet ngầm
    socketio.start_background_task(auto_bet_worker, sid)

@socketio.on('stop_auto')
def handle_stop_auto():
    sid = request.sid
    sess = get_session(sid)
    sess.auto_bet = False
    socketio.emit('log', {'msg': "ĐÃ TẮT AUTO CƯỢC", 'type': 'error'}, to=sid)
    socketio.emit('state', {'auto_bet': False}, to=sid)

# ==========================================
# ROUTES
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
