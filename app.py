import os
import math
import time
import hashlib
import random
import traceback
from datetime import datetime
from collections import defaultdict
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

HEEP_WINDOW = 5
HEEP_FAIR_RATIO = 0.60
HEEP_DECAY = 0.85
HEEP_ENTROPY_HIGH = 0.95
HEEP_REVERSAL_STREAK = 3

# ====== PREDICTION LOCK (ổn định) ======
PREDICTION_LOCK = {}          # phien -> dict (pred, conf, dice, dice_sum, ts, meta_brief)
PREDICTION_LOCK_MAX = 100
LOCK_CONF_DRIFT_MAX = 3       # conf được phép dao động ±3 giữa các poll
LOCK_FLIP_GUARD = True        # không đổi pred sau khi khoá


# =====================================================================
# UTILS
# =====================================================================
def _opp(v):
    return "Xỉu" if v == "Tài" else "Tài"


def get_groups(results):
    if not results:
        return []
    g, cur, c = [], results[0], 1
    for r in results[1:]:
        if r == cur:
            c += 1
        else:
            g.append(c)
            cur, c = r, 1
    g.append(c)
    return g


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
# HEEP 5 PHIÊN
# =====================================================================
def heep_extract_5(results):
    if not results:
        return None
    win = results[:HEEP_WINDOW]
    bits = [1 if r == "Tài" else 0 for r in win]
    streak = 1
    for r in results[1:]:
        if r == results[0]: streak += 1
        else: break
    alternating = len(bits) >= 5 and all(bits[i] != bits[i + 1] for i in range(len(bits) - 1))
    pair_alt = False
    if len(bits) >= 4:
        pair_alt = (bits[0] == bits[1]) and (bits[2] == bits[3]) and (bits[0] != bits[2])
    tai_c = win.count("Tài")
    xiu_c = win.count("Xỉu")
    dom, mino, cnt = ("Tài", "Xỉu", tai_c) if tai_c >= xiu_c else ("Xỉu", "Tài", xiu_c)
    return {
        "window": win, "streak": streak,
        "alternating": alternating, "pair_alternating": pair_alt,
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
                     "weighted_ratio": round(ratio, 3)})


def heep_mode_nghich(results, info):
    if not info:
        return None
    cur = results[0]
    ratio = _weighted_ratio(results, cur)
    if ratio < HEEP_FAIR_RATIO or info["streak"] >= 4 or info["entropy"] < 0.4:
        return None
    w = max(8, min(18, 8 + int((ratio - 0.55) * 30)))
    return (_opp(cur), w, {"mode": "nghich_reversion", "weighted_ratio": round(ratio, 3)})


def heep_mode_dao(results, info):
    if not info:
        return None
    if info["alternating"]:
        return (_opp(results[0]), 14, {"mode": "dao_1_1"})
    if info["pair_alternating"]:
        return (_opp(results[0]), 12, {"mode": "dao_2_2"})
    if info["streak"] >= HEEP_REVERSAL_STREAK:
        g = get_groups(results[1:11])
        avg = sum(g) / max(1, len(g)) if g else 2.0
        if info["streak"] >= avg * 1.6:
            return (_opp(results[0]), 11, {"mode": "dao_streak_break",
                                           "streak": info["streak"]})
    return None


def lc79_heep(results):
    if not results or len(results) < 5:
        return None
    info = heep_extract_5(results)
    if not info:
        return None
    sigs = []
    for fn in (heep_mode_dao, heep_mode_nghich, heep_mode_thuan):
        try:
            r = fn(results, info)
        except Exception:
            r = None
        if r:
            sigs.append(r)
    if not sigs:
        return None
    st = sum(w for p, w, _ in sigs if p == "Tài")
    sx = sum(w for p, w, _ in sigs if p == "Xỉu")
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    tot = st + sx
    ratio = max(st, sx) / tot
    w = max(10, min(24, 10 + int((ratio - 0.5) * 30) + len(sigs) * 2))
    return (pred, w, {"mode": "heep_5", "signals": len(sigs),
                      "ratio": round(ratio, 3), "info": info})


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
    return (best["pred"], w, {"window": best["window"],
                              "samples": round(best["samples"], 2),
                              "ratio": round(best["ratio"], 3)})


