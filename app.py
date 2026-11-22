import os
import random
import math
from datetime import datetime
from collections import Counter, defaultdict
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
MAX_CONFIDENCE = 90
RESET_ID = 0
WINDOW = 5

# =====================================================================
# HTML TEMPLATE (GIỮ NGUYÊN 100%)
# =====================================================================
HTML_TEMPLATE = """..."""  # <-- GIỮ NGUYÊN NHƯ CŨ

# =====================================================================
# CORE UTILS
# =====================================================================
def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"


def format_tx(results, length):
    if len(results) < length:
        return None
    return "-".join("T" if r == "Tài" else "X" for r in results[:length])


def _tx(seq):
    return "".join("T" if r == "Tài" else "X" for r in seq)


# =====================================================================
# 🧠 HOUSE-STYLE ENGINE
# =====================================================================

class HouseEngine:
    """
    Engine mô phỏng cách nhà cái "đọc" cầu:
    - Nhiều khung thời gian
    - Markov bậc cao
    - Pattern memory
    - Volatility regime
    - House bias detector
    - Adaptive weights (học từ kết quả gần đây)
    """

    # Trọng số cho từng tín hiệu (có thể học lại)
    DEFAULT_WEIGHTS = {
        "markov1": 0.18,
        "markov2": 0.22,
        "markov3": 0.12,
        "pattern_memory": 0.18,
        "multi_tf": 0.14,
        "streak_physics": 0.10,
        "bias_detector": 0.06,
    }

    def __init__(self):
        self.weights = dict(self.DEFAULT_WEIGHTS)
        self.recent_perf = []  # [(pred, actual), ...] 50 phiên gần nhất

    # ---------- Markov chains ----------
    @staticmethod
    def _markov_1(seq):
        """P(X|T) và P(T|X) từ toàn bộ lịch sử."""
        tt = tx = xt = xx = 0
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i + 1]
            if a == "Tài" and b == "Tài": tt += 1
            elif a == "Tài" and b == "Xỉu": tx += 1
            elif a == "Xỉu" and b == "Tài": xt += 1
            else: xx += 1
        last = seq[0]
        if last == "Tài":
            denom = tt + tx
            p_next_tai = tt / denom if denom else 0.5
        else:
            denom = xt + xx
            p_next_tai = xt / denom if denom else 0.5
        return p_next_tai

    @staticmethod
    def _markov_n(seq, n):
        """Markov bậc n: nhìn n phiên gần nhất để dự đoán phiên tới."""
        if len(seq) < n + 2:
            return None
        ctx = tuple(seq[:n])
        tai_after = xiu_after = 0
        for i in range(n, len(seq) - 1):
            if tuple(seq[i - n + 1:i + 1]) == ctx:
                # actually need careful indexing
                pass
        # Đơn giản hoá: đếm chuỗi n phần tử == ctx, xem phần tử ngay sau
        pat = _tx(ctx)
        s = _tx(seq)
        t_after = x_after = 0
        for i in range(len(s) - n):
            if s[i:i + n] == pat:
                if s[i + n] == "T": t_after += 1
                else: x_after += 1
        total = t_after + x_after
        if total == 0:
            return None
        return t_after / total

    # ---------- Pattern memory ----------
    @staticmethod
    def _pattern_memory(seq, max_len=4):
        """
        Với mỗi độ dài pattern 2..max_len, tìm pattern khớp với tail
        và xem kết quả sau đó trong lịch sử.
        Trả về dict {pattern_len: p_next_tai or None, support: int}
        """
        s = _tx(seq)
        results = {}
        for L in range(2, max_len + 1):
            if len(s) < L + 1:
                continue
            tail = s[:L]  # L phiên mới nhất
            t_after = x_after = 0
            # Tìm tất cả vị trí mà pattern L phần tử == tail
            for i in range(0, len(s) - L):
                if s[i:i + L] == tail:
                    if s[i + L] == "T": t_after += 1
                    else: x_after += 1
            total = t_after + x_after
            if total >= 2:  # cần ít nhất 2 mẫu
                results[L] = (t_after / total, total)
            else:
                results[L] = (None, total)
        return results

    # ---------- Multi-timeframe ----------
    @staticmethod
    def _multi_tf_bias(seq):
        """
        Mỗi khung: 3,5,8,12,20 phiên.
        Bias = %Tài trong khung - 0.5 (dương → nghiêng Tài).
        Trả về bias trung bình có trọng số (khung ngắn quan trọng hơn).
        """
        weights = {3: 0.35, 5: 0.30, 8: 0.18, 12: 0.12, 20: 0.05}
        total_w = 0.0
        bias = 0.0
        for w_len, w in weights.items():
            if len(seq) >= w_len:
                p_tai = sum(1 for r in seq[:w_len] if r == "Tài") / w_len
                bias += (p_tai - 0.5) * w
                total_w += w
        if total_w == 0:
            return 0.0
        return bias / total_w

    # ---------- Streak physics ----------
    @staticmethod
    def _streak_physics(seq):
        """
        Đo "lực" cầu hiện tại.
        Trả về (bias, reason):
            bias > 0 → thiên Tài, < 0 → thiên Xỉu
        """
        if not seq:
            return 0.0, "empty"
        # độ dài streak hiện tại
        streak_val = seq[0]
        streak_len = 1
        for r in seq[1:]:
            if r == streak_val:
                streak_len += 1
            else:
                break
        # đảo 1-1 đã chạy bao lâu
        flips = sum(1 for i in range(min(len(seq) - 1, 5)) if seq[i] != seq[i + 1])

        bias = 0.0
        reason = ""
        if flips >= 4:
            # cầu đảo → nghiêng đảo tiếp (nhưng nhẹ, vì dễ gãy)
            bias = -0.15 if streak_val == "Tài" else 0.15
            reason = f"dao1-1({streak_len})"
        elif streak_len >= 3:
            # bệt dài → nhà cái hay "gãy" ở 4-5, nên bias giảm dần
            decay = max(0.05, 0.25 - 0.04 * (streak_len - 3))
            bias = decay if streak_val == "Xỉu" else -decay
            # tức: bệt Xỉu dài → nghiêng Tài (gãy), bệt Tài dài → nghiêng Xỉu
            reason = f"bet{streak_len}"
        else:
            reason = "normal"
        return bias, reason

    # ---------- House bias detector ----------
    @staticmethod
    def _bias_detector(seq):
        """
        So sánh tỉ lệ Tài thực tế 30 phiên vs 50% lý thuyết.
        Nếu lệch nhiều → nhà cái đang "bẻ cầu" → dự đoán ngược lại xu hướng.
        Trả về bias (dương → thiên Tài).
        """
        if len(seq) < 15:
            return 0.0
        recent = seq[:30]
        p_tai = sum(1 for r in recent if r == "Tài") / len(recent)
        # mean-reversion: nếu lệch > 0.15 → kéo về
        dev = p_tai - 0.5
        if abs(dev) < 0.10:
            return 0.0
        # kéo về phía ngược lại
        return -dev * 0.5

    # ---------- Volatility regime ----------
    @staticmethod
    def _volatility(seq):
        """Entropy của 15 phiên gần nhất. Cao → nhiễu, thấp → mượt."""
        if len(seq) < 10:
            return 0.5
        recent = seq[:15]
        p = sum(1 for r in recent if r == "Tài") / len(recent)
        if p in (0.0, 1.0):
            return 0.0
        ent = -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
        return ent / 1.0  # 0..1

    # ---------- Adaptive learning ----------
    def update_performance(self, pred, actual):
        """Gọi sau khi có kết quả phiên trước đó."""
        if pred in ("Tài", "Xỉu") and actual in ("Tài", "Xỉu"):
            self.recent_perf.append(1 if pred == actual else 0)
            if len(self.recent_perf) > 60:
                self.recent_perf.pop(0)

    def _adaptive_weights(self):
        """Điều chỉnh trọng số dựa trên rolling accuracy 30 phiên."""
        if len(self.recent_perf) < 15:
            return self.weights
        recent = self.recent_perf[-30:]
        acc = sum(recent) / len(recent)
        # Nếu accuracy thấp → tăng trọng số bias_detector và giảm pattern_memory
        w = dict(self.weights)
        if acc < 0.45:
            w["bias_detector"] = min(0.20, w["bias_detector"] + 0.05)
            w["markov1"] = max(0.10, w["markov1"] - 0.03)
            w["pattern_memory"] = max(0.10, w["pattern_memory"] - 0.03)
        elif acc > 0.60:
            w["pattern_memory"] = min(0.25, w["pattern_memory"] + 0.03)
            w["markov2"] = min(0.28, w["markov2"] + 0.02)
            w["bias_detector"] = max(0.03, w["bias_detector"] - 0.02)
        # Chuẩn hoá
        s = sum(w.values())
        return {k: v / s for k, v in w.items()}

    # ---------- Main predict ----------
    def predict(self, results):
        """
        results[0] = phiên mới nhất.
        Trả về (pred, confidence, label)
        """
        if not results:
            return "Tài", 50, "empty"

        if len(results) < 5:
            t = results.count("Tài")
            x = len(results) - t
            if t > x: return "Tài", 55, "short-majority"
            if x > t: return "Xỉu", 55, "short-majority"
            return results[0], 52, "follow-last"

        # ---- Collect signals ----
        signals = {}   # name -> bias (+Tài / -Xỉu)
        supports = {}  # name -> support 0..1

        # 1. Markov bậc 1
        p1 = self._markov_1(results)
        signals["markov1"] = p1 - 0.5
        supports["markov1"] = 0.6

        # 2. Markov bậc 2, 3
        for n in (2, 3):
            pn = self._markov_n(results, n)
            if pn is not None:
                signals[f"markov{n}"] = pn - 0.5
                supports[f"markov{n}"] = 0.7 if n == 2 else 0.5

        # 3. Pattern memory
        pm = self._pattern_memory(results, max_len=4)
        pm_bias = 0.0
        pm_support = 0.0
        pm_total = 0
        for L, (p, sup) in pm.items():
            if p is not None:
                w = {2: 0.5, 3: 0.3, 4: 0.2}.get(L, 0.1)
                pm_bias += (p - 0.5) * w
                pm_support += w
                pm_total += sup
        if pm_support > 0:
            pm_bias /= pm_support
        signals["pattern_memory"] = pm_bias
        supports["pattern_memory"] = min(1.0, pm_total / 10.0)

        # 4. Multi-timeframe
        signals["multi_tf"] = self._multi_tf_bias(results)
        supports["multi_tf"] = 0.8

        # 5. Streak physics
        sp_bias, sp_reason = self._streak_physics(results)
        signals["streak_physics"] = sp_bias
        supports["streak_physics"] = 0.7

        # 6. House bias detector
        signals["bias_detector"] = self._bias_detector(results)
        supports["bias_detector"] = 0.6

        # ---- Weighted sum ----
        w = self._adaptive_weights()
        total_score = 0.0
        total_weight = 0.0
        for name, bias in signals.items():
            if name in w:
                eff_w = w[name] * supports.get(name, 0.5)
                total_score += bias * eff_w
                total_weight += eff_w

        if total_weight == 0:
            return results[0], 52, "fallback"

        score = total_score / total_weight  # -1..1
        pred = "Tài" if score >= 0 else "Xỉu"

        # ---- Anti-trap tinh chỉnh ----
        # nếu score quá sát 0 → theo streak hiện tại
        if abs(score) < 0.02:
            pred = results[0]
            label_extra = "edge"
        else:
            label_extra = ""

        # entropy penalty
        vol = self._volatility(results)
        conf_raw = 50 + abs(score) * 40  # 50..90
        conf_raw *= (1 - 0.25 * vol)  # nhiễu cao → giảm
        conf = int(round(conf_raw))
        conf = max(52, min(MAX_CONFIDENCE, conf))

        # random jitter nhẹ
        conf += random.randint(-2, 2)
        conf = max(52, min(MAX_CONFIDENCE, conf))

        # ---- Label ----
        seq5 = results[:5]
        pattern = _tx(seq5)
        flips = sum(1 for i in range(4) if seq5[i] != seq5[i + 1])
        if flips == 4:
            mode = "Đảo 1-1"
        elif flips <= 2:
            mode = f"Bệt {self._streak_len(results)}P"
        else:
            mode = "Hỗn tạp"
        label = f"{mode} ({pattern}) | {sp_reason}{label_extra}"

        return pred, conf, label

    @staticmethod
    def _streak_len(seq):
        v = seq[0]
        n = 1
        for r in seq[1:]:
            if r == v: n += 1
            else: break
        return n


