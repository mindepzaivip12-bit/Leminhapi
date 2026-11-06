import os
import random
import traceback
import time
from datetime import datetime
from collections import Counter
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

DISCLAIMER = (
    "DPI"
)

# =====================================================================
# HTML TEMPLATE — honest UI
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
    :root{--bg-page:#0f172a;--bg-card:#1e293b;--text-main:#f8fafc;--text-muted:#94a3b8;--border-color:#334155;--tai-color:#38bdf8;--tai-bg:rgba(56,189,248,.15);--xiu-color:#f472b6;--xiu-bg:rgba(244,114,182,.15);--warn:#fbbf24;--warn-bg:rgba(251,191,36,.12)}
    *{box-sizing:border-box;margin:0;padding:0;font-family:'Plus Jakarta Sans',sans-serif}
    body{background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 100%);color:var(--text-main);min-height:100vh;padding-bottom:40px}
    .header{background:rgba(30,41,59,.85);backdrop-filter:blur(12px);border-bottom:1px solid var(--border-color);padding:16px 24px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
    .header-title{font-size:20px;font-weight:800;color:#38bdf8;display:flex;align-items:center;gap:10px}
    .header-title span{font-size:10px;background:#334155;color:#cbd5e1;padding:4px 10px;border-radius:20px;font-weight:800;letter-spacing:1px}
    .header-actions{display:flex;gap:12px;align-items:center}
    .time-update{font-size:12px;color:var(--text-muted);font-weight:600}
    .btn-refresh{background:var(--bg-card);color:var(--text-main);border:1px solid var(--border-color);width:38px;height:38px;border-radius:10px;font-weight:700;font-size:16px;cursor:pointer}
    .btn-reset{background:rgba(248,113,113,.2);color:#f87171;border:1px solid #f87171;padding:8px 16px;border-radius:10px;font-weight:700;font-size:13px;cursor:pointer}
    .disclaimer{max-width:800px;margin:16px auto;padding:14px 18px;background:var(--warn-bg);border:1px solid rgba(251,191,36,.3);border-radius:12px;color:var(--warn);font-size:12px;font-weight:600;line-height:1.5}
    .stats-bar{max-width:800px;margin:16px auto;padding:0 16px;display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
    .stat-item{background:var(--bg-card);border:1px solid var(--border-color);border-radius:14px;padding:16px 10px;text-align:center}
    .stat-label{font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:700;margin-bottom:6px}
    .stat-value{font-size:22px;font-weight:800}
    .stat-value.tai{color:var(--tai-color)}.stat-value.xiu{color:var(--xiu-color)}.stat-value.neutral{color:var(--text-main)}
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
    .badge-random{background:var(--warn-bg);color:var(--warn);border:1px solid rgba(251,191,36,.3);font-size:10px}
    .dice-text{font-size:11px;color:var(--text-muted);display:block;margin-top:4px}
    .loading{text-align:center;padding:40px;color:var(--tai-color);font-weight:600}
    .note-tag{font-size:10px;color:var(--text-muted);font-style:italic;display:block;margin-top:2px}
    @media(max-width:500px){.data-table th,.data-table td{padding:10px 6px;font-size:12px}.stats-bar{grid-template-columns:repeat(2,1fr)}.time-update{display:none}}
</style>
</head>
<body>
<div class="header">
    <div class="header-title">LE MINH <span>V3</span></div>
    <div class="header-actions">
        <div class="time-update" id="time-update">--:--:--</div>
        <button class="btn-refresh" onclick="fetchData()">↻</button>
        <button class="btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>

<div class="disclaimer" id="disclaimer">Đang tải...</div>

<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng phiên</div><div class="stat-value neutral" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Số Tài</div><div class="stat-value tai" id="stat-tai">0</div></div>
    <div class="stat-item"><div class="stat-label">Số Xỉu</div><div class="stat-value xiu" id="stat-xiu">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ Tài</div><div class="stat-value neutral" id="stat-ratio">0%</div></div>
</div>

<div class="table-wrapper"><div class="table-container">
<table class="data-table"><thead><tr><th>Phiên</th><th>Kết quả</th><th>Xúc xắc</th><th>Ghi chú</th></tr></thead>
<tbody id="table-body"><tr><td colspan="4" class="loading">Đang kết nối...</td></tr></tbody></table>
</div></div>

<script>
let isResetting=false;

async function fetchData(){
    if(isResetting) return;
    try{
        const r = await fetch('/api/history',{cache:'no-store'});
        const data = await r.json();
        document.getElementById('time-update').innerText = new Date().toLocaleTimeString('vi-VN');
        document.getElementById('disclaimer').innerText = data.disclaimer || '';
        renderTable(data.rows||[], data.stats||{});
    }catch(e){console.error(e)}
}

function renderTable(rows, stats){
    const tb = document.getElementById('table-body');
    const total = stats.total||0, tai = stats.tai||0, xiu = stats.xiu||0;
    document.getElementById('stat-total').innerText = total;
    document.getElementById('stat-tai').innerText = tai;
    document.getElementById('stat-xiu').innerText = xiu;
    document.getElementById('stat-ratio').innerText = total>0 ? Math.round(tai/total*100)+'%' : '0%';

    if(!rows.length){tb.innerHTML='<tr><td colspan="4" class="loading">Chưa có dữ liệu.</td></tr>';return}
    let html='';
    rows.forEach(row=>{
        const trCls = row.is_next ? 'class="row-next"' : '';
        let rh = `<span class="badge badge-empty">-</span>`;
        if(row.result==="Tài") rh = `<span class="badge badge-tai">TÀI</span>`;
        if(row.result==="Xỉu") rh = `<span class="badge badge-xiu">XỈU</span>`;
        let dd = '';
        if(row.dice && row.dice!=="? + ? + ?"){
            dd = `<span class="dice-text">${row.dice} (${row.total})</span>`;
        }
        const note = row.is_next
            ? `<span class="badge badge-random">🎲 NGẪU NHIÊN</span><span class="note-tag">Không dự đoán được</span>`
            : `<span class="note-tag">—</span>`;
        html += `<tr ${trCls}><td>#${row.phien}</td><td>${rh}</td><td>${dd||'<span class="badge badge-empty">-</span>'}</td><td>${note}</td></tr>`;
    });
    tb.innerHTML = html;
}

async function confirmReset(){
    Swal.fire({
        title:'Reset?',
        text:'Xoá toàn bộ lịch sử đang cache?',
        icon:'warning',
        background:'#1e293b', color:'#f8fafc',
        showCancelButton:true,
        confirmButtonColor:'#0ea5e9', cancelButtonColor:'#64748b',
        confirmButtonText:'Đồng ý', cancelButtonText:'Hủy'
    }).then(async r=>{
        if(r.isConfirmed){
            isResetting=true;
            try{
                const res = await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
                const d = await res.json();
                if(d.status==='success'){
                    isResetting=false;
                    fetchData();
                    Swal.fire({title:'OK!',text:'Đã reset.',icon:'success',background:'#1e293b',color:'#f8fafc',confirmButtonColor:'#0ea5e9'});
                } else throw new Error(d.message||'Lỗi');
            }catch(e){
                isResetting=false;
                Swal.fire({title:'Lỗi!',text:e.message,icon:'error',background:'#1e293b',color:'#f8fafc'});
            }
        }
    });
}

fetchData();
setInterval(fetchData, 5000);
</script>
</body>
</html>"""


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
    # Xoá các phiên cũ hơn RESET_ID
    if RESET_ID > 0:
        for k in [k for k in HISTORY_CACHE if k < RESET_ID]:
            del HISTORY_CACHE[k]
    valid = sorted(HISTORY_CACHE.values(), key=lambda x: x['phien'])
    return valid, True


def _honest_stats(valid):
    """Thống kê trung thực — không bịa, không suy diễn."""
    total = len(valid)
    tai = sum(1 for v in valid if v['result'] == 'Tài')
    xiu = total - tai
    return {
        'total': total,
        'tai': tai,
        'xiu': xiu,
        'ratio_tai': round(tai / total, 3) if total else 0,
    }


def _honest_prediction():
    """
    Dự đoán trung thực: 50/50.
    Lý do: 3 viên xúc xắc độc lập, tổng 11-17 (Tài) và 4-10 (Xỉu) đối xứng
    → P(Tài) = P(Xỉu) ≈ 0.5. Không pattern nào thay đổi điều này.
    """
    return random.choice(["Tài", "Xỉu"])


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
                'rows': [{
                    'phien': RESET_ID + 1,
                    'is_next': True,
                    'result': 'Chờ...',
                    'dice': '? + ? + ?',
                    'total': None,
                    'note': 'random',
                }],
                'stats': {'total': 0, 'tai': 0, 'xiu': 0},
            })

        next_phien = valid[-1]['phien'] + 1
        stats = _honest_stats(valid)

        out = [{
            'phien': next_phien,
            'is_next': True,
            'result': 'Chờ...',
            'dice': '? + ? + ?',
            'total': None,
            'note': 'random',
        }]

        # 200 phiên gần nhất
        for v in reversed(valid[-200:]):
            if v['phien'] <= RESET_ID:
                continue
            out.append({
                'phien': v['phien'],
                'is_next': False,
                'result': v['result'],
                'dice': v['dice'],
                'total': v['total'],
                'note': None,
            })

        return jsonify({
            'disclaimer': DISCLAIMER,
            'rows': out,
            'stats': stats,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict')
def predict():
    """
    Dự đoán trung thực: 50/50. Không giả vờ có edge.
    Trả về đầy đủ thông tin lịch sử + disclaimer.
    """
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API', 'disclaimer': DISCLAIMER}), 500

        last = valid[-1] if valid else None
        next_phien = (last['phien'] + 1) if last else (RESET_ID + 1)
        prediction = _honest_prediction()
        stats = _honest_stats(valid)

        return jsonify({
            'disclaimer': DISCLAIMER,
            'last_phien': last['phien'] if last else None,
            'next_phien': next_phien,
            'last_result': last['result'] if last else None,
            'last_dice': last['dice'] if last else None,
            'last_total': last['total'] if last else None,

            'prediction': prediction,
            'confidence': 50,  # trung thực: không có edge
            'note': 'Dự đoán ngẫu nhiên — không có giá trị dự báo thực sự.',
            'method': 'random',

            'stats': stats,
            'total_sessions': len(valid),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lc79')
def lc79():
    """Endpoint gọn cho tích hợp ngoài — nội dung trung thực."""
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API', 'disclaimer': DISCLAIMER}), 500
        last = valid[-1] if valid else None
        next_phien = (last['phien'] + 1) if last else (RESET_ID + 1)
        prediction = _honest_prediction()
        stats = _honest_stats(valid)
        return jsonify({
            'Id': 'le minh honest',
            'Phien': str(next_phien),
            'Ket_qua': last['result'].lower() if last else None,
            'Du_doan': prediction,
            'Do_tin_cay': '50%',
            'Ghi_chu': 'Ngẫu nhiên — không dự báo được',
            'Tong_phien': stats['total'],
            'So_Tai': stats['tai'],
            'So_Xiu': stats['xiu'],
            'Ty_le_Tai': f"{stats['ratio_tai']*100:.1f}%",
            'Disclaimer': DISCLAIMER,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def stats_only():
    """Chỉ trả thống kê thực — không dự đoán gì."""
    try:
        valid, success = _sync_history()
        if not success:
            return jsonify({'error': 'Không thể kết nối API', 'disclaimer': DISCLAIMER}), 500
        stats = _honest_stats(valid)
        last = valid[-1] if valid else None
        return jsonify({
            'disclaimer': DISCLAIMER,
            'stats': stats,
            'last_result': last['result'] if last else None,
            'last_phien': last['phien'] if last else None,
            'last_dice': last['dice'] if last else None,
            'total_sessions': len(valid),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_api():
    global RESET_ID, HISTORY_CACHE
    try:
        raw_rows, success = fetch_sessions()
        if success and raw_rows:
            valid = sorted(raw_rows, key=lambda x: x['phien'])
            if valid:
                RESET_ID = valid[-1]['phien']
                HISTORY_CACHE = {valid[-1]['phien']: valid[-1]}
                return jsonify({'status': 'success', 'reset_to': RESET_ID + 1})
        elif HISTORY_CACHE:
            RESET_ID = max(HISTORY_CACHE.keys())
            HISTORY_CACHE = {RESET_ID: HISTORY_CACHE[RESET_ID]}
            return jsonify({'status': 'success', 'reset_to': RESET_ID + 1, 'note': 'Offline reset'})
        return jsonify({'status': 'error', 'message': 'Không có dữ liệu để reset'}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
