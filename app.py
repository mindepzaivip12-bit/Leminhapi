import os
import math
import time
import hashlib
import traceback
from datetime import datetime
from collections import defaultdict
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
PREDICTION_CACHE = {}
MAX_PREDICTION_CACHE = 3000
RESET_ID = 0
BOOTSTRAP_SESSIONS = []
LAST_FETCH_OK_TS = 0
FETCH_RETRY = 2
FETCH_TIMEOUT = 6

LAYER_PERF = defaultdict(lambda: {"hit": 0, "total": 0})

# =====================================================================
# CẤU HÌNH
# =====================================================================
WINDOW_SIZE = 5
FINGERPRINT_MIN_MATCH = 3
FINGERPRINT_STRONG = 0.72
TRANSITION_MIN_SAMPLES = 6
MOMENTUM_MIN_STREAK = 3
ENTROPY_HIGH = 0.98
ENTROPY_LOW = 0.55

PATTERN_MIN_OCCURRENCES = 3
BAYES_PRIOR_ALPHA = 1.0
MARKOV_ORDER = 2
DRIFT_WINDOW = 30
CONFIDENCE_FLOOR = 50
CONFIDENCE_CEIL = 95

FUZZY_MATCH_RATIO = 0.75
CLUSTER_MIN_SAMPLES = 4
CYCLE_MIN_PERIOD = 4
CYCLE_MAX_PERIOD = 12
CYCLE_MIN_CONFIDENCE = 0.65
MULTI_WINDOW_LIST = (5, 8, 12, 20)
DRIFT_ALPHA = 0.7

CHANGEPOINT_MIN_SEG = 8
RUNLENGTH_MIN_SAMPLES = 4
KALMAN_ALPHA = 0.6
ADAPTIVE_MIN_SAMPLES = 20
CALIBRATION_BINS = 8

# HEEP config
HEEP_WINDOW = 5
HEEP_MIN_SAMPLES = 4
HEEP_STRONG_RATIO = 0.68
HEEP_FAIR_RATIO = 0.60
HEEP_FUZZY_RATIO = 0.80
HEEP_DECAY = 0.85
HEEP_ENTROPY_HIGH = 0.95
HEEP_ENTROPY_LOW = 0.55
HEEP_TREND_LOOKBACK = 20
HEEP_VOLATILITY_MIN = 0.10
HEEP_REVERSAL_STREAK = 3


# =====================================================================
# UTILS
# =====================================================================
def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"


def get_groups(results):
    if not results:
        return []
    groups = []
    cur = results[0]
    cnt = 1
    for r in results[1:]:
        if r == cur:
            cnt += 1
        else:
            groups.append(cnt)
            cur = r
            cnt = 1
    groups.append(cnt)
    return groups


def _entropy(seq):
    if not seq:
        return 0.0
    t = seq.count("Tài")
    p = t / len(seq)
    q = 1 - p
    e = 0.0
    if p > 0:
        e -= p * math.log2(p)
    if q > 0:
        e -= q * math.log2(q)
    return e


def _to_bits(results):
    return "".join("1" if r == "Tài" else "0" for r in results)


def _md5(s):
    return hashlib.md5(s.encode()).hexdigest()


def _safe_div(a, b, default=0.5):
    return a / b if b > 0 else default


def _hamming(a, b):
    if len(a) != len(b):
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
    return sum(1 for x, y in zip(a, b) if x != y)


def _weighted_count(seq, base_pred, decay=0.9):
    w = 0.0
    for i, v in enumerate(seq):
        weight = decay ** i
        if v == base_pred:
            w += weight
    return w


# =====================================================================
# HEEP — PHÂN TÍCH 5 PHIÊN ĐẢO / NGHỊCH / THUẬN (đã sửa bug)
# =====================================================================
def heep_extract_5(results):
    if not results:
        return None
    win = results[:HEEP_WINDOW]
    bits = [1 if r == "Tài" else 0 for r in win]

    streak = 1
    for r in results[1:]:
        if r == results[0]:
            streak += 1
        else:
            break

    alternating = len(bits) >= 5 and all(bits[i] != bits[i + 1] for i in range(len(bits) - 1))

    pair_alt = False
    if len(bits) >= 4:
        p0 = bits[0] == bits[1]
        p1 = bits[2] == bits[3]
        pair_alt = p0 and p1 and bits[0] != bits[2]

    tai_c = win.count("Tài")
    xiu_c = win.count("Xỉu")
    if tai_c >= xiu_c:
        dom, mino, cnt = "Tài", "Xỉu", tai_c
    else:
        dom, mino, cnt = "Xỉu", "Tài", xiu_c

    return {
        "window": win,
        "bits_newest_first": bits,
        "streak": streak,
        "alternating": alternating,
        "pair_alternating": pair_alt,
        "dominant": dom,
        "minority": mino,
        "count_major": cnt,
        "count_minor": HEEP_WINDOW - cnt,
        "ratio_major": round(cnt / HEEP_WINDOW, 4),
        "entropy": round(_entropy(win), 4),
    }


def heep_mode_thuan(results, info=None):
    """THUẬN — theo momentum khi streak đủ dài."""
    if info is None:
        info = heep_extract_5(results)
    if not info:
        return None
    streak = info["streak"]
    if streak < 2:
        return None
    cur = results[0]
    ratio_cur = _weighted_ratio(results, cur, HEEP_DECAY)
    if ratio_cur < HEEP_FAIR_RATIO:
        return None
    if info["entropy"] >= HEEP_ENTROPY_HIGH:
        return None
    weight = 9 + min(6, streak) + int(ratio_cur * 6)
    weight = max(9, min(22, weight))
    return (cur, weight, {
        "mode": "thuan_momentum",
        "streak": streak,
        "weighted_ratio": round(ratio_cur, 3),
        "entropy": info["entropy"],
    })


def heep_mode_nghich(results, info=None):
    """NGHỊCH — mean reversion khi lệch đủ mạnh nhưng chưa đảo cấu trúc."""
    if info is None:
        info = heep_extract_5(results)
    if not info:
        return None
    cur = results[0]
    ratio_cur = _weighted_ratio(results, cur, HEEP_DECAY)
    ratio_opp = 1 - ratio_cur
    if ratio_cur < HEEP_FAIR_RATIO or info["streak"] >= 4:
        return None
    if info["entropy"] < 0.4:
        return None
    pred = _opp(cur)
    weight = 8 + int((ratio_cur - 0.55) * 30)
    weight = max(8, min(18, weight))
    return (pred, weight, {
        "mode": "nghich_reversion",
        "current": cur,
        "weighted_ratio": round(ratio_cur, 3),
        "entropy": info["entropy"],
    })


def heep_mode_dao(results, info=None):
    """ĐẢO — đảo chiều khi phát hiện pattern zig-zag / đảo cấu trúc / streak dài."""
    if info is None:
        info = heep_extract_5(results)
    if not info:
        return None

    if info["alternating"]:
        return (_opp(results[0]), 14, {
            "mode": "dao_1_1",
            "entropy": info["entropy"],
        })

    if info["pair_alternating"]:
        return (_opp(results[0]), 12, {
            "mode": "dao_2_2",
            "entropy": info["entropy"],
        })

    if info["streak"] >= HEEP_REVERSAL_STREAK:
        if len(results) >= 10:
            avg_streak = sum(get_groups(results[1:11])) / max(1, len(get_groups(results[1:11])))
        else:
            avg_streak = 2.0
        if info["streak"] >= avg_streak * 1.6:
            return (_opp(results[0]), 11, {
                "mode": "dao_streak_break",
                "streak": info["streak"],
                "avg_streak": round(avg_streak, 2),
            })

    return None


