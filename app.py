import os
import random
import traceback
import time
import json
from datetime import datetime
from collections import Counter, defaultdict, deque
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_URL_MD5 = (
    "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions"
    "?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df"
)

HISTORY_CACHE = {}
RESET_ID = 0

# =====================================================================
# PREDICTION TRACKING — lưu dự đoán và đánh giá đúng/sai
# =====================================================================
PREDICTION_LOG = {}   # {phien: {'prediction': 'Tài'/'Xỉu', 'confidence': int, 'method': str, 'actual': 'Tài'/'Xỉu'/None, 'correct': bool/None}}
MAX_LOG_SIZE = 500

DISCLAIMER = (
    "⚠️ Dự đoán dựa trên phân tích pattern lịch sử. "
    "Xúc xắc là ngẫu nhiên thực sự — không thuật toán nào đảm bảo thắng. "
    "Hãy xem đây là công cụ tham khảo, không phải lời khuyên đầu tư."
)


# =====================================================================
# MULTI-STRATEGY PREDICTOR
# =====================================================================
class MultiStrategyPredictor:
    """
    Kết hợp nhiều chiến lược phân tích pattern.
    Mỗi chiến lược trả về (prediction, confidence 0-100, weight).
    """

    @staticmethod
    def _markov(valid):
        """Markov chain: P(next | last)."""
        if len(valid) < 10:
            return None, 0, 0
        trans = defaultdict(lambda: {'Tài': 0, 'Xỉu': 0})
        for i in range(len(valid) - 1):
            a = valid[i]['result']
            b = valid[i + 1]['result']
            trans[a][b] += 1
        last = valid[-1]['result']
        counts = trans[last]
        total = counts['Tài'] + counts['Xỉu']
        if total < 5:
            return None, 0, 0
        p_tai = counts['Tài'] / total
        if p_tai > 0.55:
            return 'Tài', int(p_tai * 100), 1.2
        elif p_tai < 0.45:
            return 'Xỉu', int((1 - p_tai) * 100), 1.2
        return None, 0, 0

    @staticmethod
    def _streak_break(valid):
        """Nếu streak >= 3, dự đoán bẻ streak (mean reversion)."""
        if len(valid) < 4:
            return None, 0, 0
        last = valid[-1]['result']
        streak = 1
        for i in range(len(valid) - 2, -1, -1):
            if valid[i]['result'] == last:
                streak += 1
            else:
                break
        if streak >= 4:
            opp = 'Xỉu' if last == 'Tài' else 'Tài'
            return opp, min(50 + streak * 8, 75), 1.0
        return None, 0, 0

    @staticmethod
    def _pattern_match(valid):
        """Tìm mẫu 3-5 phiên cuối trong lịch sử, xem phiên tiếp theo là gì."""
        if len(valid) < 20:
            return None, 0, 0
        results = [v['result'] for v in valid]
        best_hit = None
        best_confidence = 0
        for plen in (5, 4, 3):
            if len(results) < plen + 5:
                continue
            pattern = tuple(results[-plen:])
            matches = []
            for i in range(len(results) - plen):
                if tuple(results[i:i + plen]) == pattern:
                    if i + plen < len(results):
                        matches.append(results[i + plen])
            if len(matches) >= 3:
                c = Counter(matches)
                top, count = c.most_common(1)[0]
                conf = int(count / len(matches) * 100)
                if conf > best_confidence and conf >= 55:
                    best_hit = top
                    best_confidence = conf
        if best_hit:
            return best_hit, best_confidence, 1.5
        return None, 0, 0

    @staticmethod
    def _weighted_freq(valid, window=30):
        """Tần suất có trọng số: phiên gần đây quan trọng hơn."""
        recent = valid[-window:]
        if len(recent) < 10:
            return None, 0, 0
        tai_score = 0
        xiu_score = 0
        for i, v in enumerate(recent):
            w = (i + 1) / len(recent)
            if v['result'] == 'Tài':
                tai_score += w
            else:
                xiu_score += w
        total = tai_score + xiu_score
        if total == 0:
            return None, 0, 0
        p_tai = tai_score / total
        if p_tai > 0.58:
            return 'Tài', int(p_tai * 100), 0.8
        elif p_tai < 0.42:
            return 'Xỉu', int((1 - p_tai) * 100), 0.8
        return None, 0, 0

    @staticmethod
    def _dice_sum_bias(valid, window=50):
        """Phân tích phân bố tổng điểm gần đây (nếu Tài/Xỉu lệch)."""
        recent = [v for v in valid[-window:] if v.get('total')]
        if len(recent) < 15:
            return None, 0, 0
        tais = sum(1 for v in recent if v['result'] == 'Tài')
        ratio = tais / len(recent)
        # Không dùng để dự đoán hướng đi tiếp, nhưng nếu lệch mạnh → mean reversion
        if ratio > 0.62:
            return 'Xỉu', int(ratio * 100), 0.6
        elif ratio < 0.38:
            return 'Tài', int((1 - ratio) * 100), 0.6
        return None, 0, 0

    @classmethod
    def predict(cls, valid):
        """Ensemble voting từ tất cả chiến lược."""
        if len(valid) < 5:
            # Không đủ dữ liệu → ngẫu nhiên có ghi chú
            pick = random.choice(['Tài', 'Xỉu'])
            return {
                'prediction': pick,
                'confidence': 50,
                'method': 'random',
                'signals': [],
                'reason': 'Chưa đủ dữ liệu — dự đoán ngẫu nhiên',
            }

        strategies = [
            ('markov', cls._markov(valid)),
            ('streak_break', cls._streak_break(valid)),
            ('pattern_match', cls._pattern_match(valid)),
            ('weighted_freq', cls._weighted_freq(valid)),
            ('dice_bias', cls._dice_sum_bias(valid)),
        ]

        tai_score = 0.0
        xiu_score = 0.0
        signals = []
        for name, (pred, conf, weight) in strategies:
            if pred is None or weight == 0:
                continue
            score = (conf / 100.0) * weight
            if pred == 'Tài':
                tai_score += score
            else:
                xiu_score += score
            signals.append({
                'name': name,
                'prediction': pred,
                'confidence': conf,
                'weight': weight,
            })

        if tai_score == 0 and xiu_score == 0:
            pick = random.choice(['Tài', 'Xỉu'])
            return {
                'prediction': pick,
                'confidence': 50,
                'method': 'random',
                'signals': [],
                'reason': 'Không có tín hiệu rõ ràng — dự đoán ngẫu nhiên',
            }

        if tai_score > xiu_score:
            pred = 'Tài'
            total = tai_score + xiu_score
            conf = int((tai_score / total) * 100)
        else:
            pred = 'Xỉu'
            total = tai_score + xiu_score
            conf = int((xiu_score / total) * 100)

        method = '+'.join(s['name'] for s in signals)
        reason = f"Kết hợp {len(signals)} tín hiệu: " + ", ".join(
            f"{s['name']}({s['prediction']}@{s['confidence']}%)" for s in signals
        )

        return {
            'prediction': pred,
            'confidence': conf,
            'method': method or 'ensemble',
            'signals': signals,
            'reason': reason,
        }


