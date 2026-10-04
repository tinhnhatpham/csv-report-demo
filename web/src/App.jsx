import { useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5002";
const MAX_FILE_BYTES = 1024 * 1024; // same cap as the backend

function fmt(n) {
  return typeof n === "number" ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n ?? "";
}

function reportAsText(r) {
  return [
    r.title,
    "",
    r.overview,
    "",
    "Key findings",
    ...r.key_findings.map((f) => `- ${f.headline} ${f.detail}`),
    ...(r.caveats.length ? ["", "Keep in mind", ...r.caveats.map((c) => `- ${c}`)] : []),
    "",
    "Next steps",
    ...r.next_steps.map((s) => `- ${s}`),
  ].join("\n");
}

export default function App() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [copied, setCopied] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  async function run({ file, sample }) {
    setError("");
    setResult(null);
    setCopied(false);
    if (file && file.size > MAX_FILE_BYTES) return setError("That file is too big. This demo handles files up to 1 MB.");
    setBusy(true);
    setStage("Calculating the numbers…");
    const writing = setTimeout(() => setStage("Writing the summary… (this takes about 10-30 seconds)"), 2500);
    const waking = setTimeout(
      () => setStage("Still working. The free demo server may be waking up, which can take up to a minute."),
      40000
    );
    try {
      let body;
      if (file) {
        body = new FormData();
        body.append("file", file);
      }
      let res;
      try {
        res = await fetch(`${API_URL}/api/report${sample ? "?sample=1" : ""}`, {
          method: "POST",
          body,
          signal: AbortSignal.timeout(150000),
        });
      } catch {
        throw new Error("Can't reach the server. Please try again in a minute.");
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Something went wrong. Please try again.");
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      clearTimeout(writing);
      clearTimeout(waking);
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && !busy) run({ file });
  }

  async function copyReport() {
    try {
      await navigator.clipboard.writeText(reportAsText(result.report));
      setCopied(true);
    } catch {
      setError("Couldn't copy. Select the text and copy it by hand.");
    }
  }

  function downloadReport() {
    const blob = new Blob([reportAsText(result.report)], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = result.filename.replace(/\.(csv|txt)$/i, "") + "-summary.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="wrap">
      <header>
        <p className="eyebrow">Demo</p>
        <h1>Turn a spreadsheet into a summary you can read in a minute.</h1>
        <p className="lead">
          Upload a CSV of sales, orders or expenses. You get the key numbers, trends and what to look into next, in
          plain English.
        </p>
      </header>

      <section
        className={`card upload ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <p className="drop-hint">Drop a .csv file here, or</p>
        <div className="row">
          <label className={`btn ${busy ? "disabled" : ""}`}>
            Choose a CSV file
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              disabled={busy}
              onChange={(e) => e.target.files?.[0] && run({ file: e.target.files[0] })}
              hidden
            />
          </label>
          <button className="btn ghost" onClick={() => run({ sample: true })} disabled={busy}>
            Try the sample data
          </button>
        </div>
        <p className="muted small">
          Sample: 6 months of sales for a made-up coffee shop (
          <a href="/sample_sales.csv" download>
            download it
          </a>
          ). Up to 1 MB / 20,000 rows. Your file is processed in memory and not stored.
        </p>
      </section>

      {busy && (
        <p className="status" role="status">
          <span className="spinner" aria-hidden="true" /> {stage}
        </p>
      )}
      {error && <p className="error">{error}</p>}

      {result && (
        <>
          <article className="card report">
            <div className="report-head">
              <h2>{result.report.title}</h2>
              <div className="row">
                <button className="btn small" onClick={copyReport}>
                  {copied ? "Copied" : "Copy"}
                </button>
                <button className="btn small ghost" onClick={downloadReport}>
                  Download
                </button>
              </div>
            </div>
            <p className="overview">{result.report.overview}</p>

            <h3>Key findings</h3>
            <ol className="findings">
              {result.report.key_findings.map((f, i) => (
                <li key={i}>
                  <strong>{f.headline}</strong> {f.detail}
                </li>
              ))}
            </ol>

            {result.report.caveats.length > 0 && (
              <>
                <h3>Keep in mind</h3>
                <ul>
                  {result.report.caveats.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </>
            )}

            <h3>Next steps</h3>
            <ul>
              {result.report.next_steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
            <p className="muted small">
              Every number above was calculated by code from {result.filename}; the AI only wrote the words. Check them
              against the table below.
            </p>
          </article>

          <Numbers stats={result.stats} />
        </>
      )}

      <footer className="muted small">
        Built by Steven (LogicAgentry) · Python, React and the Claude API
      </footer>
    </div>
  );
}

function Numbers({ stats }) {
  const trend = stats.monthly_trend;
  return (
    <details className="card numbers" open>
      <summary>The numbers behind it</summary>
      <p className="muted small">
        {fmt(stats.rows)} rows · {stats.columns.length} columns
        {stats.main_metric && <> · main metric: <strong>{stats.main_metric}</strong></>}
      </p>

      {trend && (
        <>
          <h4>
            {stats.main_metric} by month ({trend.date_column})
          </h4>
          <table>
            <thead>
              <tr><th>Month</th><th className="num">Total</th><th className="num">Rows</th></tr>
            </thead>
            <tbody>
              {trend.by_month.map((m) => (
                <tr key={m.month}>
                  <td>{m.month}</td><td className="num">{fmt(m.total)}</td><td className="num">{fmt(m.rows)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {stats.breakdowns?.map((b) => (
        <div key={b.by}>
          <h4>{stats.main_metric} by {b.by}</h4>
          <table>
            <thead>
              <tr><th>{b.by}</th><th className="num">Total</th><th className="num">Share</th></tr>
            </thead>
            <tbody>
              {b.groups.map((g) => (
                <tr key={g.group}>
                  <td>{g.group}</td><td className="num">{fmt(g.total)}</td><td className="num">{fmt(g.share_pct)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          {b.groups_not_shown > 0 && <p className="muted small">+ {b.groups_not_shown} smaller groups not shown</p>}
        </div>
      ))}

      <h4>Columns</h4>
      <table>
        <thead>
          <tr><th>Column</th><th>Type</th><th>Details</th></tr>
        </thead>
        <tbody>
          {stats.columns.map((c) => (
            <tr key={c.name}>
              <td>{c.name}</td>
              <td>{c.type}</td>
              <td className="small">
                {c.type === "number" && <>sum {fmt(c.sum)} · average {fmt(c.mean)} · min {fmt(c.min)} · max {fmt(c.max)}</>}
                {c.type === "date" && <>{c.first} to {c.last}</>}
                {c.type === "text" && <>{fmt(c.distinct)} different values</>}
                {c.missing > 0 && <> · {fmt(c.missing)} empty</>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
