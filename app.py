import os
import math
import time
import hashlib
import traceback
from datetime import datetime
from collections import defaultdict, deque
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

app = Flask(__name__)
CORS(app)

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
PREDICTION_CACHE = {}
MAX_PREDICTION_CACHE = 3000
RESET_ID = 0
LAST_FETCH_OK_TS = 0
FETCH_RETRY = 2
FETCH_TIMEOUT = 6

LAYER_PERF = defaultdict(lambda: {"hit": 0, "total": 0})

# =====================================================================
# CONFIG
# =====================================================================
WINDOW_SIZE = 5
FINGERPRINT_MIN_MATCH = 3
TRANSITION_MIN_SAMPLES = 6
MOMENTUM_MIN_STREAK = 3
ENTROPY_HIGH = 0.98
ENTROPY_LOW = 0.55
PATTERN_MIN_OCCURRENCES = 3
BAYES_PRIOR_ALPHA = 1.0
CONFIDENCE_FLOOR = 50
CONFIDENCE_CEIL = 95
FUZZY_MATCH_RATIO = 0.75
CLUSTER_MIN_SAMPLES = 4
CYCLE_MIN_PERIOD = 4
CYCLE_MAX_PERIOD = 12
CYCLE_MIN_CONFIDENCE = 0.65
MULTI_WINDOW_LIST = (5, 8, 12, 20)
CHANGEPOINT_MIN_SEG = 8
ADAPTIVE_MIN_SAMPLES = 20

# HEEP config
HEEP_WINDOW = 5
HEEP_FAIR_RATIO = 0.60
HEEP_DECAY = 0.85
HEEP_ENTROPY_HIGH = 0.95
HEEP_ENTROPY_LOW = 0.55
HEEP_REVERSAL_STREAK = 3

# AI config
AI_ENABLED = NUMPY_OK
AI_FEATURE_WINDOW = 32
AI_MIN_TRAIN = 60
AI_ONLINE_LR = 0.03
AI_ONLINE_DECAY = 0.995
AI_MLP_HIDDEN = 24
AI_GBM_TREES = 12
AI_GBM_DEPTH = 3
AI_CONF_MIN_SIGNAL = 0.55
AI_STACKER_LR = 0.05
AI_REGIME_LOOKBACK = 50

AI_STATE = {
    "mlp_W1": None, "mlp_b1": None, "mlp_W2": None, "mlp_b2": None,
    "mlp_trained": 0,
    "gbm_trees": [],
    "stacker_w": None,
    "stacker_bias": 0.0,
    "regime": "neutral",
    "online_samples": 0,
    "ai_hits": 0, "ai_total": 0,
    "confidence_calibration": {},
}


# =====================================================================
# UTILS
# =====================================================================
def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"


def get_groups(results):
    if not results:
        return []
    groups, cur, cnt = [], results[0], 1
    for r in results[1:]:
        if r == cur:
            cnt += 1
        else:
            groups.append(cnt)
            cur, cnt = r, 1
    groups.append(cnt)
    return groups


def _entropy(seq):
    if not seq:
        return 0.0
    t = seq.count("Tài")
    p = t / len(seq)
    q = 1 - p
    e = 0.0
    if p > 0: e -= p * math.log2(p)
    if q > 0: e -= q * math.log2(q)
    return e


def _to_bits(results):
    return "".join("1" if r == "Tài" else "0" for r in results)


def _md5(s):
    return hashlib.md5(s.encode()).hexdigest()


def _hamming(a, b):
    n = min(len(a), len(b))
    return sum(1 for x, y in zip(a[:n], b[:n]) if x != y)


def _weighted_count(seq, base, decay=0.9):
    w = 0.0
    for i, v in enumerate(seq):
        if v == base:
            w += decay ** i
    return w


def _weighted_ratio(seq, target, decay=HEEP_DECAY):
    num = den = 0.0
    for i, v in enumerate(seq):
        w = decay ** i
        den += w
        if v == target:
            num += w
    return num / den if den > 0 else 0.5


# =====================================================================
# HEEP 5 PHIÊN — ĐẢO / NGHỊCH / THUẬN
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
    dom, mino, cnt = ("Tài", "Xỉu", tai_c) if tai_c >= xiu_c else ("Xỉu", "Tài", xiu_c)
    return {
        "window": win, "bits_newest_first": bits,
        "streak": streak, "alternating": alternating,
        "pair_alternating": pair_alt,
        "dominant": dom, "minority": mino,
        "count_major": cnt, "count_minor": HEEP_WINDOW - cnt,
        "ratio_major": round(cnt / HEEP_WINDOW, 4),
        "entropy": round(_entropy(win), 4),
    }


def heep_mode_thuan(results, info):
    if not info or info["streak"] < 2:
        return None
    cur = results[0]
    ratio = _weighted_ratio(results, cur)
    if ratio < HEEP_FAIR_RATIO or info["entropy"] >= HEEP_ENTROPY_HIGH:
        return None
    w = max(9, min(22, 9 + min(6, info["streak"]) + int(ratio * 6)))
    return (cur, w, {"mode": "thuan_momentum", "streak": info["streak"],
                     "weighted_ratio": round(ratio, 3), "entropy": info["entropy"]})


def heep_mode_nghich(results, info):
    if not info:
        return None
    cur = results[0]
    ratio = _weighted_ratio(results, cur)
    if ratio < HEEP_FAIR_RATIO or info["streak"] >= 4 or info["entropy"] < 0.4:
        return None
    w = max(8, min(18, 8 + int((ratio - 0.55) * 30)))
    return (_opp(cur), w, {"mode": "nghich_reversion",
                           "current": cur, "weighted_ratio": round(ratio, 3),
                           "entropy": info["entropy"]})


def heep_mode_dao(results, info):
    if not info:
        return None
    if info["alternating"]:
        return (_opp(results[0]), 14, {"mode": "dao_1_1", "entropy": info["entropy"]})
    if info["pair_alternating"]:
        return (_opp(results[0]), 12, {"mode": "dao_2_2", "entropy": info["entropy"]})
    if info["streak"] >= HEEP_REVERSAL_STREAK:
        g = get_groups(results[1:11])
        avg = sum(g) / max(1, len(g)) if g else 2.0
        if info["streak"] >= avg * 1.6:
            return (_opp(results[0]), 11, {"mode": "dao_streak_break",
                                           "streak": info["streak"],
                                           "avg_streak": round(avg, 2)})
    return None


def lc79_heep(results):
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
    st = sum(w for p, w, _ in signals if p == "Tài")
    sx = sum(w for p, w, _ in signals if p == "Xỉu")
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    tot = st + sx
    ratio = max(st, sx) / tot
    w = max(10, min(24, 10 + int((ratio - 0.5) * 30) + len(signals) * 2))
    return (pred, w, {"mode": "heep_5",
                      "signals": [{"pred": p, "w": round(w2, 2), "info": i}
                                  for p, w2, i in signals],
                      "info": info, "ratio": round(ratio, 3)})


