import os
import traceback
import time
import json
import hashlib
import math
import threading
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

_FETCH_LOCK = threading.Lock()
_LAST_FETCH_TIME = 0.0
_LAST_FETCH_RESULT = ([], False)
_FETCH_CACHE_TTL = 15.0

SIGNAL_NAMES = {
    'markov': 'Markov', 'streak': 'Bẻ chuỗi', 'pattern': 'Khớp mẫu',
    'trend': 'Xu hướng', 'cycle': 'Chu kỳ', 'entropy': 'Entropy',
    'table13': 'Bảng 13 ký tự', 'cau': 'Bắt cầu',
    'dice_bias': 'Lệch xúc xắc', 'parity': 'Chẵn lẻ',
    'anti_streak': 'Chống chuỗi thua', 'alternation': 'Cầu đảo 1-1'
}

# ========== BẢNG TRA CỨU 13 KÝ TỰ ==========
TABLE_13_RAW = {
    "TTTTTTTTTTTTT": "Tài", "TTTTTTTTTTTTX": "Tài", "TTTTTTTTTTTXT": "Xỉu", "TTTTTTTTTTTXX": "Xỉu",
    "TTTTTTTTTTXTT": "Tài", "TTTTTTTTTTXTX": "Tài", "TTTTTTTTTTXXT": "Tài", "TTTTTTTTTTXXX": "Tài",
    "TTTTTTTTTXTTT": "Tài", "TTTTTTTTTXTTX": "Tài", "TTTTTTTTTXTXT": "Xỉu", "TTTTTTTTTXTXX": "Xỉu",
    "TTTTTTTTTXXTT": "Tài", "TTTTTTTTTXXTX": "Tài", "TTTTTTTTTXXXT": "Xỉu", "TTTTTTTTTXXXX": "Tài",
    "TTTTTTTTXTTTT": "Tài", "TTTTTTTTXTTTX": "Tài", "TTTTTTTTXTTXT": "Xỉu", "TTTTTTTTXTTXX": "Xỉu",
    "TTTTTTTTXTXTT": "Tài", "TTTTTTTTXTXTX": "Tài", "TTTTTTTTXTXXT": "Tài", "TTTTTTTTXTXXX": "Tài",
    "TTTTTTTTXXTTT": "Tài", "TTTTTTTTXXTTX": "Tài", "TTTTTTTTXXTXT": "Xỉu", "TTTTTTTTXXTXX": "Xỉu",
    "TTTTTTTTXXXTT": "Tài", "TTTTTTTTXXXTX": "Tài", "TTTTTTTTXXXXT": "Xỉu", "TTTTTTTTXXXXX": "Xỉu",
    "TTTTTTTXTTTTT": "Tài", "TTTTTTTXTTTTX": "Tài", "TTTTTTTXTTTXT": "Xỉu", "TTTTTTTXTTTXX": "Xỉu",
    "TTTTTTTXTTXTT": "Tài", "TTTTTTTXTTXTX": "Tài", "TTTTTTTXTTXXT": "Tài", "TTTTTTTXTTXXX": "Xỉu",
    "TTTTTTTXTXTTT": "Tài", "TTTTTTTXTXTTX": "Tài", "TTTTTTTXTXTXT": "Xỉu", "TTTTTTTXTXTXX": "Xỉu",
    "TTTTTTTXTXXTT": "Tài", "TTTTTTTXTXXTX": "Tài", "TTTTTTTXTXXXT": "Xỉu", "TTTTTTTXTXXXX": "Xỉu",
    "TTTTTTTXXTTTT": "Tài", "TTTTTTTXXTTTX": "Tài", "TTTTTTTXXTTXT": "Xỉu", "TTTTTTTXXTTXX": "Xỉu",
    "TTTTTTTXXTXTT": "Tài", "TTTTTTTXXTXTX": "Tài", "TTTTTTTXXTXXT": "Tài", "TTTTTTTXXTXXX": "Tài",
    "TTTTTTTXXXTTT": "Tài", "TTTTTTTXXXTTX": "Tài", "TTTTTTTXXXTXT": "Xỉu", "TTTTTTTXXXTXX": "Xỉu",
    "TTTTTTTXXXXTT": "Tài", "TTTTTTTXXXXTX": "Tài", "TTTTTTTXXXXXT": "Xỉu", "TTTTTTTXXXXXX": "Xỉu",
    "TTTTTTXTTTTTT": "Tài", "TTTTTTXTTTTTX": "Tài", "TTTTTTXTTTTXT": "Xỉu", "TTTTTTXTTTTXX": "Xỉu",
    "TTTTTTXTTTXTT": "Tài", "TTTTTTXTTTXTX": "Tài", "TTTTTTXTTTXXT": "Tài", "TTTTTTXTTTXXX": "Tài",
    "TTTTTTXTTXTTT": "Tài", "TTTTTTXTTXTTX": "Tài", "TTTTTTXTTXTXT": "Xỉu", "TTTTTTXTTXTXX": "Xỉu",
    "TTTTTTXTTXXTT": "Tài", "TTTTTTXTTXXTX": "Tài", "TTTTTTXTTXXXT": "Xỉu", "TTTTTTXTTXXXX": "Tài",
    "TTTTTTXTXTTTT": "Tài", "TTTTTTXTXTTTX": "Tài", "TTTTTTXTXTTXT": "Xỉu", "TTTTTTXTXTTXX": "Xỉu",
    "TTTTTTXTXTXTT": "Tài", "TTTTTTXTXTXTX": "Tài", "TTTTTTXTXTXXT": "Tài", "TTTTTTXTXTXXX": "Tài",
    "TTTTTTXTXXTTT": "Tài", "TTTTTTXTXXTTX": "Xỉu", "TTTTTTXTXXTXT": "Xỉu", "TTTTTTXTXXTXX": "Xỉu",
    "TTTTTTXTXXXTT": "Tài", "TTTTTTXTXXXTX": "Tài", "TTTTTTXTXXXXT": "Xỉu", "TTTTTTXTXXXXX": "Xỉu",
    "TTTTTTXXTTTTT": "Tài", "TTTTTTXXTTTTX": "Tài", "TTTTTTXXTTTXT": "Xỉu", "TTTTTTXXTTTXX": "Xỉu",
    "TTTTTTXXTTXTT": "Tài", "TTTTTTXXTTXTX": "Tài", "TTTTTTXXTTXXT": "Tài", "TTTTTTXXTTXXX": "Xỉu",
    "TTTTTTXXTXTTT": "Tài", "TTTTTTXXTXTTX": "Tài", "TTTTTTXXTXTXT": "Xỉu", "TTTTTTXXTXTXX": "Xỉu",
    "TTTTTTXXTXXTT": "Tài", "TTTTTTXXTXXTX": "Tài", "TTTTTTXXTXXXT": "Xỉu", "TTTTTTXXTXXXX": "Xỉu",
    "TTTTTTXXXTTTT": "Tài", "TTTTTTXXXTTTX": "Tài", "TTTTTTXXXTTXT": "Xỉu", "TTTTTTXXXTTXX": "Xỉu",
    "TTTTTTXXXTXTT": "Tài", "TTTTTTXXXTXTX": "Tài", "TTTTTTXXXTXXT": "Tài", "TTTTTTXXXTXXX": "Xỉu",
    "TTTTTTXXXXTTT": "Tài", "TTTTTTXXXXTTX": "Tài", "TTTTTTXXXXTXT": "Xỉu", "TTTTTTXXXXTXX": "Xỉu",
    "TTTTTTXXXXXTT": "Tài", "TTTTTTXXXXXTX": "Tài", "TTTTTTXXXXXXT": "Xỉu", "TTTTTTXXXXXXX": "Xỉu",
    "TTTTTXTTTTTTT": "Tài", "TTTTTXTTTTTTX": "Tài", "TTTTTXTTTTTXT": "Xỉu", "TTTTTXTTTTTXX": "Xỉu",
    "TTTTTXTTTTXTT": "Tài", "TTTTTXTTTTXTX": "Tài", "TTTTTXTTTTXXT": "Tài", "TTTTTXTTTTXXX": "Tài",
    "TTTTTXTTTXTTT": "Tài", "TTTTTXTTTXTTX": "Tài", "TTTTTXTTTXTXT": "Xỉu", "TTTTTXTTTXTXX": "Xỉu",
    "TTTTTXTTTXXTT": "Tài", "TTTTTXTTTXXTX": "Tài", "TTTTTXTTTXXXT": "Xỉu", "TTTTTXTTTXXXX": "Tài",
    "TTTTTXTTXTTTT": "Tài", "TTTTTXTTXTTTX": "Tài", "TTTTTXTTXTTXT": "Xỉu", "TTTTTXTTXTTXX": "Xỉu",
    "TTTTTXTTXTXTT": "Tài", "TTTTTXTTXTXTX": "Tài", "TTTTTXTTXTXXT": "Xỉu", "TTTTTXTTXTXXX": "Xỉu",
    "TTTTTXTTXXTTT": "Tài", "TTTTTXTTXXTTX": "Tài", "TTTTTXTTXXTXT": "Xỉu", "TTTTTXTTXXTXX": "Xỉu",
    "TTTTTXTTXXXTT": "Tài", "TTTTTXTTXXXTX": "Tài", "TTTTTXTTXXXXT": "Xỉu", "TTTTTXTTXXXXX": "Xỉu",
    "TTTTTXTXTTTTT": "Tài", "TTTTTXTXTTTTX": "Tài", "TTTTTXTXTTTXT": "Xỉu", "TTTTTXTXTTTXX": "Xỉu",
    "TTTTTXTXTTXTT": "Tài", "TTTTTXTXTTXTX": "Tài", "TTTTTXTXTTXXT": "Tài", "TTTTTXTXTTXXX": "Xỉu",
    "TTTTTXTXTXTTT": "Tài", "TTTTTXTXTXTTX": "Tài", "TTTTTXTXTXTXT": "Xỉu", "TTTTTXTXTXTXX": "Xỉu",
    "TTTTTXTXTXXTT": "Tài", "TTTTTXTXTXXTX": "Tài", "TTTTTXTXTXXXT": "Xỉu", "TTTTTXTXTXXXX": "Tài",
    "TTTTTXTXXTTTT": "Tài", "TTTTTXTXXTTTX": "Tài", "TTTTTXTXXTTXT": "Xỉu", "TTTTTXTXXTTXX": "Xỉu",
    "TTTTTXTXXTXTT": "Tài", "TTTTTXTXXTXTX": "Tài", "TTTTTXTXXTXXT": "Tài", "TTTTTXTXXTXXX": "Tài",
    "TTTTTXTXXXTTT": "Xỉu", "TTTTTXTXXXTTX": "Tài", "TTTTTXTXXXTXT": "Xỉu", "TTTTTXTXXXTXX": "Xỉu",
    "TTTTTXTXXXXTT": "Tài", "TTTTTXTXXXXTX": "Tài", "TTTTTXTXXXXXT": "Xỉu", "TTTTTXTXXXXXX": "Xỉu",
    "TTTTTXXTTTTTT": "Tài", "TTTTTXXTTTTTX": "Tài", "TTTTTXXTTTTXT": "Xỉu", "TTTTTXXTTTTXX": "Xỉu",
    "TTTTTXXTTTXTT": "Tài", "TTTTTXXTTTXTX": "Tài", "TTTTTXXTTTXXT": "Xỉu", "TTTTTXXTTTXXX": "Xỉu",
    "TTTTTXXTTXTTT": "Tài", "TTTTTXXTTXTTX": "Xỉu", "TTTTTXXTTXTXT": "Xỉu", "TTTTTXXTTXTXX": "Xỉu",
    "TTTTTXXTTXXTT": "Tài", "TTTTTXXTTXXTX": "Tài", "TTTTTXXTTXXXT": "Xỉu", "TTTTTXXTTXXXX": "Xỉu",
    "TTTTTXXTXTTTT": "Tài", "TTTTTXXTXTTTX": "Tài", "TTTTTXXTXTTXT": "Xỉu", "TTTTTXXTXTTXX": "Xỉu",
    "TTTTTXXTXTXTT": "Tài", "TTTTTXXTXTXTX": "Tài", "TTTTTXXTXTXXT": "Tài", "TTTTTXXTXTXXX": "Xỉu",
    "TTTTTXXTXXTTT": "Tài", "TTTTTXXTXXTTX": "Xỉu", "TTTTTXXTXXTXT": "Xỉu", "TTTTTXXTXXTXX": "Xỉu",
    "TTTTTXXTXXXTT": "Tài", "TTTTTXXTXXXTX": "Tài", "TTTTTXXTXXXXT": "Xỉu", "TTTTTXXTXXXXX": "Xỉu",
    "TTTTTXXXTTTTT": "Tài", "TTTTTXXXTTTTX": "Tài", "TTTTTXXXTTTXT": "Xỉu", "TTTTTXXXTTTXX": "Xỉu",
    "TTTTTXXXTTXTT": "Tài", "TTTTTXXXTTXTX": "Tài", "TTTTTXXXTTXXT": "Xỉu", "TTTTTXXXTTXXX": "Xỉu",
    "TTTTTXXXTXTTT": "Xỉu", "TTTTTXXXTXTTX": "Tài", "TTTTTXXXTXTXT": "Xỉu", "TTTTTXXXTXTXX": "Xỉu",
    "TTTTTXXXTXXTT": "Tài", "TTTTTXXXTXXTX": "Tài", "TTTTTXXXTXXXT": "Xỉu", "TTTTTXXXTXXXX": "Xỉu",
    "TTTTTXXXXTTTT": "Tài", "TTTTTXXXXTTTX": "Tài", "TTTTTXXXXTTXT": "Xỉu", "TTTTTXXXXTTXX": "Xỉu",
    "TTTTTXXXXTXTT": "Tài", "TTTTTXXXXTXTX": "Tài", "TTTTTXXXXTXXT": "Xỉu", "TTTTTXXXXTXXX": "Tài",
    "TTTTTXXXXXTTT": "Xỉu", "TTTTTXXXXXTTX": "Tài", "TTTTTXXXXXTXT": "Xỉu", "TTTTTXXXXXTXX": "Xỉu",
    "TTTTTXXXXXXTT": "Tài", "TTTTTXXXXXXTX": "Tài", "TTTTTXXXXXXXT": "Xỉu", "TTTTTXXXXXXXX": "Xỉu",
    "TTTTXTTTTTTTT": "Tài", "TTTTXTTTTTTTX": "Tài", "TTTTXTTTTTTXT": "Xỉu", "TTTTXTTTTTTXX": "Xỉu",
    "TTTTXTTTTTXTT": "Tài", "TTTTXTTTTTXTX": "Tài", "TTTTXTTTTTXXT": "Tài", "TTTTXTTTTTXXX": "Xỉu",
    "TTTTXTTTTXTTT": "Tài", "TTTTXTTTTXTTX": "Tài", "TTTTXTTTTXTXT": "Xỉu", "TTTTXTTTTXTXX": "Xỉu",
    "TTTTXTTTTXXTT": "Tài", "TTTTXTTTTXXTX": "Tài", "TTTTXTTTTXXXT": "Xỉu", "TTTTXTTTTXXXX": "Tài",
    "TTTTXTTTXTTTT": "Tài", "TTTTXTTTXTTTX": "Tài", "TTTTXTTTXTTXT": "Xỉu", "TTTTXTTTXTTXX": "Xỉu",
    "TTTTXTTTXTXTT": "Tài", "TTTTXTTTXTXTX": "Tài", "TTTTXTTTXTXXT": "Tài", "TTTTXTTTXTXXX": "Tài",
    "TTTTXTTTXXTTT": "Tài", "TTTTXTTTXXTTX": "Tài", "TTTTXTTTXXTXT": "Xỉu", "TTTTXTTTXXTXX": "Xỉu",
    "TTTTXTTTXXXTT": "Tài", "TTTTXTTTXXXTX": "Tài", "TTTTXTTTXXXXT": "Xỉu", "TTTTXTTTXXXXX": "Xỉu",
    "TTTTXTTXTTTTT": "Tài", "TTTTXTTXTTTTX": "Tài", "TTTTXTTXTTTXT": "Xỉu", "TTTTXTTXTTTXX": "Xỉu",
    "TTTTXTTXTTXTT": "Tài", "TTTTXTTXTTXTX": "Tài", "TTTTXTTXTTXXT": "Xỉu", "TTTTXTTXTTXXX": "Tài",
    "TTTTXTTXTXTTT": "Tài", "TTTTXTTXTXTTX": "Tài", "TTTTXTTXTXTXT": "Xỉu", "TTTTXTTXTXTXX": "Xỉu",
    "TTTTXTTXTXXTT": "Tài", "TTTTXTTXTXXTX": "Tài", "TTTTXTTXTXXXT": "Xỉu", "TTTTXTTXTXXXX": "Xỉu",
    "TTTTXTTXXTTTT": "Tài", "TTTTXTTXXTTTX": "Tài", "TTTTXTTXXTTXT": "Xỉu", "TTTTXTTXXTTXX": "Xỉu",
    "TTTTXTTXXTXTT": "Tài", "TTTTXTTXXTXTX": "Tài", "TTTTXTTXXTXXT": "Tài", "TTTTXTTXXTXXX": "Tài",
    "TTTTXTTXXXTTT": "Tài", "TTTTXTTXXXTTX": "Tài", "TTTTXTTXXXTXT": "Xỉu", "TTTTXTTXXXTXX": "Xỉu",
    "TTTTXTTXXXXTT": "Tài", "TTTTXTTXXXXTX": "Tài", "TTTTXTTXXXXXT": "Xỉu", "TTTTXTTXXXXXX": "Xỉu",
    "TTTTXTXTTTTTT": "Tài", "TTTTXTXTTTTTX": "Tài", "TTTTXTXTTTTXT": "Xỉu", "TTTTXTXTTTTXX": "Xỉu",
    "TTTTXTXTTTXTT": "Tài", "TTTTXTXTTTXTX": "Tài", "TTTTXTXTTTXXT": "Tài", "TTTTXTXTTTXXX": "Xỉu",
    "TTTTXTXTTXTTT": "Tài", "TTTTXTXTTXTTX": "Xỉu", "TTTTXTXTTXTXT": "Xỉu", "TTTTXTXTTXTXX": "Xỉu",
    "TTTTXTXTTXXTT": "Tài", "TTTTXTXTTXXTX": "Tài", "TTTTXTXTTXXXT": "Xỉu", "TTTTXTXTTXXXX": "Xỉu",
    "TTTTXTXTXTTTT": "Tài", "TTTTXTXTXTTTX": "Tài", "TTTTXTXTXTTXT": "Xỉu", "TTTTXTXTXTTXX": "Xỉu",
    "TTTTXTXTXTXTT": "Tài", "TTTTXTXTXTXTX": "Tài", "TTTTXTXTXTXXT": "Xỉu", "TTTTXTXTXTXXX": "Xỉu",
    "TTTTXTXTXXTTT": "Xỉu", "TTTTXTXTXXTTX": "Xỉu", "TTTTXTXTXXTXT": "Xỉu", "TTTTXTXTXXTXX": "Xỉu",
    "TTTTXTXTXXXTT": "Tài", "TTTTXTXTXXXTX": "Tài", "TTTTXTXTXXXXT": "Xỉu", "TTTTXTXTXXXXX": "Xỉu",
    "TTTTXTXXTTTTT": "Tài", "TTTTXTXXTTTTX": "Tài", "TTTTXTXXTTTXT": "Xỉu", "TTTTXTXXTTTXX": "Xỉu",
    "TTTTXTXXTTXTT": "Tài", "TTTTXTXXTTXTX": "Tài", "TTTTXTXXTTXXT": "Xỉu", "TTTTXTXXTTXXX": "Xỉu",
    "TTTTXTXXTXTTT": "Tài", "TTTTXTXXTXTTX": "Xỉu", "TTTTXTXXTXTXT": "Xỉu", "TTTTXTXXTXTXX": "Xỉu",
    "TTTTXTXXTXXTT": "Tài", "TTTTXTXXTXXTX": "Tài", "TTTTXTXXTXXXT": "Xỉu", "TTTTXTXXTXXXX": "Xỉu",
    "TTTTXTXXXTTTT": "Xỉu", "TTTTXTXXXTTTX": "Tài", "TTTTXTXXXTTXT": "Xỉu", "TTTTXTXXXTTXX": "Xỉu",
    "TTTTXTXXXTXTT": "Tài", "TTTTXTXXXTXTX": "Tài", "TTTTXTXXXTXXT": "Xỉu", "TTTTXTXXXTXXX": "Xỉu",
    "TTTTXTXXXXTTT": "Tài", "TTTTXTXXXXTTX": "Tài", "TTTTXTXXXXTXT": "Xỉu", "TTTTXTXXXXTXX": "Xỉu",
    "TTTTXTXXXXXTT": "Tài", "TTTTXTXXXXXTX": "Tài", "TTTTXTXXXXXXT": "Xỉu", "TTTTXTXXXXXXX": "Xỉu",
    "TTTTXXTTTTTTT": "Tài", "TTTTXXTTTTTTX": "Tài", "TTTTXXTTTTTXT": "Xỉu", "TTTTXXTTTTTXX": "Xỉu",
    "TTTTXXTTTTXTT": "Tài", "TTTTXXTTTTXTX": "Tài", "TTTTXXTTTTXXT": "Xỉu", "TTTTXXTTTTXXX": "Tài",
    "TTTTXXTTTXTTT": "Tài", "TTTTXXTTTXTTX": "Xỉu", "TTTTXXTTTXTXT": "Xỉu", "TTTTXXTTTXTXX": "Xỉu",
    "TTTTXXTTTXXTT": "Tài", "TTTTXXTTTXXTX": "Tài", "TTTTXXTTTXXXT": "Xỉu", "TTTTXXTTTXXXX": "Tài",
    "TTTTXXTTXTTTT": "Tài", "TTTTXXTTXTTTX": "Tài", "TTTTXXTTXTTXT": "Xỉu", "TTTTXXTTXTTXX": "Xỉu",
    "TTTTXXTTXTXTT": "Tài", "TTTTXXTTXTXTX": "Tài", "TTTTXXTTXTXXT": "Tài", "TTTTXXTTXTXXX": "Xỉu",
    "TTTTXXTTXXTTT": "Xỉu", "TTTTXXTTXXTTX": "Xỉu", "TTTTXXTTXXTXT": "Xỉu", "TTTTXXTTXXTXX": "Xỉu",
    "TTTTXXTTXXXTT": "Tài", "TTTTXXTTXXXTX": "Tài", "TTTTXXTTXXXXT": "Xỉu", "TTTTXXTTXXXXX": "Xỉu",
    "TTTTXXTXTTTTT": "Tài", "TTTTXXTXTTTTX": "Tài", "TTTTXXTXTTTXT": "Xỉu", "TTTTXXTXTTTXX": "Xỉu",
    "TTTTXXTXTTXTT": "Tài", "TTTTXXTXTTXTX": "Tài", "TTTTXXTXTTXXT": "Xỉu", "TTTTXXTXTTXXX": "Xỉu",
    "TTTTXXTXTXTTT": "Tài", "TTTTXXTXTXTTX": "Xỉu", "TTTTXXTXTXTXT": "Xỉu", "TTTTXXTXTXTXX": "Xỉu",
    "TTTTXXTXTXXTT": "Tài", "TTTTXXTXTXXTX": "Tài", "TTTTXXTXTXXXT": "Xỉu", "TTTTXXTXTXXXX": "Xỉu",
    "TTTTXXTXXTTTT": "Xỉu", "TTTTXXTXXTTTX": "Tài", "TTTTXXTXXTTXT": "Xỉu", "TTTTXXTXXTTXX": "Xỉu",
    "TTTTXXTXXTXTT": "Tài", "TTTTXXTXXTXTX": "Tài", "TTTTXXTXXTXXT": "Tài", "TTTTXXTXXTXXX": "Tài",
    "TTTTXXTXXXTTT": "Xỉu", "TTTTXXTXXXTTX": "Xỉu", "TTTTXXTXXXTXT": "Xỉu", "TTTTXXTXXXTXX": "Xỉu",
    "TTTTXXTXXXXTT": "Tài", "TTTTXXTXXXXTX": "Tài", "TTTTXXTXXXXXT": "Xỉu", "TTTTXXTXXXXXX": "Xỉu",
    "TTTTXXXTTTTTT": "Tài", "TTTTXXXTTTTTX": "Tài", "TTTTXXXTTTTXT": "Xỉu", "TTTTXXXTTTTXX": "Xỉu",
    "TTTTXXXTTTXTT": "Tài", "TTTTXXXTTTXTX": "Tài", "TTTTXXXTTTXXT": "Xỉu", "TTTTXXXTTTXXX": "Xỉu",
    "TTTTXXXTTXTTT": "Tài", "TTTTXXXTTXTTX": "Xỉu", "TTTTXXXTTXTXT": "Xỉu", "TTTTXXXTTXTXX": "Xỉu",
    "TTTTXXXTTXXTT": "Tài", "TTTTXXXTTXXTX": "Tài", "TTTTXXXTTXXXT": "Xỉu", "TTTTXXXTTXXXX": "Tài",
    "TTTTXXXTXTTTT": "Tài", "TTTTXXXTXTTTX": "Tài", "TTTTXXXTXTTXT": "Xỉu", "TTTTXXXTXTTXX": "Xỉu",
    "TTTTXXXTXTXTT": "Tài", "TTTTXXXTXTXTX": "Tài", "TTTTXXXTXTXXT": "Xỉu", "TTTTXXXTXTXXX": "Tài",
    "TTTTXXXTXXTTT": "Xỉu", "TTTTXXXTXXTTX": "Tài", "TTTTXXXTXXTXT": "Xỉu", "TTTTXXXTXXTXX": "Xỉu",
    "TTTTXXXTXXXTT": "Tài", "TTTTXXXTXXXTX": "Tài", "TTTTXXXTXXXXT": "Xỉu", "TTTTXXXTXXXXX": "Xỉu",
    "TTTTXXXXTTTTT": "Tài", "TTTTXXXXTTTTX": "Tài", "TTTTXXXXTTTXT": "Xỉu", "TTTTXXXXTTTXX": "Xỉu",
    "TTTTXXXXTTXTT": "Tài", "TTTTXXXXTTXTX": "Tài", "TTTTXXXXTTXXT": "Xỉu", "TTTTXXXXTTXXX": "Tài",
    "TTTTXXXXTXTTT": "Tài", "TTTTXXXXTXTTX": "Xỉu", "TTTTXXXXTXTXT": "Xỉu", "TTTTXXXXTXTXX": "Xỉu",
    "TTTTXXXXTXXTT": "Tài", "TTTTXXXXTXXTX": "Tài", "TTTTXXXXTXXXT": "Xỉu", "TTTTXXXXTXXXX": "Tài",
    "TTTTXXXXXTTTT": "Tài", "TTTTXXXXXTTTX": "Tài", "TTTTXXXXXTTXT": "Xỉu", "TTTTXXXXXTTXX": "Xỉu",
    "TTTTXXXXXTXTT": "Tài", "TTTTXXXXXTXTX": "Tài", "TTTTXXXXXTXXT": "Tài", "TTTTXXXXXTXXX": "Xỉu",
    "TTTTXXXXXXTTT": "Tài", "TTTTXXXXXXTTX": "Tài", "TTTTXXXXXXTXT": "Xỉu", "TTTTXXXXXXTXX": "Xỉu",
    "TTTTXXXXXXXTT": "Tài", "TTTTXXXXXXXTX": "Tài", "TTTTXXXXXXXXT": "Xỉu", "TTTTXXXXXXXXX": "Xỉu",
    "TTTXTTTTTTTTT": "Tài", "TTTXTTTTTTTTX": "Tài", "TTTXTTTTTTTXT": "Xỉu", "TTTXTTTTTTTXX": "Xỉu",
    "TTTXTTTTTTXTT": "Tài", "TTTXTTTTTTXTX": "Tài", "TTTXTTTTTTXXT": "Tài", "TTTXTTTTTTXXX": "Tài",
    "TTTXTTTTTXTTT": "Tài", "TTTXTTTTTXTTX": "Tài", "TTTXTTTTTXTXT": "Xỉu", "TTTXTTTTTXTXX": "Xỉu",
    "TTTXTTTTTXXTT": "Tài", "TTTXTTTTTXXTX": "Tài", "TTTXTTTTTXXXT": "Xỉu", "TTTXTTTTTXXXX": "Tài",
    "TTTXTTTTXTTTT": "Tài", "TTTXTTTTXTTTX": "Tài", "TTTXTTTTXTTXT": "Xỉu", "TTTXTTTTXTTXX": "Xỉu",
    "TTTXTTTTXTXTT": "Tài", "TTTXTTTTXTXTX": "Tài", "TTTXTTTTXTXXT": "Tài", "TTTXTTTTXTXXX": "Tài",
    "TTTXTTTTXXTTT": "Tài", "TTTXTTTTXXTTX": "Tài", "TTTXTTTTXXTXT": "Xỉu", "TTTXTTTTXXTXX": "Xỉu",
    "TTTXTTTTXXXTT": "Tài", "TTTXTTTTXXXTX": "Tài", "TTTXTTTTXXXXT": "Xỉu", "TTTXTTTTXXXXX": "Xỉu",
    "TTTXTTTXTTTTT": "Tài", "TTTXTTTXTTTTX": "Tài", "TTTXTTTXTTTXT": "Xỉu", "TTTXTTTXTTTXX": "Xỉu",
    "TTTXTTTXTTXTT": "Tài", "TTTXTTTXTTXTX": "Tài", "TTTXTTTXTTXXT": "Xỉu", "TTTXTTTXTTXXX": "Xỉu",
    "TTTXTTTXTXTTT": "Tài", "TTTXTTTXTXTTX": "Xỉu", "TTTXTTTXTXTXT": "Xỉu", "TTTXTTTXTXTXX": "Xỉu",
    "TTTXTTTXTXXTT": "Tài", "TTTXTTTXTXXTX": "Tài", "TTTXTTTXTXXXT": "Xỉu", "TTTXTTTXTXXXX": "Tài",
    "TTTXTTTXXTTTT": "Tài", "TTTXTTTXXTTTX": "Tài", "TTTXTTTXXTTXT": "Xỉu", "TTTXTTTXXTTXX": "Xỉu",
    "TTTXTTTXXTXTT": "Tài", "TTTXTTTXXTXTX": "Tài", "TTTXTTTXXTXXT": "Tài", "TTTXTTTXXTXXX": "Xỉu",
    "TTTXTTTXXXTTT": "Tài", "TTTXTTTXXXTTX": "Xỉu", "TTTXTTTXXXTXT": "Xỉu", "TTTXTTTXXXTXX": "Xỉu",
    "TTTXTTTXXXXTT": "Tài", "TTTXTTTXXXXTX": "Tài", "TTTXTTTXXXXXT": "Xỉu", "TTTXTTTXXXXXX": "Xỉu",
    "TTTXTTXTTTTTT": "Tài", "TTTXTTXTTTTTX": "Tài", "TTTXTTXTTTTXT": "Xỉu", "TTTXTTXTTTTXX": "Xỉu",
    "TTTXTTXTTTXTT": "Tài", "TTTXTTXTTTXTX": "Tài", "TTTXTTXTTTXXT": "Xỉu", "TTTXTTXTTTXXX": "Tài",
    "TTTXTTXTTXTTT": "Tài", "TTTXTTXTTXTTX": "Xỉu", "TTTXTTXTTXTXT": "Xỉu", "TTTXTTXTTXTXX": "Xỉu",
    "TTTXTTXTTXXTT": "Tài", "TTTXTTXTTXXTX": "Tài", "TTTXTTXTTXXXT": "Xỉu", "TTTXTTXTTXXXX": "Xỉu",
    "TTTXTTXTXTTTT": "Tài", "TTTXTTXTXTTTX": "Tài", "TTTXTTXTXTTXT": "Xỉu", "TTTXTTXTXTTXX": "Xỉu",
    "TTTXTTXTXTXTT": "Tài", "TTTXTTXTXTXTX": "Tài", "TTTXTTXTXTXXT": "Tài", "TTTXTTXTXTXXX": "Xỉu",
    "TTTXTTXTXXTTT": "Tài", "TTTXTTXTXXTTX": "Xỉu", "TTTXTTXTXXTXT": "Xỉu", "TTTXTTXTXXTXX": "Xỉu",
    "TTTXTTXTXXXTT": "Tài", "TTTXTTXTXXXTX": "Tài", "TTTXTTXTXXXXT": "Xỉu", "TTTXTTXTXXXXX": "Xỉu",
    "TTTXTTXXTTTTT": "Tài", "TTTXTTXXTTTTX": "Tài", "TTTXTTXXTTTXT": "Xỉu", "TTTXTTXXTTTXX": "Xỉu",
    "TTTXTTXXTTXTT": "Tài", "TTTXTTXXTTXTX": "Tài", "TTTXTTXXTTXXT": "Xỉu", "TTTXTTXXTTXXX": "Xỉu",
    "TTTXTTXXTXTTT": "Tài", "TTTXTTXXTXTTX": "Tài", "TTTXTTXXTXTXT": "Xỉu", "TTTXTTXXTXTXX": "Xỉu",
    "TTTXTTXXTXXTT": "Tài", "TTTXTTXXTXXTX": "Tài", "TTTXTTXXTXXXT": "Xỉu", "TTTXTTXXTXXXX": "Xỉu",
    "TTTXTTXXXTTTT": "Xỉu", "TTTXTTXXXTTTX": "Tài", "TTTXTTXXXTTXT": "Xỉu", "TTTXTTXXXTTXX": "Xỉu",
    "TTTXTTXXXTXTT": "Tài", "TTTXTTXXXTXTX": "Tài", "TTTXTTXXXTXXT": "Xỉu", "TTTXTTXXXTXXX": "Xỉu",
    "TTTXTTXXXXTTT": "Xỉu", "TTTXTTXXXXTTX": "Tài", "TTTXTTXXXXTXT": "Xỉu", "TTTXTTXXXXTXX": "Xỉu",
    "TTTXTTXXXXXTT": "Tài", "TTTXTTXXXXXTX": "Tài", "TTTXTTXXXXXXT": "Xỉu", "TTTXTTXXXXXXX": "Xỉu",
    "TTTXTXTTTTTTT": "Tài", "TTTXTXTTTTTTX": "Tài", "TTTXTXTTTTTXT": "Xỉu", "TTTXTXTTTTTXX": "Xỉu",
    "TTTXTXTTTTXTT": "Tài", "TTTXTXTTTTXTX": "Tài", "TTTXTXTTTTXXT": "Tài", "TTTXTXTTTTXXX": "Xỉu",
    "TTTXTXTTTXTTT": "Tài", "TTTXTXTTTXTTX": "Tài", "TTTXTXTTTXTXT": "Xỉu", "TTTXTXTTTXTXX": "Xỉu",
    "TTTXTXTTTXXTT": "Tài", "TTTXTXTTTXXTX": "Tài", "TTTXTXTTTXXXT": "Xỉu", "TTTXTXTTTXXXX": "Xỉu",
    "TTTXTXTTXTTTT": "Tài", "TTTXTXTTXTTTX": "Tài", "TTTXTXTTXTTXT": "Xỉu", "TTTXTXTTXTTXX": "Xỉu",
    "TTTXTXTTXTXTT": "Tài", "TTTXTXTTXTXTX": "Tài", "TTTXTXTTXTXXT": "Tài", "TTTXTXTTXTXXX": "Tài",
    "TTTXTXTTXXTTT": "Xỉu", "TTTXTXTTXXTTX": "Tài", "TTTXTXTTXXTXT": "Xỉu", "TTTXTXTTXXTXX": "Xỉu",
    "TTTXTXTTXXXTT": "Tài", "TTTXTXTTXXXTX": "Tài", "TTTXTXTTXXXXT": "Xỉu", "TTTXTXTTXXXXX": "Xỉu",
    "TTTXTXTXTTTTT": "Tài", "TTTXTXTXTTTTX": "Tài", "TTTXTXTXTTTXT": "Xỉu", "TTTXTXTXTTTXX": "Xỉu",
    "TTTXTXTXTTXTT": "Tài", "TTTXTXTXTTXTX": "Tài", "TTTXTXTXTTXXT": "Xỉu", "TTTXTXTXTTXXX": "Xỉu",
    "TTTXTXTXTXTTT": "Xỉu", "TTTXTXTXTXTTX": "Xỉu", "TTTXTXTXTXTXT": "Xỉu", "TTTXTXTXTXTXX": "Xỉu",
    "TTTXTXTXTXXTT": "Tài", "TTTXTXTXTXXTX": "Tài", "TTTXTXTXTXXXT": "Xỉu", "TTTXTXTXTXXXX": "Xỉu",
    "TTTXTXTXXTTTT": "Xỉu", "TTTXTXTXXTTTX": "Tài", "TTTXTXTXXTTXT": "Xỉu", "TTTXTXTXXTTXX": "Xỉu",
    "TTTXTXTXXTXTT": "Tài", "TTTXTXTXXTXTX": "Tài", "TTTXTXTXXTXXT": "Xỉu", "TTTXTXTXXTXXX": "Tài",
    "TTTXTXTXXXTTT": "Tài", "TTTXTXTXXXTTX": "Xỉu", "TTTXTXTXXXTXT": "Xỉu", "TTTXTXTXXXTXX": "Xỉu",
    "TTTXTXTXXXXTT": "Tài", "TTTXTXTXXXXTX": "Tài", "TTTXTXTXXXXXT": "Xỉu", "TTTXTXTXXXXXX": "Xỉu",
    "TTTXTXXTTTTTT": "Tài", "TTTXTXXTTTTTX": "Tài", "TTTXTXXTTTTXT": "Xỉu", "TTTXTXXTTTTXX": "Xỉu",
    "TTTXTXXTTTXTT": "Tài", "TTTXTXXTTTXTX": "Tài", "TTTXTXXTTTXXT": "Xỉu", "TTTXTXXTTTXXX": "Tài",
    "TTTXTXXTTXTTT": "Tài", "TTTXTXXTTXTTX": "Xỉu", "TTTXTXXTTXTXT": "Xỉu", "TTTXTXXTTXTXX": "Xỉu",
    "TTTXTXXTTXXTT": "Tài", "TTTXTXXTTXXTX": "Tài", "TTTXTXXTTXXXT": "Xỉu", "TTTXTXXTTXXXX": "Tài",
    "TTTXTXXTXTTTT": "Xỉu", "TTTXTXXTXTTTX": "Tài", "TTTXTXXTXTTXT": "Xỉu", "TTTXTXXTXTTXX": "Xỉu",
    "TTTXTXXTXTXTT": "Tài", "TTTXTXXTXTXTX": "Tài", "TTTXTXXTXTXXT": "Xỉu", "TTTXTXXTXTXXX": "Xỉu",
    "TTTXTXXTXXTTT": "Xỉu", "TTTXTXXTXXTTX": "Xỉu", "TTTXTXXTXXTXT": "Xỉu", "TTTXTXXTXXTXX": "Xỉu",
    "TTTXTXXTXXXTT": "Tài", "TTTXTXXTXXXTX": "Tài", "TTTXTXXTXXXXT": "Xỉu", "TTTXTXXTXXXXX": "Xỉu",
    "TTTXTXXXTTTTT": "Tài", "TTTXTXXXTTTTX": "Tài", "TTTXTXXXTTTXT": "Xỉu", "TTTXTXXXTTTXX": "Xỉu",
    "TTTXTXXXTTXTT": "Tài", "TTTXTXXXTTXTX": "Tài", "TTTXTXXXTTXXT": "Xỉu", "TTTXTXXXTTXXX": "Xỉu",
    "TTTXTXXXTXTTT": "Tài", "TTTXTXXXTXTTX": "Tài", "TTTXTXXXTXTXT": "Xỉu", "TTTXTXXXTXTXX": "Xỉu",
    "TTTXTXXXTXXTT": "Tài", "TTTXTXXXTXXTX": "Tài", "TTTXTXXXTXXXT": "Xỉu", "TTTXTXXXTXXXX": "Xỉu",
    "TTTXTXXXXTTTT": "Tài", "TTTXTXXXXTTTX": "Tài", "TTTXTXXXXTTXT": "Xỉu", "TTTXTXXXXTTXX": "Xỉu",
    "TTTXTXXXXTXTT": "Tài", "TTTXTXXXXTXTX": "Tài", "TTTXTXXXXTXXT": "Tài", "TTTXTXXXXTXXX": "Tài",
    "TTTXTXXXXXTTT": "Xỉu", "TTTXTXXXXXTTX": "Xỉu", "TTTXTXXXXXTXT": "Xỉu", "TTTXTXXXXXTXX": "Xỉu",
    "TTTXTXXXXXXTT": "Tài", "TTTXTXXXXXXTX": "Tài", "TTTXTXXXXXXXT": "Xỉu", "TTTXTXXXXXXXX": "Xỉu",
}

