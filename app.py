import os
import time
import json
import hashlib
import base64
import traceback
import requests
from flask import Flask, render_template, request
from flask_socketio import SocketIO
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'leminh_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ==========================================
# API ENDPOINTS (GIẢ LẬP TRÌNH DUYỆT)
# ==========================================
API_LOGIN_1 = "https://apifo88daigia.tele68.com/api?c=3&un={username}&pw={password_md5}&cp=R&cl=R&pf=web&at="
API_LOGIN_2 = "https://wlb.tele68.com/v1/lobby/auth/login?cp=R&cl=R&pf=web&at="

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://wtxmd52.tele68.com",
    "Referer": "https://wtxmd52.tele68.com/"
}

# ==========================================
# QUẢN LÝ PHIÊN
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

sessions = {}

def get_session(sid):
    if sid not in sessions:
        sessions[sid] = UserSession(sid)
    return sessions[sid]

# ==========================================
# LOGIC AUTO CƯỢC
# ==========================================
def auto_bet_worker(sid):
    sess = get_session(sid)
    if not sess.logged_in: return

    socketio.emit('log', {'msg': "Hệ thống Auto Cược đã khởi động!", 'type': 'info'}, to=sid)
    session_id = 1000000 
    
    while sess.auto_bet and sess.logged_in:
        try:
            # Tính cược X2 nếu thua
            if sess.win_streak < 0:
                sess.current_bet = sess.base_bet * (2 ** abs(sess.win_streak))
            else:
                sess.current_bet = sess.base_bet
            
            socketio.emit('log', {'msg': f"Phiên #{session_id} | Dự đoán: TÀI | Cược: {sess.current_bet:,}", 'type': 'info'}, to=sid)
            
            if sess.current_bet > sess.balance:
                socketio.emit('log', {'msg': "Số dư không đủ! Dừng Auto.", 'type': 'error'}, to=sid)
                sess.auto_bet = False
                break

            # (Đây là nơi gọi API đặt cược thật)
            socketio.emit('log', {'msg': "Đang gửi lệnh cược lên Server...", 'type': 'warn'}, to=sid)
            eventlet.sleep(2) # Giả lập chờ API
            
            # Giả lập kết quả 60% thắng
            is_win = (hashlib.md5(str(session_id).encode()).hexdigest()[0] in '0123456')
            
            if is_win:
                sess.balance += int(sess.current_bet * 0.98)
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

            # Cập nhật UI
            socketio.emit('state', {
                'balance': sess.balance,
                'ai_correct': sess.ai_correct,
                'ai_wrong': sess.ai_wrong,
                'auto_bet': sess.auto_bet
            }, to=sid)
            
            session_id += 1
            eventlet.sleep(4)
            
        except Exception as e:
            socketio.emit('log', {'msg': f"Lỗi Auto: {str(e)}", 'type': 'error'}, to=sid)
            eventlet.sleep(2)

# ==========================================
# SOCKET EVENTS
# ==========================================
@socketio.on('connect')
def on_connect():
    get_session(request.sid)

@socketio.on('login')
def handle_login(data):
    sid = request.sid
    sess = get_session(sid)
    
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    socketio.emit('log', {'msg': "Đang kết nối Server Game...", 'type': 'info'}, to=sid)
    
    try:
        pw_md5 = hashlib.md5(password.encode('utf-8')).hexdigest()
        url = API_LOGIN_1.format(username=username, password_md5=pw_md5)
        
        # Gọi API 1 với timeout 8s
        r = requests.get(url, headers=HEADERS, timeout=8)
        res = r.json()
        
        if not res.get("success"):
            socketio.emit('log', {'msg': f"Lỗi Game: {res.get('message', 'Sai tài khoản')}", 'type': 'error'}, to=sid)
            socketio.emit('login_failed', to=sid)
            return
            
        # Lấy sessionKey
        session_key = res.get("sessionKey")
        if not session_key:
            raise ValueError("Không có sessionKey từ API")
            
        session_key += "=" * ((4 - len(session_key) % 4) % 4)
        session_data = json.loads(base64.b64decode(session_key).decode('utf-8'))
        nick = session_data.get("nickname") or session_data.get("nickName", username)
        
        # Gọi API 2 lấy Token & Money
        payload = {"nickName": nick, "accessToken": res.get("accessToken")}
        r2 = requests.post(API_LOGIN_2, json=payload, headers=HEADERS, timeout=8)
        lobby = r2.json()
        
        token = lobby.get("token")
        if not token:
            raise ValueError("Không lấy được Token Lobby")
            
        sess.token = token
        sess.nickname = nick
        sess.balance = lobby.get("remoteLoginResp", {}).get("money", 0)
        sess.logged_in = True
        
        socketio.emit('log', {'msg': f"Đăng nhập OK: {nick} | Dư: {sess.balance:,} Win", 'type': 'success'}, to=sid)
        socketio.emit('login_success', {'nickname': nick, 'balance': sess.balance}, to=sid)
        
    except requests.exceptions.Timeout:
        socketio.emit('log', {'msg': "Lỗi: Server Game không phản hồi (Timeout).", 'type': 'error'}, to=sid)
        socketio.emit('login_failed', to=sid)
    except requests.exceptions.RequestException as e:
        socketio.emit('log', {'msg': f"Lỗi mạng: {str(e)}", 'type': 'error'}, to=sid)
        socketio.emit('login_failed', to=sid)
    except Exception as e:
        socketio.emit('log', {'msg': f"Lỗi hệ thống: {str(e)}", 'type': 'error'}, to=sid)
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
    # Dùng start_background_task của socketio
    socketio.start_background_task(auto_bet_worker, sid)

@socketio.on('stop_auto')
def handle_stop_auto():
    sid = request.sid
    sess = get_session(sid)
    sess.auto_bet = False
    socketio.emit('log', {'msg': "ĐÃ TẮT AUTO CƯỢC", 'type': 'error'}, to=sid)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
