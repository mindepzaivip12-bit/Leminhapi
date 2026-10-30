import os
import time
from datetime import datetime
import requests
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ✅ API TX MỚI (thay cho MD5 cũ)
API_URL = "https://wtx.tele68.com/v1/tx/lite-sessions?cp=R&cl=R&pf=web&at=6471f10890f9f8702ad1ac579f8566c7"
RESET_SESSION_ID = 0

ALL_81_PATTERNS = {}
for _i in range(81):
    _sig = ''
    _temp = _i
    for _ in range(4):
        _sig = 'SML'[_temp % 3] + _sig
        _temp //= 3
    ALL_81_PATTERNS[_i] = _sig

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API LC TX MINHLE</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-dark: #060913; --bg-card: #0d1424; --bg-card-hover: #131c30;
        --text-main: #f1f5f9; --text-muted: #64748b; --border-color: #1e293b;
        --tai-bg: #0284c7; --tai-bet-bg: rgba(2, 132, 199, 0.15);
        --xiu-bg: #db2777; --xiu-bet-bg: rgba(219, 39, 119, 0.15);
        --blue-main: #38bdf8; --blue-glow: rgba(56, 189, 248, 0.5);
        --lose-color: #ef4444; --win-color: #38bdf8;
        --gold: #fbbf24;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
    @keyframes slideIn { from { opacity: 0; transform: translateY(20px) scale(0.96); } to { opacity: 1; transform: translateY(0) scale(1); } }
    @keyframes rainbow-border { 0% { border-color: #38bdf8; } 50% { border-color: #f472b6; } 100% { border-color: #38bdf8; } }
    @keyframes dotPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    
    body { background-color: var(--bg-dark); color: var(--text-main); padding-bottom: 30px; min-height: 100vh; background-image: radial-gradient(circle at 50% 0%, #0c1a32 0%, transparent 60%); }
    .header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; border-bottom: 1px solid var(--border-color); background: rgba(6, 9, 19, 0.85); position: sticky; top: 0; z-index: 100; }
    .header-title { font-size: 20px; font-weight: 900; color: var(--blue-main); }
    .btn-reset { background: rgba(239, 68, 68, 0.1); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 8px 16px; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; }
    
    .stats-bar { max-width: 600px; margin: 15px auto 0; padding: 0 15px; display: flex; gap: 10px; }
    .stat-item { flex: 1; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px; text-align: center; }
    .stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; }
    .stat-value { font-size: 20px; font-weight: 900; color: var(--text-main); }
    
    .container { padding: 15px; display: flex; flex-direction: column; gap: 12px; max-width: 600px; margin: 0 auto; }
    .card-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 16px; display: flex; justify-content: space-between; align-items: center; animation: slideIn 0.3s ease-out; }
    .card-item.active { border: 1.5px solid var(--blue-main); animation: rainbow-border 3s linear infinite; }
    
    .col-left { display: flex; flex-direction: column; gap: 5px; flex: 1.2; }
    .id-text { font-size: 16px; font-weight: 800; color: #fff; }
    .bot-line { display: flex; align-items: center; gap: 8px; font-size: 12px; }
    .bet-badge { padding: 3px 10px; border-radius: 20px; font-weight: 700; font-size: 11px; }
    .bet-tai { background: var(--tai-bet-bg); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); }
    .bet-xiu { background: var(--xiu-bet-bg); color: #f472b6; border: 1px solid rgba(244,114,182,0.3); }
    
    .col-mid { display: flex; flex-direction: column; align-items: center; gap: 5px; flex: 1; }
    .pred-badge { padding: 5px 14px; border-radius: 20px; font-weight: 800; font-size: 13px; text-transform: uppercase; }
    .pred-tai { background: var(--tai-bg); color: #fff; }
    .pred-xiu { background: var(--xiu-bg); color: #fff; }
    .dice-text { font-size: 13px; font-weight: 600; color: #cbd5e1; }
    
    .col-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: center; flex: 0.8; gap: 3px; }
    .status-win { color: var(--win-color); font-weight: 700; font-size: 13px; }
    .status-lose { color: var(--lose-color); font-weight: 700; font-size: 13px; }
    .status-wait { color: var(--blue-main); font-weight: 700; font-size: 13px; }
    
    .pattern-tag { font-size: 10px; color: var(--text-muted); padding: 2px 8px; border-radius: 10px; background: rgba(56,189,248,0.08); display: inline-block; margin-top: 2px; }
    .pattern-tag.m81 { color: var(--gold); background: rgba(251,191,36,0.08); }
    .loading { text-align: center; padding: 50px; color: var(--blue-main); font-weight: 600; }
    .error-box { text-align: center; padding: 20px; color: #ef4444; background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; border-radius: 10px; margin: 20px auto; max-width: 500px; font-weight: 600; }
</style>
</head>
<body>
<div class="header">
    <div class="header-title">⚡ LC TX MINHLE</div>
    <button class="btn-reset" onclick="confirmReset()">↻ Reset</button>
</div>
<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng phiên</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Thắng</div><div class="stat-value" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ</div><div class="stat-value" id="stat-rate">0%</div></div>
</div>
<div class="container" id="list-container">
    <div class="loading">Đang kết nối Server...</div>
</div>
<script>
let isResetting = false;
async function fetchData() {
    if (isResetting) return;
    try {
        const r = await fetch('/api/history', { cache: 'no-store' });
        const data = await r.json();
        
        if (data.error) {
            document.getElementById('list-container').innerHTML = `<div class="error-box">⚠️ LỖI API:<br><br>${data.error}</div>`;
            return;
        }
        
        const rows = data.rows || [];
        const stats = data.stats || {};
        
        document.getElementById('stat-total').innerText = stats.total || 0;
        document.getElementById('stat-win').innerText = stats.correct || 0;
        document.getElementById('stat-rate').innerText = stats.total > 0 ? Math.round((stats.correct / stats.total) * 100) + '%' : '0%';
        
        if (!rows.length) {
            document.getElementById('list-container').innerHTML = '<div class="loading">Không có dữ liệu.</div>';
            return;
        }
        
        const container = document.getElementById('list-container');
        container.innerHTML = '';
        
        rows.forEach((row, idx) => {
            const div = document.createElement('div');
            div.className = 'card-item' + (row.is_next ? ' active' : '');
            
            let predBadge = row.prediction === "Tài" ? `<span class="pred-badge pred-tai">TÀI</span>` : `<span class="pred-badge pred-xiu">XỈU</span>`;
            let betBadge = row.prediction === "Tài" ? `<span class="bet-badge bet-tai">cược tài</span>` : `<span class="bet-badge bet-xiu">cược xỉu</span>`;
            let resultBadge = row.result === "Tài" ? `<span class="pred-badge pred-tai">TÀI</span>` : (row.result === "Xỉu" ? `<span class="pred-badge pred-xiu">XỈU</span>` : `<span class="pred-badge" style="border: 1px dashed #64748b; color: #64748b;">-</span>`);
            
            let statusHtml = row.is_next ? `<div class="status-wait">Chờ ⏳</div>` : (row.is_correct === true ? `<div class="status-win">Đúng ✅</div>` : (row.is_correct === false ? `<div class="status-lose">Sai ❌</div>` : `<div style="color:#64748b">-</div>`));
            
            const patternTag = row.pattern ? `<span class="pattern-tag ${row.pattern.includes('Mẫu') ? 'm81' : ''}">${row.pattern}</span>` : '';
            
            div.innerHTML = `
                <div class="col-left">
                    <div class="id-text">#${row.phien}</div>
                    <div class="bot-line"><span style="color:#64748b">Bot:</span> ${betBadge}</div>
                    <div style="font-size:11px; color:#64748b">Độ tin cậy: ${row.confidence}%</div>
                    ${patternTag}
                </div>
                <div class="col-mid">
                    ${row.is_next ? predBadge : resultBadge}
                    <div class="dice-text">${row.dice}</div>
                </div>
                <div class="col-right">${statusHtml}</div>
            `;
            container.appendChild(div);
        });
    } catch (e) {
        document.getElementById('list-container').innerHTML = '<div class="error-box">Lỗi kết nối đến Server!</div>';
    }
}
async function confirmReset() {
    if(confirm("Bạn có chắc muốn reset?")) {
        isResetting = true;
        await fetch('/api/reset', { method: 'POST' });
        isResetting = false; 
        fetchData();
    }
}
fetchData(); setInterval(fetchData, 5000);
</script>
</body>
</html>
"""

def build_blocks(results):
    if not results: return []
    blocks = []
    curr_val = results[0]
    curr_count = 1
    for r in results[1:]:
        if r == curr_val: curr_count += 1
        else:
            blocks.append({'val': curr_val, 'len': curr_count})
            curr_val = r
            curr_count = 1
    blocks.append({'val': curr_val, 'len': curr_count})
    return blocks

def block_class(L):
    if L == 1: return 'S'
    if L <= 3: return 'M'
    return 'L'

def encode_pattern_81(block_lengths):
    if len(block_lengths) < 4: return None
    code = 0
    for L in block_lengths[-4:]:
        code = code * 3 + {'S': 0, 'M': 1, 'L': 2}[block_class(L)]
    return code

def pattern_signature(block_lengths):
    if len(block_lengths) < 4: return "----"
    return ''.join(block_class(L) for L in block_lengths[-4:])

def learn_81_patterns(results):
    stats = {}
    n = len(results)
    for k in range(10, n):
        sub = results[k:]
        blocks = build_blocks(sub)
        if len(blocks) < 5: continue
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        if code is None: continue
        current_val = blocks[0]['val']
        current_len = blocks[0]['len']
        actual_next = results[k - 1]
        continued = (actual_next == current_val)
        
        key1 = (code, min(current_len, 4))
        if key1 not in stats: stats[key1] = {'continue': 0, 'break': 0}
        stats[key1]['continue' if continued else 'break'] += 1
        
        key2 = code
        if key2 not in stats: stats[key2] = {'continue': 0, 'break': 0}
        stats[key2]['continue' if continued else 'break'] += 1
    return stats

def analyze_pattern(results, dice_sums=None):
    if not results or len(results) < 3: return "Tài", 50.0, "Khởi tạo"
    
    last = results[0]
    opposite = "Xỉu" if last == "Tài" else "Tài"
    n = len(results)
    candidates = []
    
    blocks = build_blocks(results)
    current_val = blocks[0]['val']
    current_len = blocks[0]['len']
    
    if current_len >= 10:    candidates.append((opposite, 93.0, f"Bẻ bệt {current_len}", 92))
    elif current_len >= 8:   candidates.append((opposite, 88.0, f"Bẻ bệt {current_len}", 88))
    elif current_len >= 6:   candidates.append((opposite, 80.0, f"Bẻ bệt {current_len}", 78))
    elif current_len == 5:   candidates.append((opposite, 70.0, "Bẻ bệt 5", 68))
    elif current_len == 4:   candidates.append((current_val, 62.0, "Bám bệt 4", 60))
    elif current_len == 3:   candidates.append((current_val, 57.0, "Bám bệt 3", 55))
    elif current_len == 2:   candidates.append((current_val, 53.0, "Bám bệt 2", 52))
    
    alt_len = 0
    for i in range(n - 1):
        if results[i] != results[i + 1]: alt_len += 1
        else: break
    if alt_len >= 10:    candidates.append((opposite, 92.0, f"Đảo 1-1 dài {alt_len}", 90))
    elif alt_len >= 7:   candidates.append((opposite, 83.0, f"Đảo 1-1 {alt_len}", 80))
    elif alt_len >= 4:   candidates.append((opposite, 72.0, f"Đảo 1-1 ngắn", 68))
    
    if len(blocks) >= 3:
        is_alt = all(blocks[i]['val'] != blocks[i-1]['val'] for i in range(1, min(len(blocks), 6)))
        if is_alt:
            p1 = blocks[1]['len']
            p2 = blocks[2]['len']
            if p1 == p2 and p1 >= 2:
                cycle = p1
                if current_len < cycle: candidates.append((current_val, 94.0, f"Bám cầu {cycle}-{cycle} dở", 93))
                elif current_len == cycle: candidates.append((opposite, 96.0, f"Bẻ cầu {cycle}-{cycle}", 95))
            if len(blocks) >= 4:
                p3 = blocks[3]['len']
                if p1 == p3 and p2 != p1 and p1 <= 5: candidates.append((opposite, 82.0, f"Cầu {p1}-{p2}-{p1}", 78))
            if {p1, p2} == {1, 2}: candidates.append((opposite, 80.0, "Cầu 1-2-1", 76))
    
    if len(blocks) >= 5:
        stats = learn_81_patterns(results)
        four_lens = [b['len'] for b in blocks[1:5]]
        code = encode_pattern_81(four_lens)
        sig = pattern_signature(four_lens)
        if code is not None:
            for key in [(code, min(current_len, 4)), code]:
                if key in stats:
                    s = stats[key]
                    total = s['continue'] + s['break']
                    if total >= 2:
                        cont_rate = s['continue'] / total
                        if cont_rate >= 0.62:
                            conf = 55 + cont_rate * 32
                            candidates.append((current_val, conf, f"Mẫu#{code+1:02d}[{sig}] tiếp {s['continue']}/{total}", 75))
                        elif cont_rate <= 0.38:
                            conf = 55 + (1 - cont_rate) * 32
                            candidates.append((opposite, conf, f"Mẫu#{code+1:02d}[{sig}] gãy {s['break']}/{total}", 75))
                        break
    
    for ns in [8, 7, 6, 5, 4]:
        if n < ns + 1: continue
        current_seq = tuple(results[:ns])
        match_tai, match_xiu = 0, 0
        for i in range(len(results) - ns):
            if tuple(results[i:i+ns]) == current_seq and i + ns < len(results):
                if results[i+ns] == "Tài": match_tai += 1
                else: match_xiu += 1
        total_m = match_tai + match_xiu
        if total_m >= 2 and match_tai != match_xiu:
            winner = "Tài" if match_tai > match_xiu else "Xỉu"
            ratio = max(match_tai, match_xiu) / total_m
            if ratio >= 0.6: candidates.append((winner, 55 + ratio * 25, f"N-gram {ns} ({match_tai}T-{match_xiu}X)", 62 + ns))
    
    if n >= 8:
        trans = {"Tài": 0, "Xỉu": 0}
        for i in range(len(results) - 1):
            if results[i] == last: trans[results[i + 1]] += 1
        total_t = trans["Tài"] + trans["Xỉu"]
        if total_t >= 3 and trans["Tài"] != trans["Xỉu"]:
            winner = "Tài" if trans["Tài"] > trans["Xỉu"] else "Xỉu"
            ratio = max(trans["Tài"], trans["Xỉu"]) / total_t
            candidates.append((winner, 60 + ratio * 15, f"Markov ({trans['Tài']}T-{trans['Xỉu']}X)", 58))
    
    if dice_sums and len(dice_sums) >= 5:
        avg_recent = sum(dice_sums[:10]) / min(10, len(dice_sums))
        if avg_recent >= 12.0: candidates.append(("Tài", 62.0, f"Xúc xắc Tài (TB {avg_recent:.1f})", 60))
        elif avg_recent <= 8.5: candidates.append(("Xỉu", 62.0, f"Xúc xắc Xỉu (TB {avg_recent:.1f})", 60))
    
    if not candidates: return opposite, 55.0, "Đảo nhịp (Mặc định)"
    
    tai_conf_score = sum(c[1] for c in candidates if c[0] == "Tài")
    xiu_conf_score = sum(c[1] for c in candidates if c[0] == "Xỉu")
    tai_pri_score = sum(c[3] for c in candidates if c[0] == "Tài")
    xiu_pri_score = sum(c[3] for c in candidates if c[0] == "Xỉu")
    
    tai_combined = tai_conf_score * 0.7 + tai_pri_score * 0.3
    xiu_combined = xiu_conf_score * 0.7 + xiu_pri_score * 0.3
    winner = "Tài" if tai_combined > xiu_combined else "Xỉu"
    
    best = max(candidates, key=lambda x: (x[3], x[1]))
    if best[0] == winner:
        pattern_name = best[2]
        base_conf = best[1]
    else:
        pattern_name = f"Tổng hợp ({len(candidates)} tín hiệu)"
        base_conf = 55.0
    
    agree = tai_conf_score if winner == "Tài" else xiu_conf_score
    total_w = tai_conf_score + xiu_conf_score
    if total_w > 0:
        agree_ratio = agree / total_w
        final_conf = base_conf * (0.88 + agree_ratio * 0.15)
    else: final_conf = base_conf
    
    return winner, round(min(98.0, final_conf), 1), pattern_name

# =====================================================================
# FETCH DỮ LIỆU TX - LINH HOẠT FIELD, KHÔNG BỊA PHIÊN ẢO
# =====================================================================
def fetch_sessions():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    # Thêm timestamp để phá cache
    url = f"{API_URL}&_t={int(time.time())}"
    
    try:
        r = requests.get(url, timeout=8, headers=headers)
        if r.status_code != 200:
            return None, f"Lỗi HTTP {r.status_code} (API bị chặn hoặc token hết hạn)"
        
        data = r.json()
        if 'list' not in data or not data['list']:
            return None, "API trả về danh sách rỗng. Vui lòng lấy lại link API mới!"
        
        rows = []
        for item in data['list']:
            # Lấy session id - fallback nhiều tên field
            session_id = item.get('id') or item.get('session') or item.get('phien')
            if session_id is None:
                continue
            try:
                session_id = int(session_id)
            except (ValueError, TypeError):
                continue
            
            # Lấy kết quả - fallback nhiều field, so khớp không phân biệt dấu
            raw_result = (item.get('resultTruyenThong') or item.get('result') or '').upper()
            if 'TAI' in raw_result or 'TÀI' in raw_result:
                res = "Tài"
            elif 'XIU' in raw_result or 'XỈU' in raw_result:
                res = "Xỉu"
            else:
                continue
            
            # Lấy xúc xắc
            dices = item.get('dices') or item.get('dice') or [0, 0, 0]
            if not isinstance(dices, list) or len(dices) < 3:
                continue
            
            # Lấy tổng điểm
            point = item.get('point') or item.get('total') or sum(dices[:3])
            
            rows.append({
                'phien': session_id,
                'result': res,
                'dice': f"{dices[0]} + {dices[1]} + {dices[2]}",
                'total': point
            })
        
        if not rows:
            return None, "Không có phiên hợp lệ trong dữ liệu API trả về"
        return rows, None
    except Exception as e:
        return None, f"Lỗi mạng: {str(e)[:80]}"

# =====================================================================
# FLASK ROUTES
# =====================================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/history')
def history():
    global RESET_SESSION_ID
    try:
        raw_rows, error = fetch_sessions()
        
        if raw_rows is None:
            return jsonify({'error': error}), 500
            
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
            'phien': next_phien, 'is_next': True, 'prediction': next_pred, 'confidence': next_conf,
            'result': 'Chờ...', 'dice': "? + ? + ?", 'is_correct': None, 'pattern': next_pattern
        })
        
        for i in range(len(valid) - 1, -1, -1):
            current_session = valid[i]
            if current_session['phien'] <= RESET_SESSION_ID: break
            if len(out) > 20: break
            
            history_list = [v['result'] for v in valid[:i]][::-1]
            dice_list = [v.get('total', 0) for v in valid[:i]][::-1]
            
            if history_list:
                pred, conf, pattern = analyze_pattern(history_list, dice_list)
                is_correct = (pred == current_session['result'])
                total_past += 1
                if is_correct: correct_count += 1
            else:
                pred, conf, pattern = "Tài", 50.0, "Khởi tạo"
                is_correct = None
            
            out.append({
                'phien': current_session['phien'], 'is_next': False, 'prediction': pred, 'confidence': conf,
                'result': current_session['result'], 'dice': current_session['dice'],
                'is_correct': is_correct, 'pattern': pattern
            })
        
        return jsonify({'rows': out, 'stats': {'total': total_past, 'correct': correct_count}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_SESSION_ID
    try:
        raw_rows, error = fetch_sessions()
        if raw_rows is None:
            return jsonify({'status': 'error', 'message': error}), 500
            
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