# =====================================================================
# TẦNG 2: TRANSITION
# =====================================================================
def lc79_transition_md5(results):
    if len(results) < 20:
        return None
    bits = _to_bits(results[::-1])
    sigs = []
    for order in (2, 3, 4, 5):
        if len(bits) < order + 10:
            continue
        cur = bits[-order:]
        tr = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
        for i in range(0, len(bits) - order):
            tr[_md5(bits[i:i + order])][("Tài" if bits[i + order] == "1" else "Xỉu")] += 1
        d = tr.get(_md5(cur))
        if not d:
            continue
        tot = d["Tài"] + d["Xỉu"]
        if tot < TRANSITION_MIN_SAMPLES:
            continue
        p = (d["Tài"] + BAYES_PRIOR_ALPHA) / (tot + 2 * BAYES_PRIOR_ALPHA)
        ratio = max(p, 1 - p)
        if ratio < 0.62:
            continue
        sigs.append({"pred": "Tài" if p >= 0.5 else "Xỉu",
                     "ratio": ratio, "samples": tot, "order": order})
    if not sigs:
        return None
    st = sum(s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] ** 0.5)
             for s in sigs if s["pred"] == "Tài")
    sx = sum(s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] ** 0.5)
             for s in sigs if s["pred"] == "Xỉu")
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    if ratio < 0.58:
        return None
    w = max(9, min(24, 9 + int((ratio - 0.6) * 45) + len(sigs) * 2))
    return (pred, w, {"samples": sum(s["samples"] for s in sigs), "ratio": round(ratio, 3)})


# =====================================================================
# TẦNG 3: MOMENTUM + ENTROPY
# =====================================================================
def lc79_momentum_entropy(results):
    if len(results) < 10:
        return None
    streak = 1
    for r in results[1:]:
        if r == results[0]: streak += 1
        else: break
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
# TẦNG 4: PATTERN
# =====================================================================
def lc79_pattern_ngram(results):
    if len(results) < 20:
        return None
    bits = _to_bits(results[::-1])
    sigs = []
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
        sigs.append({"pred": "Tài" if p >= 0.5 else "Xỉu",
                     "ratio": ratio, "samples": tot, "order": order})
    if not sigs:
        return None
    st = sum(s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] - 1)
             for s in sigs if s["pred"] == "Tài")
    sx = sum(s["ratio"] * math.log2(s["samples"] + 1) * (s["order"] - 1)
             for s in sigs if s["pred"] == "Xỉu")
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    w = max(10, min(25, 10 + int((ratio - 0.6) * 40) + len(sigs) * 2))
    return (pred, w, {"ratio": round(ratio, 3), "n_signals": len(sigs)})


# =====================================================================
# TẦNG 5: MARKOV
# =====================================================================
def lc79_markov2(results):
    if len(results) < 25:
        return None
    bits = _to_bits(results[::-1])
    sigs = []
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
        sigs.append({"pred": "Tài" if p >= 0.5 else "Xỉu",
                     "ratio": ratio, "samples": tot, "order": order})
    if not sigs:
        return None
    st = sum(s["ratio"] * math.log2(s["samples"] + 1) * s["order"]
             for s in sigs if s["pred"] == "Tài")
    sx = sum(s["ratio"] * math.log2(s["samples"] + 1) * s["order"]
             for s in sigs if s["pred"] == "Xỉu")
    if st == sx:
        return None
    pred = "Tài" if st > sx else "Xỉu"
    ratio = max(st, sx) / (st + sx)
    w = max(8, min(22, 8 + int((ratio - 0.55) * 40) + len(sigs) * 2))
    return (pred, w, {"ratio": round(ratio, 3)})