def lc79_heep(results):
    """
    Tổng hợp 3 mode HEEP (Thuận/Nghịch/Đảo).
    Trả về (pred, weight, info) hoặc None.
    """
    if not results or len(results) < 5:
        return None
    info = heep_extract_5(results)
    if not info:
        return None

    signals = []
    for fn in (heep_mode_dao, heep_mode_nghich, heep_mode_thuan):
        try:
            r = fn(results, info)
        except Exception:
            r = None
        if r:
            signals.append(r)

    if not signals:
        return None

    st = sx = 0.0
    for pred, w, _ in signals:
        if pred == "Tài":
            st += w
        else:
            sx += w
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    total = st + sx
    ratio = max(st, sx) / total

    weight = 10 + int((ratio - 0.5) * 30) + len(signals) * 2
    weight = max(10, min(24, weight))

    return (pred, weight, {
        "mode": "heep_5",
        "signals": [
            {"pred": p, "w": round(w, 2), "info": i} for p, w, i in signals
        ],
        "info": info,
        "ratio": round(ratio, 3),
    })


# =====================================================================
# TẦNG 1: MD5 FINGERPRINT (đã sửa forward-looking)
# =====================================================================
def lc79_fingerprint(results):
    if len(results) < 10:
        return None
    # Đảo thành "newest last" để forward-looking đúng
    bits = _to_bits(results[::-1])  # bits[-1] = mới nhất
    best = None

    for ws in (7, 6, 5, 4, 3):
        if len(bits) < ws + 5:
            continue
        cur_fp = bits[-ws:]  # pattern mới nhất
        tai_next = xiu_next = 0.0
        total = 0.0
        fuzzy_hits = []

        # Tìm pattern khớp quá khứ và xem giá trị KẾ TIẾP
        for i in range(0, len(bits) - ws):
            segment = bits[i:i + ws]
            nxt = bits[i + ws]  # ← SỬA: giá trị tiếp theo
            if segment == cur_fp:
                if nxt == "1":
                    tai_next += 1
                else:
                    xiu_next += 1
                total += 1
            else:
                ham = _hamming(segment, cur_fp)
                sim = 1.0 - ham / ws
                if sim >= FUZZY_MATCH_RATIO:
                    if nxt == "1":
                        tai_next += sim
                    else:
                        xiu_next += sim
                    total += sim
                    fuzzy_hits.append(sim)

        if total < FINGERPRINT_MIN_MATCH:
            continue
        p_tai = tai_next / total
        ratio = max(p_tai, 1 - p_tai)
        if ratio < 0.60:
            continue
        fuzzy_bonus = 1.0 + (len(fuzzy_hits) / max(total, 1)) * 0.3
        score = ratio * math.log2(total + 1) * (ws / 5.0) * fuzzy_bonus
        if best is None or score > best["score"]:
            pred = "Tài" if p_tai >= 0.5 else "Xỉu"
            best = {
                "pred": pred, "ratio": ratio, "samples": total,
                "window": ws, "score": score,
                "exact": int(total - len(fuzzy_hits)),
                "fuzzy": len(fuzzy_hits),
            }

    if not best:
        return None
    sample_bonus = min(7, int(math.log2(best["samples"] + 1) * 2.5))
    window_bonus = min(3, max(0, best["window"] - 4))
    fuzzy_bonus = min(3, best["fuzzy"] // 3)
    weight = 11 + sample_bonus + window_bonus + fuzzy_bonus + int((best["ratio"] - 0.5) * 30)
    weight = max(11, min(28, weight))
    return (best["pred"], weight, {
        "fp": _md5(bits[-best["window"]:])[:8],
        "samples": round(best["samples"], 2),
        "ratio": round(best["ratio"], 3),
        "window": best["window"],
        "exact": best["exact"],
        "fuzzy": best["fuzzy"],
    })


# =====================================================================
# TẦNG 2: MD5 TRANSITION (đã sửa)
# =====================================================================
def lc79_transition_md5(results):
    if len(results) < 20:
        return None
    bits = _to_bits(results[::-1])
    signals = []

    for order in (2, 3, 4, 5):
        if len(bits) < order + 10:
            continue
        cur_key = _md5(bits[-order:])
        tr = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
        for i in range(0, len(bits) - order):
            k = _md5(bits[i:i + order])
            nxt = bits[i + order]  # ← SỬA
            tr[k][("Tài" if nxt == "1" else "Xỉu")] += 1
        d = tr.get(cur_key)
        if not d:
            continue
        tot = d["Tài"] + d["Xỉu"]
        if tot < TRANSITION_MIN_SAMPLES:
            continue
        p_tai = (d["Tài"] + BAYES_PRIOR_ALPHA) / (tot + 2 * BAYES_PRIOR_ALPHA)
        ratio = max(p_tai, 1 - p_tai)
        if ratio < 0.62:
            continue
        signals.append({
            "pred": "Tài" if p_tai >= 0.5 else "Xỉu",
            "ratio": ratio, "samples": tot, "order": order,
        })

    if not signals:
        return None
    st = sx = 0.0
    for s in signals:
        w = s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] ** 0.5)
        if s["pred"] == "Tài":
            st += w
        else:
            sx += w
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    if ratio < 0.58:
        return None
    weight = 9 + int((ratio - 0.6) * 45) + len(signals) * 2
    weight = max(9, min(24, weight))
    return (pred, weight, {
        "samples": sum(s["samples"] for s in signals),
        "ratio": round(ratio, 3),
        "orders": [s["order"] for s in signals],
    })


# =====================================================================
# TẦNG 3: MOMENTUM + ENTROPY
# =====================================================================
def lc79_momentum_entropy(results):
    if len(results) < 10:
        return None
    streak = 1
    for r in results[1:]:
        if r == results[0]:
            streak += 1
        else:
            break
    e = _entropy(results[:20]) if len(results) >= 20 else _entropy(results)

    if len(results) >= 6 and all(results[i] != results[i + 1] for i in range(6)):
        return (_opp(results[0]), 13, {"type": "alt_1_1", "entropy": round(e, 3)})

    if len(results) >= 8:
        pairs = [(results[i], results[i + 1]) for i in range(0, 8, 2)]
        if all(p[0] == p[1] for p in pairs):
            pv = [p[0] for p in pairs]
            if all(pv[i] != pv[i + 1] for i in range(len(pv) - 1)):
                return (_opp(pv[-1]), 12, {"type": "alt_2_2", "entropy": round(e, 3)})

    if MOMENTUM_MIN_STREAK <= streak <= 8:
        window = results[:12]
        w_tai = _weighted_count(window, "Tài", 0.85)
        w_xiu = _weighted_count(window, "Xỉu", 0.85)
        tw = w_tai + w_xiu
        if tw > 0:
            p_tai = w_tai / tw
            dom = "Tài" if p_tai > 0.5 else "Xỉu"
            ratio = max(p_tai, 1 - p_tai)
            if ratio >= 0.60:
                w = 13 if e < 0.85 else 10
                t = "momentum_hold" if results[0] == dom else "momentum_break"
                return (dom, w, {"type": t, "streak": streak,
                                 "ratio": round(ratio, 3), "entropy": round(e, 3)})

    if e >= ENTROPY_HIGH:
        return (_opp(results[0]), 9, {"type": "entropy_reverse", "entropy": round(e, 3)})

    if e <= ENTROPY_LOW and len(results) >= 20:
        tc = results[:20].count("Tài")
        if tc >= 15:
            return ("Xỉu", 12, {"type": "pressure_tai", "tai": tc})
        if tc <= 5:
            return ("Tài", 12, {"type": "pressure_xiu", "tai": tc})
    return None


