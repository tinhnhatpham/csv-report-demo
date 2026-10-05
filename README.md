# Sales report generator (CSV → written report)

Upload a CSV export of sales, orders or expenses and get the same clear report every time: the
key numbers, the trends, and what to look into next. Built as a demo for small teams.

**Live demo:** https://reports.logicagentry.com (click "Try the sample data" for a 6-month coffee
shop report in about 10 seconds; the first request after a quiet spell can take up to a minute
while the free server wakes up)

**Test results:** [TESTING.md](TESTING.md)

## How it works

```
CSV upload ──> stats.py (code)            ──> writer.py (Claude)        ──> report + the numbers table
               parses the file, works out       gets ONLY the statistics       title, overview, findings,
               every total, share and           + 5 sample rows, writes        caveats, next steps
               monthly change                   the sentences around them      (structured JSON)
```

- **The AI never does the maths.** Every number is calculated by code, and Claude is told to use
  only numbers from the statistics. The page shows the statistics table under the report, so
  anyone can check a figure. In testing, every number in the reports matched the code.
- **Privacy:** the file is processed in memory and never stored. Claude sees summary statistics
  and 5 example rows, never the whole file. The page shows exactly what the AI saw.
- **Same format every time:** the report comes back as structured JSON (fixed sections), so it
  looks the same for everyone on the team, with no prompt writing.
- **Real-world files:** Excel's Windows encoding, `;` or tab delimiters, `$1,250.00`,
  `1.250,00 €`, `1 250,00`, `(45.00)` negatives and percentages are all read correctly. Text in the
  file is treated as data: instructions hidden in a cell are ignored.
- **Cost caps:** 1 MB / 20,000 rows / 40 columns per file, 10 reports per hour per visitor and
  150 per day for the whole site. A report costs about $0.01 with Claude Sonnet.

### Why not just paste the file into an AI chat?

For one person and one file, an AI chat works fine. This is for a team: one click instead of
prompt writing, the same format every time, numbers that can be checked, only summaries sent to
the AI, and a fixed cost. It can also be embedded in an internal tool or run on a schedule.

## Stack

Python / Flask on Render · React 19 + Vite on Netlify · Claude API (Sonnet 5.5, structured outputs)

## Project layout

| Path | What |
|---|---|
| `backend/stats.py` | CSV parsing and all the statistics (types, totals, breakdowns, monthly trend) |
| `backend/writer.py` | Prompt, JSON schema for the report, Claude call |
| `backend/app.py` | Upload endpoint, limits, rate limiting, CORS |
| `backend/make_sample.py` | Generates the fictional coffee shop sample data |
| `web/src/App.jsx` | Upload page, report view, "what the AI saw" panel |

## Run locally

Backend: copy `backend/.env.example` to `backend/.env` and add your Anthropic API key, then
`pip install -r requirements.txt` and `python app.py` (port 5002).
Web: copy `web/.env.example` to `web/.env`, then `npm install` and `npm run dev` (port 5173).

Built by [LogicAgentry](https://logicagentry.com).
