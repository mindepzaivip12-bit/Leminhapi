import os
import math
import traceback
from datetime import datetime
from collections import defaultdict
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
PREDICTION_CACHE = {}
LAST_PREDICTIONS = {}          # phien -> (pred, conf) — dự đoán ĐÃ HIỂN THỊ
MAX_PREDICTION_CACHE = 2000
RESET_ID = 0

HTML_TEMPLATE = """..."""  # ← GIỮ NGUYÊN template HTML gốc


# =====================================================================
# DATA FETCHER
# =====================================================================
def fetch_sessions():
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(API_URL_MD5, timeout=5, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if 'list' in data and data['list']:
                rows = []
                for item in data['list']:
                    res = "Tài" if item['resultTruyenThong'] == "TAI" else "Xỉu"
                    dices = item.get('dices', [0, 0, 0])
                    dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
                    total = item.get('point', sum(dices))
                    rows.append({'phien': int(item['id']), 'result': res, 'dice': dice_str, 'total': total})
                return rows, True
    except Exception as e:
        print(f"[API ERROR]: {e}")
    return [], False


# =====================================================================
# UTILS
# =====================================================================
def get_groups(results):
    if not results: return []
    groups = []
    current_val = results[0]
    count = 1
    for r in results[1:]:
        if r == current_val: count += 1
        else:
            groups.append(count); current_val = r; count = 1
    groups.append(count)
    return groups


def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"


def _count_alternations(results, max_len=15):
    count = 0
    for i in range(min(len(results) - 1, max_len)):
        if results[i] != results[i+1]: count += 1
        else: break
    return count


# =====================================================================
# CORE STATISTICAL ALGORITHMS (không đổi)
# =====================================================================
def algo_bet_break(results, groups):
    if not groups or len(results) < 3: return []
    sigs = []
    r0 = results[0]; g0 = groups[0]; n = len(results)
    if   g0 >= 12: sigs.append((_opp(r0), 42, "bet_12plus"))
    elif g0 >= 10: sigs.append((_opp(r0), 38, "bet_10plus"))
    elif g0 >= 8:  sigs.append((_opp(r0), 32, "bet_8_9"))
    elif g0 >= 6:  sigs.append((_opp(r0), 25, "bet_6_7"))
    elif g0 == 5:  sigs.append((_opp(r0), 18, "bet_5"))
    elif g0 == 4:  sigs.append((_opp(r0), 12, "bet_4"))
    elif g0 == 3:
        if len(groups) >= 5:
            past = groups[1:min(12, len(groups))]
            avg_g = sum(past) / len(past)
            if   avg_g < 2.3: sigs.append((_opp(r0), 13, "bet_3_break"))
            elif avg_g >= 3.5: sigs.append((r0, 11, "bet_3_cont"))
            else:              sigs.append((_opp(r0), 9, "bet_3_def"))
        else: sigs.append((_opp(r0), 9, "bet_3_def"))
    return sigs


def algo_alternation(results):
    if len(results) < 4: return None
    alt = _count_alternations(results)
    if   alt >= 8: return (_opp(results[0]), 26, "alt_8plus")
    elif alt >= 6: return (_opp(results[0]), 22, "alt_6_7")
    elif alt >= 4: return (_opp(results[0]), 16, "alt_4_5")
    elif alt >= 3: return (_opp(results[0]), 10, "alt_3")
    return None


def algo_recency_momentum(results):
    n = len(results)
    if n < 8: return None
    st = sx = 0
    for i in range(min(n, 20)):
        w = 20 - i
        if results[i] == "Tài": st += w
        else: sx += w
    total = st + sx
    if total == 0: return None
    if max(st, sx) / total < 0.68: return None
    return ("Tài", 9, "recency_tai") if st > sx else ("Xỉu", 9, "recency_xiu")


def algo_weighted_trend(results):
    n = len(results)
    if n < 10: return None
    weights = [10.0, 8.0, 6.0, 4.0, 3.0, 2.0, 1.5, 1.0, 0.8, 0.5]
    tw = sw = 0.0
    for i, r in enumerate(results[:10]):
        w = weights[i]; tw += w
        if r == "Tài": sw += w
    if tw == 0: return None
    ratio = sw / tw
    if ratio >= 0.72: return ("Tài", 10, "wt_trend_tai")
    if ratio <= 0.28: return ("Xỉu", 10, "wt_trend_xiu")
    return None


def algo_markov1(results):
    if len(results) < 15: return None
    tr = {"Tài": {"Tài": 0, "Xỉu": 0}, "Xỉu": {"Tài": 0, "Xỉu": 0}}
    for i in range(len(results[:45]) - 1):
        tr[results[i+1]][results[i]] += 1
    last = results[0]; tot = sum(tr[last].values())
    if tot < 5: return None
    p = tr[last]["Tài"] / tot
    if   p >= 0.65: return ("Tài", 10, "markov1")
    elif p <= 0.35: return ("Xỉu", 10, "markov1")
    return None


def algo_multi_window(results):
    n = len(results)
    if n < 15: return None
    w5 = results[:5].count("Tài"); w10 = results[:10].count("Tài"); w15 = results[:15].count("Tài")
    vt = sum([w5 >= 4, w10 >= 7, w15 >= 10]); vx = sum([w5 <= 1, w10 <= 3, w15 <= 5])
    if   vt >= 2: return ("Tài", 11, "multi_window")
    elif vx >= 2: return ("Xỉu", 11, "multi_window")
    return None


def algo_hot_tilt(results):
    n = len(results)
    if n < 12: return None
    for w, hi, lo in ((8, 7, 1), (12, 10, 2)):
        if n < w: continue
        tc = results[:w].count("Tài")
        if tc >= hi: return ("Xỉu", 14 if w == 8 else 12, f"hot_tai_{w}")
        elif tc <= lo: return ("Tài", 14 if w == 8 else 12, f"hot_xiu_{w}")
    return None


def algo_tilt_ratio(results):
    n = len(results)
    if n < 15: return None
    for window in (15, 20, 30):
        if n < window: continue
        tr = results[:window].count("Tài") / window
        if   tr >= 0.73: return ("Xỉu", 10, f"tilt_tai_{window}")
        elif tr <= 0.27: return ("Tài", 10, f"tilt_xiu_{window}")
    return None


def algo_entropy(results):
    if len(results) < 20: return None
    p_tai = results[:20].count("Tài") / 20
    if p_tai in (0, 1): return ("Tài" if p_tai > 0.5 else "Xỉu", 9, "entropy_zero")
    entropy = -(p_tai * math.log2(p_tai) + (1-p_tai) * math.log2(1-p_tai))
    if entropy < 0.6: return ("Tài" if p_tai > 0.5 else "Xỉu", 9, "entropy_low")
    return None


def algo_simple_enhanced(results):
    if len(results) < 3: return None
    r0 = results[0]; streak = 1
    for r in results[1:]:
        if r == r0: streak += 1
        else: break
    if streak == 1:
        if len(results) >= 3 and results[1] == results[2]:
            return (_opp(r0), 8, "simple_break_pair")
        return (r0, 8, "simple_continue")
    if streak == 2: return (r0, 9, "simple_momentum")
    if streak == 3: return (_opp(r0), 10, "simple_break_3")
    if streak >= 4: return (_opp(r0), 11, "simple_break_4")
    return None


def algo_runlength_compare(results):
    n = len(results)
    if n < 20: return None
    groups = get_groups(results)
    if len(groups) < 4: return None
    cur = groups[0]; past = groups[1:min(20, len(groups))]
    if not past: return None
    avg = sum(past) / len(past)
    if cur > avg * 1.6 and cur >= 3: return (_opp(results[0]), 11, "rl_break")
    if cur < 1.5 and avg >= 2.5: return (results[0], 8, "rl_continue")
    return None


def analyze_full_bridge(results):
    if len(results) < 3: return []
    signals = []
    groups = get_groups(results)
    signals.extend(algo_bet_break(results, groups))
    alt = algo_alternation(results)
    if alt: signals.append(alt)
    for fn in (algo_recency_momentum, algo_weighted_trend, algo_markov1,
               algo_multi_window, algo_hot_tilt, algo_tilt_ratio,
               algo_entropy, algo_simple_enhanced, algo_runlength_compare):
        s = fn(results)
        if s: signals.append(s)
    return signals


# =====================================================================
# BASE PREDICTOR — hoạt động ngay từ phiên 0
# =====================================================================
def full_bridge_predict(results):
    if not results: return "Tài", 50
    if len(results) == 1: return _opp(results[0]), 52
    if len(results) == 2:
        if results[0] == results[1]: return _opp(results[0]), 55
        return results[1], 52
    signals = analyze_full_bridge(results)
    if not signals: return results[0], 52
    st = sx = 0.0
    for p, w, name in signals:
        if p == "Tài": st += w
        else: sx += w
    total = st + sx
    if total == 0: return results[0], 50
    ratio = max(st, sx) / total
    evidence = min(1.0, total / 40.0)
    conf = int(max(50, min(92, 50 + ((ratio - 0.5) * 100) * evidence)))
    if st > sx: return "Tài", conf
    if sx > st: return "Xỉu", conf
    return _opp(results[0]), 50


# =====================================================================
# ADAPTIVE PREDICTOR (deterministic, tự học trọng số tín hiệu)
# =====================================================================
def full_bridge_predict_adaptive(results, replay_n=80):
    n = len(results)
    if n == 0: return "Tài", 50, []
    if n == 1: return _opp(results[0]), 52, []
    if n == 2:
        if results[0] == results[1]: return _opp(results[0]), 55, []
        return results[1], 52, []

    signal_stats = defaultdict(lambda: {'wins': 0.0, 'total': 0.0})
    replay_count = min(replay_n, n - 3)
    for j in range(replay_count):
        history = results[j + 1:]; actual = results[j]
        decay = math.exp(-j / max(replay_count / 2.0, 1.0))
        for pred_sig, weight, name in analyze_full_bridge(history):
            signal_stats[name]['total'] += decay
            if pred_sig == actual:
                signal_stats[name]['wins'] += decay

    signals = analyze_full_bridge(results)
    if not signals:
        return results[0], 52, []

    st = sx = 0.0; detail = []
    for pred_sig, weight, name in signals:
        s = signal_stats[name]
        if s['total'] >= 3:
            alpha = 2.0
            acc = (s['wins'] + alpha * 0.5) / (s['total'] + alpha)
            samples = int(s['total'])
        else:
            acc, samples = 0.5, int(s['total'])
        accuracy_mult = 0.4 + max(0.0, min(1.8, (acc - 0.3) * 3.0))
        adjusted = weight * accuracy_mult
        if pred_sig == "Tài": st += adjusted
        else: sx += adjusted
        detail.append({'name': name, 'pred': pred_sig, 'base_weight': weight,
                       'accuracy': round(acc, 3), 'samples': samples,
                       'adjusted_weight': round(adjusted, 2)})

    total = st + sx
    if total == 0:
        return results[0], 50, detail
    if st > sx: pred, ratio = "Tài", st / total
    elif sx > st: pred, ratio = "Xỉu", sx / total
    else: return _opp(results[0]), 50, detail

    base_conf = 50 + (ratio - 0.5) * 100
    evidence = min(1.0, total / 50.0)
    conf = 50 + (base_conf - 50) * evidence
    if ratio >= 0.72: conf += 6
    if ratio >= 0.80 and len(signals) >= 5: conf += 6
    if len(signals) >= 8 and ratio >= 0.65: conf += 3
    if len(signals) < 4: conf -= 5
    return pred, int(max(50, min(95, conf))), detail


# =====================================================================
# PREDICTION CACHE — DỰ ĐOÁN NGAY TỪ PHIÊN ĐẦU (bỏ điều kiện <3)
# Ưu tiên dùng LAST_PREDICTIONS (đánh giá trung thực, không hindsight)
# =====================================================================
def get_prediction_for(valid, i):
    key = valid[i]['phien']
    if key in PREDICTION_CACHE:
        return PREDICTION_CACHE[key]

    # Anchor session sau reset → dùng làm history, KHÔNG đánh giá
    if key <= RESET_ID:
        result = ("-", 50, None)
        PREDICTION_CACHE[key] = result
        return result

    # Ưu tiên prediction đã thực sự hiển thị cho user
    if key in LAST_PREDICTIONS:
        pred, conf = LAST_PREDICTIONS[key]
    else:
        hist = [v['result'] for v in valid[:i]][::-1]
        pred, conf = full_bridge_predict(hist)

    is_correct = (pred == valid[i]['result'])
    result = (pred, conf, is_correct)

    if len(PREDICTION_CACHE) > MAX_PREDICTION_CACHE:
        PREDICTION_CACHE.clear()
    PREDICTION_CACHE[key] = result
    return result


# =====================================================================
# PERFORMANCE: loss_streak + recent_accuracy (1 lượt quét)
# =====================================================================
def compute_performance(valid, window=30):
    """Trả về: (loss_streak, recent_acc, recent_total)"""
    if not valid:
        return 0, 0.5, 0

    end = len(valid) - 1

    # Chuỗi thua
    loss_streak = 0
    for i in range(end, max(-1, end - 20) - 1, -1):
        _, _, ok = get_prediction_for(valid, i)
        if ok is None: break
        if ok: break
        loss_streak += 1

    # Accuracy 30 phiên gần nhất
    correct = 0; total = 0
    start = max(0, end - window)
    for i in range(end, start - 1, -1):
        _, _, ok = get_prediction_for(valid, i)
        if ok is None: continue
        total += 1
        if ok: correct += 1
    recent_acc = (correct / total) if total > 0 else 0.5
    return loss_streak, recent_acc, total


# =====================================================================
# AUTO-ADJUST — Tự điều chỉnh khi thấy sai nhiều
# Ưu tiên 1: accuracy tổng thể < 42% → lật
# Ưu tiên 2: chuỗi thua >= 2 → lật/giảm conf
# Boost khi accuracy > 60%
# =====================================================================
def apply_auto_adjust(base_pred, base_conf, valid):
    loss_streak, recent_acc, recent_total = compute_performance(valid)

    # Ưu tiên cao: accuracy 30 phiên < 42% → thuật toán đang sai hướng, lật
    if recent_total >= 15 and recent_acc < 0.42:
        return (_opp(base_pred), min(90, base_conf + 8),
                True, "flip_low_accuracy", loss_streak, recent_acc)

    # Chuỗi thua
    if loss_streak >= 5:
        return (_opp(base_pred), min(96, base_conf + 18),
                True, "flip_streak_5plus", loss_streak, recent_acc)
    if loss_streak == 4:
        return (_opp(base_pred), min(95, base_conf + 14),
                True, "flip_streak_4", loss_streak, recent_acc)
    if loss_streak == 3:
        return (_opp(base_pred), min(94, base_conf + 10),
                True, "flip_streak_3", loss_streak, recent_acc)
    if loss_streak == 2:
        if base_conf < 75:
            return (_opp(base_pred), min(93, base_conf + 6),
                    True, "flip_streak_2", loss_streak, recent_acc)
        return (base_pred, max(50, base_conf - 10),
                False, "penalty_streak_2", loss_streak, recent_acc)
    if loss_streak == 1:
        return (base_pred, max(50, base_conf - 5),
                False, "penalty_streak_1", loss_streak, recent_acc)

    # Tự tin tăng khi accuracy tốt
    if recent_total >= 15 and recent_acc > 0.60:
        return (base_pred, min(95, base_conf + 5),
                False, "boost_good_acc", loss_streak, recent_acc)

    return base_pred, base_conf, False, None, loss_streak, recent_acc


# =====================================================================
# STORAGE HELPERS
# =====================================================================
def _store_last_prediction(phien, pred, conf):
    LAST_PREDICTIONS[phien] = (pred, conf)
    if len(LAST_PREDICTIONS) > MAX_PREDICTION_CACHE:
        for k in sorted(LAST_PREDICTIONS.keys())[:len(LAST_PREDICTIONS) - MAX_PREDICTION_CACHE]:
            del LAST_PREDICTIONS[k]


def _sync_history():
    """Fetch, merge vào cache, lọc theo RESET_ID. Trả về (valid, success)."""
    raw_rows, success = fetch_sessions()
    if not success and not HISTORY_CACHE:
        return [], False
    for row in raw_rows:
        HISTORY_CACHE[row['phien']] = row
    for k in [k for k in HISTORY_CACHE if k <= RESET_ID and RESET_ID > 0]:
        if k < RESET_ID:
            del HISTORY_CACHE[k]
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    return valid, True


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
            # Sau reset, chưa có phiên nào → vẫn dự đoán ngay
            base_pred, base_conf, _ = full_bridge_predict_adaptive([])
            next_pred, next_conf, flipped, reason, ls, acc = apply_auto_adjust(base_pred, base_conf, [])
            return jsonify({
                'rows': [{
                    'phien': RESET_ID + 1, 'is_next': True,
                    'prediction': next_pred, 'result': 'Chờ...',
                    'dice': "? + ? + ?", 'is_correct': None,
                    'conf': next_conf, 'recovery_flipped': flipped,
                    'recovery_reason': reason, 'loss_streak': ls,
                    'base_prediction': base_pred if flipped else None,
                }],
                'stats': {'total': 0, 'correct': 0},
                'loss_streak': ls,
                'recovery_active': flipped,
                'recovery_reason': reason,
                'base_prediction': base_pred,
                'recent_accuracy': round(acc * 100, 1),
                'recent_total': 0,
            })

        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]

        base_pred, base_conf, _ = full_bridge_predict_adaptive(history_for_next)
        next_pred, next_conf, flipped, reason, loss_streak, recent_acc = apply_auto_adjust(
            base_pred, base_conf, valid
        )
        _store_last_prediction(next_phien, next_pred, next_conf)

        out = [{
            'phien': next_phien, 'is_next': True,
            'prediction': next_pred, 'result': 'Chờ...',
            'dice': "? + ? + ?", 'is_correct': None,
            'conf': next_conf, 'recovery_flipped': flipped,
            'recovery_reason': reason, 'loss_streak': loss_streak,
            'base_prediction': base_pred if flipped else None,
        }]

        correct_count = 0
        total_past = 0
        scan_limit = min(len(valid), 200)
        for i in range(len(valid) - 1, len(valid) - scan_limit - 1, -1):
            if i < 0: break
            current_session = valid[i]
            if current_session['phien'] <= RESET_ID:
                continue  # Anchor session: dùng làm history, không hiển thị
            pred, conf, is_correct = get_prediction_for(valid, i)
            if is_correct is not None: total_past += 1
            if is_correct: correct_count += 1
            out.append({
                'phien': current_session['phien'], 'is_next': False,
                'prediction': pred, 'result': current_session['result'],
                'dice': current_session['dice'], 'is_correct': is_correct,
                'conf': conf, 'recovery_flipped': False,
            })

        return jsonify({
            'rows': out,
            'stats': {'total': total_past, 'correct': correct_count},
            'loss_streak': loss_streak,
            'recovery_active': flipped,
            'recovery_reason': reason,
            'base_prediction': base_pred,
            'recent_accuracy': round(recent_acc * 100, 1),
            'recent_total': compute_performance(valid)[2],
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

        results = [v['result'] for v in valid][::-1] if valid else []
        base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason, loss_streak, recent_acc = apply_auto_adjust(
            base_pred, base_conf, valid
        )
        next_phien = (valid[-1]['phien'] + 1) if valid else (RESET_ID + 1)
        if valid:
            _store_last_prediction(next_phien, pred, conf)

        last = valid[-1] if valid else None
        return jsonify({
            'last_phien': last['phien'] if last else None,
            'next_phien': next_phien,
            'last_result': last['result'] if last else None,
            'last_dice': last['dice'] if last else None,
            'prediction': pred, 'confidence': conf,
            'base_prediction': base_pred, 'base_confidence': base_conf,
            'recovery_flipped': flipped, 'recovery_reason': reason,
            'loss_streak': loss_streak,
            'recent_accuracy': round(recent_acc * 100, 1),
            'total_sessions': len(valid),
            'signals': detail,
            'tai_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài'), 2),
            'xiu_score': round(sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu'), 2),
            'signal_count': len(detail),
            'timestamp': datetime.now().isoformat()
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

        results = [v['result'] for v in valid][::-1] if valid else []
        base_pred, base_conf, detail = full_bridge_predict_adaptive(results)
        pred, conf, flipped, reason, loss_streak, recent_acc = apply_auto_adjust(
            base_pred, base_conf, valid
        )
        next_phien = (valid[-1]['phien'] + 1) if valid else (RESET_ID + 1)
        if valid:
            _store_last_prediction(next_phien, pred, conf)

        tai_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Tài')
        xiu_score = sum(s['adjusted_weight'] for s in detail if s['pred'] == 'Xỉu')
        total_sig = tai_score + xiu_score
        if total_sig > 0:
            ratio = max(tai_score, xiu_score) / total_sig
            base_conf_f = 50 + (ratio - 0.5) * 100
            evidence = min(1.0, total_sig / 50.0)
            conf_float = max(50.0, min(95.0, 50 + (base_conf_f - 50) * evidence))
        else:
            conf_float = 50.0
        conf_str = f"{conf_float:.1f}".replace(".", ",") + "%"

        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])
        last = valid[-1] if valid else None

        return jsonify({
            'Id': 'le minh v26',
            'Phien': str(next_phien),
            'Ket_qua': last['result'].lower() if last else None,
            'Lich_su': lich_su,
            'Du_doan': pred, 'Do_tin_cay': conf_str,
            'Base_du_doan': base_pred if flipped else None,
            'Auto_flip': flipped,
            'Chuoi_thua': loss_streak,
            'Accuracy_30': round(recent_acc * 100, 1),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE, PREDICTION_CACHE, LAST_PREDICTIONS
    try:
        raw_rows, success = fetch_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                # Reset về phiên kế tiếp → dự đoán ngay từ phiên +1
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}  # Anchor để có history
                PREDICTION_CACHE = {}
                LAST_PREDICTIONS = {}
                return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        return jsonify({'status': 'error', 'message': 'Lỗi mạng, không thể xác nhận mốc Reset'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
