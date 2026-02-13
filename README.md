# Marigold Capital Advisors — Quantitative Developer Assessment

Submission for the hands-on technical assessment: 20-day rolling momentum and top-5 tickers by date.

---

## Deliverables (assignment checklist)

| Requirement | Status | Where |
|-------------|--------|--------|
| Compute 20-day rolling momentum per ticker: `(price today / price 20 days ago) − 1` | Done | `momentum_engine.compute_top5_momentum_for_date` (uses that formula per ticker) |
| Function that returns the top 5 tickers by momentum for a given date | Done | `momentum_engine.compute_top5_momentum_for_date(rows, target_date, dates, date_to_index)` → list of `(ticker, momentum)` |
| Tests for edge cases identified in the data | Done | **test_momentum.py** — tests for all edge cases listed below (run: `python -m pytest test_momentum.py` or `python -m unittest test_momentum`) |

---

## Files in this repo

| File | Purpose |
|------|--------|
| **momentum_engine.py** | Core logic: clean raw CSV → clean CSV, load prices, compute 20-day momentum, top-5 for a date. No stdin/stdout. |
| **cli.py** | Interactive CLI: prompts for date (YYYY-MM-DD), shows top 5 (from cache or computed), loop until quit. |
| **momentum_app.py** | Entry point: runs `cli.main()` (so `python momentum_app.py` or `python cli.py`). |
| **test_momentum.py** | Tests for edge cases identified in the data (see *Edge cases* and *Testing* below). |
| **stock_prices_1.csv** | Input: daily closing prices (date, ticker, close_price). Provided with the assignment. |
| **stock_prices_2.csv** | Generated: cleaned version of `stock_prices_1.csv` (invalid/duplicate rows removed). Do not commit; regenerated on run. |
| **momentum_results.json** | Generated: cache of date → top 5 (ticker, momentum). Do not commit; regenerated on run. |

---

## Workflow

1. **One-time clean (on startup)**  
   Read `stock_prices_1.csv` → drop missing/invalid prices, resolve duplicate (date, ticker) by keeping last → write `stock_prices_2.csv`. Log what was removed.

2. **Load and prepare**  
   Load `stock_prices_2.csv` into a list of `(date, ticker, price)`. Build ordered list of trading dates and a `date → index` map for O(1) lookups.

3. **Interactive loop**  
   Prompt: *Date (YYYY-MM-DD)*.  
   - If `quit` / `exit` / `q`: exit.  
   - If date is in `momentum_results.json`: print cached top 5.  
   - Else: compute top 5 via 20-day momentum, append to cache, save JSON, print result.  
   Repeat.

4. **Momentum and top-5**  
   For a given date: index in trading-day list; date 20 trading days ago; for each ticker with both prices and positive price 20d ago, momentum = `(price_today / price_20d_ago) - 1`. Sort by momentum desc, tie-break by ticker; return first 5.

---

## How to run

**Requirements:** Python 3. No extra packages.

Place `stock_prices_1.csv` in this directory (or ensure the path in `momentum_engine.py` points to it).

```bash
python momentum_app.py
# or
python cli.py
```

Then enter dates (e.g. `2024-06-14`) or `q` to quit.

---

## Using the “top 5” function directly

The assignment asks for a **function** that returns the top 5 tickers by momentum for a given date. That function is:

```python
from momentum_engine import (
    load_clean_prices,
    get_trading_dates_ordered,
    build_date_to_index,
    compute_top5_momentum_for_date,
)

# One-time: ensure clean data exists, then load and prepare
# (If stock_prices_2.csv doesn't exist, run clean_and_save_prices() first.)
rows = load_clean_prices()
dates = get_trading_dates_ordered(rows)
date_to_index = build_date_to_index(dates)

# For a given date (e.g. "2024-06-14")
result = compute_top5_momentum_for_date(rows, "2024-06-14", dates, date_to_index)
# result is None (date not in data), [] (insufficient history), or list of (ticker, momentum)
```