# =====================================================================
# TẦNG 6-16 (rút gọn)
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
            {"p_tai": round(p, 3)})


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
                {"type": "streak_break", "streak": streak})
    return None


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
    if nt > 0.65: pred, s = "Tài", (nt - 0.5) * 2
    elif nt < 0.35: pred, s = "Xỉu", (0.5 - nt) * 2
    else: return None
    return (pred, max(7, min(15, 7 + int(s * 8))), {"drift": round(d, 3)})


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
                    return ("Tài", 12, {"type": "cp_up", "idx": ci})
                if p <= 0.3:
                    return ("Xỉu", 12, {"type": "cp_down", "idx": ci})
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
        return (_opp(results[0]), 11, {"type": "break", "streak": cur})
    pc = (lo + 0.5 * eq) / tot
    if pc >= 0.80 and cur >= 2:
        return (results[0], 10, {"type": "continue", "streak": cur})
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
    return (pred, max(7, min(16, 7 + int(s * 9))), {"p_tai": round(p, 3)})


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
    return (pred, max(7, min(15, 7 + int(s * 8))), {"smoothed": round(smoothed, 3)})


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
# DICE HISTORY
# =====================================================================
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
    return (pred, 7 + int(s * 10), {"avg": round(avg, 2), "dev": round(dev, 2)})


# =====================================================================
# DICE PREDICTOR — Sinh 3 xúc xắc dự đoán
# =====================================================================
DICE_SUM_DIST = {
    3:1, 4:3, 5:6, 6:10, 7:15, 8:21, 9:25, 10:27,
    11:27, 12:25, 13:21, 14:15, 15:10, 16:6, 17:3, 18:1
}
DICE_TOTAL = 216


def _dice_dist_blend(dice_sums, pred, window=100, prior=40):
    """
    Phân phối tổng xúc xắc: blend lý thuyết 216 outcomes + lịch sử thực tế.
    pred='Tài' → boost sums 11-18; pred='Xỉu' → boost 3-10.
    """
    # Lý thuyết
    dist = {s: DICE_SUM_DIST[s] / DICE_TOTAL for s in DICE_SUM_DIST}
    # Lịch sử
    if dice_sums:
        hist = defaultdict(int)
        for s in dice_sums[:window]:
            if 3 <= s <= 18:
                hist[s] += 1
        n = sum(hist.values())
        if n > 0:
            for s in dist:
                p_hist = hist.get(s, 0) / n
                p_prior = DICE_SUM_DIST[s] / DICE_TOTAL
                dist[s] = (prior * p_prior + n * p_hist) / (prior + n)
    # Boost theo dự đoán
    boost = 1.8 if pred == "Tài" else 1.8
    for s in dist:
        if pred == "Tài" and s >= 11:
            dist[s] *= boost
        elif pred == "Xỉu" and s <= 10:
            dist[s] *= boost
    # Chuẩn hóa
    tot = sum(dist.values())
    return {s: dist[s] / tot for s in dist}


def _sample_dice_sum(dist):
    """Sample 1 tổng theo phân phối."""
    r = random.random()
    acc = 0.0
    for s in sorted(dist.keys()):
        acc += dist[s]
        if r <= acc:
            return s
    return 11


def _split_three_dice(target_sum):
    """
    Phân rã tổng thành 3 xúc xắc (1..6) sao cho tổng = target_sum.
    Ưu tiên phân bố đồng đều, không thiên lệch.
    """
    # Tất cả bộ ba hợp lệ
    combos = []
    for a in range(1, 7):
        for b in range(1, 7):
            c = target_sum - a - b
            if 1 <= c <= 6:
                combos.append((a, b, c))
    if not combos:
        # Fallback
        return [1, 1, 1]
    # Ưu tiên bộ có tổng phương sai nhỏ (gần đều)
    mean = target_sum / 3.0
    combos.sort(key=lambda x: sum((v - mean) ** 2 for v in x))
    # Top 3 ngẫu nhiên
    top = combos[:max(1, min(3, len(combos)))]
    return list(random.choice(top))