# =====================================================================
# DATA FETCHER
# =====================================================================
def fetch_sessions():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
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
                        rows.append({
                            'phien': int(item['id']),
                            'result': res,
                            'dice': dice_str,
                            'total': total,
                        })
                    return rows, True
        except Exception as e:
            print(f"[API ERROR] Lần {attempt + 1}: {e}")
            time.sleep(1)
    return [], False


def _sync_history():
    raw_rows, success = fetch_sessions()
    if not success and not HISTORY_CACHE:
        return [], False
    for row in raw_rows:
        HISTORY_CACHE[row['phien']] = row
    if RESET_ID > 0:
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
            del HISTORY_CACHE[k]
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    _update_prediction_log(valid)
    return valid, True


def _update_prediction_log(valid):
    """Cập nhật log dự đoán: đánh giá đúng/sai khi có kết quả thực."""
    if not valid:
        return
    by_phien = {v['phien']: v for v in valid}
    for phien, entry in list(PREDICTION_LOG.items()):
        if entry.get('actual') is not None:
            continue
        if phien in by_phien:
            actual = by_phien[phien]['result']
            entry['actual'] = actual
            entry['correct'] = (entry['prediction'] == actual)
    # Giới hạn kích thước
    if len(PREDICTION_LOG) > MAX_LOG_SIZE:
        keys = sorted(PREDICTION_LOG.keys())[:len(PREDICTION_LOG) - MAX_LOG_SIZE]
        for k in keys:
            del PREDICTION_LOG[k]