# Singleton engine
ENGINE = HouseEngine()


def compute_prediction(results):
    return ENGINE.predict(results)


# =====================================================================
# API & ROUTES (giữ nguyên)
# =====================================================================
def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(API_URL_MD5, timeout=8, headers=headers)
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
                return rows, True
    except Exception as e:
        print(f"[API ERROR]: {e}")
    return [], False


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    global RESET_ID
    try:
        raw_rows, success = fetch_sessions()
        if raw_rows:
            for row in raw_rows:
                HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
                del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'rows': [], 'stats': {'total': 0, 'correct': 0}})

        # Cập nhật performance của engine (dùng cho adaptive weights)
        # Duyệt từ cũ → mới, mỗi bước predict rồi so với actual
        history_for_engine = [v['result'] for v in valid][::-1]  # mới nhất trước
        ENGINE.recent_perf = []
        # Replay để build recent_perf
        replay = []
        for i in range(len(history_for_engine) - 1, -1, -1):
            if i < len(history_for_engine) - 1:
                # có ít nhất 1 phiên sau
                hist_at_i = history_for_engine[i + 1:]  # các phiên cũ hơn
                if len(hist_at_i) >= 1:
                    p, _, _ = ENGINE.predict(hist_at_i)
                    actual = history_for_engine[i]
                    ENGINE.update_performance(p, actual)
            replay.append(history_for_engine[i])
        # Giới hạn 60
        ENGINE.recent_perf = ENGINE.recent_perf[-60:]

        out = []
        correct_count = 0
        total_past = 0
        next_pred, next_conf, _ = compute_prediction(history_for_engine)

        out.append({
            'phien': valid[-1]['phien'] + 1,
            'is_next': True,
            'prediction': next_pred,
            'result': 'Chờ...',
            'dice': "? + ? + ?",
            'is_correct': None,
            'conf': next_conf,
            'recovery_flipped': False,
            'loss_streak': 0
        })

        for i in range(len(valid) - 1, max(-1, len(valid) - 150), -1):
            hist = [v['result'] for v in valid[:i]][::-1]
            if len(hist) >= 5:
                pred, conf, _ = compute_prediction(hist)
            elif len(hist) > 0:
                t = hist.count("Tài")
                x = len(hist) - t
                if t > x: pred, conf = "Tài", 55
                elif x > t: pred, conf = "Xỉu", 55
                else: pred, conf = hist[0], 52
            else:
                pred, conf = "-", 50

            is_correct = (pred == valid[i]['result']) if pred != "-" else None
            if is_correct is not None:
                total_past += 1
            if is_correct:
                correct_count += 1

            out.append({
                'phien': valid[i]['phien'],
                'is_next': False,
                'prediction': pred,
                'result': valid[i]['result'],
                'dice': valid[i]['dice'],
                'is_correct': is_correct,
                'conf': conf,
                'recovery_flipped': False
            })

        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e), 'rows': [], 'stats': {'total': 0, 'correct': 0}})