# =====================================================================
# TẦNG 1: MD5 FINGERPRINT
# =====================================================================
def lc79_fingerprint(results):
    if len(results) < 10:
        return None
    bits = _to_bits(results[::-1])
    best = None
    for ws in (7, 6, 5, 4, 3):
        if len(bits) < ws + 5:
            continue
        cur_fp = bits[-ws:]
        tai = xiu = 0.0
        total = 0.0
        fuzzy = []
        for i in range(0, len(bits) - ws):
            seg = bits[i:i + ws]
            nxt = bits[i + ws]
            if seg == cur_fp:
                if nxt == "1": tai += 1
                else: xiu += 1
                total += 1
            else:
                sim = 1.0 - _hamming(seg, cur_fp) / ws
                if sim >= FUZZY_MATCH_RATIO:
                    if nxt == "1": tai += sim
                    else: xiu += sim
                    total += sim
                    fuzzy.append(sim)
        if total < FINGERPRINT_MIN_MATCH:
            continue
        p_tai = tai / total
        ratio = max(p_tai, 1 - p_tai)
        if ratio < 0.60:
            continue
        score = ratio * math.log2(total + 1) * (ws / 5.0) * (1 + len(fuzzy) / max(total, 1) * 0.3)
        if best is None or score > best["score"]:
            best = {"pred": "Tài" if p_tai >= 0.5 else "Xỉu",
                    "ratio": ratio, "samples": total, "window": ws,
                    "score": score, "fuzzy": len(fuzzy)}
    if not best:
        return None
    w = 11 + min(7, int(math.log2(best["samples"] + 1) * 2.5))
    w += min(3, max(0, best["window"] - 4)) + min(3, best["fuzzy"] // 3)
    w += int((best["ratio"] - 0.5) * 30)
    w = max(11, min(28, w))
    return (best["pred"], w, {"window": best["window"], "samples": round(best["samples"], 2),
                              "ratio": round(best["ratio"], 3)})


# =====================================================================
# TẦNG 2: MD5 TRANSITION
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
            tr[_md5(bits[i:i + order])][("Tài" if bits[i + order] == "1" else "Xỉu")] += 1
        d = tr.get(cur_key)
        if not d:
            continue
        tot = d["Tài"] + d["Xỉu"]
        if tot < TRANSITION_MIN_SAMPLES:
            continue
        p = (d["Tài"] + BAYES_PRIOR_ALPHA) / (tot + 2 * BAYES_PRIOR_ALPHA)
        ratio = max(p, 1 - p)
        if ratio < 0.62:
            continue
        signals.append({"pred": "Tài" if p >= 0.5 else "Xỉu",
                        "ratio": ratio, "samples": tot, "order": order})
    if not signals:
        return None
    st = sum(s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] ** 0.5)
             for s in signals if s["pred"] == "Tài")
    sx = sum(s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] ** 0.5)
             for s in signals if s["pred"] == "Xỉu")
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    if ratio < 0.58:
        return None
    w = max(9, min(24, 9 + int((ratio - 0.6) * 45) + len(signals) * 2))
    return (pred, w, {"samples": sum(s["samples"] for s in signals),
                      "ratio": round(ratio, 3), "orders": [s["order"] for s in signals]})


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
    e = _entropy(results[:20] if len(results) >= 20 else results)
    if len(results) >= 6 and all(results[i] != results[i + 1] for i in range(6)):
        return (_opp(results[0]), 13, {"type": "alt_1_1"})
    if len(results) >= 8:
        pr = [(results[i], results[i + 1]) for i in range(0, 8, 2)]
        if all(p[0] == p[1] for p in pr):
            pv = [p[0] for p in pr]
            if all(pv[i] != pv[i + 1] for i in range(len(pv) - 1)):
                return (_opp(pv[-1]), 12, {"type": "alt_2_2"})
    if MOMENTUM_MIN_STREAK <= streak <= 8:
        wt = _weighted_count(results[:12], "Tài", 0.85)
        wx = _weighted_count(results[:12], "Xỉu", 0.85)
        tw = wt + wx
        if tw > 0:
            p = wt / tw
            dom = "Tài" if p > 0.5 else "Xỉu"
            ratio = max(p, 1 - p)
            if ratio >= 0.60:
                return (dom, 13 if e < 0.85 else 10,
                        {"type": "momentum", "streak": streak, "ratio": round(ratio, 3)})
    if e >= ENTROPY_HIGH:
        return (_opp(results[0]), 9, {"type": "entropy_reverse"})
    if e <= ENTROPY_LOW and len(results) >= 20:
        tc = results[:20].count("Tài")
        if tc >= 15: return ("Xỉu", 12, {"type": "pressure_tai"})
        if tc <= 5: return ("Tài", 12, {"type": "pressure_xiu"})
    return None


# =====================================================================
# TẦNG 4: PATTERN N-GRAM
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
                if bits[i + order] == "1": tai += 1
                else: xiu += 1
        tot = tai + xiu
        if tot < PATTERN_MIN_OCCURRENCES:
            continue
        p = (tai + BAYES_PRIOR_ALPHA) / (tot + 2 * BAYES_PRIOR_ALPHA)
        ratio = max(p, 1 - p)
        if ratio < 0.62:
            continue
        signals.append({"pred": "Tài" if p >= 0.5 else "Xỉu",
                        "ratio": ratio, "samples": tot, "order": order})
    if not signals:
        return None
    st = sum(s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] - 1)
             for s in signals if s["pred"] == "Tài")
    sx = sum(s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] - 1)
             for s in signals if s["pred"] == "Xỉu")
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    w = max(10, min(25, 10 + int((ratio - 0.6) * 40) + len(signals) * 2))
    return (pred, w, {"ratio": round(ratio, 3), "n_signals": len(signals)})


# =====================================================================
# TẦNG 5: MARKOV
# =====================================================================
def lc79_markov2(results):
    if len(results) < 25:
        return None
    bits = _to_bits(results[::-1])
    signals = []
    for order in (2, 3, 4, 5):
        if len(bits) < order + 10:
            continue
        cur = bits[-order:]
        tr = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
        for i in range(0, len(bits) - order):
            tr[bits[i:i + order]][("Tài" if bits[i + order] == "1" else "Xỉu")] += 1
        d = tr.get(cur)
        if not d:
            continue
        tot = d["Tài"] + d["Xỉu"]
        if tot < 4:
            continue
        p = (d["Tài"] + BAYES_PRIOR_ALPHA) / (tot + 2 * BAYES_PRIOR_ALPHA)
        ratio = max(p, 1 - p)
        if ratio < 0.60 + (order - 2) * 0.02:
            continue
        signals.append({"pred": "Tài" if p >= 0.5 else "Xỉu",
                        "ratio": ratio, "samples": tot, "order": order})
    if not signals:
        return None
    st = sum(s["ratio"] * math.log2(s["samples"] + 1) * s["order"]
             for s in signals if s["pred"] == "Tài")
    sx = sum(s["ratio"] * math.log2(s["samples"] + 1) * s["order"]
             for s in signals if s["pred"] == "Xỉu")
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    w = max(8, min(22, 8 + int((ratio - 0.55) * 40) + len(signals) * 2))
    return (pred, w, {"ratio": round(ratio, 3), "orders": [s["order"] for s in signals]})


# =====================================================================
# TẦNG 6-10 (gọn)
# =====================================================================
def lc79_bayesian_recency(results):
    if len(results) < 15:
        return None
    n = min(len(results), 25)
    wt = wx = 0.0
    for i, r in enumerate(results[:n]):
        w = math.exp(-i / 8.0)
        if r == "Tài": wt += w
        else: wx += w
    tot = wt + wx
    if tot == 0:
        return None
    p = wt / tot
    ratio = max(p, 1 - p)
    if ratio < 0.63:
        return None
    return ("Tài" if p >= 0.5 else "Xỉu",
            max(7, min(18, 7 + int((ratio - 0.6) * 35))),
            {"p_tai": round(p, 3), "ratio": round(ratio, 3)})