# =====================================================================
# TẦNG 4: PATTERN N-GRAM (đã sửa)
# =====================================================================
def lc79_pattern_ngram(results):
    if len(results) < 20:
        return None
    bits = _to_bits(results[::-1])
    signals = []

    for order in (3, 4, 5, 6):
        if len(bits) < order + 10:
            continue
        cur = bits[-order:]
        tai = xiu = 0
        for i in range(0, len(bits) - order):
            if bits[i:i + order] == cur:
                if bits[i + order] == "1":
                    tai += 1
                else:
                    xiu += 1
        tot = tai + xiu
        if tot < PATTERN_MIN_OCCURRENCES:
            continue
        p_tai = (tai + BAYES_PRIOR_ALPHA) / (tot + 2 * BAYES_PRIOR_ALPHA)
        ratio = max(p_tai, 1 - p_tai)
        if ratio < 0.62:
            continue
        signals.append({
            "pred": "Tài" if p_tai >= 0.5 else "Xỉu",
            "ratio": ratio, "samples": tot, "order": order, "type": "forward",
        })

    if not signals:
        return None
    st = sx = 0.0
    for s in signals:
        w = s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] - 1)
        if s["pred"] == "Tài":
            st += w
        else:
            sx += w
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    weight = 10 + int((ratio - 0.6) * 40) + len(signals) * 2
    weight = max(10, min(25, weight))
    return (pred, weight, {
        "ratio": round(ratio, 3),
        "n_signals": len(signals),
        "total_samples": sum(s["samples"] for s in signals),
    })


# =====================================================================
# TẦNG 5: MARKOV (đã sửa)
# =====================================================================
def lc79_markov2(results):
    if len(results) < 25:
        return None
    bits = _to_bits(results[::-1])
    if len(bits) < 3:
        return None
    signals = []
    for order in (2, 3, 4, 5):
        if len(bits) < order + 10:
            continue
        cur_state = bits[-order:]
        tr = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
        for i in range(0, len(bits) - order):
            state = bits[i:i + order]
            nxt = bits[i + order]  # ← SỬA
            tr[state][("Tài" if nxt == "1" else "Xỉu")] += 1
        d = tr.get(cur_state)
        if not d:
            continue
        tot = d["Tài"] + d["Xỉu"]
        if tot < 4:
            continue
        p_tai = (d["Tài"] + BAYES_PRIOR_ALPHA) / (tot + 2 * BAYES_PRIOR_ALPHA)
        ratio = max(p_tai, 1 - p_tai)
        min_ratio = 0.60 + (order - 2) * 0.02
        if ratio < min_ratio:
            continue
        signals.append({
            "pred": "Tài" if p_tai >= 0.5 else "Xỉu",
            "ratio": ratio, "samples": tot, "order": order,
        })
    if not signals:
        return None
    st = sx = 0.0
    for s in signals:
        w = s["ratio"] * math.log2(s["samples"] + 1) * s["order"]
        if s["pred"] == "Tài":
            st += w
        else:
            sx += w
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    weight = 8 + int((ratio - 0.55) * 40) + len(signals) * 2
    weight = max(8, min(22, weight))
    return (pred, weight, {
        "ratio": round(ratio, 3),
        "orders": [s["order"] for s in signals],
    })


# =====================================================================
# TẦNG 6: BAYESIAN RECENCY
# =====================================================================
def lc79_bayesian_recency(results):
    if len(results) < 15:
        return None
    n = min(len(results), 25)
    wt = wx = 0.0
    for i, r in enumerate(results[:n]):
        w = math.exp(-i / 8.0)
        if r == "Tài":
            wt += w
        else:
            wx += w
    tot = wt + wx
    if tot == 0:
        return None
    p_tai = wt / tot
    ratio = max(p_tai, 1 - p_tai)
    if ratio < 0.63:
        return None
    pred = "Tài" if p_tai >= 0.5 else "Xỉu"
    weight = 7 + int((ratio - 0.6) * 35)
    weight = max(7, min(18, weight))
    return (pred, weight, {"p_tai": round(p_tai, 3), "ratio": round(ratio, 3), "window": n})


# =====================================================================
# TẦNG 7: STREAK PRESSURE
# =====================================================================
def lc79_streak_pressure(results):
    if len(results) < 30:
        return None
    streak = 1
    for r in results[1:]:
        if r == results[0]:
            streak += 1
        else:
            break
    groups = get_groups(results)
    if len(groups) < 5:
        return None
    past = groups[1:min(len(groups), 20)]
    if not past:
        return None
    avg = sum(past) / len(past)
    if streak >= 5 and streak >= avg * 1.8:
        w = 10 + min(5, int(streak / 2))
        return (_opp(results[0]), w, {
            "type": "streak_break", "streak": streak, "avg_group": round(avg, 2),
        })
    return None


# =====================================================================
# TẦNG 8: DICE
# =====================================================================
def _parse_dice_history(valid_rows):
    sums = []
    for row in valid_rows:
        try:
            dice = row.get("dice", "")
            if "+" in dice:
                parts = [p.strip() for p in dice.replace("+", " + ").split("+") if p.strip()]
                if len(parts) >= 3:
                    s = sum(int(p) for p in parts[:3])
                    sums.append(s)
        except Exception:
            continue
    return sums


def lc79_dice_analysis(dice_sums):
    if not dice_sums or len(dice_sums) < 15:
        return None
    recent = dice_sums[:20]
    avg = sum(recent) / len(recent)
    dev = avg - 10.5
    if abs(dev) < 1.2:
        return None
    pred = "Xỉu" if dev > 0 else "Tài"
    strength = min(1.0, abs(dev) / 3.0)
    weight = 7 + int(strength * 10)
    return (pred, weight, {
        "type": "dice_bias", "avg_dice": round(avg, 2),
        "deviation": round(dev, 2), "samples": len(recent),
    })