def predict_dice_for(pred, conf, dice_sums):
    """
    Sinh bộ 3 xúc xắc dự đoán + xác suất từng sum.
    Trả về dict đầy đủ.
    """
    dist = _dice_dist_blend(dice_sums, pred, prior=40)
    target_sum = _sample_dice_sum(dist)
    # Nếu tổng sampled lệch pred (do ngẫu nhiên), đảm bảo đúng hướng
    if pred == "Tài" and target_sum < 11:
        # Resample từ nhánh Tài
        tai_dist = {s: p for s, p in dist.items() if s >= 11}
        tot = sum(tai_dist.values())
        if tot > 0:
            tai_dist = {s: p / tot for s, p in tai_dist.items()}
            target_sum = _sample_dice_sum(tai_dist)
    elif pred == "Xỉu" and target_sum > 10:
        xiu_dist = {s: p for s, p in dist.items() if s <= 10}
        tot = sum(xiu_dist.values())
        if tot > 0:
            xiu_dist = {s: p / tot for s, p in xiu_dist.items()}
            target_sum = _sample_dice_sum(xiu_dist)

    dice = _split_three_dice(target_sum)
    sum_dist_sorted = sorted(dist.items(), key=lambda x: -x[1])
    top_sums = [{"sum": s, "p": round(p, 4)} for s, p in sum_dist_sorted[:5]]

    # Xác suất Tài / Xỉu theo phân phối
    p_tai = sum(p for s, p in dist.items() if s >= 11)
    p_xiu = 1 - p_tai

    return {
        "dice": dice,
        "sum": sum(dice),
        "confidence": conf,
        "sum_distribution_top5": top_sums,
        "p_tai_dist": round(p_tai, 4),
        "p_xiu_dist": round(p_xiu, 4),
    }