def lc79_streak_pressure(results):
    if len(results) < 30:
        return None
    streak = 1
    for r in results[1:]:
        if r == results[0]: streak += 1
        else: break
    g = get_groups(results)
    if len(g) < 5:
        return None
    past = g[1:20]
    if not past:
        return None
    avg = sum(past) / len(past)
    if streak >= 5 and streak >= avg * 1.8:
        return (_opp(results[0]), max(10, min(15, 10 + streak // 2)),
                {"type": "streak_break", "streak": streak, "avg": round(avg, 2)})
    return None


def _parse_dice_history(valid_rows):
    sums = []
    for row in valid_rows:
        try:
            dice = row.get("dice", "")
            if "+" in dice:
                parts = [p.strip() for p in dice.replace("+", " + ").split("+") if p.strip()]
                if len(parts) >= 3:
                    sums.append(sum(int(p) for p in parts[:3]))
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
    s = min(1.0, abs(dev) / 3.0)
    return (pred, 7 + int(s * 10),
            {"type": "dice_bias", "avg": round(avg, 2), "dev": round(dev, 2)})


def lc79_md5_cluster(results):
    if len(results) < 25:
        return None
    bits = _to_bits(results[::-1])
    cur = _md5(bits[-5:])[:3]
    cluster = []
    for i in range(0, len(bits) - 5):
        if _md5(bits[i:i + 5])[:3] == cur:
            cluster.append(bits[i + 5])
    if len(cluster) < CLUSTER_MIN_SAMPLES:
        return None
    tai = cluster.count("1")
    tot = len(cluster)
    p = (tai + BAYES_PRIOR_ALPHA) / (tot + 2 * BAYES_PRIOR_ALPHA)
    ratio = max(p, 1 - p)
    if ratio < 0.65:
        return None
    return ("Tài" if p >= 0.5 else "Xỉu",
            max(9, min(21, 9 + int((ratio - 0.6) * 40) + min(3, tot // 5))),
            {"size": tot, "ratio": round(ratio, 3)})


def lc79_cycle_detector(results):
    if len(results) < 24:
        return None
    best = None
    for period in range(CYCLE_MIN_PERIOD, CYCLE_MAX_PERIOD + 1):
        if len(results) < period * 2 + 2:
            continue
        m = c = 0
        for off in range(1, period * 2 + 1):
            if off >= len(results) or period >= len(results):
                continue
            c += 1
            if results[off - 1] == results[off - 1 + period]:
                m += 1
        if c < period:
            continue
        conf = m / c
        if conf < CYCLE_MIN_CONFIDENCE:
            continue
        if period < len(results):
            score = conf * math.log2(c + 1) / period
            if best is None or score > best["score"]:
                best = {"pred": results[period - 1], "period": period,
                        "confidence": conf, "score": score}
    if not best:
        return None
    return (best["pred"], max(8, min(20, 8 + int(best["confidence"] * 15))),
            {"period": best["period"], "confidence": round(best["confidence"], 3)})


def lc79_bayesian_drift(results):
    if len(results) < 30:
        return None
    ot = results[15:30].count("Tài") / 15
    nt = results[:15].count("Tài") / 15
    d = nt - ot
    if abs(d) < 0.25:
        return None
    if nt > 0.65:
        pred, s = "Tài", (nt - 0.5) * 2
    elif nt < 0.35:
        pred, s = "Xỉu", (0.5 - nt) * 2
    else:
        return None
    return (pred, max(7, min(15, 7 + int(s * 8))),
            {"drift": round(d, 3), "new_tai": round(nt, 3)})


def lc79_multi_window_consensus(results):
    if len(results) < 20:
        return None
    votes = []
    for ws in MULTI_WINDOW_LIST:
        if len(results) < ws:
            continue
        p = results[:ws].count("Tài") / ws
        if ws <= 8:
            if p >= 0.65: votes.append(("Tài", 1.0))
            elif p <= 0.35: votes.append(("Xỉu", 1.0))
        else:
            if p >= 0.70: votes.append(("Xỉu", 0.8))
            elif p <= 0.30: votes.append(("Tài", 0.8))
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
    return (pred, max(7, min(18, 7 + int((ratio - 0.6) * 30) + len(votes) * 2)),
            {"votes": len(votes), "ratio": round(ratio, 3)})


def lc79_changepoint(results):
    if len(results) < 30:
        return None
    bits = [1 if r == "Tài" else 0 for r in results[:40]]
    n = len(bits)
    if n < CHANGEPOINT_MIN_SEG * 2:
        return None
    mean = sum(bits) / n
    sp = sn = bp = bn = 0.0
    cip = cin = 0
    for i, b in enumerate(bits):
        sp = max(0, sp + b - mean - 0.05)
        sn = max(0, sn - b + mean - 0.05)
        if sp > bp: bp, cip = sp, i
        if sn > bn: bn, cin = sn, i
    for best, ci in ((bp, cip), (bn, cin)):
        if best > 2.5 and 3 <= ci <= 10:
            seg = bits[:ci]
            if len(seg) >= 4:
                p = sum(seg) / len(seg)
                if p >= 0.7:
                    return ("Tài", 12, {"type": "cp_up", "idx": ci, "p_new": round(p, 3)})
                if p <= 0.3:
                    return ("Xỉu", 12, {"type": "cp_down", "idx": ci, "p_new": round(p, 3)})
    return None


def lc79_run_length(results):
    if len(results) < 30:
        return None
    g = get_groups(results)
    if len(g) < 10:
        return None
    cur = g[0]
    past = g[1:30]
    if len(past) < 6:
        return None
    lo = sum(1 for x in past if x > cur)
    eq = sum(1 for x in past if x == cur)
    sh = sum(1 for x in past if x < cur)
    tot = lo + eq + sh
    if tot == 0:
        return None
    pb = (sh + 0.5 * eq) / tot
    if pb >= 0.75 and cur >= 3:
        return (_opp(results[0]), 11, {"type": "break", "streak": cur, "p_break": round(pb, 3)})
    pc = (lo + 0.5 * eq) / tot
    if pc >= 0.80 and cur >= 2:
        return (results[0], 10, {"type": "continue", "streak": cur, "p_cont": round(pc, 3)})
    return None


def lc79_mean_reversion(results):
    if len(results) < 20:
        return None
    p = results[:20].count("Tài") / 20
    dev = p - 0.5
    if abs(dev) < 0.22:
        return None
    pred = "Xỉu" if dev > 0 else "Tài"
    s = min(1.0, abs(dev) * 3)
    rt = results[:6].count("Tài") / 6
    if pred == "Tài" and rt > 0.7: return None
    if pred == "Xỉu" and rt < 0.3: return None
    return (pred, max(7, min(16, 7 + int(s * 9))),
            {"type": "mean_rev", "p_tai": round(p, 3), "dev": round(dev, 3)})


def lc79_kalman_state(results):
    if len(results) < 15:
        return None
    est = []
    for w in (5, 8, 12, 20):
        if len(results) >= w:
            est.append(results[:w].count("Tài") / w)
    if len(est) < 2:
        return None
    wts = [1.0, 0.9, 0.7, 0.5][:len(est)]
    smoothed = sum(e * w for e, w in zip(est, wts)) / sum(wts)
    dev = smoothed - 0.5
    if abs(dev) < 0.12:
        return None
    pred = "Tài" if dev > 0 else "Xỉu"
    s = min(1.0, abs(dev) * 4)
    return (pred, max(7, min(15, 7 + int(s * 8))),
            {"smoothed": round(smoothed, 3), "estimates": [round(e, 3) for e in est]})


def lc79_fourier_period(results):
    if len(results) < 24:
        return None
    bits = [1 if r == "Tài" else 0 for r in results[:32]]
    n = len(bits)
    mean = sum(bits) / n
    c = [b - mean for b in bits]
    max_p = 0.0
    best = 0
    for period in range(3, 13):
        if period >= n - 1:
            continue
        re = sum(c[i] * math.cos(2 * math.pi * i / period) for i in range(n))
        im = sum(c[i] * math.sin(2 * math.pi * i / period) for i in range(n))
        p = (re * re + im * im) / n
        if p > max_p:
            max_p, best = p, period
    if max_p < 0.55 or best == 0:
        return None
    if best < len(results):
        return (results[best - 1], max(8, min(15, 8 + int(min(6, max_p * 4)))),
                {"period": best, "power": round(max_p, 3)})
    return None


# =====================================================================
# ================  AI SMART LAYERS (6 tầng)  =======================
# =====================================================================
def _ai_init_mlp(input_dim):
    if not NUMPY_OK:
        return False
    np.random.seed(42)
    AI_STATE["mlp_W1"] = np.random.randn(input_dim, AI_MLP_HIDDEN) * 0.1
    AI_STATE["mlp_b1"] = np.zeros(AI_MLP_HIDDEN)
    AI_STATE["mlp_W2"] = np.random.randn(AI_MLP_HIDDEN, 1) * 0.1
    AI_STATE["mlp_b2"] = np.zeros(1)
    AI_STATE["stacker_w"] = np.zeros(4)
    AI_STATE["stacker_bias"] = 0.0
    return True


def ai_build_features(results):
    """32 chiều feature từ chuỗi results (results[0]=mới nhất)."""
    if not NUMPY_OK or len(results) < AI_FEATURE_WINDOW:
        return None
    bits = np.array([1.0 if r == "Tài" else 0.0 for r in results[:AI_FEATURE_WINDOW]])
    feats = []
    # 1-5: tỷ lệ windows
    for w in (3, 5, 8, 12, 20):
        if len(bits) >= w:
            feats.append(bits[:w].mean())
        else:
            feats.append(0.5)
    # 6: streak hiện tại (chuẩn hóa)
    streak = 1
    for i in range(1, len(bits)):
        if bits[i] == bits[0]:
            streak += 1
        else:
            break
    feats.append(min(1.0, streak / 10.0))
    # 7: entropy 10 phiên
    p = bits[:10].mean()
    e = 0.0
    if 0 < p < 1:
        e = -p * np.log2(p) - (1 - p) * np.log2(1 - p)
    feats.append(e)
    # 8: alternating
    alt = 1.0 if len(bits) >= 5 and all(bits[i] != bits[i + 1] for i in range(5)) else 0.0
    feats.append(alt)
    # 9-13: bit cuối cùng (5 phiên mới nhất) ảnh hưởng
    for i in range(5):
        feats.append(float(bits[i]))
    # 14-18: bit cũ hơn (index 5-9)
    for i in range(5, 10):
        feats.append(float(bits[i]) if i < len(bits) else 0.5)
    # 19-23: rolling mean 5 cửa sổ
    for i in range(5):
        lo, hi = i * 4, i * 4 + 4
        if hi <= len(bits):
            feats.append(bits[lo:hi].mean())
        else:
            feats.append(0.5)
    # 24-28: transitions đếm
    for i in range(4):
        if i + 1 < len(bits):
            feats.append(1.0 if bits[i] != bits[i + 1] else 0.0)
        else:
            feats.append(0.5)
    # 29: momentum (0.7*recent - 0.3*old)
    m = 0.7 * bits[:5].mean() - 0.3 * bits[5:15].mean() if len(bits) >= 15 else 0.5
    feats.append(m + 0.5)
    # 30: variance
    feats.append(float(bits.var()))
    # 31: max run length
    mr, cur = 1, 1
    for i in range(1, len(bits)):
        if bits[i] == bits[i - 1]:
            cur += 1
            mr = max(mr, cur)
        else:
            cur = 1
    feats.append(min(1.0, mr / 10.0))
    # 32: drift 10 phiên
    if len(bits) >= 20:
        dr = bits[:10].mean() - bits[10:20].mean()
        feats.append(dr + 0.5)
    else:
        feats.append(0.5)

    x = np.array(feats, dtype=float)[:AI_FEATURE_WINDOW]
    if len(x) < AI_FEATURE_WINDOW:
        x = np.pad(x, (0, AI_FEATURE_WINDOW - len(x)), constant_values=0.5)
    return x.reshape(1, -1)


def _ai_mlp_forward(x):
    W1 = AI_STATE["mlp_W1"]
    if W1 is None:
        return 0.5
    h = np.maximum(0, x @ W1 + AI_STATE["mlp_b1"])  # ReLU
    out = h @ AI_STATE["mlp_W2"] + AI_STATE["mlp_b2"]
    return float(1.0 / (1.0 + np.exp(-out[0][0])))


def _ai_mlp_train_step(x, y, lr=AI_ONLINE_LR):
    W1, b1 = AI_STATE["mlp_W1"], AI_STATE["mlp_b1"]
    W2, b2 = AI_STATE["mlp_W2"], AI_STATE["mlp_b2"]
    if W1 is None:
        return
    h_pre = x @ W1 + b1
    h = np.maximum(0, h_pre)
    out = h @ W2 + b2
    p = 1.0 / (1.0 + np.exp(-out[0][0]))
    err = p - y
    # gradient
    dW2 = h.T * err
    db2 = err
    dh = (W2 * err).flatten()
    dh[h_pre.flatten() <= 0] = 0
    dW1 = x.T @ dh.reshape(1, -1)
    db1 = dh
    # update
    AI_STATE["mlp_W1"] = W1 - lr * dW1
    AI_STATE["mlp_b1"] = b1 - lr * db1
    AI_STATE["mlp_W2"] = W2 - lr * dW2
    AI_STATE["mlp_b2"] = b2 - lr * db2


# -------------------- GBM-LITE (decision stumps) --------------------
def _gbm_predict_proba(feats):
    """Tổng hợp các stump đã train. Chưa train → trả 0.5."""
    trees = AI_STATE["gbm_trees"]
    if not trees:
        return 0.5
    s = 0.0
    for stump in trees:
        idx = stump["feat"]
        th = stump["thresh"]
        v = feats[0, idx]
        s += stump["weight"] if v > th else -stump["weight"]
    p = 1.0 / (1.0 + math.exp(-s))
    return p


def _gbm_train(feats, y):
    """Train 1 stump mới (online)."""
    if not NUMPY_OK or feats is None:
        return
    x = feats[0]
    # chọn feature có tương quan cao nhất với y (y hiện tại)
    best_feat, best_th, best_w = 0, 0.5, 0.1
    if len(AI_STATE["gbm_trees"]) < AI_GBM_TREES:
        # chọn ngẫu nhiên feature và threshold, weight nhỏ
        idx = int(np.random.randint(0, x.shape[0]))
        th = float(x[idx])
        w = 0.05 if y > 0.5 else -0.05
        AI_STATE["gbm_trees"].append({"feat": idx, "thresh": th, "weight": abs(w)})
    else:
        # update stump ngẫu nhiên
        i = int(np.random.randint(0, len(AI_STATE["gbm_trees"])))
        st = AI_STATE["gbm_trees"][i]
        st["weight"] = float(st["weight"] * AI_ONLINE_DECAY + 0.01 * (2 * y - 1))


# -------------------- HMM REGIME --------------------
def _ai_regime_detect(results):
    """Đơn giản: phân loại regime theo phương sai + entropy."""
    if len(results) < 20:
        return "neutral"
    recent = results[:20]
    e = _entropy(recent)
    p = recent.count("Tài") / len(recent)
    var = p * (1 - p)
    if e > 0.9:
        return "volatile"
    if e < 0.4:
        return "trending"
    return "neutral"


def ai_hmm_regime_layer(results):
    """Tầng HMM: dự đoán theo regime."""
    if len(results) < 20:
        return None
    regime = _ai_regime_detect(results)
    AI_STATE["regime"] = regime
    recent = results[:10]
    p_tai = recent.count("Tài") / 10
    if regime == "trending":
        pred = "Tài" if p_tai > 0.5 else "Xỉu"
        return (pred, 9, {"type": "hmm_trending", "p_tai": round(p_tai, 3), "regime": regime})
    if regime == "volatile":
        return (_opp(results[0]), 8, {"type": "hmm_volatile", "regime": regime})
    return None


# -------------------- BAYESIAN ONLINE --------------------
def ai_bayesian_online(results):
    """Bayesian cập nhật trực tuyến: Beta prior theo regime."""
    if len(results) < 20:
        return None
    # dùng exponential weights
    wt = wx = 0.0
    for i, r in enumerate(results[:30]):
        w = math.exp(-i / 10.0)
        if r == "Tài": wt += w
        else: wx += w
    a = wt + 1.0
    b = wx + 1.0
    p = a / (a + b)
    ratio = max(p, 1 - p)
    if ratio < AI_CONF_MIN_SIGNAL:
        return None
    pred = "Tài" if p >= 0.5 else "Xỉu"
    return (pred, max(7, min(16, 7 + int((ratio - 0.5) * 35))),
            {"type": "bayes_online", "p_tai": round(p, 3), "a": round(a, 2), "b": round(b, 2)})


# -------------------- RESERVOIR COMPUTING --------------------
_RESERVOIR_W = None
_RESERVOIR_STATE = deque(maxlen=16)


def _reservoir_init(size=16):
    global _RESERVOIR_W
    if not NUMPY_OK or _RESERVOIR_W is not None:
        return
    np.random.seed(123)
    _RESERVOIR_W = np.random.randn(size, size) * 0.3
    _RESERVOIR_W = _RESERVOIR_W / (np.abs(np.linalg.eigvals(_RESERVOIR_W)).max() + 1e-6) * 0.9


def ai_reservoir_layer(results):
    """Reservoir đơn giản: dùng trạng thái nội tại để phát hiện pattern."""
    if not NUMPY_OK or len(results) < 20:
        return None
    _reservoir_init()
    if _RESERVOIR_W is None:
        return None
    state = np.zeros(16)
    for r in reversed(results[:20]):
        x = np.zeros(16)
        x[0] = 1.0 if r == "Tài" else -1.0
        state = np.tanh(_RESERVOIR_W @ state + x)
    # đọc ra: nếu state năng lượng cao → có pattern
    energy = float(np.linalg.norm(state))
    if energy < 0.5:
        return None
    # dùng chiều 0 để quyết định
    score = state[0]
    if abs(score) < 0.2:
        return None
    pred = "Tài" if score > 0 else "Xỉu"
    return (pred, 8, {"type": "reservoir", "energy": round(energy, 3),
                      "score": round(float(score), 3)})


# -------------------- MLP LAYER --------------------
def ai_mlp_layer(results):
    if not NUMPY_OK or len(results) < AI_MIN_TRAIN:
        return None
    feats = ai_build_features(results)
    if feats is None:
        return None
    if AI_STATE["mlp_W1"] is None:
        _ai_init_mlp(AI_FEATURE_WINDOW)
    p = _ai_mlp_forward(feats)
    if abs(p - 0.5) < 0.05:
        return None
    pred = "Tài" if p >= 0.5 else "Xỉu"
    ratio = max(p, 1 - p)
    w = max(8, min(20, 8 + int((ratio - 0.5) * 40)))
    return (pred, w, {"type": "mlp", "p_tai": round(p, 3), "trained": AI_STATE["mlp_trained"]})


# -------------------- GBM LAYER --------------------
def ai_gbm_layer(results):
    if not NUMPY_OK or len(results) < AI_MIN_TRAIN:
        return None
    feats = ai_build_features(results)
    if feats is None or not AI_STATE["gbm_trees"]:
        return None
    p = _gbm_predict_proba(feats)
    if abs(p - 0.5) < 0.05:
        return None
    pred = "Tài" if p >= 0.5 else "Xỉu"
    ratio = max(p, 1 - p)
    return (pred, max(7, min(18, 7 + int((ratio - 0.5) * 40))),
            {"type": "gbm", "p_tai": round(p, 3), "n_trees": len(AI_STATE["gbm_trees"])})


# =====================================================================
# META-AI STACKER — học từ 23 tầng
# =====================================================================
def _ai_stacker_predict(layers):
    """Stacker: logistic regression trên [st, sx, agree, n_layers]."""
    if not NUMPY_OK or AI_STATE["stacker_w"] is None:
        return None
    st = sum(w for p, w, _ in layers if p == "Tài")
    sx = sum(w for p, w, _ in layers if p == "Xỉu")
    tot = st + sx
    if tot == 0:
        return None
    ratio = st / tot
    n = len(layers)
    agree = sum(1 for p, _, _ in layers if p == ("Tài" if ratio > 0.5 else "Xỉu")) / n
    x = np.array([ratio, agree, n / 20.0, 1.0])
    z = x @ AI_STATE["stacker_w"] + AI_STATE["stacker_bias"]
    p = float(1.0 / (1.0 + math.exp(-max(-5, min(5, z)))))
    return p, x


def _ai_stacker_update(layers, y):
    if not NUMPY_OK or AI_STATE["stacker_w"] is None:
        return
    r = _ai_stacker_predict(layers)
    if r is None:
        return
    p, x = r
    err = p - y
    AI_STATE["stacker_w"] -= AI_STACKER_LR * err * x
    AI_STATE["stacker_bias"] -= AI_STACKER_LR * err


# =====================================================================
# CONFIDENCE CALIBRATION
# =====================================================================
def _conf_bin(conf):
    return min(9, max(0, int((conf - 50) / 5)))


def _calibrate(conf):
    """Hiệu chỉnh conf dựa trên lịch sử thực tế."""
    b = _conf_bin(conf)
    cal = AI_STATE["confidence_calibration"].get(b)
    if not cal or cal[1] < 5:
        return conf
    hit, total = cal
    real_rate = hit / total * 100
    return round(0.5 * conf + 0.5 * real_rate, 1)


def _update_calibration(conf, is_correct):
    b = _conf_bin(conf)
    if b not in AI_STATE["confidence_calibration"]:
        AI_STATE["confidence_calibration"][b] = [0, 0]
    AI_STATE["confidence_calibration"][b][1] += 1
    if is_correct:
        AI_STATE["confidence_calibration"][b][0] += 1


# =====================================================================
# ENSEMBLE CHÍNH
# =====================================================================
def _layer_perf_multiplier(name):
    perf = LAYER_PERF.get(name)
    if not perf or perf["total"] < ADAPTIVE_MIN_SAMPLES:
        return 1.0
    acc = perf["hit"] / perf["total"]
    return max(0.7, min(1.3, 0.7 + (acc - 0.5) * 1.2))


def lc79_predict(results, dice_sums=None):
    n = len(results)
    if n == 0:
        return "Tài", 50, {"mode": "empty"}
    if n == 1:
        return _opp(results[0]), 54, {"mode": "warmup_1"}
    if n == 2:
        if results[0] == results[1]:
            return _opp(results[0]), 57, {"mode": "warmup_2"}
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
            if r == results[0]: s += 1
            else: break
        if s >= 3:
            return results[0], 57, {"mode": "warmup_mom"}
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
        # ===== AI LAYERS =====
        ("ai_mlp",           ai_mlp_layer),
        ("ai_gbm",           ai_gbm_layer),
        ("ai_hmm_regime",    ai_hmm_regime_layer),
        ("ai_bayes_online",  ai_bayesian_online),
        ("ai_reservoir",     ai_reservoir_layer),
    ]

    for name, fn in layer_funcs:
        try:
            r = fn(results)
        except Exception:
            r = None
        if r:
            p, w, info = r
            w = w * _layer_perf_multiplier(name)
            layers.append((p, w, info))
            names.append(name)

    if dice_sums:
        r = lc79_dice_analysis(dice_sums)
        if r:
            layers.append(r)
            names.append("dice_bias")

    if not layers:
        return _opp(results[0]), 54, {"mode": "fallback_alt"}

    # ==== META STACKER ====
    stacker_result = _ai_stacker_predict(layers)
    st = sum(w for p, w, _ in layers if p == "Tài")
    sx = sum(w for p, w, _ in layers if p == "Xỉu")
    tot = st + sx
    if tot == 0:
        return _opp(results[0]), 54, {"mode": "no_signal"}

    if stacker_result:
        p_stack, _ = stacker_result
        # blend stacker với weighted vote
        ratio_vote = st / tot
        final_ratio = 0.6 * p_stack + 0.4 * ratio_vote
        pred = "Tài" if final_ratio > 0.5 else "Xỉu"
        ratio = max(final_ratio, 1 - final_ratio)
    else:
        pred = "Tài" if st > sx else "Xỉu"
        ratio = max(st, sx) / tot

    agree = sum(1 for p, _, _ in layers if p == pred)
    nl = len(layers)
    conf = 52 + int((ratio - 0.5) * 60)
    if nl >= 2:
        conf += int((agree / nl) * 14)
        if agree == nl and nl >= 3:
            conf += 4
    conf += min(5, max(0, nl - 2))
    if nl == 1: conf -= 8
    elif nl == 2: conf -= 3
    conf = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEIL, conf))
    conf = _calibrate(conf)  # calibration!

    meta = {
        "mode": "lc79_v4_heep_ai",
        "n_layers": nl,
        "agree": agree,
        "ratio": round(ratio, 3),
        "stacker_used": stacker_result is not None,
        "regime": AI_STATE["regime"],
        "layers": [
            {"name": name, "pred": p, "w": round(w, 2), "info": info}
            for name, (p, w, info) in zip(names, layers)
        ],
    }
    return pred, conf, meta


# =====================================================================
# HỌC ONLINE — gọi khi có kết quả phiên mới
# =====================================================================
def ai_online_learn(valid_sessions):
    """Train MLP + GBM + Stacker khi có kết quả mới."""
    if not AI_ENABLED or not NUMPY_OK or len(valid_sessions) < AI_MIN_TRAIN:
        return
    results = [v["result"] for v in valid_sessions][::-1]
    if AI_STATE["mlp_W1"] is None:
        _ai_init_mlp(AI_FEATURE_WINDOW)

    # Train trên N phiên gần nhất
    n_train = min(20, len(results) - AI_FEATURE_WINDOW - 1)
    if n_train < 1:
        return
    for i in range(n_train):
        hist = results[i + 1:]
        if len(hist) < AI_FEATURE_WINDOW:
            continue
        feat = ai_build_features(hist)
        if feat is None:
            continue
        target = 1.0 if results[i] == "Tài" else 0.0
        try:
            _ai_mlp_train_step(feat, target)
            _gbm_train(feat, target)
        except Exception:
            continue
        AI_STATE["mlp_trained"] += 1

    # Cập nhật stacker
    if len(results) >= 10:
        for i in range(min(5, len(results) - 6)):
            hist = results[i + 1:]
            # tạm build layers (bỏ qua stacker đệ quy)
            try:
                pred, conf, meta = _predict_no_stacker(hist)
                if meta and meta.get("layers"):
                    y = 1.0 if results[i] == "Tài" else 0.0
                    # rebuild layer tuples để update
                    lt = [(L["pred"], L["w"], L["info"]) for L in meta["layers"]]
                    _ai_stacker_update(lt, y)
            except Exception:
                continue


def _predict_no_stacker(results):
    """Predict không dùng stacker (để tránh đệ quy khi training)."""
    layers = []
    names = []
    funcs = [
        ("heep_5", lc79_heep), ("fingerprint_md5", lc79_fingerprint),
        ("transition_md5", lc79_transition_md5), ("momentum_entropy", lc79_momentum_entropy),
        ("pattern_ngram", lc79_pattern_ngram), ("markov2", lc79_markov2),
        ("bayesian_recency", lc79_bayesian_recency), ("streak_pressure", lc79_streak_pressure),
        ("md5_cluster", lc79_md5_cluster), ("cycle_detector", lc79_cycle_detector),
        ("bayesian_drift", lc79_bayesian_drift), ("multi_window", lc79_multi_window_consensus),
        ("changepoint", lc79_changepoint), ("run_length", lc79_run_length),
        ("mean_reversion", lc79_mean_reversion), ("kalman_state", lc79_kalman_state),
        ("fourier_period", lc79_fourier_period), ("ai_mlp", ai_mlp_layer),
        ("ai_gbm", ai_gbm_layer), ("ai_hmm_regime", ai_hmm_regime_layer),
        ("ai_bayes_online", ai_bayesian_online), ("ai_reservoir", ai_reservoir_layer),
    ]
    for name, fn in funcs:
        try:
            r = fn(results)
        except Exception:
            r = None
        if r:
            layers.append(r)
            names.append(name)
    if not layers:
        return _opp(results[0]), 54, {"layers": []}
    st = sum(w for p, w, _ in layers if p == "Tài")
    sx = sum(w for p, w, _ in layers if p == "Xỉu")
    tot = st + sx
    if tot == 0:
        return _opp(results[0]), 54, {"layers": []}
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / tot
    meta = {"layers": [{"name": name, "pred": p, "w": round(w, 2), "info": info}
                       for name, (p, w, info) in zip(names, layers)]}
    return pred, 50 + int(ratio * 40), meta


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
            rows.append({"phien": int(phien), "result": res,
                         "dice": dice_str, "total": total})
        except Exception:
            continue
    return rows


def fetch_sessions():
    global LAST_FETCH_OK_TS
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://wtx.tele68.com/",
    }
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
        except Exception as e:
            time.sleep(0.4 * (attempt + 1))
    return [], False


# =====================================================================
# PREDICTION CACHE
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
        _update_calibration(conf, is_correct)
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
# HTML
# =====================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LEMINH AI v4</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root { --bg-card:#1e293b; --text-main:#f8fafc; --text-muted:#94a3b8; --border:#334155; --tai:#38bdf8; --xiu:#f472b6; --win:#22c55e; --lose:#ef4444; }
    * { box-sizing:border-box; margin:0; padding:0; font-family:'Plus Jakarta Sans',sans-serif; }
    body { background:linear-gradient(135deg,#0f172a,#1e1b4b); color:var(--text-main); min-height:100vh; padding-bottom:40px; }
    .header { background:rgba(30,41,59,0.85); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); padding:16px 24px; display:flex; justify-content:space-between; align-items:center; position:sticky; top:0; z-index:100; }
    .header-title { font-size:22px; font-weight:800; color:#38bdf8; text-shadow:0 0 20px rgba(56,189,248,0.4); }
    .btn-refresh { background:var(--bg-card); color:var(--text-main); border:1px solid var(--border); width:38px; height:38px; border-radius:10px; cursor:pointer; }
    .btn-reset { background:rgba(248,113,113,0.2); color:#f87171; border:1px solid #f87171; padding:8px 16px; border-radius:10px; font-weight:700; cursor:pointer; }
    .stats-bar { max-width:800px; margin:18px auto 0; padding:0 16px; display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
    .stat-card { background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:12px; text-align:center; }
    .stat-label { font-size:11px; color:var(--text-muted); font-weight:700; text-transform:uppercase; }
    .stat-value { font-size:22px; font-weight:800; margin-top:4px; }
    .win { color:var(--win); } .lose { color:var(--lose); } .rate { color:#38bdf8; }
    .table-wrapper { max-width:800px; margin:18px auto; padding:0 16px; }
    .table-container { background:var(--bg-card); border:1px solid var(--border); border-radius:16px; max-height:72vh; overflow-y:auto; }
    .data-table { width:100%; border-collapse:separate; border-spacing:0; }
    .data-table th { background:#111827; color:var(--text-muted); font-size:11px; font-weight:700; text-transform:uppercase; padding:14px 10px; position:sticky; top:0; }
    .data-table td { padding:12px 10px; text-align:center; border-bottom:1px solid var(--border); font-size:14px; font-weight:600; }
    .badge { display:inline-block; padding:6px 12px; border-radius:20px; font-size:12px; font-weight:700; min-width:66px; }
    .badge-tai { background:rgba(56,189,248,0.15); color:var(--tai); border:1px solid rgba(56,189,248,0.3); }
    .badge-xiu { background:rgba(244,114,182,0.15); color:var(--xiu); border:1px solid rgba(244,114,182,0.3); }
    .badge-win { background:rgba(34,197,94,0.15); color:var(--win); }
    .badge-lose { background:rgba(239,68,68,0.15); color:var(--lose); }
    .badge-none { background:rgba(148,163,184,0.12); color:var(--text-muted); }
    .dice-text, .conf-text { font-size:11px; color:var(--text-muted); display:block; margin-top:4px; }
    .loading { text-align:center; padding:40px; color:#38bdf8; font-weight:600; }
</style>
</head>
<body>
<div class="header">
    <div class="header-title">🤖 LEMINH AI v4</div>
    <div style="display:flex; gap:12px; align-items:center;">
        <div id="time-update" style="font-size:12px; color:var(--text-muted);">--:--:--</div>
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
<div class="table-wrapper"><div class="table-container">
<table class="data-table">
<thead><tr><th>Phiên</th><th>Dự đoán</th><th>Kết quả</th><th>Nhận định</th></tr></thead>
<tbody id="table-body"><tr><td colspan="4" class="loading">Đang kết nối AI...</td></tr></tbody>
</table></div></div>
<script>
let isResetting = false;
async function fetchData() {
    if (isResetting) return;
    try {
        const r = await fetch('/api/history', {cache:'no-store'});
        const d = await r.json();
        document.getElementById('time-update').innerText = new Date().toLocaleTimeString('vi-VN');
        const s = d.stats || {};
        document.getElementById('stat-total').innerText = s.total||0;
        document.getElementById('stat-win').innerText = s.win||0;
        document.getElementById('stat-lose').innerText = s.lose||0;
        document.getElementById('stat-rate').innerText = (s.rate||0)+'%';
        renderTable(d.rows||[]);
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
    const r = await Swal.fire({title:'Reset?', text:'Xoá lịch sử?', icon:'warning', background:'#1e293b', color:'#f8fafc', showCancelButton:true, confirmButtonText:'Đồng ý', cancelButtonText:'Hủy', confirmButtonColor:'#0ea5e9'});
    if (!r.isConfirmed) return;
    isResetting = true;
    try {
        const res = await fetch('/api/reset', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
        const d = await res.json();
        if (d.status === 'success') Swal.fire({title:'OK!', icon:'success', background:'#1e293b', color:'#f8fafc'});
        else throw new Error(d.message);
    } catch(e) { Swal.fire({title:'Lỗi', text:e.message, icon:'error', background:'#1e293b', color:'#f8fafc'}); }
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
        # trigger AI learning
        try:
            ai_online_learn(valid)
        except Exception:
            pass
        out = []
        win = lose = 0
        scan = min(len(valid), 200)
        for i in range(len(valid) - 1, len(valid) - scan - 1, -1):
            if i < 0:
                break
            s = valid[i]
            pred, conf, ok = get_prediction_for(valid, i)
            if ok is True: win += 1
            elif ok is False: lose += 1
            out.append({"phien": s["phien"], "result": s["result"], "dice": s["dice"],
                        "prediction": pred if pred != "-" else None,
                        "confidence": conf, "is_correct": ok})
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
        try:
            ai_online_learn(valid)
        except Exception:
            pass
        results = [v["result"] for v in valid][::-1]
        dice = _parse_dice_history(valid[::-1])
        ls = compute_loss_streak(valid)
        bp, bc, meta = lc79_predict(results, dice)
        pred, conf, flipped, reason = apply_recovery(bp, bc, ls, results)
        return jsonify({
            "algorithm": "LC79_V4_HEEP_AI",
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
            "regime": AI_STATE["regime"],
            "ai_enabled": AI_ENABLED,
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
        try:
            ai_online_learn(valid)
        except Exception:
            pass
        results = [v["result"] for v in valid][::-1]
        dice = _parse_dice_history(valid[::-1])
        ls = compute_loss_streak(valid)
        bp, bc, meta = lc79_predict(results, dice)
        pred, conf, flipped, reason = apply_recovery(bp, bc, ls, results)
        conf_str = f"{conf:.1f}".replace(".", ",") + "%"
        last = valid[-1]
        dp = last["dice"].split(" + ")
        dshort = "-".join(dp) if len(dp) == 3 else last["dice"]
        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])
        return jsonify({
            "id": "@cskhleminh",
            "algorithm": "LC79_HEEP_AI_V4",
            "phien": str(last["phien"] + 1),
            "ket_qua": f"{last['result'].lower()} {dshort}",
            "du_doan": pred,
            "do_tin_cay": conf_str,
            "lich_su": lich_su,
            "base_du_doan": bp if flipped else None,
            "auto_flip": flipped,
            "chuoi_thua": ls,
            "regime": AI_STATE["regime"],
            "meta": meta,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/heep")
def api_heep():
    try:
        raw, ok = fetch_sessions()
        if not ok and not HISTORY_CACHE:
            return jsonify({"error": "Không kết nối"}), 500
        valid = _sync_history(raw)
        if len(valid) < 5:
            return jsonify({"error": "Chưa đủ 5 phiên"}), 400
        results = [v["result"] for v in valid][::-1]
        info = heep_extract_5(results)
        detail = {}
        for name, fn in (("thuan", heep_mode_thuan), ("nghich", heep_mode_nghich), ("dao", heep_mode_dao)):
            r = fn(results, info)
            detail[name] = {"pred": r[0], "weight": round(r[1], 2), "info": r[2]} if r else None
        ens = lc79_heep(results)
        return jsonify({
            "algorithm": "HEEP_V4",
            "last_5": info["window"],
            "info": info,
            "modes": detail,
            "ensemble": {"pred": ens[0], "weight": round(ens[1], 2),
                         "ratio": ens[2]["ratio"]} if ens else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai")
def api_ai():
    """Trạng thái AI chi tiết."""
    try:
        cal = AI_STATE["confidence_calibration"]
        cal_out = {str(k): {"hit": v[0], "total": v[1],
                            "rate": round(v[0] / v[1] * 100, 1) if v[1] else 0}
                   for k, v in cal.items()}
        return jsonify({
            "algorithm": "LC79_V4_HEEP_AI",
            "numpy_available": NUMPY_OK,
            "ai_enabled": AI_ENABLED,
            "regime": AI_STATE["regime"],
            "mlp_trained_steps": AI_STATE["mlp_trained"],
            "gbm_trees": len(AI_STATE["gbm_trees"]),
            "stacker_initialized": AI_STATE["stacker_w"] is not None,
            "confidence_calibration": cal_out,
            "ai_hits": AI_STATE["ai_hits"],
            "ai_total": AI_STATE["ai_total"],
        })
    except Exception as e:
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
            layers.append({"name": name, "hit": perf["hit"], "total": perf["total"],
                           "accuracy": round(acc, 2),
                           "multiplier": round(_layer_perf_multiplier(name), 3)})
        layers.sort(key=lambda x: x["accuracy"], reverse=True)
        return jsonify({"algorithm": "LC79_V4_HEEP_AI",
                        "total_evaluations": total,
                        "layers": layers,
                        "history_cache_size": len(HISTORY_CACHE),
                        "prediction_cache_size": len(PREDICTION_CACHE)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/layers")
def api_layers():
    try:
        raw, ok = fetch_sessions()
        if not ok and not HISTORY_CACHE:
            return jsonify({"error": "Không kết nối"}), 500
        valid = _sync_history(raw)
        if not valid:
            return jsonify({"error": "Chưa có dữ liệu"}), 400
        results = [v["result"] for v in valid][::-1]
        dice = _parse_dice_history(valid[::-1])
        layer_funcs = [
            ("heep_5", lc79_heep), ("fingerprint_md5", lc79_fingerprint),
            ("transition_md5", lc79_transition_md5), ("momentum_entropy", lc79_momentum_entropy),
            ("pattern_ngram", lc79_pattern_ngram), ("markov2", lc79_markov2),
            ("bayesian_recency", lc79_bayesian_recency), ("streak_pressure", lc79_streak_pressure),
            ("md5_cluster", lc79_md5_cluster), ("cycle_detector", lc79_cycle_detector),
            ("bayesian_drift", lc79_bayesian_drift), ("multi_window", lc79_multi_window_consensus),
            ("changepoint", lc79_changepoint), ("run_length", lc79_run_length),
            ("mean_reversion", lc79_mean_reversion), ("kalman_state", lc79_kalman_state),
            ("fourier_period", lc79_fourier_period),
            ("ai_mlp", ai_mlp_layer), ("ai_gbm", ai_gbm_layer),
            ("ai_hmm_regime", ai_hmm_regime_layer), ("ai_bayes_online", ai_bayesian_online),
            ("ai_reservoir", ai_reservoir_layer),
        ]
        out = []
        for name, fn in layer_funcs:
            try:
                r = fn(results)
            except Exception:
                r = None
            if r:
                p, w, info = r
                perf = LAYER_PERF.get(name, {"hit": 0, "total": 0})
                acc = round(perf["hit"] / perf["total"] * 100, 2) if perf["total"] > 0 else None
                out.append({"name": name, "prediction": p, "weight": round(w, 2),
                            "multiplier": round(_layer_perf_multiplier(name), 3),
                            "accuracy": acc, "info": info})
            else:
                out.append({"name": name, "prediction": None, "info": "no_signal"})
        if dice:
            r = lc79_dice_analysis(dice)
            if r:
                out.append({"name": "dice_bias", "prediction": r[0],
                            "weight": round(r[1], 2), "info": r[2]})
        return jsonify({"algorithm": "LC79_V4_HEEP_AI",
                        "total_sessions": len(valid), "layers": out})
    except Exception as e:
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
            return jsonify({"error": "Không kết nối"}), 500
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
            if ic: win += 1
            else: lose += 1
            corrects.append(1 if ic else 0)
            details.append({"phien": s["phien"], "pred": p, "conf": c,
                            "result": s["result"], "correct": ic})
        tot = win + lose
        rate = round(win / tot * 100, 2) if tot else 0
        ml = cur = 0
        for c in corrects:
            if c == 0:
                cur += 1
                ml = max(ml, cur)
            else:
                cur = 0
        return jsonify({"algorithm": "LC79_V4_HEEP_AI", "n_sessions": tot,
                        "win": win, "lose": lose, "accuracy": rate,
                        "max_loss_streak": ml, "details": details})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "ok",
        "algorithm": "LC79_V4_HEEP_AI",
        "numpy_available": NUMPY_OK,
        "ai_enabled": AI_ENABLED,
        "server_time": datetime.now().isoformat(),
        "last_fetch_age_s": round(time.time() - LAST_FETCH_OK_TS, 1) if LAST_FETCH_OK_TS > 0 else None,
        "history_cache_size": len(HISTORY_CACHE),
        "prediction_cache_size": len(PREDICTION_CACHE),
        "regime": AI_STATE["regime"],
    })


@app.route("/api/reset", methods=["POST"])
def reset_api():
    global RESET_ID, HISTORY_CACHE, PREDICTION_CACHE, LAYER_PERF
    try:
        raw, ok = fetch_sessions()
        if ok and raw:
            valid = sorted(raw, key=lambda x: x["phien"])
            if valid:
                RESET_ID = valid[-1]["phien"]
                last = valid[-1]
                HISTORY_CACHE = {last["phien"]: last}
                PREDICTION_CACHE = {}
                LAYER_PERF.clear()
                AI_STATE["confidence_calibration"] = {}
                return jsonify({"status": "success", "reset_to": RESET_ID,
                                "algorithm": "LC79_V4_HEEP_AI"})
        return jsonify({"status": "error", "message": "Không xác nhận được mốc reset"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