TABLE_13 = dict(TABLE_13_RAW)
for pat, res in list(TABLE_13_RAW.items()):
    if pat.startswith('X'):
        continue
    mirrored = pat.replace('T', 'Z').replace('X', 'T').replace('Z', 'X')
    if mirrored not in TABLE_13:
        TABLE_13[mirrored] = "Tài" if res == "Xỉu" else "Xỉu"

def _lookup_table13(seq_str):
    if len(seq_str) < 13:
        return None, 0, 0
    res = TABLE_13.get(seq_str[-13:])
    if res is None:
        return None, 0, 0
    return res, 78, 1.55

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

def _detect_regime(seq):
    if len(seq) < 12: return 'random', 0.0
    runs = _runs(seq[-22:])
    if not runs: return 'random', 0.0
    L = [l for _, l in runs]; n = len(L)
    ones = sum(1 for l in L if l == 1) / n
    longs = sum(1 for l in L if l >= 4) / n
    short = sum(1 for l in L if 2 <= l <= 3) / n
    if ones >= 0.55: return 'alternation', ones
    if longs >= 0.35: return 'streak', longs
    if short >= 0.65: return 'short_run', short
    return 'random', 0.0

def _to_seq_str(seq):
    return ''.join('T' if x == 'Tài' else 'X' for x in seq)

