import os
import traceback
from datetime import datetime
from collections import Counter
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
API_URL_MD5 = 'https://wtxmd52.tele68.com/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=d35795e07a393f91815436933a4852df'
HISTORY_CACHE = {}
RESET_ID = 0
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LE MINH MD5 </title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<style>
    :root {
        --bg-page: #0f172a; --bg-card: #1e293b; --text-main: #f8fafc;
        --text-muted: #94a3b8; --border-color: #334155;
        --tai-color: #38bdf8; --tai-bg: rgba(56, 189, 248, 0.15);
        --xiu-color: #f472b6; --xiu-bg: rgba(244, 114, 182, 0.15);
        --win-color: #34d399; --win-bg: rgba(52, 211, 153, 0.15);
        --lose-color: #f87171; --lose-bg: rgba(248, 113, 113, 0.15);
        --wait-color: #fbbf24; --wait-bg: rgba(251, 191, 36, 0.15);
        --recovery-color: #fb923c; --recovery-bg: rgba(251, 146, 60, 0.15);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: var(--text-main); min-height: 100vh; padding-bottom: 40px; }
    .header { background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-color); padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
    .header-title { font-size: 22px; font-weight: 800; color: #38bdf8; display: flex; align-items: center; gap: 10px; text-shadow: 0 0 20px rgba(56, 189, 248, 0.4); }
    .header-title span { font-size: 11px; background: linear-gradient(135deg, #38bdf8, #ec4899); color: #fff; padding: 4px 12px; border-radius: 20px; font-weight: 800; letter-spacing: 1px; box-shadow: 0 0 15px rgba(236, 72, 153, 0.4); }
    .header-actions { display: flex; gap: 12px; align-items: center; }
    .time-update { font-size: 12px; color: var(--text-muted); font-weight: 600; }
    .btn-refresh { background: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); width: 38px; height: 38px; border-radius: 10px; font-weight: 700; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: 0.2s; }
    .btn-refresh:hover { background: var(--border-color); transform: rotate(180deg); }
    .btn-reset { background: rgba(248, 113, 113, 0.2); color: var(--lose-color); border: 1px solid var(--lose-color); padding: 8px 16px; border-radius: 10px; font-weight: 700; font-size: 13px; cursor: pointer; transition: 0.2s; }
    .btn-reset:hover { background: var(--lose-color); color: #fff; box-shadow: 0 0 15px rgba(248, 113, 113, 0.4); }
    .stats-bar { max-width: 800px; margin: 24px auto 16px; padding: 0 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .stat-item { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 16px 10px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px; letter-spacing: 0.3px; }
    .stat-value { font-size: 22px; font-weight: 800; color: var(--text-main); }
    .stat-value.win { color: var(--win-color); text-shadow: 0 0 15px rgba(52, 211, 153, 0.4); }
    .stat-value.loss { color: var(--lose-color); text-shadow: 0 0 15px rgba(248, 113, 113, 0.4); }
    .stat-value.rate { color: var(--tai-color); text-shadow: 0 0 15px rgba(56, 189, 248, 0.4); }
    .table-wrapper { max-width: 800px; margin: 0 auto; padding: 0 16px; }
    .table-container { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); max-height: 70vh; overflow-y: auto; }
    .data-table { width: 100%; border-collapse: separate; border-spacing: 0; }
    .data-table th { background: #111827; color: var(--text-muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 16px 12px; text-align: center; border-bottom: 1px solid var(--border-color); position: sticky; top: 0; z-index: 10; }
    .data-table td { padding: 14px 12px; text-align: center; border-bottom: 1px solid var(--border-color); font-size: 14px; font-weight: 600; }
    .data-table tr:last-child td { border-bottom: none; }
    .data-table tr:hover { background: rgba(255, 255, 255, 0.02); }
    .row-next { background: rgba(14, 165, 233, 0.08); border-left: 4px solid var(--tai-color); }
    .row-next.recovery { background: rgba(251, 146, 60, 0.1); border-left: 4px solid var(--recovery-color); }
    .badge { display: inline-block; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; min-width: 70px; text-align: center; }
    .badge-tai { background: var(--tai-bg); color: var(--tai-color); border: 1px solid rgba(56, 189, 248, 0.3); box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); }
    .badge-xiu { background: var(--xiu-bg); color: var(--xiu-color); border: 1px solid rgba(244, 114, 182, 0.3); box-shadow: 0 0 10px rgba(244, 114, 182, 0.2); }
    .badge-empty { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); }
    .recovery-badge { display: inline-block; margin-left: 6px; padding: 2px 8px; border-radius: 8px; font-size: 10px; font-weight: 800; background: var(--recovery-bg); color: var(--recovery-color); border: 1px solid var(--recovery-color); box-shadow: 0 0 10px rgba(251, 146, 60, 0.3); animation: pulse 1.5s infinite; letter-spacing: 0.5px; }
    .status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; padding: 6px 14px; border-radius: 20px; }
    .st-win { background: var(--win-bg); color: var(--win-color); border: 1px solid rgba(52, 211, 153, 0.3); }
    .st-lose { background: var(--lose-bg); color: var(--lose-color); border: 1px solid rgba(248, 113, 113, 0.3); }
    .st-wait { background: var(--wait-bg); color: var(--wait-color); border: 1px solid rgba(251, 191, 36, 0.3); animation: pulse 1.5s infinite; }
    .st-recover { background: var(--recovery-bg); color: var(--recovery-color); border: 1px solid var(--recovery-color); animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .dice-text { font-size: 11px; color: var(--text-muted); display: block; margin-top: 4px; font-weight: 500; }
    .conf-badge { font-size: 11px; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 2px 8px; border-radius: 10px; margin-top: 4px; display: inline-block; font-weight: 700; }
    .conf-badge.high { color: #34d399; background: rgba(52, 211, 153, 0.15); box-shadow: 0 0 10px rgba(52, 211, 153, 0.2); }
    .loading { text-align: center; padding: 40px; color: var(--tai-color); font-weight: 600; }
    @media (max-width: 500px) {
        .data-table th, .data-table td { padding: 10px 6px; font-size: 12px; }
        .badge { padding: 4px 8px; font-size: 11px; min-width: 50px; }
        .header-title { font-size: 18px; }
        .time-update { display: none; }
        .stats-bar { grid-template-columns: repeat(2, 1fr); }
        .stat-value { font-size: 18px; }
    }
</style>
</head>
<body>

<div class="header">
    <div class="header-title">LE MINH <span>MD5 v5</span></div>
    <div class="header-actions">
        <div class="time-update" id="time-update">--:--:--</div>
        <button class="btn-refresh" onclick="fetchData()">↻</button>
        <button class="btn-reset" onclick="confirmReset()">Reset</button>
    </div>
</div>

<div class="stats-bar">
    <div class="stat-item"><div class="stat-label">Tổng</div><div class="stat-value" id="stat-total">0</div></div>
    <div class="stat-item"><div class="stat-label">Số Tài</div><div class="stat-value win" id="stat-win">0</div></div>
    <div class="stat-item"><div class="stat-label">Số Xỉu</div><div class="stat-value loss" id="stat-lose">0</div></div>
    <div class="stat-item"><div class="stat-label">Tỷ lệ Tài</div><div class="stat-value rate" id="stat-rate">0%</div></div>
</div>

<div class="table-wrapper">
    <div class="table-container">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Phiên</th>
                    <th>Mẫu 5 phiên</th>
                    <th>Kết quả</th>
                    <th>Trạng thái</th>
                </tr>
            </thead>
            <tbody id="table-body">
                <tr><td colspan="4" class="loading">Đang kết nối Server...</td></tr>
            </tbody>
        </table>
    </div>
</div>

<script>
let isResetting = false;

function animateNumber(el, target, suffix = '') {
    const start = parseInt(el.innerText.replace(/[^0-9]/g, '')) || 0;
    if (start === target) { el.innerText = target + suffix; return; }
    const duration = 500;
    const startTime = performance.now();
    function update(t) {
        const p = Math.min((t - startTime) / duration, 1);
        const ease = 1 - Math.pow(1 - p, 3);
        el.innerText = Math.floor(start + (target - start) * ease) + suffix;
        if (p < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

async function fetchData() {
    if (isResetting) return;
    try {
        const r = await fetch('/api/history', { cache: 'no-store' });
        const data = await r.json();
        const now = new Date();
        document.getElementById('time-update').innerText = now.toLocaleTimeString('vi-VN');
        renderTable(data.rows || [], data.stats || {});
    } catch (e) { console.error("Lỗi tải dữ liệu:", e); }
}

function renderTable(rows, stats) {
    const tbody = document.getElementById('table-body');
    animateNumber(document.getElementById('stat-total'), stats.total || 0);
    animateNumber(document.getElementById('stat-win'), stats.tai || 0);
    animateNumber(document.getElementById('stat-lose'), stats.xiu || 0);
    animateNumber(document.getElementById('stat-rate'), Math.round(stats.tai_rate || 0), '%');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading">Không có dữ liệu. Hãy đợi phiên mới.</td></tr>';
        return;
    }
    let html = '';
    rows.forEach((row) => {
        const pattern = row.pattern_label || 'Chưa đủ 5 phiên';
        const detail = row.pattern_detail || '';
        const resultHtml = row.result === "Tài"
            ? '<span class="badge badge-tai">TÀI</span>'
            : row.result === "Xỉu" ? '<span class="badge badge-xiu">XỈU</span>'
            : '<span class="badge badge-empty">-</span>';
        const p = (row.dice || '').split(" + ");
        let diceDisplay = '';
        if (p.length === 3 && p.every(x => !isNaN(parseInt(x)))) {
            diceDisplay = `<span class="dice-text">${row.dice} (${p.reduce((a,b) => a + parseInt(b), 0)})</span>`;
        }
        html += `<tr><td>#${row.phien}</td><td><div style="display:flex;flex-direction:column;align-items:center;gap:3px"><span class="badge badge-empty">${pattern}</span><span class="dice-text">${detail}</span></div></td><td><div style="display:flex;flex-direction:column;align-items:center">${resultHtml}${diceDisplay}</div></td><td><span class="status st-wait">LỊCH SỬ</span></td></tr>`;
    });
    tbody.innerHTML = html;
}

async function confirmReset() {
    Swal.fire({
        title: 'Xác nhận Reset?', text: "Toàn bộ lịch sử hiển thị sẽ bị xoá và bắt đầu lại từ đầu!",
        icon: 'warning', background: '#1e293b', color: '#f8fafc',
        showCancelButton: true, confirmButtonColor: '#0ea5e9', cancelButtonColor: '#64748b',
        confirmButtonText: 'Đồng ý', cancelButtonText: 'Hủy'
    }).then(async (result) => {
        if (result.isConfirmed) {
            isResetting = true;
            Swal.fire({ title: 'Đang Reset...', allowOutsideClick: false, background: '#1e293b', color: '#f8fafc', didOpen: () => { Swal.showLoading() } });
            try {
                const res = await fetch('/api/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
                const data = await res.json();
                if (data.status === 'success') {
                    Swal.fire({ title: 'Thành công!', text: 'Đã xoá lịch sử và bắt đầu lại.', icon: 'success', background: '#1e293b', color: '#f8fafc', confirmButtonColor: '#0ea5e9' });
                    isResetting = false; fetchData();
                } else { throw new Error(data.message); }
            } catch (error) {
                Swal.fire({title: 'Lỗi!', text: 'Không thể reset: ' + error.message, icon: 'error', background: '#1e293b', color: '#f8fafc'});
                isResetting = false;
            }
        }
    });
}

fetchData();
setInterval(fetchData, 5000);
</script>
</body>
</html>"""


def fetch_sessions():
    """Lấy kết quả đã có từ API nguồn."""
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        response = requests.get(API_URL_MD5, timeout=8, headers=headers)
        response.raise_for_status()
        data = response.json()
        rows = []
        for item in data.get("list", []):
            raw = str(item.get("resultTruyenThong", "")).upper()
            if raw not in ("TAI", "XIU"):
                continue
            dices = item.get("dices") or [0, 0, 0]
            if not isinstance(dices, (list, tuple)) or len(dices) != 3:
                dices = [0, 0, 0]
            rows.append({
                "phien": int(item["id"]),
                "result": "Tài" if raw == "TAI" else "Xỉu",
                "dice": " + ".join(str(x) for x in dices),
                "total": item.get("point", sum(int(x) for x in dices))
            })
        return rows, True
    except Exception as exc:
        print(f"[API ERROR] {exc}")
        return [], False


def analyze_five_sessions(results):
    """Thống kê mô tả 5 kết quả đã xảy ra theo thứ tự cũ -> mới."""
    window = list(results[-5:])
    counts = Counter(window)
    if len(window) < 5:
        return {
            "sample_size": len(window), "sequence": window,
            "pattern": "insufficient", "pattern_label": "Chưa đủ 5 phiên",
            "alternations": 0, "tai_count": counts["Tài"],
            "xiu_count": counts["Xỉu"], "current_streak": len(window),
            "last_change": False,
            "description": "Cần đủ 5 kết quả đã có để mô tả mẫu."
        }

    alternations = sum(window[i] != window[i - 1] for i in range(1, 5))
    streak = 1
    for value in reversed(window[:-1]):
        if value == window[-1]:
            streak += 1
        else:
            break

    last_change = len(set(window[:3])) == 1 and window[3] != window[2] and window[4] == window[3]
    if alternations == 4:
        pattern, label = "alternating_1_1", "Luân phiên 1-1"
        description = "5 phiên gần nhất thay đổi Tài/Xỉu liên tiếp; đây là mô tả lịch sử."
    elif streak >= 3:
        pattern, label = "same_result_run", f"Chuỗi {streak} phiên"
        description = f"{streak} kết quả cuối liên tiếp là {window[-1]}."
    elif counts["Tài"] >= 4:
        pattern, label = "tai_dominant", "Tài xuất hiện nhiều"
        description = f"Tài xuất hiện {counts['Tài']}/5 phiên."
    elif counts["Xỉu"] >= 4:
        pattern, label = "xiu_dominant", "Xỉu xuất hiện nhiều"
        description = f"Xỉu xuất hiện {counts['Xỉu']}/5 phiên."
    elif alternations >= 3:
        pattern, label = "frequent_changes", "Biến đổi thường xuyên"
        description = f"Có {alternations} lần đổi kết quả trong 4 khoảng chuyển tiếp."
    else:
        pattern, label = "mixed", "Mẫu hỗn hợp"
        description = f"Tài {counts['Tài']} phiên, Xỉu {counts['Xỉu']} phiên; chưa có mẫu nổi bật."
    if last_change:
        description += " Hai kết quả cuối khác với cụm 3 phiên đầu."
    return {
        "sample_size": 5, "sequence": window, "pattern": pattern,
        "pattern_label": label, "alternations": alternations,
        "tai_count": counts["Tài"], "xiu_count": counts["Xỉu"],
        "current_streak": streak, "last_change": last_change,
        "description": description
    }


def annotate_rows(valid, limit=150):
    results = [row["result"] for row in valid]
    output = []
    first = max(0, len(valid) - limit)
    for i in range(len(valid) - 1, first - 1, -1):
        window = results[max(0, i - 4):i + 1]
        info = analyze_five_sessions(window)
        row = valid[i]
        output.append({
            "phien": row["phien"], "result": row["result"],
            "dice": row["dice"], "pattern_label": info["pattern_label"],
            "pattern_detail": info["description"]
        })
    return output


def load_history():
    global HISTORY_CACHE
    raw, success = fetch_sessions()
    if success:
        for row in raw:
            if row["phien"] >= RESET_ID:
                HISTORY_CACHE[row["phien"]] = row
    return sorted(HISTORY_CACHE.values(), key=lambda x: x["phien"]), success


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/history")
def history():
    try:
        valid, success = load_history()
        results = [row["result"] for row in valid]
        tai, xiu = results.count("Tài"), results.count("Xỉu")
        return jsonify({
            "rows": annotate_rows(valid),
            "stats": {
                "total": len(valid), "tai": tai, "xiu": xiu,
                "tai_rate": tai / len(valid) * 100 if valid else 0
            },
            "source_ok": success,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/api/analysis")
def analysis():
    try:
        valid, success = load_history()
        if not valid:
            return jsonify({"error": "Chưa có dữ liệu phiên"}), 400
        info = analyze_five_sessions([row["result"] for row in valid][-5:])
        info.update({
            "latest_session": valid[-1]["phien"],
            "latest_result": valid[-1]["result"],
            "source_ok": success, "timestamp": datetime.now().isoformat()
        })
        return jsonify(info)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/api/predict")
def predict():
    return jsonify({
        "available": False,
        "message": "Phiên bản này chỉ thống kê 5 phiên lịch sử, không dự báo kết quả tương lai."
    }), 410


@app.route("/lc79")
def lc79():
    try:
        valid, success = load_history()
        if not valid:
            return jsonify({"error": "Chưa có dữ liệu"}), 400
        info = analyze_five_sessions([row["result"] for row in valid][-5:])
        last = valid[-1]
        return jsonify({
            "Id": "le minh md5 history analyzer",
            "Phien": str(last["phien"]),
            "Ket_qua": last["result"].lower(),
            "Mau_5_phien": info["sequence"],
            "Phan_tich": info["pattern_label"],
            "So_lan_doi": info["alternations"],
            "Tai_trong_5": info["tai_count"],
            "Xiu_trong_5": info["xiu_count"],
            "Mo_ta": info["description"],
            "Nguon_du_lieu": success
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/lc79md5")
def lc79md5():
    try:
        valid, success = load_history()
        if not valid:
            return jsonify({"error": "Chưa có dữ liệu"}), 400
        info = analyze_five_sessions([row["result"] for row in valid][-5:])
        last = valid[-1]
        return jsonify({
            "id": "@cskhleminh",
            "phien": str(last["phien"]),
            "ket_qua": last["result"].lower(),
            "mau_5_phien": "".join("T" if x == "Tài" else "X" for x in info["sequence"]),
            "phan_tich": info["pattern_label"],
            "so_lan_doi": info["alternations"],
            "tai_trong_5": info["tai_count"],
            "xiu_trong_5": info["xiu_count"],
            "mo_ta": info["description"],
            "source_ok": success
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/api/reset", methods=["POST"])
def reset_api():
    global RESET_ID, HISTORY_CACHE
    try:
        raw, success = fetch_sessions()
        if not success or not raw:
            return jsonify({"status": "error", "message": "Không thể xác nhận mốc Reset do lỗi API nguồn."}), 400
        latest = max(raw, key=lambda row: row["phien"])
        RESET_ID = latest["phien"]
        HISTORY_CACHE = {latest["phien"]: latest}
        return jsonify({"status": "success", "reset_to": RESET_ID})
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