def _log_prediction(phien, pred_result):
    """Ghi nhận dự đoán cho phiên tới."""
    if phien in PREDICTION_LOG and PREDICTION_LOG[phien].get('prediction') == pred_result['prediction']:
        return  # Đã log cùng dự đoán
    PREDICTION_LOG[phien] = {
        'prediction': pred_result['prediction'],
        'confidence': pred_result['confidence'],
        'method': pred_result['method'],
        'reason': pred_result['reason'],
        'signals': pred_result['signals'],
        'actual': None,
        'correct': None,
        'logged_at': datetime.now().isoformat(),
    }


def _log_stats():
    """Thống kê đúng/sai của thuật toán."""
    total = len(PREDICTION_LOG)
    evaluated = [e for e in PREDICTION_LOG.values() if e.get('actual') is not None]
    correct = sum(1 for e in evaluated if e.get('correct'))
    wrong = len(evaluated) - correct
    winrate = round(correct / len(evaluated) * 100, 1) if evaluated else 0

    # Streak hiện tại
    streak = 0
    streak_type = None
    sorted_evals = sorted(
        [e for e in evaluated if e.get('logged_at')],
        key=lambda x: x.get('logged_at', ''),
        reverse=True,
    )
    for e in sorted_evals:
        if streak == 0:
            streak = 1
            streak_type = e['correct']
        elif e['correct'] == streak_type:
            streak += 1
        else:
            break

    # Winrate 20 gần nhất
    last20 = [e for e in sorted_evals[:20] if e.get('correct') is not None]
    winrate20 = round(sum(1 for e in last20 if e['correct']) / len(last20) * 100, 1) if last20 else 0

    return {
        'total_predictions': total,
        'evaluated': len(evaluated),
        'correct': correct,
        'wrong': wrong,
        'winrate': winrate,
        'winrate_last20': winrate20,
        'current_streak': streak,
        'streak_type': 'win' if streak_type else None,
    }


def _honest_stats(valid):
    total = len(valid)
    tai = sum(1 for v in valid if v['result'] == 'Tài')
    xiu = total - tai
    return {
        'total': total,
        'tai': tai,
        'xiu': xiu,
        'ratio_tai': round(tai / total, 3) if total else 0,
    }


