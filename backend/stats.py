"""Turns an uploaded CSV into statistics. Every number in the report is computed HERE, by code.

Claude never does arithmetic on the raw data; it only writes sentences around these numbers.
That keeps the report accurate and means the whole file never has to be sent to the AI.
"""
import csv
import io
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime

MAX_ROWS = 20000
MAX_COLUMNS = 40
TYPE_THRESHOLD = 0.9  # a column is "numeric"/"date" if 90%+ of its non-empty cells parse that way
MAX_CATEGORIES = 50   # text columns with more distinct values than this aren't treated as categories
METRIC_NAME = re.compile(r"revenue|sales|amount|total|price|income|profit|cost|spend|value", re.I)

_NUMBER = re.compile(r"^[-+]?\(?\s*[$€£]?\s*[\d,]*\.?\d+\s*\)?\s*%?$")
_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%b %d, %Y", "%d %b %Y", "%B %d, %Y",
)


class CsvError(ValueError):
    """A problem with the uploaded file that the user can fix (shown to them as-is)."""


def to_number(text: str):
    text = text.strip()
    if not text or not _NUMBER.match(text):
        return None
    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    digits = re.sub(r"[^\d.]", "", text)
    try:
        value = float(digits)
    except ValueError:
        return None
    return -value if negative else value


def to_date(text: str):
    text = text.strip()
    if not text or not re.search(r"[-/ ,]", text):
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def read_csv(data: bytes):
    """Decode and parse the file. Returns (header, rows). Raises CsvError with a friendly message."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):  # Excel on Windows saves CSVs as cp1252
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue  # latin-1 accepts any bytes, so the loop always ends with text set
    if not text.strip():
        raise CsvError("The file is empty.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(cell.strip() for cell in r)]
    if len(rows) < 2:
        raise CsvError("The file needs a header row and at least one row of data.")
    header = [h.strip() or f"column_{i + 1}" for i, h in enumerate(rows[0])]
    data_rows = rows[1:]
    if len(header) > MAX_COLUMNS:
        raise CsvError(f"Too many columns ({len(header)}). This demo handles up to {MAX_COLUMNS}.")
    if len(data_rows) > MAX_ROWS:
        raise CsvError(f"Too many rows ({len(data_rows):,}). This demo handles up to {MAX_ROWS:,}.")
    return header, data_rows


def r2(x):
    return round(x, 2) if isinstance(x, float) else x


def pct_change(old, new):
    return r2((new - old) / abs(old) * 100) if old else None


def profile(header, rows):
    """Describe every column, then precompute the comparisons a report needs."""
    columns = []
    parsed = {}  # column name -> list of parsed values (None where empty/unparseable), row-aligned
    for i, name in enumerate(header):
        raw = [(r[i] if i < len(r) else "").strip() for r in rows]
        filled = [v for v in raw if v]
        info = {"name": name, "filled": len(filled), "missing": len(raw) - len(filled)}
        nums = [to_number(v) for v in raw]
        dates = [to_date(v) for v in raw]
        if filled and sum(n is not None for n in nums) >= TYPE_THRESHOLD * len(filled):
            values = [n for n in nums if n is not None]
            info.update(type="number", sum=r2(sum(values)), mean=r2(statistics.fmean(values)),
                        median=r2(statistics.median(values)), min=r2(min(values)), max=r2(max(values)))
            parsed[name] = nums
        elif filled and sum(d is not None for d in dates) >= TYPE_THRESHOLD * len(filled):
            values = [d for d in dates if d is not None]
            info.update(type="date", first=min(values).date().isoformat(), last=max(values).date().isoformat())
            parsed[name] = dates
        else:
            counts = Counter(filled)
            info.update(type="text", distinct=len(counts),
                        top_values=[{"value": v, "rows": c} for v, c in counts.most_common(5)])
            parsed[name] = raw
        columns.append(info)

    result = {"rows": len(rows), "columns": columns}
    numeric = [c["name"] for c in columns if c["type"] == "number"]
    if not numeric:
        return result

    # The "main metric" is the column a business owner most likely cares about
    metric = next((n for n in numeric if METRIC_NAME.search(n)), numeric[0])
    result["main_metric"] = metric
    metric_values = parsed[metric]
    total = sum(v for v in metric_values if v is not None)

    # Breakdowns of the main metric by each category-like text column
    breakdowns = []
    for c in columns:
        if c["type"] != "text" or not 2 <= c["distinct"] <= MAX_CATEGORIES:
            continue
        sums = defaultdict(float)
        for cat, val in zip(parsed[c["name"]], metric_values):
            if cat and val is not None:
                sums[cat] += val
        ranked = sorted(sums.items(), key=lambda kv: kv[1], reverse=True)
        breakdowns.append({
            "by": c["name"],
            "groups": [{"group": g, "total": r2(v), "share_pct": r2(v / total * 100) if total else None}
                       for g, v in ranked[:8]],
            "groups_not_shown": max(0, len(ranked) - 8),
        })
    result["breakdowns"] = breakdowns[:4]

    # Monthly trend of the main metric along the first date column
    date_col = next((c["name"] for c in columns if c["type"] == "date"), None)
    if date_col:
        months = defaultdict(lambda: [0.0, 0])
        for d, val in zip(parsed[date_col], metric_values):
            if d is not None and val is not None:
                months[d.strftime("%Y-%m")][0] += val
                months[d.strftime("%Y-%m")][1] += 1
        series = [{"month": m, "total": r2(v[0]), "rows": v[1]} for m, v in sorted(months.items())][-36:]
        trend = {"date_column": date_col, "by_month": series}
        if len(series) >= 2:
            best = max(series, key=lambda s: s["total"])
            worst = min(series, key=lambda s: s["total"])
            trend.update(
                best_month=best["month"], worst_month=worst["month"],
                last_vs_previous_month_pct=pct_change(series[-2]["total"], series[-1]["total"]),
                last_vs_first_month_pct=pct_change(series[0]["total"], series[-1]["total"]),
                note_last_month_rows=series[-1]["rows"],  # a short last month may just be incomplete
                note_typical_month_rows=r2(statistics.median(s["rows"] for s in series)),
            )
        result["monthly_trend"] = trend
    return result


def sample_rows(header, rows, n=5, max_len=60):
    """A few example rows so the writer understands what the data looks like (cells shortened)."""
    return [{h: (r[i] if i < len(r) else "")[:max_len] for i, h in enumerate(header)} for r in rows[:n]]