def _generate_dice(prediction, confidence, seed_str=None):
    if seed_str is None: seed_str = str(time.time())
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    rng = random.Random(h)

    if prediction == 'Tài':
        if confidence >= 75: target = rng.randint(13, 17)
        elif confidence >= 65: target = rng.randint(12, 15)
        else: target = rng.randint(11, 13)
    else:
        if confidence >= 75: target = rng.randint(4, 8)
        elif confidence >= 65: target = rng.randint(6, 9)
        else: target = rng.randint(7, 10)

    for _ in range(60):
        d1 = rng.randint(1, 6)
        d2 = rng.randint(1, 6)
        d3 = target - d1 - d2
        if 1 <= d3 <= 6:
            return [d1, d2, d3]
    return [5, 6, 4] if prediction == 'Tài' else [2, 3, 4]


# ========== PREDICTOR V15 ==========
class MultiStrategyPredictor:
    _TRACK = defaultdict(lambda: {'hit': 0, 'miss': 0})
    _RECENT = deque(maxlen=12)
    _RECOVERY = {'active': False, 'fail': 0}

    @staticmethod
    def _sig_markov(seq):
        best = (None, 0, 0)
        for order in (3, 2):
            if len(seq) < order + 5: continue
            trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
            for i in range(len(seq) - order):
                trans[tuple(seq[i:i + order])][seq[i + order]] += 1
            c = trans[tuple(seq[-order:])]
            t = c['Tài'] + c['Xỉu']
            if t < 3: continue
            p = (c['Tài'] + 1) / (t + 2)
            if p >= 0.68 or p <= 0.32:
                pred = 'Tài' if p >= 0.5 else 'Xỉu'
                conf = min(int(max(p, 1 - p) * 100) + order * 2, 84)
                if conf > best[1]:
                    best = (pred, conf, 1.35 + order * 0.1)
        return best

    @staticmethod
    def _sig_streak(seq, regime):
        runs = _runs(seq)
        if not runs: return (None, 0, 0)
        cur_val, cur_len = runs[-1]
        opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
        
        # Nếu đang ở nhịp đảo liên tục (1-1) thì ưu tiên đảo
        if regime == 'alternation':
            return (opp, 70, 1.5)
            
        if regime == 'streak':
            if cur_len <= 4:
                return (cur_val, min(58 + cur_len * 3, 72), 1.15)
            if cur_len >= 6:
                return (opp, min(60 + (cur_len - 5) * 4, 80), 1.30)
        if cur_len >= 5:
            return (opp, min(58 + (cur_len - 4) * 3, 76), 1.10)
        return (None, 0, 0)

    @staticmethod
    def _sig_pattern(seq):
        if len(seq) < 10: return (None, 0, 0)
        best = (None, 0, 0)
        for plen in (6, 5, 4, 3):
            if len(seq) < plen + 4: continue
            pat = tuple(seq[-plen:])
            matches = []
            for i in range(len(seq) - plen - 1):
                if tuple(seq[i:i + plen]) == pat:
                    matches.append(seq[i + plen])
            if len(matches) < 3: continue
            c = Counter(matches)
            top, cnt = c.most_common(1)[0]
            ratio = cnt / len(matches)
            if ratio >= 0.70:
                conf = min(56 + int(ratio * 25) + plen * 2, 86)
                w = 1.25 + plen * 0.08
                if conf * w > best[1] * best[2]:
                    best = (top, conf, w)
        return best

    @staticmethod
    def _sig_trend(seq):
        if len(seq) < 12: return (None, 0, 0)
        votes = []
        for w in (6, 10, 15, 20):
            if len(seq) < w: continue
            p = sum(1 for x in seq[-w:] if x == 'Tài') / w
            if p >= 0.65: votes.append(('Tài', p))
            elif p <= 0.35: votes.append(('Xỉu', p))
        if len(votes) < 3: return (None, 0, 0)
        c = Counter(v[0] for v in votes)
        top, cnt = c.most_common(1)[0]
        if cnt >= 3:
            avg = sum(v[1] if top == 'Tài' else 1 - v[1]
                      for v in votes if v[0] == top) / cnt
            return (top, min(int(avg * 100) + 3, 82), 1.25)
        return (None, 0, 0)

    @staticmethod
    def _sig_cycle(seq):
        if len(seq) < 12: return (None, 0, 0)
        best = None
        for period in range(2, 9):
            if len(seq) < period * 3: break
            pat = seq[-period:]
            ok = all(seq[-period * (k + 1):-period * k] == pat for k in range(3))
            if not ok: continue
            hits = sum(1 for i in range(period, len(seq)) if seq[i] == seq[i - period])
            total = len(seq) - period
            score = hits / total if total else 0
            if score >= 0.75 and (best is None or score > best[0]):
                best = (score, period, pat)
        if not best: return (None, 0, 0)
        _, period, pat = best
        nxt = pat[(len(seq) % period)]
        return (nxt, min(60 + int(best[0] * 25), 82), 1.3)

    @staticmethod
    def _sig_entropy(seq):
        if len(seq) < 10: return (None, 0, 0)
        seg = seq[-20:]
        h = _entropy(seg)
        p = sum(1 for x in seg if x == 'Tài') / len(seg)
        if h < 0.75:
            if p >= 0.62: return ('Tài', 64, 1.15)
            if p <= 0.38: return ('Xỉu', 64, 1.15)
        if h > 0.96:
            return ('Xỉu' if seq[-1] == 'Tài' else 'Tài', 60, 1.05)
        return (None, 0, 0)

    @staticmethod
    def _sig_table13(seq):
        return _lookup_table13(_to_seq_str(seq))

    @staticmethod
    def _sig_cau(seq):
        if len(seq) < 10: return (None, 0, 0)
        runs = _runs(seq)
        if not runs: return (None, 0, 0)
        cur_val, cur_len = runs[-1]
        opp = 'Xỉu' if cur_val == 'Tài' else 'Tài'
        
        # Phân tích 4 nhịp gần nhất
        last4 = [l for _, l in runs[-4:]]
        if len(last4) >= 3:
            if all(l == 1 for l in last4):
                return (opp, 66, 1.4)
            if all(l == 2 for l in last4):
                return (cur_val if cur_len == 1 else opp, 64, 1.3)
        
        if cur_len >= 6:
            return (opp, min(62 + (cur_len - 6) * 3, 82), 1.45)
        if 3 <= cur_len <= 4:
            return (cur_val, min(60 + cur_len * 2, 72), 1.30)
        return (None, 0, 0)

    @staticmethod
    def _sig_anti_streak(seq, log):
        """Cứu thua: Nếu 3 phiên gần nhất dự đoán sai liên tiếp, có xu hướng đảo"""
        evaluated = [e for p, e in sorted(log.items(), reverse=True) if e.get('actual') is not None][:3]
        if len(evaluated) < 3: return (None, 0, 0)
        wrong_count = sum(1 for e in evaluated if not e.get('correct'))
        if wrong_count >= 2:
            p10 = sum(1 for x in seq[-10:] if x == 'Tài') / 10
            if p10 >= 0.6: return ('Xỉu', 65, 1.3)
            if p10 <= 0.4: return ('Tài', 65, 1.3)
            return ('Xỉu' if seq[-1] == 'Tài' else 'Tài', 62, 1.2)
        return (None, 0, 0)

    @classmethod
    def _calibrate(cls, conf, log):
        evaluated = [(p, e) for p, e in log.items() if e.get('actual') is not None]
        if len(evaluated) < 10: return conf
        evaluated.sort(reverse=True)
        recent = evaluated[:30]
        acc = sum(1 for _, e in recent if e.get('correct')) / len(recent)
        if acc < 0.40: return max(50, conf - 15)
        if acc < 0.48: return max(50, conf - 8)
        if acc > 0.65: return min(84, conf + 5)
        return conf

    @classmethod
    def _update_recovery(cls, log):
        evaluated = [(p, e) for p, e in sorted(log.items(), reverse=True) if e.get('actual') is not None][:6]
        cls._RECENT.clear()
        for _, e in reversed(evaluated): cls._RECENT.append(bool(e.get('correct')))
        fail = 0
        for _, e in evaluated:
            if e.get('correct') is False: fail += 1
            else: break
        cls._RECOVERY['active'] = fail >= 2
        cls._RECOVERY['fail'] = fail

    @classmethod
    def predict(cls, valid, log=None):
        if log is None: log = PREDICTION_LOG
        if not valid:
            return {'prediction': 'Tài', 'confidence': 50, 'method': 'Random',
                    'signals': [], 'top_signals': [], 'signals_strength': [],
                    'reason': '', 'flipped': False, 'cau': 'unknown', 'cau_label': '',
                    'recovery_active': False, 'fail_streak': 0}

        cls._update_recovery(log)
        seq = [v['result'] for v in valid]

        if len(seq) < 5:
            run_val, run_len = _runs(seq)[-1]
            opp = 'Xỉu' if run_val == 'Tài' else 'Tài'
            return {'prediction': opp, 'confidence': min(52 + run_len * 2, 68),
                    'method': 'Bẻ nhịp', 'signals': [], 'top_signals': [], 'signals_strength': [],
                    'reason': 'Khởi động', 'flipped': False, 'cau': 'unknown', 'cau_label': '',
                    'recovery_active': False, 'fail_streak': 0}

        regime, _ = _detect_regime(seq)
        raw = [
            ('markov',      cls._sig_markov(seq)),
            ('streak',      cls._sig_streak(seq, regime)),
            ('pattern',     cls._sig_pattern(seq)),
            ('trend',       cls._sig_trend(seq)),
            ('cycle',       cls._sig_cycle(seq)),
            ('entropy',     cls._sig_entropy(seq)),
            ('table13',     cls._sig_table13(seq)),
            ('cau',         cls._sig_cau(seq)),
            ('anti_streak', cls._sig_anti_streak(seq, log)),
        ]

        signals = []
        log_odds = 0.0
        total_w = 0.0
        for name, (pred, conf, weight) in raw:
            if not pred or weight <= 0: continue
            tr = cls._TRACK.get(name)
            if tr and (tr['hit'] + tr['miss']) >= 5:
                acc = tr['hit'] / (tr['hit'] + tr['miss'])
                weight *= max(0.4, min(0.55 + (acc - 0.5) * 2.8, 1.65))
            
            if regime == 'alternation' and name in ('streak', 'cau'): weight *= 1.4
            if regime == 'streak' and name in ('streak', 'markov'): weight *= 1.2
            if cls._RECOVERY['active'] and name == 'anti_streak': weight *= 2.0

            p_norm = max(0.51, min(conf / 100.0, 0.90))
            lr = p_norm / (1 - p_norm)
            if pred == 'Xỉu': lr = 1.0 / lr
            log_odds += weight * (1.0 if pred == 'Tài' else -1.0) * (lr - 1.0)
            total_w += weight
            signals.append({'name': name, 'prediction': pred, 'confidence': conf, 'weight': round(weight, 2)})

        if not signals or total_w == 0:
            return {'prediction': 'Tài', 'confidence': 50, 'method': 'Fallback',
                    'signals': [], 'top_signals': [], 'signals_strength': [],
                    'reason': '', 'flipped': False, 'cau': regime, 'cau_label': '',
                    'recovery_active': False, 'fail_streak': 0}

        scaled = log_odds / max(total_w, 1.0) * 2.0
        p_tai = 1.0 / (1.0 + math.exp(-scaled))
        pred = 'Tài' if p_tai >= 0.5 else 'Xỉu'
        raw_conf = int((p_tai if pred == 'Tài' else 1 - p_tai) * 100)

        votes_tai = sum(1 for s in signals if s['prediction'] == 'Tài')
        votes_xiu = len(signals) - votes_tai
        agreement = max(votes_tai, votes_xiu) / len(signals)
        recent_h = _entropy(seq[-20:])
        penalty = 0
        if recent_h > 0.95: penalty += 6
        elif recent_h > 0.85: penalty += 3
        if agreement < 0.65: penalty += 4
        bonus = 4 if agreement >= 0.85 and recent_h < 0.7 else 0

        final_conf = max(50, min(raw_conf - penalty + bonus, 84))

        flipped = False
        if cls._RECOVERY['active']:
            if cls._RECOVERY['fail'] >= 3:
                pred = 'Xỉu' if pred == 'Tài' else 'Tài'
                final_conf = max(58, min(final_conf + 2, 75))
                flipped = True
            elif cls._RECOVERY['fail'] == 2 and agreement < 0.72 and raw_conf < 66:
                pred = 'Xỉu' if pred == 'Tài' else 'Tài'
                final_conf = max(56, final_conf - 3)
                flipped = True

        final_conf = cls._calibrate(final_conf, log)

        signals.sort(key=lambda s: s['weight'] * (s['confidence'] - 50), reverse=True)
        top = [SIGNAL_NAMES.get(s['name'], s['name']) for s in signals[:3]]

        return {
            'prediction': pred, 'confidence': final_conf,
            'method': ' + '.join(top) if top else 'Tổng hợp',
            'signals': signals, 'top_signals': top,
            'signals_strength': [{'name': s['name'], 'display': SIGNAL_NAMES.get(s['name'], s['name']),
                                  'prediction': s['prediction'], 'confidence': s['confidence'],
                                  'weight': s['weight'], 'strength': round(s['weight'] * (s['confidence'] - 50), 1)}
                                 for s in signals[:6]],
            'reason': '', 'flipped': flipped, 'cau': regime, 'cau_label': '',
            'recovery_active': cls._RECOVERY['active'], 'fail_streak': cls._RECOVERY['fail'],
        }