# =====================================================================
# HTML — UI gọn
# =====================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 — AI Predictor</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
:root{--bg:#0f172a;--card:#1e293b;--card2:#111827;--text:#f8fafc;--muted:#94a3b8;--border:#334155;--tai:#38bdf8;--xiu:#f472b6;--ok:#22c55e;--fail:#ef4444;--warn:#fbbf24}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Plus Jakarta Sans',sans-serif}
body{background:linear-gradient(135deg,#0f172a,#1e1b4b);color:var(--text);min-height:100vh;padding-bottom:30px;font-size:13px}
.header{background:rgba(30,41,59,.9);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:12px 16px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
.logo{font-size:16px;font-weight:800;color:var(--tai);display:flex;align-items:center;gap:8px}
.logo span{font-size:9px;background:#334155;color:#cbd5e1;padding:3px 8px;border-radius:20px;font-weight:800;letter-spacing:.5px}
.actions{display:flex;gap:8px;align-items:center}
.clock{font-size:11px;color:var(--muted);font-weight:600}
.btn{background:var(--card);color:var(--text);border:1px solid var(--border);padding:7px 12px;border-radius:9px;font-weight:700;font-size:12px;cursor:pointer}
.btn-reset{background:rgba(248,113,113,.15);color:#f87171;border-color:rgba(248,113,113,.4)}

.wrap{max-width:760px;margin:0 auto;padding:0 12px}
.disc{margin:12px 0;padding:10px 14px;background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.25);border-radius:10px;color:var(--warn);font-size:11px;line-height:1.5}

/* Prediction hero */
.hero{margin:12px 0;background:linear-gradient(135deg,rgba(56,189,248,.12),rgba(244,114,182,.12));border:1px solid var(--border);border-radius:14px;padding:16px;text-align:center}
.hero-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px}
.hero-pred{font-size:36px;font-weight:800;letter-spacing:1px;margin:4px 0}
.hero-pred.tai{color:var(--tai)}.hero-pred.xiu{color:var(--xiu)}
.hero-conf{font-size:12px;color:var(--muted);font-weight:600}
.hero-reason{font-size:10px;color:var(--muted);margin-top:8px;font-style:italic;line-height:1.4;opacity:.85}
.hero-phien{font-size:11px;color:var(--muted);margin-top:4px}

/* Stats row */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0}
.stat{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:10px 6px;text-align:center}
.stat-l{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:700;margin-bottom:3px;letter-spacing:.5px}
.stat-v{font-size:16px;font-weight:800}
.stat-v.tai{color:var(--tai)}.stat-v.xiu{color:var(--xiu)}.stat-v.ok{color:var(--ok)}.stat-v.fail{color:var(--fail)}

/* Table */
.tbl{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;max-height:62vh;overflow-y:auto}
table{width:100%;border-collapse:separate;border-spacing:0}
th{background:var(--card2);color:var(--muted);font-size:10px;font-weight:700;padding:10px 6px;text-align:center;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10;text-transform:uppercase}
td{padding:9px 6px;text-align:center;border-bottom:1px solid var(--border);font-size:12px;font-weight:600}
.row-next{background:rgba(56,189,248,.08);border-left:3px solid var(--tai)}
.badge{display:inline-block;padding:3px 9px;border-radius:14px;font-size:10px;font-weight:800;min-width:52px;text-align:center}
.b-tai{background:rgba(56,189,248,.18);color:var(--tai);border:1px solid rgba(56,189,248,.3)}
.b-xiu{background:rgba(244,114,182,.18);color:var(--xiu);border:1px solid rgba(244,114,182,.3)}
.b-ok{background:rgba(34,197,94,.18);color:var(--ok);border:1px solid rgba(34,197,94,.3);font-size:9px;padding:2px 7px}
.b-fail{background:rgba(239,68,68,.18);color:var(--fail);border:1px solid rgba(239,68,68,.3);font-size:9px;padding:2px 7px}
.b-pending{background:rgba(251,191,36,.18);color:var(--warn);border:1px solid rgba(251,191,36,.3);font-size:9px;padding:2px 7px}
.b-none{background:rgba(255,255,255,.05);color:var(--muted)}
.dice{font-size:10px;color:var(--muted);display:block;margin-top:2px}
.loading{text-align:center;padding:30px;color:var(--tai);font-weight:600}
.pred-cell{display:flex;flex-direction:column;gap:2px;align-items:center}
.pred-small{font-size:10px;font-weight:800}
.pred-small.tai{color:var(--tai)}.pred-small.xiu{color:var(--xiu)}
@media(max-width:520px){
  .stats{grid-template-columns:repeat(2,1fr)}
  th,td{padding:7px 4px;font-size:11px}
  .hero-pred{font-size:30px}
  .clock{display:none}
  .badge{min-width:44px;font-size:9px}
}
</style>
</head>
<body>
<div class="header">
    <div class="logo">LE MINH <span>AI v4</span></div>
    <div class="actions">
        <div class="clock" id="clock">--:--:--</div>
        <button class="btn" onclick="fetchData()">↻</button>
        <button class="btn btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>

<div class="wrap">
    <div class="disc" id="disc">Đang tải...</div>

    <!-- Prediction hero -->
    <div class="hero" id="hero">
        <div class="hero-label">🎯 Dự đoán phiên tới</div>
        <div class="hero-pred" id="hero-pred">...</div>
        <div class="hero-conf" id="hero-conf">Độ tin cậy: --</div>
        <div class="hero-phien" id="hero-phien">Phiên #--</div>
        <div class="hero-reason" id="hero-reason"></div>
    </div>

    <!-- Stats: tổng quan + thuật toán -->
    <div class="stats">
        <div class="stat"><div class="stat-l">Tổng phiên</div><div class="stat-v" id="s-total">0</div></div>
        <div class="stat"><div class="stat-l">Tài / Xỉu</div><div class="stat-v"><span class="tai" id="s-tai">0</span> <span style="color:var(--muted)">/</span> <span class="xiu" id="s-xiu">0</span></div></div>
        <div class="stat"><div class="stat-l">AI đúng / tổng</div><div class="stat-v"><span class="ok" id="s-correct">0</span> <span style="color:var(--muted)">/</span> <span id="s-eval">0</span></div></div>
        <div class="stat"><div class="stat-l">Winrate AI</div><div class="stat-v ok" id="s-winrate">0%</div></div>
    </div>

    <div class="tbl">
        <table>
            <thead><tr><th>Phiên</th><th>Kết quả</th><th>Dự đoán AI</th><th>Đúng/Sai</th></tr></thead>
            <tbody id="tbody"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody>
        </table>
    </div>
</div>

<script>
let isResetting = false;

async function fetchData(){
    if(isResetting) return;
    try{
        const r = await fetch('/api/history', {cache:'no-store'});
        const data = await r.json();
        document.getElementById('clock').innerText = new Date().toLocaleTimeString('vi-VN');
        document.getElementById('disc').innerText = data.disclaimer || '';
        renderHero(data.prediction);
        renderStats(data.stats, data.ai_stats);
        renderTable(data.rows || []);
    }catch(e){ console.error(e); }
}

function renderHero(p){
    const el = document.getElementById('hero-pred');
    if(!p){ el.innerText='...'; return; }
    el.innerText = p.prediction || '...';
    el.className = 'hero-pred ' + (p.prediction === 'Tài' ? 'tai' : 'xiu');
    document.getElementById('hero-conf').innerText = `Độ tin cậy: ${p.confidence || 0}% · PP: ${p.method || '--'}`;
    document.getElementById('hero-phien').innerText = `Phiên #${p.phien || '--'}`;
    document.getElementById('hero-reason').innerText = p.reason || '';
}

function renderStats(stats, ai){
    document.getElementById('s-total').innerText = stats.total || 0;
    document.getElementById('s-tai').innerText = stats.tai || 0;
    document.getElementById('s-xiu').innerText = stats.xiu || 0;
    if(ai){
        document.getElementById('s-correct').innerText = ai.correct || 0;
        document.getElementById('s-eval').innerText = ai.evaluated || 0;
        const wr = ai.winrate || 0;
        const el = document.getElementById('s-winrate');
        el.innerText = wr + '%';
        el.className = 'stat-v ' + (wr >= 55 ? 'ok' : wr >= 45 ? '' : 'fail');
    }
}

function renderTable(rows){
    const tb = document.getElementById('tbody');
    if(!rows.length){ tb.innerHTML = '<tr><td colspan="4" class="loading">Chưa có dữ liệu.</td></tr>'; return; }
    let html = '';
    rows.forEach(row => {
        const trCls = row.is_next ? 'class="row-next"' : '';
        let rh = '<span class="badge b-none">—</span>';
        if(row.result === 'Tài') rh = '<span class="badge b-tai">TÀI</span>';
        if(row.result === 'Xỉu') rh = '<span class="badge b-xiu">XỈU</span>';

        let dice = '';
        if(row.dice && row.dice !== '? + ? + ?') dice = `<span class="dice">${row.dice} · ${row.total}</span>`;

        // Dự đoán AI cho phiên này
        let predCell = '<span class="badge b-none">—</span>';
        if(row.ai_prediction){
            const cls = row.ai_prediction === 'Tài' ? 'tai' : 'xiu';
            predCell = `<div class="pred-cell"><span class="pred-small ${cls}">${row.ai_prediction}</span><span style="font-size:9px;color:var(--muted)">${row.ai_confidence||0}%</span></div>`;
        }

        // Đúng/Sai
        let evalCell = '<span class="badge b-none">—</span>';
        if(row.ai_correct === true) evalCell = '<span class="badge b-ok">✓ ĐÚNG</span>';
        else if(row.ai_correct === false) evalCell = '<span class="badge b-fail">✗ SAI</span>';
        else if(row.ai_prediction && row.ai_correct === null) evalCell = '<span class="badge b-pending">⏳</span>';

        html += `<tr ${trCls}>
            <td>#${row.phien}${row.is_next ? '<br><span style="font-size:9px;color:var(--tai)">NEXT</span>' : ''}</td>
            <td>${rh}${dice}</td>
            <td>${predCell}</td>
            <td>${evalCell}</td>
        </tr>`;
    });
    tb.innerHTML = html;
}

async function confirmReset(){
    Swal.fire({
        title:'Reset?', text:'Xoá toàn bộ cache và log dự đoán?', icon:'warning',
        background:'#1e293b', color:'#f8fafc', showCancelButton:true,
        confirmButtonColor:'#0ea5e9', cancelButtonColor:'#64748b',
        confirmButtonText:'Đồng ý', cancelButtonText:'Hủy'
    }).then(async r => {
        if(!r.isConfirmed) return;
        isResetting = true;
        try{
            const res = await fetch('/api/reset', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
            const d = await res.json();
            isResetting = false;
            if(d.status === 'success'){
                fetchData();
                Swal.fire({title:'OK!', text:'Đã reset.', icon:'success', background:'#1e293b', color:'#f8fafc', confirmButtonColor:'#0ea5e9'});
            } else throw new Error(d.message || 'Lỗi');
        }catch(e){
            isResetting = false;
            Swal.fire({title:'Lỗi!', text:e.message, icon:'error', background:'#1e293b', color:'#f8fafc'});
        }
    });
}

fetchData();
setInterval(fetchData, 5000);
</script>
</body>
</html>"""


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
            return jsonify({'error': 'Không thể kết nối API', 'disclaimer': DISCLAIMER}), 500

        if not valid:
            return jsonify({
                'disclaimer': DISCLAIMER,
                'rows': [],
                'stats': {'total': 0, 'tai': 0, 'xiu': 0},
                'ai_stats': _log_stats(),
                'prediction': None,
            })

        next_phien = valid[-1]['phien'] + 1

        # Dự đoán cho phiên tới
        pred = MultiStrategyPredictor.predict(valid)
        _log_prediction(next_phien, pred)

        stats = _honest_stats(valid)
        ai_stats = _log_stats()

        out = [{
            'phien': next_phien,
            'is_next': True,
            'result': 'Chờ...',
            'dice': '? + ? + ?',
            'total': None,
            'ai_prediction': pred['prediction'],
            'ai_confidence': pred['confidence'],
            'ai_correct': None,
        }]

        for v in reversed(valid[-200:]):
            if v['phien'] <= RESET_ID:
                continue
            log = PREDICTION_LOG.get(v['phien'])
            out.append({
                'phien': v['phien'],
                'is_next': False,
                'result': v['result'],
                'dice': v['dice'],
                'total': v['total'],
                'ai_prediction': log['prediction'] if log else None,
                'ai_confidence': log['confidence'] if log else None,
                'ai_correct': log['correct'] if log else None,
            })

        return jsonify({
            'disclaimer': DISCLAIMER,
            'rows': out,
            'stats': stats,
            'ai_stats': ai_stats,
            'prediction': {
                'phien': next_phien,
                'prediction': pred['prediction'],
                'confidence': pred['confidence'],
                'method': pred['method'],
                'reason': pred['reason'],
                'signals': pred['signals'],
            },
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict():
    """Dự đoán chi tiết với đầy đủ tín hiệu + thống kê đúng/sai."""
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API', 'disclaimer': DISCLAIMER}), 500

        if not valid:
            return jsonify({
                'disclaimer': DISCLAIMER,
                'prediction': None,
                'ai_stats': _log_stats(),
            })

        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats()

        return jsonify({
            'disclaimer': DISCLAIMER,
            'last_phien': last['phien'],
            'next_phien': next_phien,
            'last_result': last['result'],
            'last_dice': last['dice'],
            'last_total': last['total'],

            'prediction': pred['prediction'],
            'confidence': pred['confidence'],
            'method': pred['method'],
            'reason': pred['reason'],
            'signals': pred['signals'],

            'stats': stats,
            'ai_stats': ai_stats,
            'total_sessions': len(valid),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lc79')
def lc79():
    """Endpoint gọn cho tích hợp ngoài."""
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API', 'disclaimer': DISCLAIMER}), 500

        if not valid:
            return jsonify({'Id': 'le minh ai', 'Phien': None, 'Du_doan': None, 'Disclaimer': DISCLAIMER})

        last = valid[-1]
        next_phien = last['phien'] + 1
        pred = MultiStrategyPredictor.predict(valid)
        _log_prediction(next_phien, pred)
        stats = _honest_stats(valid)
        ai_stats = _log_stats()

        return jsonify({
            'Id': 'le minh ai v4',
            'Phien': str(next_phien),
            'Ket_qua_truoc': last['result'].lower(),
            'Du_doan': pred['prediction'],
            'Do_tin_cay': f"{pred['confidence']}%",
            'Phuong_phap': pred['method'],
            'Ly_do': pred['reason'],
            'Tong_phien': stats['total'],
            'So_Tai': stats['tai'],
            'So_Xiu': stats['xiu'],
            'Ty_le_Tai': f"{stats['ratio_tai']*100:.1f}%",
            'AI_dung': ai_stats['correct'],
            'AI_da_danh_gia': ai_stats['evaluated'],
            'AI_winrate': f"{ai_stats['winrate']}%",
            'AI_streak': ai_stats['current_streak'],
            'Disclaimer': DISCLAIMER,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def stats_only():
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API', 'disclaimer': DISCLAIMER}), 500
        stats = _honest_stats(valid)
        ai_stats = _log_stats()
        last = valid[-1] if valid else None
        return jsonify({
            'disclaimer': DISCLAIMER,
            'stats': stats,
            'ai_stats': ai_stats,
            'last_result': last['result'] if last else None,
            'last_phien': last['phien'] if last else None,
            'last_dice': last['dice'] if last else None,
            'total_sessions': len(valid),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/prediction_log')
def prediction_log():
    """Xem log đầy đủ các dự đoán để tự kiểm chứng."""
    try:
        _sync_history()  # cập nhật
        items = sorted(PREDICTION_LOG.items(), key=lambda x: x[0], reverse=True)[:100]
        out = []
        for phien, entry in items:
            out.append({
                'phien': phien,
                'prediction': entry['prediction'],
                'confidence': entry['confidence'],
                'method': entry['method'],
                'actual': entry.get('actual'),
                'correct': entry.get('correct'),
                'logged_at': entry.get('logged_at'),
            })
        return jsonify({
            'disclaimer': DISCLAIMER,
            'stats': _log_stats(),
            'predictions': out,
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
                PREDICTION_LOG = {}
                return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys())
            HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
            PREDICTION_LOG = {}
            return jsonify({'status': 'success', 'reset_to': RESET_ID + 1, 'note': 'Offline reset'})
        return jsonify({'status': 'error', 'message': 'Không có dữ liệu để reset'}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
