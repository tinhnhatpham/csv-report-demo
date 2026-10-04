"""CSV report generator: upload a CSV, get a plain-English summary. Run locally: python app.py

The file is processed in memory and never stored. Code computes the statistics (stats.py);
Claude only writes the words (writer.py).
"""
import os
import time
from collections import defaultdict
from datetime import date

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

import anthropic  # noqa: E402
from stats import CsvError, profile, read_csv, sample_rows  # noqa: E402
from writer import WriterError, write_report  # noqa: E402

MAX_FILE_BYTES = 1024 * 1024
MAX_REPORTS_PER_HOUR = int(os.getenv("MAX_REPORTS_PER_HOUR", "10"))  # per visitor
MAX_REPORTS_PER_DAY = int(os.getenv("MAX_REPORTS_PER_DAY", "150"))   # whole site: caps the AI bill
SAMPLE_FILE = os.path.join(os.path.dirname(__file__), "sample_sales.csv")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_BYTES + 64 * 1024  # file + form overhead
CORS(app, origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","))

_hits = defaultdict(list)  # ip -> timestamps (resets on restart; fine for a demo)
_daily = {"day": None, "count": 0}


def client_ip() -> str:
    # Render sits behind Cloudflare, which sets CF-Connecting-IP and blocks forged values
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or ""


def over_limits() -> str | None:
    today = date.today()
    if _daily["day"] != today:
        _daily.update(day=today, count=0)
    if _daily["count"] >= MAX_REPORTS_PER_DAY:
        return "The demo has reached today's report limit. Please try again tomorrow."
    now = time.time()
    ip = client_ip()
    _hits[ip] = [t for t in _hits[ip] if now - t < 3600]
    if len(_hits[ip]) >= MAX_REPORTS_PER_HOUR:
        return "You've made a lot of reports this hour. Please try again later."
    _hits[ip].append(now)
    _daily["count"] += 1
    return None


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "That file is too big. This demo handles files up to 1 MB."}), 413


@app.post("/api/report")
def create_report():
    if request.args.get("sample") == "1":
        with open(SAMPLE_FILE, "rb") as f:
            data, filename = f.read(), "sample_sales.csv"
    else:
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"error": "Please choose a CSV file."}), 400
        if not upload.filename.lower().endswith((".csv", ".txt")):
            return jsonify({"error": "Please upload a .csv file (Excel: File > Save As > CSV)."}), 400
        data, filename = upload.read(), upload.filename

    try:
        header, rows = read_csv(data)
        stats = profile(header, rows)
    except CsvError as e:
        return jsonify({"error": str(e)}), 400

    if limit := over_limits():
        return jsonify({"error": limit}), 429

    try:
        report = write_report(stats, sample_rows(header, rows))
    except WriterError as e:
        return jsonify({"error": str(e)}), 502
    except anthropic.APIError as e:
        app.logger.error(f"Claude API error: {e}")
        return jsonify({"error": "The AI writer is unavailable right now. Please try again."}), 502

    return jsonify({"filename": filename, "report": report, "stats": stats})


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5002")))