# =====================================================================
# TẦNG 9: MD5 CLUSTER (đã sửa)
# =====================================================================
def lc79_md5_cluster(results):
    if len(results) < 25:
        return None
    bits = _to_bits(results[::-1])
    cur_prefix = _md5(bits[-5:])[:3]
    cluster = []
    for i in range(0, len(bits) - 5):
        h = _md5(bits[i:i + 5])[:3]
        if h == cur_prefix:
            cluster.append(bits[i + 5])  # ← SỬA
    if len(cluster) < CLUSTER_MIN_SAMPLES:
        return None
    tai = cluster.count("1")
    xiu = cluster.count("0")
    tot = len(cluster)
    p_tai = (tai + BAYES_PRIOR_ALPHA) / (tot + 2 * BAYES_PRIOR_ALPHA)
    ratio = max(p_tai, 1 - p_tai)
    if ratio < 0.65:
        return None
    pred = "Tài" if p_tai >= 0.5 else "Xỉu"
    weight = 9 + int((ratio - 0.6) * 40) + min(3, tot // 5)
    weight = max(9, min(21, weight))
    return (pred, weight, {
        "cluster_prefix": cur_prefix,
        "cluster_size": tot,
        "tai": tai, "xiu": xiu,
        "ratio": round(ratio, 3),
    })


# =====================================================================
# TẦNG 10: CYCLE DETECTOR
# =====================================================================
def lc79_cycle_detector(results):
    if len(results) < 24:
        return None
    best = None
    for period in range(CYCLE_MIN_PERIOD, CYCLE_MAX_PERIOD + 1):
        if len(results) < period * 2 + 2:
            continue
        matches = checks = 0
        for offset in range(1, period * 2 + 1):
            if offset >= len(results) or period >= len(results):
                continue
            checks += 1
            if results[offset - 1] == results[offset - 1 + period]:
                matches += 1
        if checks < period:
            continue
        conf = matches / checks
        if conf < CYCLE_MIN_CONFIDENCE:
            continue
        if period < len(results):
            pred = results[period - 1]
            score = conf * math.log2(checks + 1) / period
            if best is None or score > best["score"]:
                best = {"pred": pred, "period": period, "confidence": conf, "score": score}
    if not best:
        return None
    weight = 8 + int(best["confidence"] * 15)
    weight = max(8, min(20, weight))
    return (best["pred"], weight, {
        "type": "cycle", "period": best["period"],
        "confidence": round(best["confidence"], 3),
    })


# =====================================================================
# TẦNG 11: BAYESIAN DRIFT
# =====================================================================
def lc79_bayesian_drift(results):
    if len(results) < 30:
        return None
    old = results[15:30]
    new = results[:15]
    ot = old.count("Tài") / len(old)
    nt = new.count("Tài") / len(new)
    drift = nt - ot
    if abs(drift) < 0.25:
        return None
    if nt > 0.65:
        pred = "Tài"
        strength = (nt - 0.5) * 2
    elif nt < 0.35:
        pred = "Xỉu"
        strength = (0.5 - nt) * 2
    else:
        return None
    weight = 7 + int(strength * 8)
    weight = max(7, min(15, weight))
    return (pred, weight, {
        "type": "drift",
        "old_tai_rate": round(ot, 3),
        "new_tai_rate": round(nt, 3),
        "drift": round(drift, 3),
    })


# =====================================================================
# TẦNG 12: MULTI-WINDOW CONSENSUS
# =====================================================================
def lc79_multi_window_consensus(results):
    if len(results) < 20:
        return None
    votes = []
    for ws in MULTI_WINDOW_LIST:
        if len(results) < ws:
            continue
        window = results[:ws]
        p = window.count("Tài") / ws
        if ws <= 8:
            if p >= 0.65:
                votes.append(("Tài", 1.0))
            elif p <= 0.35:
                votes.append(("Xỉu", 1.0))
        else:
            if p >= 0.70:
                votes.append(("Xỉu", 0.8))
            elif p <= 0.30:
                votes.append(("Tài", 0.8))
    if len(votes) < 2:
        return None
    st = sum(w for p, w in votes if p == "Tài")
    sx = sum(w for p, w in votes if p == "Xỉu")
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    if ratio < 0.6:
        return None
    weight = 7 + int((ratio - 0.6) * 30) + len(votes) * 2
    weight = max(7, min(18, weight))
    return (pred, weight, {
        "type": "multi_window",
        "votes": [{"pred": p, "w": w} for p, w in votes],
        "ratio": round(ratio, 3),
    })


# =====================================================================
# TẦNG 13: CHANGEPOINT
# =====================================================================
def lc79_changepoint(results):
    if len(results) < 30:
        return None
    seq = results[:40]
    bits = [1 if r == "Tài" else 0 for r in seq]
    n = len(bits)
    if n < CHANGEPOINT_MIN_SEG * 2:
        return None
    mean = sum(bits) / n
    s_pos = s_neg = best_pos = best_neg = 0.0
    cip = cin = 0
    for i, b in enumerate(bits):
        s_pos = max(0, s_pos + b - mean - 0.05)
        s_neg = max(0, s_neg - b + mean - 0.05)
        if s_pos > best_pos:
            best_pos = s_pos
            cip = i
        if s_neg > best_neg:
            best_neg = s_neg
            cin = i
    th = 2.5
    for best, ci in ((best_pos, cip), (best_neg, cin)):
        if best > th and 3 <= ci <= 10:
            seg = bits[:ci]
            if len(seg) >= 4:
                p = sum(seg) / len(seg)
                if p >= 0.7:
                    return ("Tài", 12, {"type": "cp_up", "change_idx": ci, "p_new": round(p, 3)})
                if p <= 0.3:
                    return ("Xỉu", 12, {"type": "cp_down", "change_idx": ci, "p_new": round(p, 3)})
    return None


# =====================================================================
# TẦNG 14: RUN-LENGTH
# =====================================================================
def lc79_run_length(results):
    if len(results) < 30:
        return None
    groups = get_groups(results)
    if len(groups) < 10:
        return None
    cur = groups[0]
    past = groups[1:min(len(groups), 30)]
    if len(past) < 6:
        return None
    longer = sum(1 for g in past if g > cur)
    equal = sum(1 for g in past if g == cur)
    shorter = sum(1 for g in past if g < cur)
    tot = longer + equal + shorter
    if tot == 0:
        return None
    p_break = (shorter + 0.5 * equal) / tot
    if p_break >= 0.75 and cur >= 3:
        return (_opp(results[0]), 11, {
            "type": "runlength_break", "streak": cur,
            "p_break": round(p_break, 3), "samples": tot,
        })
    p_cont = (longer + 0.5 * equal) / tot
    if p_cont >= 0.80 and cur >= 2:
        return (results[0], 10, {
            "type": "runlength_continue", "streak": cur,
            "p_continue": round(p_cont, 3), "samples": tot,
        })
    return None


# =====================================================================
# TẦNG 15: MEAN REVERSION
# =====================================================================
def lc79_mean_reversion(results):
    if len(results) < 20:
        return None
    window = results[:20]
    p_tai = window.count("Tài") / len(window)
    dev = p_tai - 0.5
    if abs(dev) < 0.22:
        return None
    if dev > 0:
        pred = "Xỉu"
        strength = min(1.0, dev * 3)
    else:
        pred = "Tài"
        strength = min(1.0, abs(dev) * 3)
    recent = results[:6]
    rt = recent.count("Tài") / len(recent)
    if pred == "Tài" and rt > 0.7:
        return None
    if pred == "Xỉu" and rt < 0.3:
        return None
    weight = 7 + int(strength * 9)
    weight = max(7, min(16, weight))
    return (pred, weight, {
        "type": "mean_reversion",
        "p_tai_20": round(p_tai, 3),
        "deviation": round(dev, 3),
    })


# =====================================================================
# TẦNG 16: KALMAN STATE
# =====================================================================
def lc79_kalman_state(results):
    if len(results) < 15:
        return None
    windows = [5, 8, 12, 20]
    estimates = []
    for w in windows:
        if len(results) >= w:
            seg = results[:w]
            estimates.append(seg.count("Tài") / w)
    if len(estimates) < 2:
        return None
    wts = [1.0, 0.9, 0.7, 0.5][:len(estimates)]
    tw = sum(wts)
    smoothed = sum(e * w for e, w in zip(estimates, wts)) / tw
    dev = smoothed - 0.5
    if abs(dev) < 0.12:
        return None
    pred = "Tài" if dev > 0 else "Xỉu"
    strength = min(1.0, abs(dev) * 4)
    weight = 7 + int(strength * 8)
    weight = max(7, min(15, weight))
    return (pred, weight, {
        "type": "kalman",
        "smoothed_p_tai": round(smoothed, 3),
        "estimates": [round(e, 3) for e in estimates],
    })


# =====================================================================
# TẦNG 17: FOURIER
# =====================================================================
def lc79_fourier_period(results):
    if len(results) < 24:
        return None
    bits = [1 if r == "Tài" else 0 for r in results[:32]]
    n = len(bits)
    mean = sum(bits) / n
    centered = [b - mean for b in bits]
    max_p = 0.0
    best_period = 0
    for period in range(3, 13):
        if period >= n - 1:
            continue
        re = sum(centered[i] * math.cos(2 * math.pi * i / period) for i in range(n))
        im = sum(centered[i] * math.sin(2 * math.pi * i / period) for i in range(n))
        p = (re * re + im * im) / n
        if p > max_p:
            max_p = p
            best_period = period
    if max_p < 0.55 or best_period == 0:
        return None
    if best_period < len(results):
        pred = results[best_period - 1]
        weight = 8 + int(min(6, max_p * 4))
        weight = max(8, min(15, weight))
        return (pred, weight, {
            "type": "fourier", "period": best_period,
            "power": round(max_p, 3),
        })
    return None


# =====================================================================
# ADAPTIVE MULTIPLIER
# =====================================================================
def _layer_perf_multiplier(name):
    perf = LAYER_PERF.get(name)
    if not perf or perf["total"] < ADAPTIVE_MIN_SAMPLES:
        return 1.0
    acc = perf["hit"] / perf["total"]
    mult = 0.7 + (acc - 0.5) * 1.2
    return max(0.7, min(1.3, mult))


# =====================================================================
# ENSEMBLE
# =====================================================================
def lc79_predict(results, dice_sums=None):
    n = len(results)
    if n == 0:
        return "Tài", 50, {"mode": "empty"}
    if n == 1:
        return _opp(results[0]), 54, {"mode": "warmup_1"}
    if n == 2:
        if results[0] == results[1]:
            return _opp(results[0]), 57, {"mode": "warmup_2_reverse"}
        return results[0], 53, {"mode": "warmup_2_hold"}
    if n == 3:
        if results[0] != results[1] and results[1] != results[2]:
            return _opp(results[0]), 60, {"mode": "warmup_3_zigzag"}
        if results[0] == results[1] == results[2]:
            return results[0], 58, {"mode": "warmup_3_streak"}
        return results[0], 54, {"mode": "warmup_3_mixed"}
    if n < WINDOW_SIZE + 5:
        s = 1
        for r in results[1:]:
            if r == results[0]:
                s += 1
            else:
                break
        if s >= 3:
            return results[0], 57, {"mode": "warmup_momentum"}
        return _opp(results[0]), 55, {"mode": "warmup_alt"}

    layers = []
    names = []

    layer_funcs = [
        ("heep_5",           lc79_heep),
        ("fingerprint_md5",  lc79_fingerprint),
        ("transition_md5",   lc79_transition_md5),
        ("momentum_entropy", lc79_momentum_entropy),
        ("pattern_ngram",    lc79_pattern_ngram),
        ("markov2",          lc79_markov2),
        ("bayesian_recency", lc79_bayesian_recency),
        ("streak_pressure",  lc79_streak_pressure),
        ("md5_cluster",      lc79_md5_cluster),
        ("cycle_detector",   lc79_cycle_detector),
        ("bayesian_drift",   lc79_bayesian_drift),
        ("multi_window",     lc79_multi_window_consensus),
        ("changepoint",      lc79_changepoint),
        ("run_length",       lc79_run_length),
        ("mean_reversion",   lc79_mean_reversion),
        ("kalman_state",     lc79_kalman_state),
        ("fourier_period",   lc79_fourier_period),
    ]

    for name, fn in layer_funcs:
        try:
            r = fn(results)
        except Exception:
            r = None
        if r:
            pred, w, info = r
            w = w * _layer_perf_multiplier(name)
            layers.append((pred, w, info))
            names.append(name)

    if dice_sums:
        r = lc79_dice_analysis(dice_sums)
        if r:
            layers.append(r)
            names.append("dice_bias")

    if not layers:
        return _opp(results[0]), 54, {"mode": "fallback_alt"}

    st = sx = 0.0
    for pred, w, _ in layers:
        if pred == "Tài":
            st += w
        else:
            sx += w

    total = st + sx
    if total == 0:
        return _opp(results[0]), 54, {"mode": "no_signal"}
    if st > sx:
        pred = "Tài"
        ratio = st / total
    elif sx > st:
        pred = "Xỉu"
        ratio = sx / total
    else:
        return _opp(results[0]), 55, {"mode": "tie"}

    agree = sum(1 for p, _, _ in layers if p == pred)
    nl = len(layers)
    conf = 52 + int((ratio - 0.5) * 60)
    if nl >= 2:
        conf += int((agree / nl) * 14)
        if agree == nl and nl >= 3:
            conf += 4
    conf += min(5, max(0, nl - 2))
    if nl == 1:
        conf -= 8
    elif nl == 2:
        conf -= 3
    conf = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEIL, conf))

    meta = {
        "mode": "lc79_md5_pro_v3_heep",
        "n_layers": nl,
        "agree": agree,
        "ratio": round(ratio, 3),
        "layers": [
            {"name": name, "pred": p, "w": round(w, 2), "info": info}
            for name, (p, w, info) in zip(names, layers)
        ],
    }
    return pred, conf, meta


