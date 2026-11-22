import os
import random
import math
from datetime import datetime
from collections import Counter
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
MAX_CONFIDENCE = 90
RESET_ID = 0
WINDOW = 5  # số phiên gần nhất để phân tích


# =====================================================================
# CORE UTILS
# =====================================================================
def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"


def format_tx(results, length):
    if len(results) < length:
        return None
    return "-".join("T" if r == "Tài" else "X" for r in results[:length])


# =====================================================================
# THUẬT TOÁN: ĐẢO THUẬN-NGHỊCH 1-1 (5 PHIÊN GẦN NHẤT)
# =====================================================================

def _analyze_5p(results):
    """
    Phân tích 5 phiên gần nhất (results[0] = mới nhất).
    Trả về dict:
      - pattern: chuỗi T/X 5 phiên (mới -> cũ)
      - flips: số lần đổi chiều trong 5 phiên
      - streak: độ dài bệt cuối
      - mode: 'dao' (đảo 1-1) | 'thuan' (bệt) | 'hontap' (hỗn tạp)
      - trend: hướng phiên kế nếu theo mode hiện tại
    """
    if len(results) < 5:
        return None

    seq = results[:5]
    pattern = "".join("T" if r == "Tài" else "X" for r in seq)

    # Số lần đổi chiều (flip) giữa các phiên liền kề
    flips = sum(1 for i in range(4) if seq[i] != seq[i + 1])

    # Độ dài bệt cuối (từ phiên mới nhất ngược về)
    streak_val = seq[0]
    streak_len = 1
    for r in seq[1:]:
        if r == streak_val:
            streak_len += 1
        else:
            break

    # Phân loại mode
    if flips == 4:
        mode = "dao"          # đảo 1-1 thuần (T X T X T hoặc X T X T X)
    elif flips == 0:
        mode = "thuan"        # bệt 5 phiên
    elif flips <= 2:
        mode = "thuan"        # xu hướng bệt (chỉ 1-2 lần đổi)
    else:
        mode = "hontap"       # hỗn tạp (flips = 3)

    # Dự đoán theo mode (dựa vào phiên mới nhất seq[0])
    if mode == "dao":
        # Đảo 1-1 -> phiên tới PHẢI đảo so với phiên mới nhất
        trend = _opp(seq[0])
        strength = 0.88
    elif mode == "thuan":
        # Bệt -> phiên tới tiếp tục cùng chiều
        trend = seq[0]
        strength = 0.75 + min(streak_len, 5) * 0.03  # bệt càng dài càng mạnh
    else:  # hontap
        # Hỗn tạp -> dựa vào phiên mới nhất + phiên thứ 2
        # Nếu 2 phiên cuối giống nhau -> nghiêng về đảo nhẹ
        if seq[0] == seq[1]:
            trend = seq[0]
            strength = 0.58
        else:
            # 2 phiên cuối khác nhau -> ưu tiên đảo (theo nhịp 1-1 nhẹ)
            trend = _opp(seq[0])
            strength = 0.60

    return {
        "pattern": pattern,
        "flips": flips,
        "streak": streak_len,
        "mode": mode,
        "trend": trend,
        "strength": strength,
    }


def _anti_trap_check(analysis, results):
    """
    Kiểm tra bẫy nhà cái:
    - Nếu mode quá rõ (flips=4 hoặc streak>=4) liên tục nhiều phiên
      => có xác suất flip để tránh bị bắt bài.
    - Nếu 2 phiên gần nhất đã đảo liên tiếp giống dự đoán => giảm tin.
    Trả về (final_pred, penalty, is_trap_flip)
    """
    if not analysis:
        return (results[0] if results else "Tài", 0.0, False)

    pred = analysis["trend"]
    strength = analysis["strength"]
    is_trap_flip = False

    # Anti-trap #1: nếu 5 phiên đảo thuần (flips=4) mà 3 phiên trước đó
    # cũng đảo thuần => cầu đã "già", có xác suất gãy
    if analysis["flips"] == 4 and len(results) >= 8:
        prev3 = results[5:8]
        prev_flips = sum(1 for i in range(len(prev3) - 1) if prev3[i] != prev3[i + 1])
        if prev_flips >= 2:
            # Cầu đảo đã chạy dài -> tăng rủi ro gãy
            strength -= 0.10

    # Anti-trap #2: bệt >= 5 phiên -> nhà cái hay "gãy" ở phiên 6-7
    if analysis["mode"] == "thuan" and analysis["streak"] >= 5:
        strength -= 0.08

    # Anti-trap #3: phát hiện "cầu giả" — nếu 5 phiên vừa rồi có 3 phiên
    # cùng chiều ở vị trí lẻ/chẵn (nhà cái tạo nhịp giả)
    seq = results[:5]
    even_side = [seq[0], seq[2], seq[4]]
    odd_side = [seq[1], seq[3]]
    if len(set(even_side)) == 1 and len(set(odd_side)) == 1:
        # Pattern chẵn-lẻ hoàn hảo => dễ bị bắt bài => flip nhẹ
        # (vd T X T X T -> phiên tới X là hiển nhiên, nhà cái có thể phá)
        if random.random() < 0.25:  # 25% flip để phá trap
            pred = _opp(pred)
            strength = 0.55
            is_trap_flip = True

    # Anti-trap #4: entropy cao => giảm confidence
    if len(results) >= 10:
        recent = results[:10]
        p_tai = recent.count("Tài") / 10
        ent = 0.0
        for p in (p_tai, 1 - p_tai):
            if p > 0:
                ent -= p * math.log2(p)
        if ent > 0.95:  # gần như ngẫu nhiên hoàn toàn
            strength *= 0.85

    # Clamp
    strength = max(0.50, min(0.95, strength))
    penalty = 0.0

    return (pred, strength, is_trap_flip)


def compute_prediction(results):
    """
    Entry point: dự đoán dựa trên 5 phiên gần nhất.
    Trả về (prediction, confidence, pattern_label).
    """
    if not results:
        return ("Tài", 50, "Chưa có dữ liệu")

    # Chưa đủ 5 phiên -> fallback đơn giản
    if len(results) < 5:
        t = results.count("Tài")
        x = len(results) - t
        if t > x:
            return ("Tài", 55, "Đa số ngắn hạn")
        elif x > t:
            return ("Xỉu", 55, "Đa số ngắn hạn")
        return (results[0], 52, "Theo phiên mới")

    analysis = _analyze_5p(results)
    pred, strength, is_trap = _anti_trap_check(analysis, results)

    # Confidence mapping: strength (0.5..0.95) -> conf (52..90)
    conf = 52 + (strength - 0.50) * 2 * (MAX_CONFIDENCE - 52)
    conf = int(max(52, min(MAX_CONFIDENCE, round(conf))))

    # Jitter nhẹ ±2 để tránh fingerprint
    conf = max(52, min(MAX_CONFIDENCE, conf + random.randint(-2, 2)))

    # Label
    mode = analysis["mode"]
    if mode == "dao":
        label = f"Đảo 1-1 (5P: {analysis['pattern']})"
    elif mode == "thuan":
        label = f"Bệt {analysis['streak']}P ({analysis['pattern']})"
    else:
        label = f"Hỗn tạp ({analysis['pattern']})"
    if is_trap:
        label += " [Anti-trap]"

    return (pred, conf, label)