# ========== FETCH ==========
def fetch_sessions():
    global _LAST_FETCH_TIME, _LAST_FETCH_RESULT
    with _FETCH_LOCK:
        now = time.time()
        if now - _LAST_FETCH_TIME < _FETCH_CACHE_TTL and _LAST_FETCH_RESULT[0]:
            return _LAST_FETCH_RESULT
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        for attempt in range(3):
            try:
                r = requests.get(API_URL_MD5, timeout=6, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    if 'list' in data and data['list']:
                        rows = [{'phien': int(i['id']),
                                 'result': "Tài" if i['resultTruyenThong'] == "TAI" else "Xỉu",
                                 'dice': f"{i.get('dices', [0,0,0])[0]} + {i.get('dices', [0,0,0])[1]} + {i.get('dices', [0,0,0])[2]}",
                                 'total': i.get('point', sum(i.get('dices', [0,0,0])))} for i in data['list']]
                        _LAST_FETCH_TIME = now
                        _LAST_FETCH_RESULT = (rows, True)
                        return rows, True
            except Exception as e:
                time.sleep(1)
        return _LAST_FETCH_RESULT

def _load_log():
    global PREDICTION_LOG, RESET_ID
    if not os.path.exists(LOG_FILE): return
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        PREDICTION_LOG = {int(k): v for k, v in data.get('log', {}).items()}
        RESET_ID = int(data.get('reset_id', 0))
    except Exception: pass

def _save_log():
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'log': PREDICTION_LOG, 'reset_id': RESET_ID}, f)
    except Exception: pass

