import os
import time
import random
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=ab36aa88e2c9868ae0e8bc61adbd18dc"
RESET_SESSION_ID = 0

# ==================== HTML TEMPLATE ====================
# (Giữ nguyên HTML template của bạn - không thay đổi UI)

# =====================================================================
# THUẬT TOÁN v4.0 - ĐA TẦNG VOTING + BLOCK DETECTION
# =====================================================================

def check_block_alternation(results, block_size, min_blocks=2):
    """
    Phát hiện cầu block xen kẽ (2-2, 3-3, 4-4, 5-5).
    Hỗ trợ block chưa hoàn chỉnh ở đầu (partial).
    Trả về: (next_value, full_count, state, blocks) hoặc None
    """
    n = len(results)
    if n < block_size:
        return None

    blocks = []
    i = 0
    while i < n and len(blocks) < 12:
        val = results[i]
        run_len = 1
        while i + run_len < n and results[i + run_len] == val:
            run_len += 1
        if run_len > block_size:
            return None  # run quá dài → cầu bị phá
        blocks.append((val, run_len))
        i += run_len

    full_blocks = sum(1 for v, l in blocks if l == block_size)
    if full_blocks < min_blocks:
        return None

    # Kiểm tra xen kẽ: không được có 2 block liền kề cùng giá trị
    for j in range(1, len(blocks)):
        if blocks[j][0] == blocks[j - 1][0]:
            return None

    last_val, last_len = blocks[0]
    if last_len == block_size:
        next_val = "Xỉu" if last_val == "Tài" else "Tài"
        state = "complete"
    else:
        next_val = last_val  # đang giữa block → dự đoán tiếp tục
        state = "partial"

    return next_val, full_blocks, state, blocks