@app.route('/api/predict')
def predict():
    global RESET_ID
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            for row in raw_rows:
                HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
                del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'error': 'Chưa có dữ liệu'})

        results = [v['result'] for v in valid][::-1]
        pred, conf, pattern_label = compute_prediction(results)

        ls_5p = format_tx(results, 5)

        return jsonify({
            'last_phien': valid[-1]['phien'],
            'next_phien': valid[-1]['phien'] + 1,
            'prediction': pred,
            'confidence': conf,
            'recovery_flipped': False,
            'loss_streak': 0,
            'ls_5p': ls_5p,
            'pattern_label': pattern_label,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/lc79')
@app.route('/lc79md5')
def lc79_api():
    global RESET_ID
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            for row in raw_rows:
                HISTORY_CACHE[row['phien']] = row
            for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
                del HISTORY_CACHE[k]

        valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
        if not valid:
            return jsonify({'id': '@cskhleminh', 'phien': '-', 'du_doan': '-', 'do_tin_cay': '50%'})

        results = [v['result'] for v in valid][::-1]
        pred, conf, pattern_label = compute_prediction(results)
        ls_5p = format_tx(results, 5)

        return jsonify({
            'id': '@cskhleminh',
            'phien': str(valid[-1]['phien'] + 1),
            'ket_qua': f"{valid[-1]['result'].lower()} {valid[-1]['dice'].replace(' + ', '-')}",
            'du_doan': pred,
            'do_tin_cay': f"{conf}%",
            'ls_5p': ls_5p,
            'cau': pattern_label,
            'auto_flip': False,
            'chuoi_thua': 0
        })
    except Exception as e:
        return jsonify({'id': '@cskhleminh', 'phien': '-', 'du_doan': '-', 'do_tin_cay': '50%', 'error': str(e)})


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE
    try:
        raw_rows, _ = fetch_sessions()
        if raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                ENGINE.recent_perf = []
                return jsonify({'status': 'success', 'reset_to': RESET_ID})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