# =====================================================================
# ADAPTIVE MULTIPLIER
# =====================================================================
def _layer_perf_multiplier(name):
    perf = LAYER_PERF.get(name)
    if not perf or perf["total"] < ADAPTIVE_MIN_SAMPLES:
        return 1.0
    acc = perf["hit"] / perf["total"]
    return max(0.7, min(1.3, 0.7 + (acc - 0.5) * 1.2))


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

    layers, names = [], []
    funcs = [
        ("heep_5", lc79_heep),
        ("fingerprint_md5", lc79_fingerprint),
        ("transition_md5", lc79_transition_md5),
        ("momentum_entropy", lc79_momentum_entropy),
        ("pattern_ngram", lc79_pattern_ngram),
        ("markov2", lc79_markov2),
        ("bayesian_recency", lc79_bayesian_recency),
        ("streak_pressure", lc79_streak_pressure),
        ("md5_cluster", lc79_md5_cluster),
        ("cycle_detector", lc79_cycle_detector),
        ("bayesian_drift", lc79_bayesian_drift),
        ("multi_window", lc79_multi_window_consensus),
        ("changepoint", lc79_changepoint),
        ("run_length", lc79_run_length),
        ("mean_reversion", lc79_mean_reversion),
        ("kalman_state", lc79_kalman_state),
        ("fourier_period", lc79_fourier_period),
    ]
    for name, fn in funcs:
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

    st = sum(w for p, w, _ in layers if p == "Tài")
    sx = sum(w for p, w, _ in layers if p == "Xỉu")
    tot = st + sx
    if tot == 0:
        return _opp(results[0]), 54, {"mode": "no_signal"}
    if st > sx:
        pred, ratio = "Tài", st / tot
    elif sx > st:
        pred, ratio = "Xỉu", sx / tot
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
    if nl == 1: conf -= 8
    elif nl == 2: conf -= 3
    conf = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEIL, conf))

    meta = {
        "mode": "lc79_v5",
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
# RECOVERY (fix flip 2 lần)
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
# PREDICTION LOCK — Khóa dự đoán theo phiên
# =====================================================================
def _lock_prune():
    if len(PREDICTION_LOCK) <= PREDICTION_LOCK_MAX:
        return
    keys = sorted(PREDICTION_LOCK.keys())
    for k in keys[:len(PREDICTION_LOCK) - PREDICTION_LOCK_MAX]:
        del PREDICTION_LOCK[k]


def get_or_create_lock(phien, pred, conf, dice_sums):
    """
    Trả về dict dự đoán đã khóa cho phiên.
    - Nếu chưa có → tạo mới (gồm dice).
    - Nếu có → giữ nguyên pred, chỉ chỉnh conf ±LOCK_CONF_DRIFT_MAX.
    """
    if phien in PREDICTION_LOCK:
        locked = PREDICTION_LOCK[phien]
        # Conf drift: chỉ cho lệch nhẹ so với lần đầu
        old_c = locked["confidence"]
        new_c = max(old_c - LOCK_CONF_DRIFT_MAX,
                    min(old_c + LOCK_CONF_DRIFT_MAX, conf))
        locked["confidence"] = new_c
        return locked

    # Tạo mới
    dice_info = predict_dice_for(pred, conf, dice_sums)
    locked = {
        "phien": phien,
        "prediction": pred,
        "confidence": conf,
        "dice": dice_info["dice"],
        "dice_sum": dice_info["sum"],
        "sum_distribution_top5": dice_info["sum_distribution_top5"],
        "p_tai_dist": dice_info["p_tai_dist"],
        "p_xiu_dist": dice_info["p_xiu_dist"],
        "ts": time.time(),
        "flipped": False,
    }
    PREDICTION_LOCK[phien] = locked
    _lock_prune()
    return locked


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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
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
        except Exception:
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
        if ok is None: break
        if ok: break
        streak += 1
    return streak


# =====================================================================
# ROUTES
# =====================================================================
@app.route("/")
def index():
    return jsonify({
        "algorithm": "LC79_v5",
        "endpoints": ["/lc79md5", "/api/predict", "/api/history",
                      "/api/layers", "/api/backtest", "/api/health"],
    })


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
        out, win, lose = [], 0, 0
        scan = min(len(valid), 200)
        for i in range(len(valid) - 1, len(valid) - scan - 1, -1):
            if i < 0: break
            s = valid[i]
            pred, conf, ok2 = get_prediction_for(valid, i)
            if ok2 is True: win += 1
            elif ok2 is False: lose += 1
            out.append({"phien": s["phien"], "result": s["result"], "dice": s["dice"],
                        "prediction": pred if pred != "-" else None,
                        "confidence": conf, "is_correct": ok2})
        tot = win + lose
        return jsonify({"rows": out, "stats": {"total": tot, "win": win, "lose": lose,
                                               "rate": round(win / tot * 100, 1) if tot else 0}})
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

        next_phien = valid[-1]["phien"] + 1
        locked = get_or_create_lock(next_phien, pred, conf, dice)

        return jsonify({
            "algorithm": "LC79_v5",
            "last_phien": valid[-1]["phien"],
            "next_phien": next_phien,
            "last_result": valid[-1]["result"],
            "last_dice": valid[-1]["dice"],
            "prediction": locked["prediction"],
            "confidence": locked["confidence"],
            "dice": locked["dice"],
            "dice_sum": locked["dice_sum"],
            "base_prediction": bp,
            "recovery_flipped": flipped,
            "recovery_reason": reason,
            "loss_streak": ls,
            "total_sessions": len(valid),
            "last_5": results[:5],
            "meta": meta,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================================================================
# /lc79md5 — ENDPOINT CHÍNH (nâng cấp ổn định + xúc xắc)
# =====================================================================
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
        dice_sums = _parse_dice_history(valid[::-1])
        ls = compute_loss_streak(valid)

        # Dự đoán base + recovery
        bp, bc, meta = lc79_predict(results, dice_sums)
        pred, conf, flipped, reason = apply_recovery(bp, bc, ls, results)

        next_phien = valid[-1]["phien"] + 1

        # ==== KHOÁ DỰ ĐOÁN THEO PHIÊN ====
        locked = get_or_create_lock(next_phien, pred, conf, dice_sums)

        # ==== FORMAT ====
        conf_str = f"{locked['confidence']:.1f}".replace(".", ",") + "%"
        last = valid[-1]
        dp = last["dice"].split(" + ")
        dshort = "-".join(dp) if len(dp) == 3 else last["dice"]
        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])

        # Sinh chuỗi hiển thị xúc xắc dự đoán
        d1, d2, d3 = locked["dice"]
        dice_du_doan_str = f"{d1} + {d2} + {d3} = {locked['dice_sum']}"
        dice_short = f"{d1}-{d2}-{d3}"

        # Phân phối top 5
        top5 = locked["sum_distribution_top5"]

        # Trạng thái lock
        age = round(time.time() - locked["ts"], 1)

        return jsonify({
            "id": "@cskhleminh",
            "algorithm": "LC79_HEEP_V5",
            # Phiên
            "phien": str(next_phien),
            # Kết quả phiên trước
            "ket_qua": f"{last['result'].lower()} {dshort}",
            "ket_qua_tong": last.get("total", 0),
            # Dự đoán
            "du_doan": locked["prediction"],
            "do_tin_cay": conf_str,
            # Dự đoán xúc xắc
            "du_doan_xuc_xac": dice_du_doan_str,
            "du_doan_xuc_xac_short": dice_short,
            "du_doan_tong": locked["dice_sum"],
            "phan_bo_tong_top5": top5,
            "p_tai_theo_tong": locked["p_tai_dist"],
            "p_xiu_theo_tong": locked["p_xiu_dist"],
            # Lịch sử
            "lich_su": lich_su,
            # Recovery
            "base_du_doan": bp if flipped else None,
            "auto_flip": flipped,
            "ly_do_flip": reason,
            "chuoi_thua": ls,
            # Metadata
            "lock_age_s": age,
            "locked": True,
            "meta": {
                "mode": meta.get("mode"),
                "n_layers": meta.get("n_layers"),
                "agree": meta.get("agree"),
                "ratio": meta.get("ratio"),
                "layers": meta.get("layers", [])[:5],  # chỉ top 5 để gọn
            },
        })
    except Exception as e:
        traceback.print_exc()
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
        funcs = [
            ("heep_5", lc79_heep), ("fingerprint_md5", lc79_fingerprint),
            ("transition_md5", lc79_transition_md5), ("momentum_entropy", lc79_momentum_entropy),
            ("pattern_ngram", lc79_pattern_ngram), ("markov2", lc79_markov2),
            ("bayesian_recency", lc79_bayesian_recency), ("streak_pressure", lc79_streak_pressure),
            ("md5_cluster", lc79_md5_cluster), ("cycle_detector", lc79_cycle_detector),
            ("bayesian_drift", lc79_bayesian_drift), ("multi_window", lc79_multi_window_consensus),
            ("changepoint", lc79_changepoint), ("run_length", lc79_run_length),
            ("mean_reversion", lc79_mean_reversion), ("kalman_state", lc79_kalman_state),
            ("fourier_period", lc79_fourier_period),
        ]
        out = []
        for name, fn in funcs:
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
        return jsonify({"algorithm": "LC79_v5", "total_sessions": len(valid), "layers": out})
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
        details, corrects = [], []
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
        ml = cur = 0
        for c in corrects:
            if c == 0: cur += 1; ml = max(ml, cur)
            else: cur = 0
        return jsonify({"algorithm": "LC79_v5", "n_sessions": tot,
                        "win": win, "lose": lose,
                        "accuracy": round(win / tot * 100, 2) if tot else 0,
                        "max_loss_streak": ml, "details": details})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "ok",
        "algorithm": "LC79_v5",
        "server_time": datetime.now().isoformat(),
        "last_fetch_age_s": round(time.time() - LAST_FETCH_OK_TS, 1) if LAST_FETCH_OK_TS > 0 else None,
        "history_cache_size": len(HISTORY_CACHE),
        "prediction_cache_size": len(PREDICTION_CACHE),
        "lock_cache_size": len(PREDICTION_LOCK),
    })


@app.route("/api/reset", methods=["POST"])
def reset_api():
    global RESET_ID, HISTORY_CACHE, PREDICTION_CACHE, PREDICTION_LOCK, LAYER_PERF
    try:
        raw, ok = fetch_sessions()
        if ok and raw:
            valid = sorted(raw, key=lambda x: x["phien"])
            if valid:
                RESET_ID = valid[-1]["phien"]
                last = valid[-1]
                HISTORY_CACHE = {last["phien"]: last}
                PREDICTION_CACHE = {}
                PREDICTION_LOCK = {}
                LAYER_PERF.clear()
                return jsonify({"status": "success", "reset_to": RESET_ID,
                                "algorithm": "LC79_v5"})
        return jsonify({"status": "error", "message": "Không xác nhận được mốc reset"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