def analyze_pattern(results, dice_sums=None):
    """
    Phân tích đa tầng - Voting System v4.0
    Trả về: (prediction, confidence, pattern_name)
    """
    if not results or len(results) < 3:
        return "Tài", 50.0, "Khởi tạo"

    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    n = len(results)

    candidates = []  # (pred, conf, name, priority)

    # ========== 1. STREAK / BỆT ==========
    streak = 1
    for r in results[1:]:
        if r == last:
            streak += 1
        else:
            break

    if streak >= 12:
        candidates.append((opposite, 95.0, f"Bẻ bệt {streak} siêu cấp", 100))
    elif streak >= 10:
        candidates.append((opposite, 92.0, f"Bẻ bệt {streak} cực mạnh", 96))
    elif streak >= 8:
        candidates.append((opposite, 88.0, f"Bẻ bệt {streak} mạnh", 92))
    elif streak >= 6:
        candidates.append((opposite, 82.0, f"Bẻ bệt {streak}", 86))
    elif streak == 5:
        candidates.append((opposite, 74.0, f"Bẻ bệt {streak}", 75))
    elif streak == 4:
        candidates.append((last, 62.0, f"Bám bệt {streak}", 60))
    elif streak == 3:
        candidates.append((last, 55.0, f"Bám bệt {streak}", 50))
    elif streak == 2:
        candidates.append((last, 52.0, f"Bám bệt {streak}", 42))

    # ========== 2. ĐẢO 1-1 ==========
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]:
            alt_len += 1
        else:
            break

    if alt_len >= 12:
        candidates.append((opposite, 94.0, f"Đảo 1-1 siêu dài {alt_len}", 99))
    elif alt_len >= 10:
        candidates.append((opposite, 90.0, f"Đảo 1-1 dài {alt_len}", 95))
    elif alt_len >= 7:
        candidates.append((opposite, 85.0, f"Đảo 1-1 {alt_len}", 87))
    elif alt_len >= 5:
        candidates.append((opposite, 78.0, f"Đảo 1-1 {alt_len}", 78))
    elif alt_len >= 4:
        candidates.append((opposite, 68.0, "Đảo 1-1 ngắn", 63))

    # ========== 3. BLOCK PATTERNS (2-2, 3-3, 4-4, 5-5) ==========
    for bs in [2, 3, 4, 5]:
        res = check_block_alternation(results, bs, min_blocks=2)
        if res:
            next_val, full_count, state, blocks = res
            if full_count >= 4:
                conf = 88.0
            elif full_count == 3:
                conf = 80.0
            else:
                conf = 70.0
            conf = min(92.0, conf + (bs - 2) * 2)

            if bs == 2:
                pri = 82 if full_count >= 4 else (72 if full_count == 3 else 60)
            elif bs == 3:
                pri = 85 if full_count >= 3 else 78
            elif bs == 4:
                pri = 88 if full_count >= 3 else 82
            else:
                pri = 90

            count_str = str(full_count) + ("+" if state == "partial" else "")
            name = f"Cầu {bs}-{bs} x{count_str}"
            candidates.append((next_val, conf, name, pri))

    # ========== 4. SHORT PATTERNS ==========
    if n >= 5:
        # 1-2-1 (X-Y-Y-X)
        if results[0] == results[3] and results[1] == results[2] and results[0] != results[1]:
            candidates.append((results[1], 83.0, "Cầu 1-2-1", 72))
        # 2-1-2 (X-X-Y-X-X) → dự đoán Y (opposite)
        if (results[0] == results[1] and results[3] == results[4]
                and results[1] != results[2] and results[2] != results[3]):
            candidates.append((opposite, 82.0, "Cầu 2-1-2", 71))
        # 2-2-1
        if (results[0] != results[1] and results[1] == results[2]
                and results[2] != results[3] and results[3] == results[4]):
            candidates.append((results[1], 75.0, "Cầu 2-2-1", 65))

    if n >= 6:
        # 1-1-2 (X-Y-Y-X-X-Y pattern)
        if (results[0] == results[1] and results[1] != results[2]
                and results[3] == results[4] and results[4] != results[5]):
            candidates.append((results[2], 82.0, "Cầu 1-1-2", 71))
        # 1-2-3
        if (results[0] != results[1] and results[1] == results[2]
                and results[2] != results[3] and results[3] == results[4] == results[5]):
            candidates.append((results[3], 80.0, "Cầu 1-2-3", 69))
        # 3-2-1
        if (results[0] == results[1] == results[2] and results[2] != results[3]
                and results[3] == results[4] and results[4] != results[5]):
            candidates.append((results[3], 80.0, "Cầu 3-2-1", 69))

    if n >= 7:
        # 3-1-3
        if (results[0] == results[1] == results[2] and results[3] != results[0]
                and results[3] == results[4] == results[5] == results[6]):
            candidates.append((results[3], 85.0, "Cầu 3-1-3", 76))
        # 2-3-2
        if (results[0] == results[1] and results[2] == results[3] == results[4]
                and results[5] == results[6] and results[1] != results[2]
                and results[4] != results[5]):
            candidates.append((results[2], 83.0, "Cầu 2-3-2", 74))

    # ========== 5. N-GRAM MATCHING ==========
    for ns in [6, 5, 4, 3]:
        if n < ns + 1:
            continue
        current = tuple(results[:ns])
        matches = {"Tài": 0, "Xỉu": 0}
        total = 0
        for i in range(len(results) - ns):
            if tuple(results[i:i + ns]) == current:
                if i + ns < len(results):
                    matches[results[i + ns]] += 1
                    total += 1
        if total >= 2:
            if matches["Tài"] == matches["Xỉu"]:
                continue
            winner = "Tài" if matches["Tài"] > matches["Xỉu"] else "Xỉu"
            ratio = matches[winner] / total
            if ratio >= 0.6:
                conf = 55 + ratio * 35
                pri = 55 + ns * 3
                candidates.append((
                    winner, conf,
                    f"N-gram({ns}) {winner} {matches[winner]}/{total}", pri
                ))

    # ========== 6. MARKOV ==========
    if n >= 6:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 1):
            if results[i] == last:
                trans[results[i + 1]] += 1
        total = trans["Tài"] + trans["Xỉu"]
        if total >= 3 and trans["Tài"] != trans["Xỉu"]:
            winner = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            ratio = trans[winner] / total
            conf = 55 + ratio * 25
            candidates.append((
                winner, conf,
                f"Markov {winner} {trans[winner]}/{total}", 60
            ))

    # Markov bậc 2
    if n >= 8:
        trans2 = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 2):
            if results[i] == results[0] and results[i + 1] == results[1]:
                if i + 2 < len(results):
                    trans2[results[i + 2]] += 1
        total2 = trans2["Tài"] + trans2["Xỉu"]
        if total2 >= 2 and trans2["Tài"] != trans2["Xỉu"]:
            winner = "Tài" if trans2["Tài"] > trans2["Xỉu"] else "Xỉu"
            ratio = trans2[winner] / total2
            conf = 58 + ratio * 28
            candidates.append((
                winner, conf,
                f"Markov-2 {winner} {trans2[winner]}/{total2}", 63
            ))

    # ========== 7. NGHIÊNG / FREQUENCY ==========
    if n >= 10:
        tai10 = sum(1 for r in results[:10] if r == "Tài")
        if tai10 >= 9:
            candidates.append(("Xỉu", 85.0, "Nghiêng Xỉu cực mạnh", 80))
        elif tai10 <= 1:
            candidates.append(("Tài", 85.0, "Nghiêng Tài cực mạnh", 80))
        elif tai10 >= 8:
            candidates.append(("Xỉu", 74.0, "Nghiêng Xỉu mạnh", 68))
        elif tai10 <= 2:
            candidates.append(("Tài", 74.0, "Nghiêng Tài mạnh", 68))
        elif tai10 >= 7:
            candidates.append(("Xỉu", 63.0, "Nghiêng Xỉu", 57))
        elif tai10 <= 3:
            candidates.append(("Tài", 63.0, "Nghiêng Tài", 57))

    # ========== 8. DICE BIAS ==========
    if dice_sums and len(dice_sums) >= 5:
        recent = dice_sums[:10]
        if len(recent) >= 3:
            avg = sum(recent) / len(recent)
            if avg >= 12.5:
                candidates.append(("Tài", 62.0, "Dice lệch Tài", 55))
            elif avg <= 8.5:
                candidates.append(("Xỉu", 62.0, "Dice lệch Xỉu", 55))

    # ========== FINAL VOTING ==========
    if not candidates:
        return opposite, 55.0, "Đảo nhịp"

    # Chọn pattern có ưu tiên cao nhất (đặc trưng nhất)
    best = max(candidates, key=lambda x: (x[3], x[1]))
    pred = best[0]
    name = best[2]

    # Điều chỉnh confidence theo độ đồng thuận
    agree_w = sum(c[1] * c[3] for c in candidates if c[0] == pred)
    disagree_w = sum(c[1] * c[3] for c in candidates if c[0] != pred)
    total_w = agree_w + disagree_w

    if total_w > 0:
        agreement = agree_w / total_w
        conf = best[1] * (0.85 + agreement * 0.15)
    else:
        conf = best[1]

    return pred, round(min(98.0, conf), 1), name