def _sync_history():
    raw_rows, success = fetch_sessions()
    if not success and not HISTORY_CACHE: return [], False
    for row in raw_rows:
        HISTORY_CACHE[row['phien']] = row
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
        pred = MultiStrategyPredictor.predict(history_before, log=PREDICTION_LOG)
        actual = by_phien[phien]['result']
        PREDICTION_LOG[phien] = {
            'prediction': pred['prediction'], 'confidence': pred['confidence'],
            'method': pred['method'], 'actual': actual, 'correct': (pred['prediction'] == actual),
            'logged_at': datetime.now().isoformat(), 'retroactive': True, 'flipped': pred.get('flipped', False)}
        changed = True
    if len(PREDICTION_LOG) > MAX_LOG_SIZE:
        for k in sorted(PREDICTION_LOG.keys())[:len(PREDICTION_LOG) - MAX_LOG_SIZE]: del PREDICTION_LOG[k]
        changed = True
    if changed: _save_log()

def _log_prediction(phien, pred_result):
    if phien in PREDICTION_LOG: return
    PREDICTION_LOG[phien] = {
        'prediction': pred_result['prediction'], 'confidence': pred_result['confidence'],
        'method': pred_result['method'], 'actual': None, 'correct': None,
        'logged_at': datetime.now().isoformat(), 'retroactive': False, 'flipped': pred_result.get('flipped', False)}
    _save_log()