Return convention:

- **None** — date not in the dataset (e.g. weekend or out of range).
- **[]** — date in dataset but fewer than 20 trading days before it (cannot compute 20d momentum).
- **[(ticker, momentum), ...]** — up to 5 pairs, sorted by momentum descending, ties broken by ticker.

---

## Edge cases and how they are handled

The following edge cases were identified in the data and are handled in code; each is covered by tests in **test_momentum.py**.

| # | Edge case | Handling |
|---|-----------|----------|
| 1–2 | Missing ticker on some dates (e.g. TICK12, TICK47) | Momentum only where both “today” and “20d ago” prices exist; fewer than 50 tickers possible. |
| 3 | Empty close price (e.g. TICK38 on 4 dates) | Cleaning drops invalid/missing prices; count logged. |
| 4 | Duplicate (date, ticker) | Cleaning keeps last occurrence; count logged. |
| 5–6 | Date outside range / not a trading day | Treated as “date not in data”; return None and user message. |
| 7 | Insufficient history (first 20 trading days) | Return []; message; no cache. |
| 8 | Ticker with no valid momentum on a date | Omitted from ranking; “Only N tickers had valid momentum” when N < 5. |
| 9 | Ties in momentum | Sort by `(-momentum, ticker)` for deterministic order. |
| 10 | Zero price 20 days ago | Skip that ticker (`p_20 <= 0`). |
| 11 | Trailing empty line in CSV | Cleaning skips empty lines. |
| 12 | Non-numeric close_price | Cleaning: try float; on failure drop row and count. |

---

## Features and design choices

- **Data cleaning:** One-time step from raw CSV to clean CSV; logs removed rows and duplicate resolution.
- **Separation of concerns:** `momentum_engine.py` = logic only; `cli.py` = I/O and flow (easy to test engine, add another UI).
- **Date → index map:** Built once per session for O(1) date lookups instead of repeated `list.index()`.
- **Results cache:** JSON cache so repeated queries for the same date don’t recompute.
- **Defensive handling:** Missing/invalid prices, duplicates, out-of-range dates, insufficient history, zero price 20d ago all handled explicitly; no silent failures.
- **Deterministic tie-break:** Same momentum → order by ticker name.

---

## Testing

Run the edge-case tests (no extra packages required; uses Python’s built-in `unittest`):

```bash
python -m unittest test_momentum
```

With pytest (optional):

```bash
python -m pytest test_momentum.py -v
```

**test_momentum.py** covers the edge cases listed above:

- **Date not in data** (e.g. weekend, out of range) → `compute_top5_momentum_for_date` returns `None`.
- **Insufficient history** (fewer than 20 trading days before date) → returns `[]`.
- **Valid date** → returns up to 5 `(ticker, momentum)` pairs; momentum = `(price_today / price_20d_ago) - 1`; sort by momentum desc, tie-break by ticker.
- **Missing ticker** on target date or 20d-ago date → that ticker excluded from result (fewer than 5 can be returned).
- **Zero price 20 days ago** → that ticker skipped (no division).
- **Ties in momentum** → deterministic order by ticker name.
- **Cleaning step:** empty/missing price dropped; duplicate (date, ticker) kept last; empty lines and non-numeric price dropped; log messages mention removed rows.

---

## What to exclude before pushing to GitHub

**Remove or add to `.gitignore` so they are not committed:**

1. **stock_prices_2.csv** — Generated by the app from `stock_prices_1.csv`. Regenerated on every run.
2. **momentum_results.json** — Generated cache. Regenerated as users query dates.

**Optional (if repo size or privacy is a concern):**

3. **stock_prices_1.csv** — Provided with the assignment; the reviewer may use their own copy. If you omit it, the README should state “Place `stock_prices_1.csv` in this directory before running.”

Suggested `.gitignore`:

```
stock_prices_2.csv
momentum_results.json
```

Add `stock_prices_1.csv` to `.gitignore` only if you decide not to commit the data file.
