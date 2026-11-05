# python · le_minh_v91_plus_v2.py · Python 3.10+ · Flask 2.x · requests 2.x
import os
import math
import traceback
import time
import itertools
from datetime import datetime
from collections import defaultdict, deque, Counter
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    pass

API_URL_MD5 = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"

HISTORY_CACHE = {}
PREDICTION_CACHE = {}
LAST_PREDICTIONS = {}
MAX_PREDICTION_CACHE = 2000
RESET_ID = 0

# =====================================================================
# HTML TEMPLATE (v91 — unchanged)
# =====================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 </title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root{--bg-page:#0f172a;--bg-card:#1e293b;--text-main:#f8fafc;--text-muted:#94a3b8;--border-color:#334155;--tai-color:#38bdf8;--tai-bg:rgba(56,189,248,.15);--xiu-color:#f472b6;--xiu-bg:rgba(244,114,182,.15);--win-color:#34d399;--win-bg:rgba(52,211,153,.15);--lose-color:#f87171;--lose-bg:rgba(248,113,113,.15);--wait-color:#fbbf24;--wait-bg:rgba(251,191,36,.15)}
    *{box-sizing:border-box;margin:0;padding:0;font-family:'Plus Jakarta Sans',sans-serif}
    body{background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 100%);color:var(--text-main);min-height:100vh;padding-bottom:40px}
    .header{background:rgba(30,41,59,.85);backdrop-filter:blur(12px);border-bottom:1px solid var(--border-color);padding:16px 24px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
    .header-title{font-size:22px;font-weight:800;color:#38bdf8;display:flex;align-items:center;gap:10px}
    .header-title span{font-size:11px;background:linear-gradient(135deg,#38bdf8,#ec4899);color:#fff;padding:4px 12px;border-radius:20px;font-weight:800;letter-spacing:1px}
    .header-actions{display:flex;gap:12px;align-items:center}
    .time-update{font-size:12px;color:var(--text-muted);font-weight:600}
    .btn-refresh{background:var(--bg-card);color:var(--text-main);border:1px solid var(--border-color);width:38px;height:38px;border-radius:10px;font-weight:700;font-size:16px;cursor:pointer}
    .btn-reset{background:rgba(248,113,113,.2);color:var(--lose-color);border:1px solid var(--lose-color);padding:8px 16px;border-radius:10px;font-weight:700;font-size:13px;cursor:pointer}
    .stats-bar{max-width:800px;margin:24px auto 16px;padding:0 16px;display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
    .stat-item{background:var(--bg-card);border:1px solid var(--border-color);border-radius:14px;padding:16px 10px;text-align:center}
    .stat-label{font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:700;margin-bottom:6px}
    .stat-value{font-size:22px;font-weight:800}
    .stat-value.win{color:var(--win-color)}.stat-value.loss{color:var(--lose-color)}.stat-value.rate{color:var(--tai-color)}
    .table-wrapper{max-width:800px;margin:0 auto;padding:0 16px}
    .table-container{background:var(--bg-card);border:1px solid var(--border-color);border-radius:16px;max-height:70vh;overflow-y:auto}
    .data-table{width:100%;border-collapse:separate;border-spacing:0}
    .data-table th{background:#111827;color:var(--text-muted);font-size:11px;font-weight:700;padding:16px 12px;text-align:center;border-bottom:1px solid var(--border-color);position:sticky;top:0;z-index:10}
    .data-table td{padding:14px 12px;text-align:center;border-bottom:1px solid var(--border-color);font-size:14px;font-weight:600}
    .row-next{background:rgba(14,165,233,.08);border-left:4px solid var(--tai-color)}
    .badge{display:inline-block;padding:6px 14px;border-radius:20px;font-size:12px;font-weight:700;min-width:70px;text-align:center}
    .badge-tai{background:var(--tai-bg);color:var(--tai-color);border:1px solid rgba(56,189,248,.3)}
    .badge-xiu{background:var(--xiu-bg);color:var(--xiu-color);border:1px solid rgba(244,114,182,.3)}
    .badge-empty{background:rgba(255,255,255,.05);color:var(--text-muted)}
    .status{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:700;padding:6px 14px;border-radius:20px}
    .st-win{background:var(--win-bg);color:var(--win-color)}.st-lose{background:var(--lose-bg);color:var(--lose-color)}.st-wait{background:var(--wait-bg);color:var(--wait-color);animation:pulse 1.5s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
    .dice-text{font-size:11px;color:var(--text-muted);display:block;margin-top:4px}
    .conf-badge{font-size:11px;color:#38bdf8;background:rgba(56,189,248,.1);padding:2px 8px;border-radius:10px;margin-top:4px;display:inline-block;font-weight:700}
    .conf-badge.high{color:#34d399;background:rgba(52,211,153,.15)}
    .flip-tag{font-size:9px;color:#fbbf24;font-weight:800;margin-top:2px;display:inline-block;background:rgba(251,191,36,.15);padding:1px 6px;border-radius:6px}
    .regime-tag{font-size:9px;color:#a78bfa;font-weight:800;margin-top:2px;display:inline-block;background:rgba(167,139,250,.15);padding:1px 6px;border-radius:6px}
    .loading{text-align:center;padding:40px;color:var(--tai-color);font-weight:600}
    @media(max-width:500px){.data-table th,.data-table td{padding:10px 6px;font-size:12px}.stats-bar{grid-template-columns:repeat(2,1fr)}.time-update{display:none}}
</style>
</head>
<body>
<div class="header">
    <div class="header-title">LE MINH <span> v2</span></div>
    <div class="header-actions">
        <div class="time-update" id="time-update">--:--:--</div>
        <button class="btn-refresh" onclick="fetchData()">↻</button>
        <button class="btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>
<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Thua</div><div class="stat-value loss" id="stat-lose">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ</div><div class="stat-value rate" id="stat-rate">0%</div></div>
</div>
<div class="table-wrapper"><div class="table-container">
<table class="data-table"><thead><tr><th>Phiên</th><th>Dự đoán</th><th>Kết quả</th><th>Trạng thái</th></tr></thead>
<tbody id="table-body"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody></table>
</div></div>
<script>
let isResetting=false;
function animateNumber(el,target,suffix=''){const s=parseInt(el.innerText.replace(/[^0-9]/g,''))||0;if(s===target){el.innerText=target+suffix;return}const d=500,st=performance.now();function u(t){const p=Math.min((t-st)/d,1),e=1-Math.pow(1-p,3);el.innerText=Math.floor(s+(target-s)*e)+suffix;if(p<1)requestAnimationFrame(u)}requestAnimationFrame(u)}
async function fetchData(){if(isResetting)return;try{const r=await fetch('/api/history',{cache:'no-store'});const data=await r.json();document.getElementById('time-update').innerText=new Date().toLocaleTimeString('vi-VN');renderTable(data.rows||[],data.stats||{})}catch(e){console.error(e)}}
function renderTable(rows,stats){const tb=document.getElementById('table-body');const total=stats.total||0,correct=stats.correct||0,wrong=total-correct;animateNumber(document.getElementById('stat-total'),total);animateNumber(document.getElementById('stat-win'),correct);animateNumber(document.getElementById('stat-lose'),wrong);animateNumber(document.getElementById('stat-rate'),Math.round(total>0?(correct/total)*100:0),'%');if(!rows.length){tb.innerHTML='<tr><td colspan="4" class="loading">Chưa có dữ liệu.</td></tr>';return}let html='';rows.forEach(row=>{const trCls=row.is_next?'class="row-next"':'';let ph=`<span class="badge badge-empty">-</span>`;if(row.prediction==="Tài")ph=`<span class="badge badge-tai">TÀI</span>`;if(row.prediction==="Xỉu")ph=`<span class="badge badge-xiu">XỈU</span>`;let ch='';if(row.conf&&row.prediction!=="-"){const c=row.conf>=70?'conf-badge high':'conf-badge';ch=`<div class="${c}">${row.conf}%</div>`}let fh='';if(row.recovery_flipped&&row.prediction!=="-"){fh=`<span class="flip-tag">🔄 FLIP</span>`}let rh2='';if(row.regime){rh2=`<span class="regime-tag">${row.regime}</span>`}const pf=`<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">${ph}${ch}${fh}${rh2}</div>`;let rh=`<span class="badge badge-empty">-</span>`;if(row.result==="Tài")rh=`<span class="badge badge-tai">TÀI</span>`;if(row.result==="Xỉu")rh=`<span class="badge badge-xiu">XỈU</span>`;let dd='';if(row.dice!=="? + ? + ?"){const p=row.dice.split(" + ");const s=parseInt(p[0])+parseInt(p[1])+parseInt(p[2]);dd=`<span class="dice-text">${row.dice} (${s})</span>`}const rf=`<div style="display:flex;flex-direction:column;align-items:center;">${rh}${dd}</div>`;let sh='';if(row.is_next)sh=`<span class="status st-wait">Chờ</span>`;else if(row.is_correct===true)sh=`<span class="status st-win">✔ THẮNG</span>`;else if(row.is_correct===false)sh=`<span class="status st-lose">✖ THUA</span>`;else sh=`<span class="status">-</span>`;html+=`<tr ${trCls}><td>#${row.phien}</td><td>${pf}</td><td>${rf}</td><td>${sh}</td></tr>`});tb.innerHTML=html}
async function confirmReset(){Swal.fire({title:'Reset?',text:'Xoá toàn bộ lịch sử?',icon:'warning',background:'#1e293b',color:'#f8fafc',showCancelButton:true,confirmButtonColor:'#0ea5e9',cancelButtonColor:'#64748b',confirmButtonText:'Đồng ý',cancelButtonText:'Hủy'}).then(async r=>{if(r.isConfirmed){isResetting=true;Swal.fire({title:'Đang Reset...',allowOutsideClick:false,background:'#1e293b',color:'#f8fafc',didOpen:()=>{Swal.showLoading()}});try{const res=await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const d=await res.json();if(d.status==='success'){Swal.fire({title:'OK!',text:'Đã reset.',icon:'success',background:'#1e293b',color:'#f8fafc',confirmButtonColor:'#0ea5e9'});isResetting=false;fetchData()}else throw new Error(d.message)}catch(e){Swal.fire({title:'Lỗi!',text:e.message,icon:'error',background:'#1e293b',color:'#f8fafc'});isResetting=false}}})}
fetchData();setInterval(fetchData,3000);
</script>
</body>
</html>"""


# =====================================================================
# DATA FETCHER
# =====================================================================
def fetch_sessions():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept': 'application/json'}
    for attempt in range(3):
        try:
            r = requests.get(API_URL_MD5, timeout=6, headers=headers)
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
            print(f"[API ERROR] Lần {attempt + 1}: {e}")
            time.sleep(1)
    return [], False


# =====================================================================
# UTILS
# =====================================================================
def get_groups(results):
    if not results: return []
    groups = []; current_val = results[0]; count = 1
    for r in results[1:]:
        if r == current_val: count += 1
        else: groups.append(count); current_val = r; count = 1
    groups.append(count)
    return groups

def _opp(v): return "Xỉu" if v == "Tài" else "Tài"

def _count_alternations(results, max_len=15):
    count = 0
    for i in range(min(len(results) - 1, max_len)):
        if results[i] != results[i + 1]: count += 1
        else: break
    return count

def _dice_sum_from_str(dice_str):
    if not dice_str: return None
    try:
        parts = dice_str.split(" + ")
        if len(parts) != 3: return None
        vals = [int(p.strip()) for p in parts]
        if any(v <= 0 or v > 6 for v in vals): return None
        return sum(vals)
    except (ValueError, AttributeError): return None


# =====================================================================
# CORE ALGORITHMS (v91)
# =====================================================================
def algo_bet_break(results, groups):
    if not groups or len(results) < 3: return []
    sigs = []; r0 = results[0]; g0 = groups[0]
    if g0 >= 12: sigs.append((_opp(r0), 42, "bet_12plus"))
    elif g0 >= 10: sigs.append((_opp(r0), 38, "bet_10plus"))
    elif g0 >= 8: sigs.append((_opp(r0), 32, "bet_8_9"))
    elif g0 >= 6: sigs.append((_opp(r0), 25, "bet_6_7"))
    elif g0 == 5: sigs.append((_opp(r0), 18, "bet_5"))
    elif g0 == 4: sigs.append((_opp(r0), 12, "bet_4"))
    elif g0 == 3:
        if len(groups) >= 5:
            past = groups[1:min(12, len(groups))]; avg_g = sum(past) / len(past)
            if avg_g < 2.3: sigs.append((_opp(r0), 13, "bet_3_break"))
            elif avg_g >= 3.5: sigs.append((r0, 11, "bet_3_cont"))
            else: sigs.append((_opp(r0), 9, "bet_3_def"))
        else: sigs.append((_opp(r0), 9, "bet_3_def"))
    return sigs

def algo_alternation(results):
    if len(results) < 4: return None
    alt = _count_alternations(results)
    if alt >= 8: return (_opp(results[0]), 26, "alt_8plus")
    if alt >= 6: return (_opp(results[0]), 22, "alt_6_7")
    if alt >= 4: return (_opp(results[0]), 16, "alt_4_5")
    if alt >= 3: return (_opp(results[0]), 10, "alt_3")
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
        tr[results[i + 1]][results[i]] += 1
    last = results[0]; tot = sum(tr[last].values())
    if tot < 5: return None
    p = tr[last]["Tài"] / tot
    if p >= 0.65: return ("Tài", 10, "markov1")
    if p <= 0.35: return ("Xỉu", 10, "markov1")
    return None

def algo_multi_window(results):
    n = len(results)
    if n < 15: return None
    w5 = results[:5].count("Tài"); w10 = results[:10].count("Tài"); w15 = results[:15].count("Tài")
    vt = sum([w5 >= 4, w10 >= 7, w15 >= 10]); vx = sum([w5 <= 1, w10 <= 3, w15 <= 5])
    if vt >= 2: return ("Tài", 11, "multi_window")
    if vx >= 2: return ("Xỉu", 11, "multi_window")
    return None

def algo_hot_tilt(results):
    n = len(results)
    if n < 12: return None
    for w, hi, lo in ((8, 7, 1), (12, 10, 2)):
        if n < w: continue
        tc = results[:w].count("Tài")
        if tc >= hi: return ("Xỉu", 14 if w == 8 else 12, f"hot_tai_{w}")
        if tc <= lo: return ("Tài", 14 if w == 8 else 12, f"hot_xiu_{w}")
    return None

def algo_tilt_ratio(results):
    n = len(results)
    if n < 15: return None
    for window in (15, 20, 30):
        if n < window: continue
        tr = results[:window].count("Tài") / window
        if tr >= 0.73: return ("Xỉu", 10, f"tilt_tai_{window}")
        if tr <= 0.27: return ("Tài", 10, f"tilt_xiu_{window}")
    return None

def algo_entropy(results):
    if len(results) < 20: return None
    p_tai = results[:20].count("Tài") / 20
    if p_tai in (0, 1): return ("Tài" if p_tai > 0.5 else "Xỉu", 9, "entropy_zero")
    entropy = -(p_tai * math.log2(p_tai) + (1 - p_tai) * math.log2(1 - p_tai))
    if entropy < 0.6: return ("Tài" if p_tai > 0.5 else "Xỉu", 9, "entropy_low")
    return None

def algo_simple_enhanced(results):
    if len(results) < 3: return None
    r0 = results[0]; streak = 1
    for r in results[1:]:
        if r == r0: streak += 1
        else: break
    if streak == 1:
        if len(results) >= 3 and results[1] == results[2]: return (_opp(r0), 8, "simple_break_pair")
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

def algo_markov2(results):
    n = len(results)
    if n < 20: return None
    counts = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
    for i in range(min(n, 60) - 2):
        context = (results[i + 1], results[i + 2])
        counts[context][results[i]] += 1
    context = (results[0], results[1])
    c = counts.get(context)
    if not c: return None
    total = c["Tài"] + c["Xỉu"]
    if total < 4: return None
    p_tai = c["Tài"] / total
    if p_tai >= 0.68: return ("Tài", 11, "markov2_tai")
    if p_tai <= 0.32: return ("Xỉu", 11, "markov2_xiu")
    return None

def algo_markov3(results):
    n = len(results)
    if n < 30: return None
    counts = defaultdict(lambda: {"Tài": 0, "Xỉu": 0})
    for i in range(min(n, 70) - 3):
        context = (results[i + 1], results[i + 2], results[i + 3])
        counts[context][results[i]] += 1
    context = (results[0], results[1], results[2])
    c = counts.get(context)
    if not c: return None
    total = c["Tài"] + c["Xỉu"]
    if total < 3: return None
    p_tai = c["Tài"] / total
    if p_tai >= 0.70: return ("Tài", 13, "markov3_tai")
    if p_tai <= 0.30: return ("Xỉu", 13, "markov3_xiu")
    return None

def algo_pattern_match(results):
    n = len(results)
    if n < 15: return None
    best = None
    for plen in (2, 3, 4):
        if n < plen + 5: continue
        pattern = tuple(results[:plen])
        counts = {"Tài": 0, "Xỉu": 0}
        for i in range(1, n - plen + 1):
            if tuple(results[i:i + plen]) == pattern: counts[results[i - 1]] += 1
        total = counts["Tài"] + counts["Xỉu"]
        if total < 3: continue
        p_tai = counts["Tài"] / total
        weight = min(14, 8 + plen * 2)
        if p_tai >= 0.72:
            cand = ("Tài", weight, f"pattern_L{plen}")
            if best is None or cand[1] > best[1]: best = cand
        elif p_tai <= 0.28:
            cand = ("Xỉu", weight, f"pattern_L{plen}")
            if best is None or cand[1] > best[1]: best = cand
    return best

def algo_streak_probability(results):
    n = len(results)
    if n < 10: return None
    cur_streak = 1
    for r in results[1:]:
        if r == results[0]: cur_streak += 1
        else: break
    if cur_streak < 2: return None
    streaks = []; i = 0
    while i < n:
        j = i + 1
        while j < n and results[j] == results[i]: j += 1
        streaks.append((i, j - i)); i = j
    rev = cont = 0
    for start, length in streaks:
        if start == 0: continue
        if start + length == n: continue
        if length >= cur_streak:
            if length == cur_streak: rev += 1
            else: cont += 1
    total = rev + cont
    if total < 5: return None
    p_rev = rev / total
    if p_rev >= 0.72: return (_opp(results[0]), 12, "streak_reversal_high")
    if p_rev <= 0.28: return (results[0], 11, "streak_continuation_high")
    return None

def algo_dice_sum_extreme(dice_sums):
    if not dice_sums or len(dice_sums) < 5: return None
    recent = [s for s in dice_sums[:5] if s is not None]
    if len(recent) < 5: return None
    avg = sum(recent) / len(recent)
    if avg >= 13.0: return ("Xỉu", 12, "dice_avg_high")
    if avg <= 8.0: return ("Tài", 12, "dice_avg_low")
    return None

def algo_dice_sum_trend(dice_sums):
    if not dice_sums or len(dice_sums) < 10: return None
    valid = [s for s in dice_sums[:10] if s is not None]
    if len(valid) < 10: return None
    n = len(valid); xs = list(range(n))
    mean_x = sum(xs) / n; mean_y = sum(valid) / n
    num = sum((xs[i] - mean_x) * (valid[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den == 0: return None
    slope = num / den
    if slope > 0.9: return ("Tài", 9, "dice_trend_revert")
    if slope < -0.9: return ("Xỉu", 9, "dice_trend_revert")
    return None


# =====================================================================
# 64-PATTERN SYSTEM (v91 — unchanged)
# =====================================================================
def _all_groups(results):
    if not results: return []
    groups = []; val = results[0]; count = 1
    for r in results[1:]:
        if r == val: count += 1
        else: groups.append((val, count)); val = r; count = 1
    groups.append((val, count))
    return groups

def _match_seq(results, pattern_tuple, window=200):
    plen = len(pattern_tuple)
    if len(results) < plen + 4: return None
    if tuple(results[:plen]) != pattern_tuple: return None
    counts = {"Tài": 0, "Xỉu": 0}
    end = min(len(results), window)
    for i in range(1, end - plen + 1):
        if tuple(results[i:i+plen]) == pattern_tuple: counts[results[i-1]] += 1
    total = counts["Tài"] + counts["Xỉu"]
    if total < 3: return None
    return counts["Tài"] / total, total

def _bet_detector(L):
    def detect(results, dice_sums=None):
        if len(results) < L + 5: return None
        val = results[0]; cur = 1
        for r in results[1:]:
            if r == val: cur += 1
            else: break
        matched = (cur == L) if L < 8 else (cur >= 8)
        if not matched: return None
        groups = _all_groups(results)
        cont = brk = 0
        for i in range(1, len(groups) - 1):
            v, ln = groups[i]
            m = (ln == cur) if L < 8 else (ln >= 8)
            if m:
                if groups[i-1][0] == v: cont += 1
                else: brk += 1
        total = cont + brk
        if total < 2:
            if cur <= 3: return (val, 9)
            if cur <= 5: return (_opp(val), 11)
            return (_opp(val), 14)
        p = cont / total
        if p >= 0.60: return (val, 12 + int((p - 0.5) * 20))
        if p <= 0.40: return (_opp(val), 12 + int((0.5 - p) * 20))
        return None
    return detect

def _alt_detector(N):
    def detect(results, dice_sums=None):
        if len(results) < N + 4: return None
        for i in range(N - 1):
            if results[i] == results[i+1]: return None
        cont = brk = 0
        for i in range(1, len(results) - N):
            is_alt = True
            for j in range(N - 1):
                if results[i+j] == results[i+j+1]: is_alt = False; break
            if is_alt:
                if results[i-1] != results[i]: cont += 1
                else: brk += 1
        total = cont + brk
        if total < 2: return (_opp(results[0]), 10)
        p = cont / total
        if p >= 0.60: return (_opp(results[0]), 12 + int((p - 0.5) * 20))
        if p <= 0.40: return (results[0], 12 + int((0.5 - p) * 20))
        return None
    return detect

def _keo_detector(a, b):
    def detect(results, dice_sums=None):
        groups = _all_groups(results)
        if len(groups) < 4: return None
        if a == b:
            if not all(groups[i][1] == a for i in range(min(3, len(groups)))): return None
        else:
            if not (groups[0][1] == a and groups[1][1] == b and groups[2][1] == a and groups[3][1] == b): return None
        cur_val = groups[0][0]; cur_len = groups[0][1]
        cont = brk = 0
        for i in range(1, len(groups) - 3):
            match = False
            if a == b:
                match = all(groups[i+j][1] == a for j in range(min(3, len(groups) - i - 1)))
            else:
                if i + 3 < len(groups):
                    match = (groups[i][1] == a and groups[i+1][1] == b and groups[i+2][1] == a and groups[i+3][1] == b)
            if match and i > 0:
                if groups[i-1][0] == groups[i][0]: cont += 1
                else: brk += 1
        total = cont + brk
        if total < 2:
            if cur_len >= a: return (_opp(cur_val), 10)
            return (cur_val, 9)
        p = cont / total
        if p >= 0.62: return (cur_val, 11 + int((p - 0.5) * 20))
        if p <= 0.38: return (_opp(cur_val), 11 + int((0.5 - p) * 20))
        return None
    return detect

def _seq_detector(pattern_str):
    pattern_tuple = tuple('Tài' if c == 'T' else 'Xỉu' for c in pattern_str)
    weight_base = 8 + len(pattern_str) * 2
    def detect(results, dice_sums=None):
        info = _match_seq(results, pattern_tuple)
        if info is None: return None
        p_tai, total = info
        if p_tai >= 0.65: return ('Tài', weight_base + int((p_tai - 0.5) * 15))
        if p_tai <= 0.35: return ('Xỉu', weight_base + int((0.5 - p_tai) * 15))
        return None
    return detect

def _dice_detector(kind):
    def detect(results, dice_sums=None):
        if not dice_sums: return None
        valid = [s for s in dice_sums[:10] if s is not None]
        if len(valid) < 10: return None
        avg = sum(valid) / len(valid)
        if kind == 'avg_high' and 12.5 <= avg < 14: return ('Xỉu', 10)
        if kind == 'avg_low' and 7 < avg <= 9.5: return ('Tài', 10)
        if kind == 'avg_extreme_high' and avg >= 14: return ('Xỉu', 13)
        if kind == 'avg_extreme_low' and avg <= 7: return ('Tài', 13)
        if kind == 'trend_up':
            xs = list(range(10)); mx = 4.5; my = avg
            num = sum((xs[i]-mx)*(valid[i]-my) for i in range(10))
            den = sum((xs[i]-mx)**2 for i in range(10))
            if den > 0 and num/den > 0.8: return ('Tài', 9)
        if kind == 'trend_down':
            xs = list(range(10)); mx = 4.5; my = avg
            num = sum((xs[i]-mx)*(valid[i]-my) for i in range(10))
            den = sum((xs[i]-mx)**2 for i in range(10))
            if den > 0 and num/den < -0.8: return ('Xỉu', 9)
        if kind == 'high_streak' and all(s >= 13 for s in valid[:5]): return ('Xỉu', 11)
        if kind == 'low_streak' and all(s <= 8 for s in valid[:5]): return ('Tài', 11)
        return None
    return detect

PATTERNS_64 = []
for _L in range(1, 8):
    PATTERNS_64.append({'id': f'bet_{_L}', 'name': f'Bệt {_L}', 'group': 'bet', 'fn': _bet_detector(_L)})
PATTERNS_64.append({'id': 'bet_8plus', 'name': 'Bệt 8+', 'group': 'bet', 'fn': _bet_detector(8)})
for _N in range(2, 10):
    PATTERNS_64.append({'id': f'alt_{_N}', 'name': f'Đảo {_N}', 'group': 'alt', 'fn': _alt_detector(_N)})
_KEO_PAIRS = [(2,2),(2,3),(3,2),(3,3),(2,4),(4,2),(3,4),(4,3),(4,4),(2,1),(1,2),(3,1),(1,3),(4,1),(1,4),(1,5)]
for _a, _b in _KEO_PAIRS:
    PATTERNS_64.append({'id': f'keo_{_a}_{_b}', 'name': f'Kèo {_a}-{_b}', 'group': 'keo', 'fn': _keo_detector(_a, _b)})
for _seq in ['TTT','TTX','TXT','TXX','XTT','XTX','XXT','XXX']:
    PATTERNS_64.append({'id': f'seq3_{_seq}', 'name': f'3 mẫu {_seq}', 'group': 'seq3', 'fn': _seq_detector(_seq)})
for _tup in itertools.product('TX', repeat=4):
    _s = ''.join(_tup)
    PATTERNS_64.append({'id': f'seq4_{_s}', 'name': f'4 mẫu {_s}', 'group': 'seq4', 'fn': _seq_detector(_s)})
for _k in ['avg_high','avg_low','avg_extreme_high','avg_extreme_low','trend_up','trend_down','high_streak','low_streak']:
    PATTERNS_64.append({'id': f'dice_{_k}', 'name': f'Dice {_k}', 'group': 'dice', 'fn': _dice_detector(_k)})

assert len(PATTERNS_64) == 64, f"Expected 64, got {len(PATTERNS_64)}"

def analyze_64_patterns(results, dice_sums=None):
    if dice_sums is not None and len(dice_sums) != len(results): dice_sums = None
    out = []
    for p in PATTERNS_64:
        try: res = p['fn'](results, dice_sums)
        except Exception: res = None
        out.append({'id': p['id'], 'name': p['name'], 'group': p['group'],
                    'matched': res is not None, 'pred': res[0] if res else None,
                    'weight': res[1] if res else 0})
    return out

def algo_patterns_64_aggregate(results, dice_sums=None):
    if len(results) < 5: return None
    prs = analyze_64_patterns(results, dice_sums)
    tai = sum(p['weight'] for p in prs if p['matched'] and p['pred'] == 'Tài')
    xiu = sum(p['weight'] for p in prs if p['matched'] and p['pred'] == 'Xỉu')
    total = tai + xiu
    if total < 18: return None
    ratio = max(tai, xiu) / total
    if ratio >= 0.64:
        pred = 'Tài' if tai > xiu else 'Xỉu'
        weight = min(16, 8 + int((ratio - 0.5) * 24))
        return (pred, weight, 'patterns64_agg')
    return None


# =====================================================================
# BRIDGE
# =====================================================================
def analyze_full_bridge(results, dice_sums=None, include_patterns64=True):
    if len(results) < 3: return []
    signals = []
    groups = get_groups(results)
    signals.extend(algo_bet_break(results, groups))
    alt = algo_alternation(results)
    if alt: signals.append(alt)
    fns = (algo_recency_momentum, algo_weighted_trend, algo_markov1,
           algo_multi_window, algo_hot_tilt, algo_tilt_ratio,
           algo_entropy, algo_simple_enhanced, algo_runlength_compare,
           algo_markov2, algo_markov3, algo_pattern_match, algo_streak_probability)
    for fn in fns:
        try:
            s = fn(results)
            if s: signals.append(s)
        except Exception: pass
    if dice_sums is not None and len(dice_sums) == len(results):
        for fn in (algo_dice_sum_extreme, algo_dice_sum_trend):
            try:
                s = fn(dice_sums)
                if s: signals.append(s)
            except Exception: pass
    if include_patterns64:
        try:
            s = algo_patterns_64_aggregate(results, dice_sums if (dice_sums is not None and len(dice_sums) == len(results)) else None)
            if s: signals.append(s)
        except Exception: pass
    return signals


def full_bridge_predict(results, dice_sums=None):
    if dice_sums is not None and len(dice_sums) != len(results): dice_sums = None
    if not results: return "Tài", 50
    if len(results) == 1: return _opp(results[0]), 52
    if len(results) == 2:
        if results[0] == results[1]: return _opp(results[0]), 55
        return results[1], 52
    signals = analyze_full_bridge(results, dice_sums, include_patterns64=True)
    if not signals: return results[0], 52
    st = sx = 0.0
    for p, w, name in signals:
        if p == "Tài": st += w
        else: sx += w
    total = st + sx
    if total == 0: return results[0], 50
    ratio = max(st, sx) / total
    evidence = min(1.0, total / 60.0)
    conf = int(max(50, min(92, 50 + ((ratio - 0.5) * 100) * evidence)))
    if st > sx: return "Tài", conf
    if sx > st: return "Xỉu", conf
    return _opp(results[0]), 50


# =====================================================================
# REGIME DETECTOR
# =====================================================================
def detect_regime(results):
    if len(results) < 8:
        return 'unknown', {'cur_streak': 0, 'avg_group_len': 0, 'alt_rate': 0, 'groups_count': 0}
    groups = _all_groups(results)
    cur_streak = groups[0][1] if groups else 0
    past = [g[1] for g in groups[1:min(20, len(groups))]]
    avg_len = sum(past) / len(past) if past else 2.0
    alt_count = _count_alternations(results, 20)
    denom = max(1, min(20, len(results) - 1))
    alt_rate = alt_count / denom
    info = {
        'cur_streak': cur_streak,
        'avg_group_len': round(avg_len, 2),
        'alt_rate': round(alt_rate, 2),
        'groups_count': len(groups),
    }
    if cur_streak >= 4: return 'bet_strong', info
    if alt_rate >= 0.65: return 'alt_strong', info
    if alt_rate >= 0.45: return 'alternating', info
    if avg_len >= 3.0: return 'bet_friendly', info
    return 'normal', info


# =====================================================================
# FULL BRIDGE ADAPTIVE v2
# =====================================================================
def _predict_result(pred, conf, detail, regime, regime_info, tai_score, xiu_score, edge=0.0):
    return {
        'pred': pred, 'conf': conf, 'detail': detail,
        'regime': regime, 'regime_info': regime_info,
        'tai_score': round(tai_score, 2), 'xiu_score': round(xiu_score, 2),
        'edge': round(edge, 3),
    }


def full_bridge_predict_adaptive_v2(results, replay_n=80, dice_sums=None):
    if dice_sums is not None and len(dice_sums) != len(results):
        dice_sums = None
    n = len(results)
    cur_regime, cur_regime_info = detect_regime(results)

    if n == 0:
        return _predict_result('Tài', 50, [], cur_regime, cur_regime_info, 0, 0)
    if n == 1:
        return _predict_result(_opp(results[0]), 52, [], cur_regime, cur_regime_info, 0, 0)
    if n == 2:
        p, c = (_opp(results[0]), 55) if results[0] == results[1] else (results[1], 52)
        return _predict_result(p, c, [], cur_regime, cur_regime_info, 0, 0)

    signal_stats = defaultdict(lambda: defaultdict(lambda: {'wins': 0.0, 'total': 0.0}))
    replay_count = min(replay_n, n - 3)

    for j in range(replay_count):
        history = results[j + 1:]
        history_dice = dice_sums[j + 1:] if dice_sums else None
        hist_regime, _ = detect_regime(history)
        decay = math.exp(-j / max(replay_count / 2.0, 1.0))
        try:
            for pred_sig, weight, name in analyze_full_bridge(history, history_dice, include_patterns64=False):
                signal_stats[hist_regime][name]['total'] += decay
                if pred_sig == results[j]:
                    signal_stats[hist_regime][name]['wins'] += decay
        except Exception:
            continue

    signals = analyze_full_bridge(results, dice_sums, include_patterns64=True)
    if not signals:
        return _predict_result(results[0], 52, [], cur_regime, cur_regime_info, 0, 0)

    st = sx = 0.0
    detail = []

    for pred_sig, weight, name in signals:
        s = signal_stats[cur_regime].get(name)
        regime_used = cur_regime
        if s is None or s['total'] < 3:
            s = signal_stats['normal'].get(name)
            regime_used = 'normal'
        if s is None or s['total'] < 3:
            agg_w = agg_t = 0.0
            for reg in signal_stats:
                entry = signal_stats[reg].get(name)
                if entry:
                    agg_w += entry['wins']
                    agg_t += entry['total']
            if agg_t >= 3:
                s = {'wins': agg_w, 'total': agg_t}
                regime_used = 'global'

        if s is not None and s['total'] >= 3:
            alpha = 2.0
            acc = (s['wins'] + alpha * 0.5) / (s['total'] + alpha)
            samples = int(s['total'])
        else:
            acc, samples = 0.5, 0

        accuracy_mult = 0.4 + max(0.0, min(1.8, (acc - 0.3) * 3.0))
        adjusted = weight * accuracy_mult

        if pred_sig == "Tài": st += adjusted
        else: sx += adjusted

        detail.append({
            'name': name, 'pred': pred_sig, 'base_weight': weight,
            'accuracy': round(acc, 3), 'samples': samples,
            'adjusted_weight': round(adjusted, 2),
            'regime_used': regime_used,
        })

    total = st + sx
    if total == 0:
        return _predict_result(results[0], 50, detail, cur_regime, cur_regime_info, st, sx)

    if st > sx:
        pred, ratio = "Tài", st / total
    elif sx > st:
        pred, ratio = "Xỉu", sx / total
    else:
        return _predict_result(_opp(results[0]), 50, detail, cur_regime, cur_regime_info, st, sx)

    base_conf = 50 + (ratio - 0.5) * 100
    evidence = min(1.0, total / 60.0)
    conf = 50 + (base_conf - 50) * evidence
    if ratio >= 0.72: conf += 6
    if ratio >= 0.80 and len(signals) >= 5: conf += 6
    if len(signals) >= 8 and ratio >= 0.65: conf += 3
    if len(signals) < 4: conf -= 5
    edge = (max(st, sx) - min(st, sx)) / total if total > 0 else 0

    return _predict_result(
        pred, int(max(50, min(95, conf))), detail,
        cur_regime, cur_regime_info, st, sx, edge,
    )


# =====================================================================
# CACHE + PERFORMANCE
# =====================================================================
def get_prediction_for(valid, i):
    key = valid[i]['phien']
    if key in PREDICTION_CACHE: return PREDICTION_CACHE[key]
    if key <= RESET_ID:
        PREDICTION_CACHE[key] = ("-", 50, None)
        return PREDICTION_CACHE[key]
    if key in LAST_PREDICTIONS:
        pred, conf = LAST_PREDICTIONS[key]
    else:
        hist = [v['result'] for v in valid[:i]][::-1]
        hist_dice = [_dice_sum_from_str(v['dice']) for v in valid[:i]][::-1]
        pred, conf = full_bridge_predict(hist, hist_dice)
    is_correct = (pred == valid[i]['result'])
    result = (pred, conf, is_correct)
    if len(PREDICTION_CACHE) > MAX_PREDICTION_CACHE: PREDICTION_CACHE.clear()
    PREDICTION_CACHE[key] = result
    return result


def compute_performance(valid, window=30):
    if not valid: return 0, 0.5, 0
    end = len(valid) - 1
    loss_streak = 0
    for i in range(end, max(-1, end - 20) - 1, -1):
        _, _, ok = get_prediction_for(valid, i)
        if ok is None: break
        if ok: break
        loss_streak += 1
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
# SMART FLIP v2
# =====================================================================
def _classify_last_bet(valid):
    if len(valid) < 2: return None
    try:
        last_idx = len(valid) - 1
        prev_phien = valid[last_idx]['phien']
        pred = None
        if prev_phien in LAST_PREDICTIONS:
            pred, _ = LAST_PREDICTIONS[prev_phien]
        elif prev_phien in PREDICTION_CACHE:
            pred, _, _ = PREDICTION_CACHE[prev_phien]
        else:
            if last_idx > 0:
                hist = [v['result'] for v in valid[:last_idx]][::-1]
                hist_dice = [_dice_sum_from_str(v['dice']) for v in valid[:last_idx]][::-1]
                pred, _ = full_bridge_predict(hist, hist_dice)
        if pred is None or pred == '-': return None
        prev_result = valid[last_idx - 1]['result']
        if pred == prev_result: return 'continue'
        if pred == _opp(prev_result): return 'break'
        return None
    except Exception:
        return None


def apply_auto_adjust_v2(base_pred, base_conf, valid, regime='normal', signal_detail=None):
    if len(valid) < 3:
        return {'pred': base_pred, 'conf': base_conf, 'flipped': False,
                'reason': None, 'loss_streak': 0, 'recent_acc': 0.5,
                'score': 0.0, 'score_reasons': []}

    loss_streak, recent_acc, recent_total = compute_performance(valid, window=25)
    bet_ctx = _classify_last_bet(valid)
    score = 0.0
    reasons = []

    if loss_streak >= 5: score += 5.0; reasons.append(f's{loss_streak}')
    elif loss_streak == 4: score += 4.0; reasons.append('s4')
    elif loss_streak == 3: score += 3.0; reasons.append('s3')
    elif loss_streak == 2: score += 2.0; reasons.append('s2')
    elif loss_streak == 1: score += 0.5; reasons.append('s1')

    if bet_ctx == 'continue': score += 1.5; reasons.append('bet_fail')
    elif bet_ctx == 'break': score += 1.0; reasons.append('break_fail')

    if recent_total >= 15:
        if recent_acc < 0.38: score += 2.5; reasons.append('acc_crit')
        elif recent_acc < 0.43: score += 1.8; reasons.append('acc_low')
        elif recent_acc < 0.48: score += 0.9; reasons.append('acc_soft')
        elif recent_acc > 0.62: score -= 0.8; reasons.append('acc_good')

    if regime == 'bet_strong' and bet_ctx == 'continue':
        score += 1.8; reasons.append('regime_bet_break')
    elif regime == 'alt_strong' and bet_ctx == 'break':
        score += 1.5; reasons.append('regime_alt_break')
    elif regime == 'bet_friendly' and bet_ctx == 'continue':
        score += 0.8; reasons.append('regime_bet_ready')

    if signal_detail:
        tw = sum(s['adjusted_weight'] for s in signal_detail if s['pred'] == 'Tài')
        xw = sum(s['adjusted_weight'] for s in signal_detail if s['pred'] == 'Xỉu')
        tot = tw + xw
        if tot > 0:
            maj_pred = 'Tài' if tw > xw else 'Xỉu'
            maj_ratio = max(tw, xw) / tot
            if maj_pred != base_pred and maj_ratio > 0.68:
                score += 1.2; reasons.append('sig_disagree')

    if len(valid) >= 5:
        dice_sums = [_dice_sum_from_str(v['dice']) for v in valid[-5:]][::-1]
        valid_dice = [s for s in dice_sums if s is not None]
        if len(valid_dice) >= 3:
            avg_dice = sum(valid_dice) / len(valid_dice)
            if avg_dice > 12.5 and base_pred == 'Tài':
                score += 0.8; reasons.append('dice_high_tension')
            elif avg_dice < 9.0 and base_pred == 'Xỉu':
                score += 0.8; reasons.append('dice_low_tension')

    base = {'loss_streak': loss_streak, 'recent_acc': recent_acc,
            'score': round(score, 2), 'score_reasons': reasons}

    if score >= 4.0:
        return {**base, 'pred': _opp(base_pred),
                'conf': min(96, base_conf + 12 + loss_streak * 2),
                'flipped': True, 'reason': 'HARD:' + '+'.join(reasons)}
    if score >= 2.5:
        return {**base, 'pred': _opp(base_pred),
                'conf': min(93, base_conf + 7),
                'flipped': True, 'reason': 'SOFT:' + '+'.join(reasons)}
    if score >= 1.5:
        return {**base, 'pred': base_pred,
                'conf': max(50, base_conf - 10),
                'flipped': False, 'reason': 'PENALTY:' + '+'.join(reasons)}
    if recent_total >= 15 and recent_acc > 0.60 and loss_streak == 0:
        return {**base, 'pred': base_pred,
                'conf': min(95, base_conf + 5),
                'flipped': False, 'reason': 'boost_good_acc'}
    return {**base, 'pred': base_pred, 'conf': base_conf,
            'flipped': False, 'reason': None}


def _store_last_prediction(phien, pred, conf):
    LAST_PREDICTIONS[phien] = (pred, conf)
    if len(LAST_PREDICTIONS) > MAX_PREDICTION_CACHE:
        for k in sorted(LAST_PREDICTIONS.keys())[:len(LAST_PREDICTIONS) - MAX_PREDICTION_CACHE]:
            del LAST_PREDICTIONS[k]


def _sync_history():
    raw_rows, success = fetch_sessions()
    if not success and not HISTORY_CACHE: return [], False
    for row in raw_rows: HISTORY_CACHE[row['phien']] = row
    for k in [k for k in HISTORY_CACHE if k <= RESET_ID and RESET_ID > 0]:
        if k < RESET_ID: del HISTORY_CACHE[k]
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    return valid, True


def _extract_dice_sums(valid_slice):
    return [_dice_sum_from_str(v['dice']) for v in valid_slice]


# =====================================================================
# =====================================================================
# V2 MODULE — 12-BO Ensemble + Adaptive Filter (ADDITIVE, isolated)
# =====================================================================
# =====================================================================

DEFAULT_CONFIG = {
    "GID": "vgmn_100", "POLL_SEC": 3.0, "HIST_KEEP": 600, "PERSIST_KEEP": 300,
    "TIE_LOGIC": "PPM6", "CONSEC_CHECK": True,
    "WR_WINDOW": 13, "WR_DECAY": 0.95, "WR_FLOOR": 1.0, "WR_WEIGHT_NEWEST": 1.0,
    "WR_FLIP_WEIGHT": False, "WR_MIN_GAMES": 1, "FLIP_FINAL": False,
    "AF_ENABLED": True, "AF_FLIP_LOW": 37.0, "AF_FLIP_HIGH": 63.0, "AF_FLIP_BAND": True,
    "AF_FLIP_LOW_MIN": 30.0, "AF_FLIP_LOW_MAX": 45.0,
    "AF_FLIP_HIGH_MIN": 53.0, "AF_FLIP_HIGH_MAX": 68.0, "AF_MIN_GAMES": 7,
    "AF_GROUP_FLIPPED_ONLY": True, "AF_GROUP_NEED_MAJORITY": True,
    "AF_SWITCH": True, "AF_SWITCH_NEED": 6, "AF_SWITCH_LEAD": False, "AF_SWITCH_PRIO": True,
    "AF_MODE_FLIP": False, "AF_MODE_WINDOW": 13, "AF_MODE_MIN": 7, "AF_MODE_BELOW": 45.0,
    "AF_FLIP_FINAL": False, "AF_FLIP_FINAL_CT": False,
    "AF_FLIP_FINAL_CAO": True, "AF_FLIP_FINAL_THAP": False, "AF_FLIP_FINAL_ALL": True,
    "EVAL_WINDOW": 300,
}


def _norm(x):
    if not x: return "HOA"
    u = str(x).strip().upper()
    if u.startswith("T"): return "TAI"
    if u.startswith("X"): return "XIU"
    return "HOA"


def _label(x):
    return "Tài" if x == "TAI" else ("Xỉu" if x == "XIU" else "Hòa")


def _binomial_smooth(k, n, alpha=1.0):
    return (k + alpha) / (n + 2 * alpha)


class HistoryStore:
    def __init__(self, keep=600, persist_keep=300):
        self.keep = keep
        self.persist_keep = persist_keep
        self.data = deque(maxlen=keep)
        self.predictions = deque(maxlen=keep)

    def append(self, phien, ket_qua, tong=0, sid=None):
        self.data.append({"phien": phien, "ket_qua": ket_qua, "tong": tong, "sid": sid})

    def append_prediction(self, phien, du_doan):
        self.predictions.append({"phien": phien, "du_doan": du_doan})

    def last_results(self, n):
        return [x["ket_qua"] for x in list(self.data)[-n:]]

    def last_phien(self):
        return self.data[-1]["phien"] if self.data else None

    def next_phien(self):
        p = self.last_phien()
        return (p + 1) if p is not None else None

    def update_ket_qua(self, phien, ket_qua):
        for item in reversed(self.data):
            if item["phien"] == phien:
                item["ket_qua"] = ket_qua
                return True
        return False


def ppm6_predict(seq, order=6):
    if not seq: return "TAI", 0.5
    if len(seq) < order + 1:
        tai = seq.count("TAI"); xiu = seq.count("XIU"); total = tai + xiu
        if total == 0: return "TAI", 0.5
        p = _binomial_smooth(tai, total)
        return ("TAI" if p >= 0.5 else "XIU"), max(p, 1 - p)
    ctx = tuple(seq[-order:]); counts = Counter()
    tail = list(seq)
    for i in range(len(tail) - order):
        if tuple(tail[i:i + order]) == ctx:
            nxt = tail[i + order]
            if nxt in ("TAI", "XIU"): counts[nxt] += 1
    if not counts: return ppm6_predict(seq, order - 1)
    total = sum(counts.values())
    p_tai = _binomial_smooth(counts["TAI"], total)
    p_xiu = 1 - p_tai
    return ("TAI", p_tai) if p_tai >= p_xiu else ("XIU", p_xiu)


def regime_predict(seq, window=20):
    if len(seq) < 5: return "TAI", 0.5
    seg = seq[-window:]; tai = seg.count("TAI"); xiu = seg.count("XIU")
    total = tai + xiu
    p = _binomial_smooth(tai, total)
    return ("TAI" if p >= 0.5 else "XIU"), max(p, 1 - p)


def knnh_predict(seq, window=10, k=5):
    if len(seq) < window + 1: return "TAI", 0.5
    q = seq[-window:]; candidates = []
    for i in range(len(seq) - window):
        seg = seq[i:i + window]
        dist = sum(1 for a, b in zip(seg, q) if a != b)
        candidates.append((dist, seq[i + window]))
    candidates.sort(key=lambda x: x[0])
    top = candidates[:k]
    if not top: return "TAI", 0.5
    weight = Counter()
    for dist, nxt in top:
        weight[nxt] += 1.0 / (1.0 + dist)
    total = sum(weight.values())
    p_tai = weight["TAI"] / total if total else 0.5
    return ("TAI", p_tai) if p_tai >= 0.5 else ("XIU", 1 - p_tai)


def runctk_predict(seq, max_run=10):
    if not seq: return "TAI", 0.5
    last = seq[-1]; run = 1
    for x in reversed(seq[:-1]):
        if x == last: run += 1
        else: break
    if run >= max_run:
        return ("XIU" if last == "TAI" else "TAI"), 0.6
    return last, 0.55


def totk_predict(seq):
    if not seq: return "TAI", 0.5
    return seq[-1], 0.52


def sparse_predict(seq, window=30, min_hits=2):
    if len(seq) < window: return "TAI", 0.5
    ctx_len = 4
    if len(seq) < ctx_len + 1: return "TAI", 0.5
    ctx = tuple(seq[-ctx_len:]); counts = Counter()
    tail = list(seq)
    for i in range(len(tail) - ctx_len):
        if tuple(tail[i:i + ctx_len]) == ctx:
            nxt = tail[i + ctx_len]
            if nxt in ("TAI", "XIU"): counts[nxt] += 1
    if sum(counts.values()) < min_hits: return "TAI", 0.5
    total = sum(counts.values())
    p_tai = counts["TAI"] / total
    return ("TAI", p_tai) if p_tai >= 0.5 else ("XIU", 1 - p_tai)


def cautpl_predict(seq, window=15):
    if len(seq) < window: return "TAI", 0.5
    seg = seq[-window:]
    has_tai = "TAI" in seg; has_xiu = "XIU" in seg
    if has_tai and not has_xiu: return "XIU", 0.6
    if has_xiu and not has_tai: return "TAI", 0.6
    return regime_predict(seq, window)


def fshare_predict(seq, window=20):
    if not seq: return "TAI", 0.5
    seg = seq[-window:] if len(seq) >= window else seq
    tai = seg.count("TAI"); xiu = seg.count("XIU"); total = tai + xiu
    if total == 0: return "TAI", 0.5
    p = tai / total
    if p > 0.55: return "XIU", p
    if p < 0.45: return "TAI", 1 - p
    return ("TAI" if p >= 0.5 else "XIU"), max(p, 1 - p)


def blkhaz_predict(seq):
    if not seq: return "TAI", 0.5
    tai = seq.count("TAI"); xiu = seq.count("XIU"); total = tai + xiu
    if total == 0: return "TAI", 0.5
    p = _binomial_smooth(tai, total)
    return ("TAI" if p >= 0.5 else "XIU"), max(p, 1 - p)


def bocpd_predict(seq, threshold=0.6):
    if len(seq) < 10: return "TAI", 0.5
    n = len(seq); seg = seq[-10:]
    p1 = seg.count("TAI") / len(seg)
    prior = seq[:n - 10].count("TAI") / max(1, n - 10)
    if abs(p1 - prior) > threshold:
        if p1 > prior: return "XIU", 0.6
        return "TAI", 0.6
    return ("TAI" if prior >= 0.5 else "XIU"), max(prior, 1 - prior)


def gbs_predict(seq, window=12):
    if len(seq) < window: return "TAI", 0.5
    seg = seq[-window:]; score = 0
    for i in range(1, len(seg)):
        if seg[i] != seg[i - 1]: score += 1
        else: score -= 1
    if score > 0: return seg[-1], 0.58
    return ("XIU" if seg[-1] == "TAI" else "TAI"), 0.58


def afm_predict(seq):
    if not seq: return "TAI", 0.5
    return seq[-1], 0.51


BO_FUNCS = {
    "PPM6": ppm6_predict, "REGIME": regime_predict, "KNNH": knnh_predict,
    "RUNCTX": runctk_predict, "TOTK": totk_predict, "SPARSE": sparse_predict,
    "CAUTPL": cautpl_predict, "FSHARE": fshare_predict, "BLKHAZ": blkhaz_predict,
    "BOCPD": bocpd_predict, "GBS": gbs_predict, "AFM": afm_predict,
}


def weighted_vote(results, weights, decay=0.95, floor=1.0, newest_weight=1.0, flip_weight=False):
    score_tai = 0.0; score_xiu = 0.0
    n = len(results)
    for i, (name, (pred, conf)) in enumerate(results.items()):
        age = n - 1 - i
        w_age = max(floor, decay ** age)
        w_new = newest_weight if i == n - 1 else 1.0
        base_w = weights.get(name, 1.0) * w_age * w_new
        if flip_weight and i == n - 1: base_w *= -1
        w = base_w * conf
        if pred == "TAI": score_tai += w
        elif pred == "XIU": score_xiu += w
    if score_tai == score_xiu: return None, 0.5
    total = score_tai + score_xiu
    if score_tai > score_xiu:
        return "TAI", (score_tai / total if total else 0.5)
    return "XIU", (score_xiu / total if total else 0.5)


def tie_break(seq, logic="PPM6"):
    func = BO_FUNCS.get(logic, ppm6_predict)
    return func(seq)


def consec_check(seq):
    if len(seq) < 3: return None
    last = seq[-1]; run = 1
    for x in reversed(seq[:-1]):
        if x == last: run += 1
        else: break
    if run >= 6: return ("XIU" if last == "TAI" else "TAI")
    return None


def af_filter(seq, pred, conf, config):
    if not config.get("AF_ENABLED", True): return pred, conf
    if len(seq) < config.get("AF_MIN_GAMES", 7): return pred, conf
    conf_pct = conf * 100.0
    low_min = config.get("AF_FLIP_LOW_MIN", 30.0); low_max = config.get("AF_FLIP_LOW_MAX", 45.0)
    high_min = config.get("AF_FLIP_HIGH_MIN", 53.0); high_max = config.get("AF_FLIP_HIGH_MAX", 68.0)
    low_band = low_min <= conf_pct <= low_max
    high_band = high_min <= conf_pct <= high_max
    if not config.get("AF_FLIP_BAND", True):
        low_band = conf_pct <= config.get("AF_FLIP_LOW", 37.0)
        high_band = conf_pct >= config.get("AF_FLIP_HIGH", 63.0)
    should_flip = False
    if low_band and pred == "TAI": should_flip = True
    if high_band and pred == "XIU": should_flip = True
    if config.get("AF_MODE_FLIP", False):
        window = config.get("AF_MODE_WINDOW", 13); min_g = config.get("AF_MODE_MIN", 7)
        below = config.get("AF_MODE_BELOW", 45.0); seg = seq[-window:]
        if len(seg) >= min_g:
            ratio = seg.count("TAI") / len(seg) * 100.0
            if ratio < below and pred == "XIU": should_flip = True
    if should_flip:
        pred = "XIU" if pred == "TAI" else "TAI"
        conf = 1.0 - conf
    return pred, conf


def af_switch(seq, pred, conf, config):
    if not config.get("AF_SWITCH", True): return pred, conf
    need = config.get("AF_SWITCH_NEED", 6)
    if len(seq) < need: return pred, conf
    seg = seq[-need:]; tai = seg.count("TAI"); xiu = seg.count("XIU")
    if tai == xiu: return pred, conf
    lead = "TAI" if tai > xiu else "XIU"
    lead_conf = tai / need if lead == "TAI" else xiu / need
    if config.get("AF_SWITCH_PRIO", True):
        if lead != pred: pred, conf = lead, max(conf, lead_conf)
    else:
        if lead == pred: conf = max(conf, lead_conf)
    return pred, conf


def af_final(pred, conf, config):
    if not config.get("AF_FLIP_FINAL_ALL", False) and not config.get("AF_FLIP_FINAL", False):
        return pred, conf
    conf_pct = conf * 100.0
    if config.get("AF_FLIP_FINAL_ALL", False):
        if pred == "XIU" and config.get("AF_FLIP_FINAL_CAO", True) and conf_pct >= config.get("AF_FLIP_HIGH", 63.0):
            pred, conf = "TAI", 1.0 - conf
        elif pred == "TAI" and config.get("AF_FLIP_FINAL_THAP", False) and conf_pct <= config.get("AF_FLIP_LOW", 37.0):
            pred, conf = "XIU", 1.0 - conf
    return pred, conf


class Predictor:
    def __init__(self, config=None):
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.history = HistoryStore(
            keep=self.config.get("HIST_KEEP", 600),
            persist_keep=self.config.get("PERSIST_KEEP", 300),
        )
        self.bo_logic = ["PPM6", "REGIME", "KNNH", "RUNCTX", "TOTK", "SPARSE",
                         "CAUTPL", "FSHARE", "BLKHAZ", "BOCPD", "GBS", "AFM"]
        self.wr_weights = {name: 1.0 for name in self.bo_logic}
        self.stats = {name: {"hit": 0, "total": 0} for name in self.bo_logic}
        self._last_bo_predictions = {}

    def update_result(self, phien, ket_qua, tong=0, sid=None):
        kq = _norm(ket_qua)
        self.history.append(phien, kq, tong, sid)
        for name, (pred, conf) in self._last_bo_predictions.items():
            if pred == kq:
                self.stats[name]["hit"] += 1
            self.stats[name]["total"] += 1
            total = self.stats[name]["total"]
            hit = self.stats[name]["hit"]
            if total >= self.config.get("WR_MIN_GAMES", 1):
                self.wr_weights[name] = _binomial_smooth(hit, total)
        self._last_bo_predictions = {}

    def predict_next(self):
        seq = self.history.last_results(self.config.get("HIST_KEEP", 600))
        if not seq:
            return {"phien": None, "du_doan": "Tài", "do_tin_cay": 0.5, "chi_tiet": {}}
        results = {}
        for name in self.bo_logic:
            func = BO_FUNCS[name]
            pred, conf = func(seq)
            results[name] = (pred, conf)
        self._last_bo_predictions = dict(results)
        pred, conf = weighted_vote(
            results, self.wr_weights,
            decay=self.config.get("WR_DECAY", 0.95),
            floor=self.config.get("WR_FLOOR", 1.0),
            newest_weight=self.config.get("WR_WEIGHT_NEWEST", 1.0),
            flip_weight=self.config.get("WR_FLIP_WEIGHT", False),
        )
        if pred is None:
            pred, conf = tie_break(seq, self.config.get("TIE_LOGIC", "PPM6"))
        if self.config.get("CONSEC_CHECK", True):
            forced = consec_check(seq)
            if forced is not None:
                pred = forced
                conf = max(conf, 0.6)
        if self.config.get("AF_ENABLED", True):
            pred, conf = af_filter(seq, pred, conf, self.config)
            pred, conf = af_switch(seq, pred, conf, self.config)
            pred, conf = af_final(pred, conf, self.config)
        if self.config.get("FLIP_FINAL", False):
            pred = "XIU" if pred == "TAI" else "TAI"
            conf = 1.0 - conf
        phien = self.history.next_phien()
        if phien is not None:
            self.history.append_prediction(phien, _label(pred))
        return {
            "phien": phien,
            "du_doan": _label(pred),
            "do_tin_cay": round(conf, 4),
            "chi_tiet": {k: {"du_doan": _label(v[0]), "tin_cay": round(v[1], 4)} for k, v in results.items()},
        }

    def get_wr_weights(self):
        return {k: round(v, 4) for k, v in self.wr_weights.items()}

    def get_stats(self):
        out = {}
        for name, s in self.stats.items():
            total = s["total"]; hit = s["hit"]
            out[name] = {
                "hit": hit, "total": total,
                "ty_le": round(_binomial_smooth(hit, total), 4) if total else None,
            }
        return out


# =====================================================================
# V2 SINGLETON + SYNC
# =====================================================================
V2_PREDICTOR = Predictor()
V2_LAST_PHIEN = None


def _reset_v2():
    global V2_PREDICTOR, V2_LAST_PHIEN
    V2_PREDICTOR = Predictor()
    V2_LAST_PHIEN = None


def _sync_v2(valid_sessions):
    """Feed only new sessions into V2 predictor. Auto-reset on phien backwards."""
    global V2_LAST_PHIEN
    if not valid_sessions:
        return V2_PREDICTOR
    # Detect reset triggered from v91 side
    if V2_LAST_PHIEN is not None and valid_sessions[-1]['phien'] < V2_LAST_PHIEN:
        _reset_v2()
    for v in valid_sessions:
        if V2_LAST_PHIEN is not None and v['phien'] <= V2_LAST_PHIEN:
            continue
        if V2_LAST_PHIEN is not None:
            V2_PREDICTOR.predict_next()
        V2_PREDICTOR.update_result(v['phien'], v['result'], v.get('total', 0))
        V2_LAST_PHIEN = v['phien']
    return V2_PREDICTOR


# =====================================================================
# ROUTES — v91 (unchanged)
# =====================================================================
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)


@app.route('/api/history')
def history():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        if not valid:
            base = full_bridge_predict_adaptive_v2([])
            adj = apply_auto_adjust_v2(base['pred'], base['conf'], [], base['regime'], base['detail'])
            return jsonify({'rows': [{
                'phien': RESET_ID + 1, 'is_next': True, 'prediction': adj['pred'],
                'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None,
                'conf': adj['conf'], 'recovery_flipped': adj['flipped'],
                'regime': base['regime'],
            }], 'stats': {'total': 0, 'correct': 0}})
        latest_session = valid[-1]
        next_phien = latest_session['phien'] + 1
        history_for_next = [v['result'] for v in valid][::-1]
        dice_for_next = _extract_dice_sums(valid)[::-1]
        base = full_bridge_predict_adaptive_v2(history_for_next, dice_sums=dice_for_next)
        adj = apply_auto_adjust_v2(base['pred'], base['conf'], valid, base['regime'], base['detail'])
        _store_last_prediction(next_phien, adj['pred'], adj['conf'])
        out = [{
            'phien': next_phien, 'is_next': True,
            'prediction': adj['pred'], 'result': 'Chờ...', 'dice': "? + ? + ?",
            'is_correct': None, 'conf': adj['conf'],
            'recovery_flipped': adj['flipped'], 'flip_reason': adj['reason'],
            'regime': base['regime'],
        }]
        correct_count = 0; total_past = 0
        scan_limit = min(len(valid), 200)
        for i in range(len(valid) - 1, len(valid) - scan_limit - 1, -1):
            if i < 0: break
            current_session = valid[i]
            if current_session['phien'] <= RESET_ID: continue
            pred, conf, is_correct = get_prediction_for(valid, i)
            if is_correct is not None: total_past += 1
            if is_correct: correct_count += 1
            out.append({
                'phien': current_session['phien'], 'is_next': False,
                'prediction': pred, 'result': current_session['result'],
                'dice': current_session['dice'], 'is_correct': is_correct,
                'conf': conf, 'recovery_flipped': False, 'regime': None,
            })
        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        results = [v['result'] for v in valid][::-1] if valid else []
        dice_sums = _extract_dice_sums(valid)[::-1] if valid else []
        base = full_bridge_predict_adaptive_v2(results, dice_sums=dice_sums if dice_sums else None)
        adj = apply_auto_adjust_v2(base['pred'], base['conf'], valid, base['regime'], base['detail'])
        next_phien = (valid[-1]['phien'] + 1) if valid else (RESET_ID + 1)
        if valid: _store_last_prediction(next_phien, adj['pred'], adj['conf'])
        last = valid[-1] if valid else None
        return jsonify({
            'last_phien': last['phien'] if last else None,
            'next_phien': next_phien,
            'last_result': last['result'] if last else None,
            'last_dice': last['dice'] if last else None,
            'prediction': adj['pred'], 'confidence': adj['conf'],
            'base_prediction': base['pred'], 'base_confidence': base['conf'],
            'was_flipped': adj['flipped'], 'flip_reason': adj['reason'],
            'flip_score': adj['score'], 'flip_score_reasons': adj['score_reasons'],
            'flip_decision': 'HARD' if adj['flipped'] and adj['score'] >= 4.0
                            else ('SOFT' if adj['flipped'] else ('PENALTY' if adj['reason'] and adj['reason'].startswith('PENALTY') else 'NONE')),
            'regime': base['regime'], 'regime_info': base['regime_info'],
            'loss_streak': adj['loss_streak'],
            'recent_accuracy': round(adj['recent_acc'] * 100, 1),
            'edge': base['edge'],
            'tai_score': base['tai_score'], 'xiu_score': base['xiu_score'],
            'signal_count': len(base['detail']), 'signals': base['detail'],
            'total_sessions': len(valid),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lc79')
def lc79():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        results = [v['result'] for v in valid][::-1] if valid else []
        dice_sums = _extract_dice_sums(valid)[::-1] if valid else []
        base = full_bridge_predict_adaptive_v2(results, dice_sums=dice_sums if dice_sums else None)
        adj = apply_auto_adjust_v2(base['pred'], base['conf'], valid, base['regime'], base['detail'])
        next_phien = (valid[-1]['phien'] + 1) if valid else (RESET_ID + 1)
        if valid: _store_last_prediction(next_phien, adj['pred'], adj['conf'])
        groups = get_groups(results)
        lich_su = "-" + "-".join(str(g) for g in groups[:4])
        last = valid[-1] if valid else None
        return jsonify({
            'Id': 'le minh v91 - 64P + SmartFlip v2',
            'Phien': str(next_phien),
            'Ket_qua': last['result'].lower() if last else None,
            'Lich_su': lich_su,
            'Du_doan': adj['pred'], 'Do_tin_cay': f"{adj['conf']}%",
            'Base_du_doan': base['pred'], 'Was_flipped': adj['flipped'],
            'Flip_reason': adj['reason'], 'Flip_score': adj['score'],
            'Regime': base['regime'],
            'Chuoi_thua': adj['loss_streak'],
            'Accuracy_25': round(adj['recent_acc'] * 100, 1),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/patterns64')
def patterns64():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        results = [v['result'] for v in valid][::-1] if valid else []
        dice_sums = _extract_dice_sums(valid)[::-1] if valid else []
        prs = analyze_64_patterns(results, dice_sums if dice_sums else None)
        tai = sum(p['weight'] for p in prs if p['matched'] and p['pred'] == 'Tài')
        xiu = sum(p['weight'] for p in prs if p['matched'] and p['pred'] == 'Xỉu')
        total = tai + xiu
        matched_count = sum(1 for p in prs if p['matched'])
        if total > 0:
            if tai > xiu: pred = 'Tài'; ratio = tai / total
            elif xiu > tai: pred = 'Xỉu'; ratio = xiu / total
            else: pred = results[0] if results else 'Tài'; ratio = 0.5
            evidence = min(1.0, total / 150.0)
            conf = int(max(50, min(95, 50 + (ratio - 0.5) * 100 * evidence)))
        else:
            pred = results[0] if results else 'Tài'; ratio = 0.5; conf = 50
        group_summary = defaultdict(lambda: {'tai': 0.0, 'xiu': 0.0, 'matched': 0})
        for p in prs:
            if p['matched']:
                g = p['group']
                if p['pred'] == 'Tài': group_summary[g]['tai'] += p['weight']
                else: group_summary[g]['xiu'] += p['weight']
                group_summary[g]['matched'] += 1
        last = valid[-1] if valid else None
        next_phien = (valid[-1]['phien'] + 1) if valid else (RESET_ID + 1)
        regime, regime_info = detect_regime(results)
        return jsonify({
            'algorithm': 'LE MINH 64-Pattern + SmartFlip v2', 'version': '4.0',
            'next_phien': next_phien, 'last_phien': last['phien'] if last else None,
            'last_result': last['result'] if last else None,
            'prediction': pred, 'confidence': conf,
            'tai_score': round(tai, 2), 'xiu_score': round(xiu, 2),
            'ratio': round(ratio, 3), 'total_matched': matched_count,
            'total_patterns': 64, 'regime': regime, 'regime_info': regime_info,
            'group_summary': {k: dict(v) for k, v in group_summary.items()},
            'patterns': prs, 'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/patterns64/summary')
def patterns64_summary():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        results = [v['result'] for v in valid][::-1] if valid else []
        dice_sums = _extract_dice_sums(valid)[::-1] if valid else []
        prs = analyze_64_patterns(results, dice_sums if dice_sums else None)
        matched = [p for p in prs if p['matched']]
        tai = sum(p['weight'] for p in matched if p['pred'] == 'Tài')
        xiu = sum(p['weight'] for p in matched if p['pred'] == 'Xỉu')
        total = tai + xiu
        pred = 'Tài' if tai > xiu else ('Xỉu' if xiu > tai else (results[0] if results else 'Tài'))
        conf = 50
        if total > 0:
            ratio = max(tai, xiu) / total
            evidence = min(1.0, total / 150.0)
            conf = int(max(50, min(95, 50 + (ratio - 0.5) * 100 * evidence)))
        last = valid[-1] if valid else None
        regime, regime_info = detect_regime(results)
        return jsonify({
            'next_phien': (valid[-1]['phien'] + 1) if valid else (RESET_ID + 1),
            'last_result': last['result'] if last else None,
            'prediction': pred, 'confidence': conf,
            'tai_score': round(tai, 2), 'xiu_score': round(xiu, 2),
            'matched_count': len(matched),
            'regime': regime, 'regime_info': regime_info,
            'matched_patterns': [{'id': p['id'], 'name': p['name'], 'group': p['group'],
                                  'pred': p['pred'], 'weight': p['weight']} for p in matched],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/full')
def full():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        results = [v['result'] for v in valid][::-1] if valid else []
        dice_sums = _extract_dice_sums(valid)[::-1] if valid else []
        base = full_bridge_predict_adaptive_v2(results, dice_sums=dice_sums if dice_sums else None)
        adj = apply_auto_adjust_v2(base['pred'], base['conf'], valid, base['regime'], base['detail'])
        next_phien = (valid[-1]['phien'] + 1) if valid else (RESET_ID + 1)
        if valid: _store_last_prediction(next_phien, adj['pred'], adj['conf'])
        last = valid[-1] if valid else None
        return jsonify({
            'next_phien': next_phien,
            'last_phien': last['phien'] if last else None,
            'last_result': last['result'] if last else None,
            'last_dice': last['dice'] if last else None,
            'prediction': adj['pred'], 'confidence': adj['conf'],
            'base_prediction': base['pred'], 'base_confidence': base['conf'],
            'was_flipped': adj['flipped'],
            'flip_decision': 'HARD' if adj['flipped'] and adj['score'] >= 4.0
                            else ('SOFT' if adj['flipped'] else ('PENALTY' if adj['reason'] and adj['reason'].startswith('PENALTY') else 'NONE')),
            'flip_reason': adj['reason'],
            'flip_score': adj['score'],
            'flip_score_reasons': adj['score_reasons'],
            'regime': base['regime'], 'regime_info': base['regime_info'],
            'loss_streak': adj['loss_streak'],
            'recent_accuracy': round(adj['recent_acc'] * 100, 1),
            'recent_accuracy_samples': 25,
            'edge': base['edge'],
            'tai_score': base['tai_score'], 'xiu_score': base['xiu_score'],
            'signal_count': len(base['detail']), 'signals': base['detail'],
            'total_sessions': len(valid),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/debug/flip')
def debug_flip():
    try:
        valid, success = _sync_history()
        if not success: return jsonify({'error': 'Không thể kết nối API'}), 500
        if len(valid) < 3:
            return jsonify({'error': 'Chưa đủ dữ liệu (cần >=3 phiên)'})
        results = [v['result'] for v in valid][::-1]
        dice = _extract_dice_sums(valid)[::-1]
        base = full_bridge_predict_adaptive_v2(results, dice_sums=dice)
        bet_ctx = _classify_last_bet(valid)
        adj = apply_auto_adjust_v2(base['pred'], base['conf'], valid, base['regime'], base['detail'])
        recent_log = []
        for i in range(max(0, len(valid) - 5), len(valid)):
            p, c, ok = get_prediction_for(valid, i)
            recent_log.append({
                'phien': valid[i]['phien'], 'result': valid[i]['result'],
                'predicted': p, 'conf': c, 'correct': ok,
                'bet_type': 'continue' if (i > 0 and p == valid[i-1]['result'])
                            else ('break' if (i > 0 and p == _opp(valid[i-1]['result'])) else '?'),
            })
        last = valid[-1]
        return jsonify({
            'next_phien': last['phien'] + 1,
            'last_result': last['result'],
            'base_prediction': base['pred'], 'base_confidence': base['conf'],
            'last_bet_context': bet_ctx,
            'loss_streak': adj['loss_streak'],
            'recent_accuracy_25': round(adj['recent_acc'] * 100, 1),
            'final_prediction': adj['pred'], 'final_confidence': adj['conf'],
            'was_flipped': adj['flipped'],
            'flip_decision': 'HARD' if adj['flipped'] and adj['score'] >= 4.0 else ('SOFT' if adj['flipped'] else 'NONE'),
            'flip_score': adj['score'], 'flip_score_reasons': adj['score_reasons'],
            'flip_reason': adj['reason'],
            'regime': base['regime'], 'regime_info': base['regime_info'],
            'recent_log': recent_log,
            'signals': base['detail'],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/sample')
def sample():
    return jsonify({
        'note': 'Static sample responses — không cần live data',
        'samples': {
            '/api/full': {
                'next_phien': 123456, 'last_phien': 123455,
                'last_result': 'Tài', 'last_dice': '4 + 5 + 6',
                'prediction': 'Xỉu', 'confidence': 78,
                'base_prediction': 'Tài', 'base_confidence': 62,
                'was_flipped': True, 'flip_decision': 'SOFT',
                'flip_reason': 'SOFT:s2+bet_fail+regime_bet_break',
                'flip_score': 5.3,
                'flip_score_reasons': ['s2', 'bet_fail', 'regime_bet_break'],
                'regime': 'bet_strong',
                'regime_info': {'cur_streak': 5, 'avg_group_len': 2.4, 'alt_rate': 0.35, 'groups_count': 12},
                'loss_streak': 2, 'recent_accuracy': 58.0, 'recent_accuracy_samples': 25,
                'edge': 0.234, 'signal_count': 9,
                'signals': [{
                    'name': 'bet_3_def', 'pred': 'Xỉu',
                    'base_weight': 9, 'accuracy': 0.62, 'samples': 38,
                    'adjusted_weight': 10.4, 'regime_used': 'bet_strong',
                }],
                'tai_score': 42.1, 'xiu_score': 68.5,
                'total_sessions': 240, 'timestamp': '2025-01-01T12:00:00',
            },
            '/lc79': {
                'Id': 'le minh v91 - 64P + SmartFlip v2',
                'Phien': '123456', 'Ket_qua': 'tài',
                'Lich_su': '-5-3-2-4', 'Du_doan': 'Xỉu',
                'Do_tin_cay': '78%', 'Base_du_doan': 'Tài',
                'Was_flipped': True, 'Flip_reason': 'SOFT:s2+bet_fail+regime_bet_break',
                'Flip_score': 5.3, 'Regime': 'bet_strong',
                'Chuoi_thua': 2, 'Accuracy_25': 58.0,
            },
            '/api/v2/predict': {
                'next_phien': 123456, 'prediction': 'Xỉu', 'confidence': 72.5,
                'bo_details': {
                    'PPM6': {'du_doan': 'Xỉu', 'tin_cay': 0.72},
                    'REGIME': {'du_doan': 'Xỉu', 'tin_cay': 0.61},
                    'KNNH': {'du_doan': 'Tài', 'tin_cay': 0.55},
                },
                'wr_weights': {'PPM6': 0.63, 'REGIME': 0.58, 'KNNH': 0.44},
                'stats': {
                    'PPM6': {'hit': 42, 'total': 60, 'ty_le': 0.701},
                    'REGIME': {'hit': 38, 'total': 60, 'ty_le': 0.635},
                },
                'history_size': 240,
                'timestamp': '2025-01-01T12:00:00',
            },
        },
    })


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE, PREDICTION_CACHE, LAST_PREDICTIONS
    try:
        raw_rows, success = fetch_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                PREDICTION_CACHE = {}
                LAST_PREDICTIONS = {}
                _reset_v2()
                return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys())
            HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
            PREDICTION_CACHE = {}
            LAST_PREDICTIONS = {}
            _reset_v2()
            return jsonify({'status': 'success', 'reset_to': RESET_ID + 1, 'note': 'Offline reset'})
        return jsonify({'status': 'error', 'message': 'Không có kết nối mạng và không có dữ liệu cache'}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# =====================================================================
# ROUTES — V2 (ADDITIVE, new endpoints only)
# =====================================================================
@app.route('/api/v2/predict')
def v2_predict():
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        predictor = _sync_v2(valid)
        result = predictor.predict_next()
        return jsonify({
            'algorithm': 'v2 - 12-BO Ensemble + Adaptive Filter',
            'next_phien': result['phien'],
            'prediction': result['du_doan'],
            'confidence': round(result['do_tin_cay'] * 100, 1),
            'bo_details': result['chi_tiet'],
            'wr_weights': predictor.get_wr_weights(),
            'stats': predictor.get_stats(),
            'history_size': len(predictor.history.data),
            'config': {k: v for k, v in predictor.config.items() if not k.startswith('_')},
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/stats')
def v2_stats():
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        predictor = _sync_v2(valid)
        return jsonify({
            'stats': predictor.get_stats(),
            'wr_weights': predictor.get_wr_weights(),
            'history_size': len(predictor.history.data),
            'last_phien': predictor.history.last_phien(),
            'next_phien': predictor.history.next_phien(),
            'bo_logic': predictor.bo_logic,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/config', methods=['GET', 'POST'])
def v2_config():
    if request.method == 'GET':
        return jsonify({
            'config': V2_PREDICTOR.config,
            'default_config': DEFAULT_CONFIG,
        })
    try:
        data = request.get_json() or {}
        _reset_v2()
        V2_PREDICTOR.config.update(data)
        # Re-sync immediately with new config
        valid, success = _sync_history()
        if success and valid:
            _sync_v2(valid)
        return jsonify({
            'status': 'success',
            'config': V2_PREDICTOR.config,
            'note': 'V2 predictor reset + resynced with new config',
            'history_size': len(V2_PREDICTOR.history.data),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/reset', methods=['POST'])
def v2_reset():
    try:
        _reset_v2()
        return jsonify({'status': 'success', 'note': 'V2 predictor reset (v91 untouched)'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/v2/bo/<name>')
def v2_single_bo(name):
    """Test một BO đơn lẻ — dùng debug."""
    try:
        if name not in BO_FUNCS:
            return jsonify({'error': f'BO "{name}" không tồn tại', 'available': list(BO_FUNCS.keys())}), 404
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API'}), 500
        seq = [_norm(v['result']) for v in valid][::-1]
        pred, conf = BO_FUNCS[name](seq)
        return jsonify({
            'bo': name,
            'prediction': _label(pred),
            'confidence': round(conf * 100, 1),
            'raw': {'pred': pred, 'conf': round(conf, 4)},
            'history_size': len(seq),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