# =====================================================================
# FETCH DATA (giữ nguyên)
# =====================================================================
def generate_fallback(base=7116040):
    elapsed = int(time.time() / 60)
    current = base + elapsed
    random.seed(elapsed)
    rows = []
    for i in range(15):
        sid = current - i
        r = "Tài" if random.random() > 0.5 else "Xỉu"
        d = [random.randint(1, 6) for _ in range(3)]
        rows.append({
            "phien": sid,
            "result": r,
            "dice": f"{d[0]} + {d[1]} + {d[2]}",
            "total": sum(d)
        })
    return rows


def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(API_URL, timeout=8, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']:
                rows = []
                for item in data['list']:
                    res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
                    total = item.get('point', sum(dices))
                    rows.append({
                        'phien': int(item['id']),
                        'result': res,
                        'dice': dice_str,
                        'total': total
                    })
                return rows, 'live'
    except Exception as e:
        print(f"[API ERROR] {e}")
    return generate_fallback(), 'fallback'


# =====================================================================
# API ROUTES
# =====================================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api')
def api_root():
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    return jsonify({
        "name": "LC MD5 MINHLE API Server",
        "version": "4.0.0 (Advanced Pattern Recognition + Voting System)",
        "features": [
            "Block Detection động (2-2, 3-3, 4-4, 5-5)",
            "N-gram matching (3-6 phần tử)",
            "Markov bậc 1 & 2",
            "Bám/Bẻ bệt thông minh",
            "Đảo 1-1 adaptive",
            "Cầu 1-2-1, 2-1-2, 1-1-2, 2-2-1",
            "Cầu 1-2-3, 3-2-1, 3-1-3, 2-3-2",
            "Dice bias analysis",
            "Multi-layer voting system"
        ],
        "endpoints": {
            "lich_su": "/api/history",
            "du_doan": "/api/predict",
            "thong_ke": "/api/stats",
            "reset": "/api/reset"
        },
        "lastUpdate": now,
        "status": "active"
    })


@app.route('/api/history')
def history():
    global RESET_SESSION_ID
    try:
        raw_rows, source = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])

        out = []
        correct_count = 0
        total_past = 0

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next, dice_for_next)

        out.append({
            'phien': next_phien,
            'is_next': True,
            'prediction': next_pred,
            'confidence': next_conf,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None,
            'pattern': next_pattern
        })

        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID:
                break
            if len(out) > 20:
                break

            history_list = [v['result'] for v in valid[:i]][::-1]
            dice_list = [v.get('total', 0) for v in valid[:i]][::-1]

            if history_list:
                pred, conf, pattern = analyze_pattern(history_list, dice_list)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct:
                    correct_count += 1
            else:
                pred, conf, pattern = "Tài", 50.0, "Khởi tạo"
                is_correct = None

            out.append({
                'phien': current_session['phien'],
                'is_next': False,
                'prediction': pred,
                'confidence': conf,
                'result': current_session['result'],
                'dice': current_session['dice'],
                'is_correct': is_correct,
                'pattern': pattern
            })

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count}
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict_only():
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if not valid:
            return jsonify({'status': 'error', 'message': 'Không có dữ liệu'}), 404

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = [v.get('total', 0) for v in valid][::-1]
        next_pred, next_conf, next_pattern = analyze_pattern(history_for_next, dice_for_next)

        return jsonify({
            'status': 'success',
            'next_session': next_phien,
            'prediction': next_pred,
            'confidence': next_conf,
            'pattern': next_pattern,
            'updated_at': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/stats')
def stats_only():
    global RESET_SESSION_ID
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])

        correct_count = 0
        total_past = 0

        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID:
                break

            history_list = [v['result'] for v in valid[:i]][::-1]
            dice_list = [v.get('total', 0) for v in valid[:i]][::-1]

            if history_list:
                pred, conf, _ = analyze_pattern(history_list, dice_list)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct:
                    correct_count += 1

        win_rate = round((correct_count / total_past * 100), 2) if total_past > 0 else 0

        return jsonify({
            'status': 'success',
            'data': {
                'total_predictions': total_past,
                'correct_predictions': correct_count,
                'win_rate_percent': win_rate
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        raw_rows, _ = fetch_sessions()
        valid = sorted(raw_rows, key=lambda x: x['phien'])
        if valid:
            RESET_SESSION_ID = valid[-1]['phien']
            return jsonify({'status': 'success', 'reset_to': RESET_SESSION_ID})
        return jsonify({'status': 'error', 'message': 'Không lấy được dữ liệu'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