# =====================================================================
# RECOVERY
# =====================================================================
def apply_recovery(base_pred, conf, loss_streak, results=None):
    if loss_streak < 2:
        return base_pred, conf, False, None
    if results and len(results) >= 15:
        e = _entropy(results[:20] if len(results) >= 20 else results)
        if e >= 0.95 and loss_streak < 4:
            return base_pred, max(50, conf - 6), False, "high_entropy_hold"
    if loss_streak >= 5:
        return _opp(base_pred), min(92, conf + 16), True, "flip_5plus"
    if loss_streak == 4:
        return _opp(base_pred), min(90, conf + 13), True, "flip_4"
    if loss_streak == 3:
        return _opp(base_pred), min(88, conf + 10), True, "flip_3"
    if loss_streak == 2:
        if conf < 70:
            return _opp(base_pred), min(87, conf + 7), True, "flip_2"
        return base_pred, max(50, conf - 10), False, "penalty_2"
    return base_pred, conf, False, None


# =====================================================================
# DATA FETCHER
# =====================================================================
def _parse_list(data):
    rows = []
    if not isinstance(data, dict):
        return rows
    lst = data.get("list") or data.get("data") or data.get("sessions")
    if not lst or not isinstance(lst, list):
        return rows
    for item in lst:
        try:
            if not isinstance(item, dict):
                continue
            raw = item.get("resultTruyenThong") or item.get("result") or ""
            res = "Tài" if str(raw).upper() == "TAI" else "Xỉu"
            dices = item.get("dices") or item.get("dice") or [0, 0, 0]
            if not isinstance(dices, list) or len(dices) < 3:
                dices = [0, 0, 0]
            dice_str = f"{dices[0]} + {dices[1]} + {dices[2]}"
            total = item.get("point")
            if total is None:
                try:
                    total = int(dices[0]) + int(dices[1]) + int(dices[2])
                except Exception:
                    total = 0
            phien = item.get("id") or item.get("phien")
            if phien is None:
                continue
            rows.append({
                "phien": int(phien),
                "result": res,
                "dice": dice_str,
                "total": total,
            })
        except Exception:
            continue
    return rows