def _log_stats(log=None):
    if log is None: log = PREDICTION_LOG
    evaluated = [e for e in log.values() if e.get('actual') is not None]
    correct = sum(1 for e in evaluated if e.get('correct'))
    wrong = len(evaluated) - correct
    pending = sum(1 for e in log.values() if e.get('actual') is None)
    return {'correct': correct, 'wrong': wrong, 'pending': pending, 'evaluated': len(evaluated)}

_load_log()

# ========== HTML ĐÃ XÓA PHẦN CẦU & CẢNH BÁO ==========
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>LE MINH MD5 V2</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
:root{--bg-1:#eff6ff;--text:#0f172a;--text-soft:#475569;--muted:#94a3b8;--border:#dbeafe;--border-blue:#93c5fd;--border-strong:#60a5fa;--primary:#0ea5e9;--primary-dark:#0284c7;--tai:#0284c7;--tai-bg:#e0f2fe;--xiu:#0891b2;--xiu-bg:#cffafe;--ok:#059669;--ok-bg:#d1fae5;--fail:#dc2626;--fail-bg:#fee2e2;--warn:#d97706;--warn-bg:#fef3c7;--shadow:0 4px 12px rgba(14,165,233,.10);--shadow-lg:0 12px 32px rgba(2,132,199,.15)}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Plus Jakarta Sans',sans-serif}
body{background:linear-gradient(135deg,#eff6ff,#f0f9ff 35%,#e0f2fe 70%,#dbeafe);background-attachment:fixed;color:var(--text);min-height:100vh;padding-bottom:30px;font-size:13px}
.header{background:rgba(255,255,255,.9);backdrop-filter:blur(20px);border-bottom:1px solid var(--border-blue);padding:12px 16px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(14,165,233,.08)}
.logo{font-size:16px;font-weight:800;display:flex;align-items:center;gap:8px}
.logo-text{background:linear-gradient(90deg,#0284c7,#0ea5e9,#38bdf8,#0284c7);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:shine 4s linear infinite}
@keyframes shine{to{background-position:200% center}}
.logo span.ver{font-size:9px;background:linear-gradient(135deg,#0284c7,#0ea5e9);color:#fff;padding:3px 8px;border-radius:20px;font-weight:800}
.actions{display:flex;gap:8px;align-items:center}
.clock{font-size:11px;color:var(--muted);font-weight:600}
.btn{background:#fff;color:var(--text-soft);border:1px solid var(--border);padding:7px 12px;border-radius:9px;font-weight:700;font-size:12px;cursor:pointer;transition:.2s}
.btn:hover{background:var(--bg-1);border-color:var(--border-strong);color:var(--primary-dark)}
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
.scorebar{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}
.sc{background:#fff;border:1px solid var(--border);border-radius:11px;padding:12px 8px;text-align:center}
.sc-l{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:700;margin-bottom:4px}
.sc-v{font-size:22px;font-weight:800}
.sc-v.ok{color:var(--ok)}.sc-v.fail{color:var(--fail)}.sc-v.warn{color:var(--warn)}
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
@media(max-width:520px){th,td{padding:8px 4px;font-size:11px}.clock{display:none}.badge{min-width:44px;font-size:9px}.sc-v{font-size:17px}.pred-value{font-size:26px}}
</style></head><body>
<div class="header"><div class="logo"><span class="logo-text">LE MINH</span><span class="ver">V15</span></div>
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
</div>
<div class="scorebar">
<div class="sc"><div class="sc-l">✓ Đúng</div><div class="sc-v ok" id="sc-correct">0</div></div>
<div class="sc"><div class="sc-l">✗ Sai</div><div class="sc-v fail" id="sc-wrong">0</div></div>
<div class="sc"><div class="sc-l">Chờ</div><div class="sc-v warn" id="sc-pending">0</div></div>
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
    if(!d.ready){document.getElementById('loading-screen').style.display='block';document.getElementById('main-content').style.display='none';return;}
    document.getElementById('loading-screen').style.display='none';
    document.getElementById('main-content').style.display='block';
    const ai=d.ai_stats||{};
    document.getElementById('sc-correct').innerText=ai.correct||0;
    document.getElementById('sc-wrong').innerText=ai.wrong||0;
    document.getElementById('sc-pending').innerText=ai.pending||0;
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
fetchData();
setInterval(fetchData,5000);
</script></body></html>"""

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
            return jsonify({'ready': False, 'message': 'Đang tải dữ liệu...', 'ai_stats': _log_stats()})
        next_phien = valid[-1]['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        
        # Trả về giao diện (đã bỏ cau_info và canh_bao)
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
            'ready': True, 'rows': out, 'ai_stats': _log_stats(),
            'prediction': {
                'prediction': pred['prediction'],
                'confidence': pred['confidence']
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
            return jsonify({
                'Id': '@cskhleminh', 'Phien': None, 'Du_doan': None, 'Xuc_xac': None,
                'Do_tin_cay': None, 'Ket_qua_du_doan': None, 'message': 'Đang tải dữ liệu...'
            })
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)

        dice = _generate_dice(pred['prediction'], pred['confidence'], seed_str=f"phien_{next_phien}_{last['phien']}")
        dice_str = f"{dice[0]}-{dice[1]}-{dice[2]}"

        return jsonify({
            'Id': '@cskhleminh',
            'Phien': str(next_phien),
            'Du_doan': pred['prediction'],
            'Xuc_xac': dice_str,
            'Do_tin_cay': f"{pred['confidence']}%",
            'Ket_qua_du_doan': pred['prediction'],
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
            return jsonify({'Id': '@cskhleminh', 'Phien': None, 'Du_doan': None, 'Ket_qua': None, 'message': 'Đang tải dữ liệu...'})
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
            'Ket_qua': ket_qua,
            'Xuc_xac_truoc': last['dice'],
            'Diem_truoc': last['total'],
            'Ket_qua_truoc': last['result'],
            'Tin_hieu_chinh': pred.get('top_signals', []),
            'Da_dao': pred.get('flipped', False),
            'Recovery': pred.get('recovery_active', False),
            'AI_dung': ai_stats['correct'],
            'AI_sai': ai_stats['wrong'],
            'AI_cho': ai_stats['pending'],
            'Ti_le_AI': round(ai_stats['correct'] / max(ai_stats['evaluated'], 1) * 100, 1),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict')
def predict():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid: return jsonify({'ready': False, 'prediction': None})
        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid, log=PREDICTION_LOG)
        _log_prediction(next_phien, pred)
        return jsonify({
            'version': 'V15', 'next_phien': next_phien, 'last_result': last['result'],
            'prediction': pred['prediction'], 'confidence': pred['confidence'],
            'method': pred['method'], 'top_signals': pred.get('top_signals', []),
            'reason': pred['reason'], 'flipped': pred.get('flipped', False),
            'recovery_active': pred.get('recovery_active', False), 'ai_stats': _log_stats(),
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
        MultiStrategyPredictor._RECOVERY = {'active': False, 'fail': 0}
        _save_log()
        return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