def fetch_sessions():
    global LAST_FETCH_OK_TS
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "vi,en;q=0.9",
        "Referer": "https://wtx.tele68.com/",
    }
    last_err = None
    for attempt in range(FETCH_RETRY):
        try:
            r = requests.get(API_URL_MD5, timeout=FETCH_TIMEOUT, headers=headers)
            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception:
                    import json as _json
                    data = _json.loads(r.text)
                rows = _parse_list(data)
                if rows:
                    LAST_FETCH_OK_TS = time.time()
                    return rows, True
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
            time.sleep(0.4 * (attempt + 1))
    print(f"[API ERROR]: {last_err}")
    return [], False


# =====================================================================
# PREDICTION CACHE + PERF
# =====================================================================
def get_prediction_for(valid, i):
    key = valid[i]["phien"]
    if key in PREDICTION_CACHE:
        return PREDICTION_CACHE[key]
    hist = [v["result"] for v in valid[:i]][::-1]
    pred, conf, meta = lc79_predict(hist)
    if pred == "-":
        result = ("-", 50, None)
    else:
        is_correct = (pred == valid[i]["result"])
        result = (pred, conf, is_correct)
        if meta and meta.get("layers"):
            for L in meta["layers"]:
                LAYER_PERF[L["name"]]["total"] += 1
                if L["pred"] == valid[i]["result"]:
                    LAYER_PERF[L["name"]]["hit"] += 1
    if len(PREDICTION_CACHE) > MAX_PREDICTION_CACHE:
        PREDICTION_CACHE.clear()
    PREDICTION_CACHE[key] = result
    return result


def compute_loss_streak(valid, max_scan=25):
    if len(valid) < 3:
        return 0
    streak = 0
    end = len(valid) - 1
    start = max(0, end - max_scan)
    for i in range(end, start - 1, -1):
        _, _, ok = get_prediction_for(valid, i)
        if ok is None:
            break
        if ok:
            break
        streak += 1
    return streak


# =====================================================================
# HTML (giữ nguyên)
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LEMINH HEEP v3</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root { --bg-page:#0f172a; --bg-card:#1e293b; --text-main:#f8fafc; --text-muted:#94a3b8; --border-color:#334155; --tai-color:#38bdf8; --tai-bg:rgba(56,189,248,0.15); --xiu-color:#f472b6; --xiu-bg:rgba(244,114,182,0.15); --win-color:#22c55e; --win-bg:rgba(34,197,94,0.15); --lose-color:#ef4444; --lose-bg:rgba(239,68,68,0.15); }
    * { box-sizing:border-box; margin:0; padding:0; font-family:'Plus Jakarta Sans',sans-serif; }
    body { background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 100%); color:var(--text-main); min-height:100vh; padding-bottom:40px; }
    .header { background:rgba(30,41,59,0.85); backdrop-filter:blur(12px); border-bottom:1px solid var(--border-color); padding:16px 24px; display:flex; justify-content:space-between; align-items:center; position:sticky; top:0; z-index:100; }
    .header-title { font-size:22px; font-weight:800; color:#38bdf8; text-shadow:0 0 20px rgba(56,189,248,0.4); }
    .header-actions { display:flex; gap:12px; align-items:center; }
    .time-update { font-size:12px; color:var(--text-muted); font-weight:600; }
    .btn-refresh { background:var(--bg-card); color:var(--text-main); border:1px solid var(--border-color); width:38px; height:38px; border-radius:10px; cursor:pointer; }
    .btn-reset { background:rgba(248,113,113,0.2); color:#f87171; border:1px solid #f87171; padding:8px 16px; border-radius:10px; font-weight:700; font-size:13px; cursor:pointer; }
    .stats-bar { max-width:800px; margin:18px auto 0; padding:0 16px; display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
    .stat-card { background:var(--bg-card); border:1px solid var(--border-color); border-radius:12px; padding:12px; text-align:center; }
    .stat-label { font-size:11px; color:var(--text-muted); font-weight:700; text-transform:uppercase; }
    .stat-value { font-size:22px; font-weight:800; margin-top:4px; }
    .stat-value.win { color:var(--win-color); } .stat-value.lose { color:var(--lose-color); } .stat-value.rate { color:#38bdf8; }
    .table-wrapper { max-width:800px; margin:18px auto; padding:0 16px; }
    .table-container { background:var(--bg-card); border:1px solid var(--border-color); border-radius:16px; max-height:72vh; overflow-y:auto; }
    .data-table { width:100%; border-collapse:separate; border-spacing:0; }
    .data-table th { background:#111827; color:var(--text-muted); font-size:11px; font-weight:700; text-transform:uppercase; padding:14px 10px; position:sticky; top:0; }
    .data-table td { padding:12px 10px; text-align:center; border-bottom:1px solid var(--border-color); font-size:14px; font-weight:600; }
    .badge { display:inline-block; padding:6px 12px; border-radius:20px; font-size:12px; font-weight:700; min-width:66px; }
    .badge-tai { background:var(--tai-bg); color:var(--tai-color); border:1px solid rgba(56,189,248,0.3); }
    .badge-xiu { background:var(--xiu-bg); color:var(--xiu-color); border:1px solid rgba(244,114,182,0.3); }
    .badge-win { background:var(--win-bg); color:var(--win-color); }
    .badge-lose { background:var(--lose-bg); color:var(--lose-color); }
    .badge-none { background:rgba(148,163,184,0.12); color:var(--text-muted); }
    .dice-text, .conf-text { font-size:11px; color:var(--text-muted); display:block; margin-top:4px; }
    .loading { text-align:center; padding:40px; color:#38bdf8; font-weight:600; }
</style>
</head>
<body>
<div class="header">
    <div class="header-title">LEMINH HEEP v3</div>
    <div class="header-actions">
        <div class="time-update" id="time-update">--:--:--</div>
        <button class="btn-refresh" onclick="fetchData()">↻</button>
        <button class="btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>
<div class="stats-bar">
    <div class="stat-card"><div class="stat-label">Tổng</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-card"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-card"><div class="stat-label">Thua</div><div class="stat-value lose" id="stat-lose">0</div></div>
    <div class="stat-card"><div class="stat-label">Tỷ lệ</div><div class="stat-value rate" id="stat-rate">0%</div></div>
</div>
<div class="table-wrapper">
    <div class="table-container">
        <table class="data-table">
            <thead><tr><th>Phiên</th><th>Dự đoán</th><th>Kết quả</th><th>Nhận định</th></tr></thead>
            <tbody id="table-body"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody>
        </table>
    </div>
</div>
<script>
let isResetting = false;
async function fetchData() {
    if (isResetting) return;
    try {
        const r = await fetch('/api/history', {cache:'no-store'});
        const data = await r.json();
        document.getElementById('time-update').innerText = new Date().toLocaleTimeString('vi-VN');
        const s = data.stats || {};
        document.getElementById('stat-total').innerText = s.total || 0;
        document.getElementById('stat-win').innerText = s.win || 0;
        document.getElementById('stat-lose').innerText = s.lose || 0;
        document.getElementById('stat-rate').innerText = (s.rate||0)+'%';
        renderTable(data.rows || []);
    } catch(e) { console.error(e); }
}
function renderTable(rows) {
    const tb = document.getElementById('table-body');
    if (!rows.length) { tb.innerHTML = '<tr><td colspan="4" class="loading">Không có dữ liệu</td></tr>'; return; }
    let html = '';
    rows.forEach(row => {
        let res = row.result === 'Tài' ? '<span class="badge badge-tai">TÀI</span>' : '<span class="badge badge-xiu">XỈU</span>';
        let dice = '';
        if (row.dice && row.dice !== '? + ? + ?') {
            const p = row.dice.split(' + ');
            dice = `<span class="dice-text">${row.dice} (${(+p[0])+(+p[1])+(+p[2])})</span>`;
        }
        let pred = '<span class="badge badge-none">—</span>';
        let conf = '';
        if (row.prediction === 'Tài') { pred = '<span class="badge badge-tai">TÀI</span>'; conf = `<span class="conf-text">${row.confidence}%</span>`; }
        else if (row.prediction === 'Xỉu') { pred = '<span class="badge badge-xiu">XỈU</span>'; conf = `<span class="conf-text">${row.confidence}%</span>`; }
        let judge = '<span class="badge badge-none">—</span>';
        if (row.is_correct === true) judge = '<span class="badge badge-win">✓ ĐÚNG</span>';
        else if (row.is_correct === false) judge = '<span class="badge badge-lose">✗ SAI</span>';
        html += `<tr><td>#${row.phien}</td><td>${pred}${conf}</td><td>${res}${dice}</td><td>${judge}</td></tr>`;
    });
    tb.innerHTML = html;
}
async function confirmReset() {
    const r = await Swal.fire({title:'Xác nhận Reset?', text:'Xoá lịch sử và bắt đầu lại!', icon:'warning', background:'#1e293b', color:'#f8fafc', showCancelButton:true, confirmButtonText:'Đồng ý', cancelButtonText:'Hủy', confirmButtonColor:'#0ea5e9'});
    if (!r.isConfirmed) return;
    isResetting = true;
    try {
        const res = await fetch('/api/reset', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
        const d = await res.json();
        if (d.status === 'success') { Swal.fire({title:'Thành công!', icon:'success', background:'#1e293b', color:'#f8fafc'}); }
        else throw new Error(d.message);
    } catch(e) { Swal.fire({title:'Lỗi!', text:e.message, icon:'error', background:'#1e293b', color:'#f8fafc'}); }
    isResetting = false; fetchData();
}
fetchData(); setInterval(fetchData, 5000);
</script>
</body>
</html>
"""


# =====================================================================
# ROUTES
# =====================================================================
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


def _sync_history(raw_rows):
    for row in raw_rows:
        HISTORY_CACHE[row["phien"]] = row
    for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
        del HISTORY_CACHE[k]
    return sorted(HISTORY_CACHE.values(), key=lambda x: x["phien"])


@app.route("/api/history")
def history():
    try:
        raw, ok = fetch_sessions()
        if not ok and not HISTORY_CACHE:
            return jsonify({"error": "Không kết nối API"}), 500
        valid = _sync_history(raw)
        if not valid:
            return jsonify({"rows": [], "stats": {"total": 0, "win": 0, "lose": 0, "rate": 0}})
        out = []
        win = lose = 0
        scan = min(len(valid), 200)
        for i in range(len(valid) - 1, len(valid) - scan - 1, -1):
            if i < 0:
                break
            s = valid[i]
            pred, conf, ok = get_prediction_for(valid, i)
            if ok is True:
                win += 1
            elif ok is False:
                lose += 1
            out.append({
                "phien": s["phien"], "result": s["result"], "dice": s["dice"],
                "prediction": pred if pred != "-" else None,
                "confidence": conf, "is_correct": ok,
            })
        tot = win + lose
        rate = round(win / tot * 100, 1) if tot else 0
        return jsonify({"rows": out, "stats": {"total": tot, "win": win, "lose": lose, "rate": rate}})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/predict")
def predict():
    try:
        raw, ok = fetch_sessions()
        if not ok and not HISTORY_CACHE:
            return jsonify({"error": "Không kết nối API"}), 500
        valid = _sync_history(raw)
        if not valid:
            return jsonify({"error": "Chưa có dữ liệu"}), 400
        results = [v["result"] for v in valid][::-1]
        dice = _parse_dice_history(valid[::-1])
        ls = compute_loss_streak(valid)
        bp, bc, meta = lc79_predict(results, dice)
        pred, conf, flipped, reason = apply_recovery(bp, bc, ls, results)
        return jsonify({
            "algorithm": "LC79_MD5_PRO_V3_HEEP",
            "last_phien": valid[-1]["phien"],
            "next_phien": valid[-1]["phien"] + 1,
            "last_result": valid[-1]["result"],
            "last_dice": valid[-1]["dice"],
            "prediction": pred, "confidence": conf,
            "base_prediction": bp, "base_confidence": bc,
            "recovery_flipped": flipped, "recovery_reason": reason,
            "loss_streak": ls,
            "total_sessions": len(valid),
            "last_5": results[:5],
            "meta": meta,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/lc79md5")
def betvipmd5():
    try:
        raw, ok = fetch_sessions()
        if not ok and not HISTORY_CACHE:
            return jsonify({"error": "Không kết nối API"}), 500
        valid = _sync_history(raw)
        if not valid:
            return jsonify({"error": "Chưa có dữ liệu"}), 400
        results = [v["result"] for v in valid][::-1]
        dice = _parse_dice_history(valid[::-1])
        ls = compute_loss_streak(valid)
        bp, bc, meta = lc79_predict(results, dice)
        pred, conf, flipped, reason = apply_recovery(bp, bc, ls, results)
        conf_str = f"{conf:.1f}".replace(".", ",") + "%"
        last = valid[-1]
        dp = last["dice"].split(" + ")
        dshort = "-".join(dp) if len(dp) == 3 else last["dice"]
        ket_qua = f"{last['result'].lower()} {dshort}"
        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])
        return jsonify({
            "id": "@cskhleminh",
            "algorithm": "LC79_HEEP_V3",
            "phien": str(last["phien"] + 1),
            "ket_qua": ket_qua,
            "du_doan": pred,
            "do_tin_cay": conf_str,
            "lich_su": lich_su,
            "base_du_doan": bp if flipped else None,
            "auto_flip": flipped,
            "chuoi_thua": ls,
            "meta": meta,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/heep")
def api_heep():
    """API chuyên phân tích 5 phiên Đảo/Nghịch/Thuận."""
    try:
        raw, ok = fetch_sessions()
        if not ok and not HISTORY_CACHE:
            return jsonify({"error": "Không kết nối API"}), 500
        valid = _sync_history(raw)
        if len(valid) < 5:
            return jsonify({"error": "Chưa đủ 5 phiên"}), 400
        results = [v["result"] for v in valid][::-1]
        info = heep_extract_5(results)
        detail = {}
        for name, fn in (("thuan", heep_mode_thuan), ("nghich", heep_mode_nghich), ("dao", heep_mode_dao)):
            r = fn(results, info)
            if r:
                p, w, i = r
                detail[name] = {"pred": p, "weight": round(w, 2), "info": i}
            else:
                detail[name] = None
        ensemble = lc79_heep(results)
        return jsonify({
            "algorithm": "HEEP_LC79_V3",
            "last_5": info["window"],
            "info": info,
            "modes": detail,
            "ensemble": {
                "pred": ensemble[0],
                "weight": round(ensemble[1], 2),
                "ratio": ensemble[2]["ratio"],
                "n_signals": len(ensemble[2]["signals"]),
            } if ensemble else None,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    try:
        total = sum(p["total"] for p in LAYER_PERF.values())
        layers = []
        for name, perf in LAYER_PERF.items():
            if perf["total"] == 0:
                continue
            acc = perf["hit"] / perf["total"] * 100
            layers.append({
                "name": name, "hit": perf["hit"], "total": perf["total"],
                "accuracy": round(acc, 2),
                "multiplier": round(_layer_perf_multiplier(name), 3),
            })
        layers.sort(key=lambda x: x["accuracy"], reverse=True)
        return jsonify({
            "algorithm": "LC79_MD5_PRO_V3_HEEP",
            "total_evaluations": total,
            "layers": layers,
            "history_cache_size": len(HISTORY_CACHE),
            "prediction_cache_size": len(PREDICTION_CACHE),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/layers")
def api_layers():
    try:
        raw, ok = fetch_sessions()
        if not ok and not HISTORY_CACHE:
            return jsonify({"error": "Không kết nối API"}), 500
        valid = _sync_history(raw)
        if not valid:
            return jsonify({"error": "Chưa có dữ liệu"}), 400
        results = [v["result"] for v in valid][::-1]
        dice = _parse_dice_history(valid[::-1])

        layer_funcs = [
            ("heep_5",           lc79_heep),
            ("fingerprint_md5",  lc79_fingerprint),
            ("transition_md5",   lc79_transition_md5),
            ("momentum_entropy", lc79_momentum_entropy),
            ("pattern_ngram",    lc79_pattern_ngram),
            ("markov2",          lc79_markov2),
            ("bayesian_recency", lc79_bayesian_recency),
            ("streak_pressure",  lc79_streak_pressure),
            ("md5_cluster",      lc79_md5_cluster),
            ("cycle_detector",   lc79_cycle_detector),
            ("bayesian_drift",   lc79_bayesian_drift),
            ("multi_window",     lc79_multi_window_consensus),
            ("changepoint",      lc79_changepoint),
            ("run_length",       lc79_run_length),
            ("mean_reversion",   lc79_mean_reversion),
            ("kalman_state",     lc79_kalman_state),
            ("fourier_period",   lc79_fourier_period),
        ]
        out = []
        for name, fn in layer_funcs:
            try:
                r = fn(results)
            except Exception:
                r = None
            if r:
                p, w, i = r
                perf = LAYER_PERF.get(name, {"hit": 0, "total": 0})
                acc = round(perf["hit"] / perf["total"] * 100, 2) if perf["total"] > 0 else None
                out.append({
                    "name": name, "prediction": p, "weight": round(w, 2),
                    "multiplier": round(_layer_perf_multiplier(name), 3),
                    "accuracy": acc, "info": i,
                })
            else:
                out.append({"name": name, "prediction": None, "info": "no_signal"})
        if dice:
            r = lc79_dice_analysis(dice)
            if r:
                p, w, i = r
                out.append({"name": "dice_bias", "prediction": p, "weight": round(w, 2), "info": i})
        return jsonify({
            "algorithm": "LC79_MD5_PRO_V3_HEEP",
            "total_sessions": len(valid),
            "layers": out,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/backtest")
def api_backtest():
    try:
        n_str = request.args.get("n", "50")
        try:
            n = max(5, min(300, int(n_str)))
        except Exception:
            n = 50
        raw, ok = fetch_sessions()
        if not ok and not HISTORY_CACHE:
            return jsonify({"error": "Không kết nối API"}), 500
        valid = _sync_history(raw)
        if len(valid) < 10:
            return jsonify({"error": "Chưa đủ dữ liệu"}), 400
        n = min(n, len(valid) - 5)
        win = lose = 0
        details = []
        corrects = []
        for i in range(len(valid) - n, len(valid)):
            s = valid[i]
            hist = [v["result"] for v in valid[:i]][::-1]
            p, c, m = lc79_predict(hist)
            ic = (p == s["result"])
            if ic:
                win += 1
                corrects.append(1)
            else:
                lose += 1
                corrects.append(0)
            details.append({
                "phien": s["phien"], "pred": p, "conf": c,
                "result": s["result"], "correct": ic,
                "n_layers": m.get("n_layers", 0),
            })
        tot = win + lose
        rate = round(win / tot * 100, 2) if tot else 0
        ml = cur = 0
        for c in corrects:
            if c == 0:
                cur += 1
                ml = max(ml, cur)
            else:
                cur = 0
        return jsonify({
            "algorithm": "LC79_MD5_PRO_V3_HEEP",
            "n_sessions": tot, "win": win, "lose": lose,
            "accuracy": rate, "max_loss_streak": ml,
            "details": details,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def api_health():
    now = time.time()
    age = round(now - LAST_FETCH_OK_TS, 1) if LAST_FETCH_OK_TS > 0 else None
    return jsonify({
        "status": "ok",
        "algorithm": "LC79_MD5_PRO_V3_HEEP",
        "server_time": datetime.now().isoformat(),
        "last_fetch_age_s": age,
        "history_cache_size": len(HISTORY_CACHE),
        "prediction_cache_size": len(PREDICTION_CACHE),
        "reset_id": RESET_ID,
        "layer_perf_layers": len(LAYER_PERF),
    })


@app.route("/api/reset", methods=["POST"])
def reset_api():
    global RESET_ID, HISTORY_CACHE, PREDICTION_CACHE, BOOTSTRAP_SESSIONS, LAYER_PERF
    try:
        raw, ok = fetch_sessions()
        if ok and raw:
            valid = sorted(raw, key=lambda x: x["phien"])
            if valid:
                RESET_ID = valid[-1]["phien"]
                last = valid[-1]
                HISTORY_CACHE = {last["phien"]: last}
                BOOTSTRAP_SESSIONS = [last]
                PREDICTION_CACHE = {}
                LAYER_PERF.clear()
                return jsonify({
                    "status": "success",
                    "reset_to": RESET_ID,
                    "bootstrap": True,
                    "algorithm": "LC79_MD5_PRO_V3_HEEP",
                    "message": "Reset OK",
                })
        return jsonify({"status": "error", "message": "Không thể xác nhận mốc reset"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
