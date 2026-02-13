"""
Momentum engine: data cleaning, loading, and 20-day momentum computation.
No I/O to stdin/stdout; pure logic for reuse by CLI, tests, or other callers.
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

# Paths (callers can override via env or args if needed)
BASE = Path(__file__).resolve().parent
PRICES_RAW = BASE / "stock_prices_1.csv"
PRICES_CLEAN = BASE / "stock_prices_2.csv"
RESULTS_FILE = BASE / "momentum_results.json"


def clean_and_save_prices():
    """
    Read stock_prices_1.csv, clean data, write stock_prices_2.csv.
    Returns (rows_written, log_messages).
    """
    if not PRICES_RAW.exists():
        raise FileNotFoundError(f"Input file not found: {PRICES_RAW}")

    log = []
    rows_read = 0
    empty_or_invalid_price = 0
    duplicate_keys = {}

    last_seen = {}
    for line in open(PRICES_RAW, newline="", encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 3:
            empty_or_invalid_price += 1
            log.append(f"Skipped malformed line (expected 3 columns): {line[:80]!r}")
            continue
        date_str, ticker, price_str = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if date_str.lower() == "date" and ticker.lower() == "ticker":
            continue
        rows_read += 1
        try:
            price = float(price_str)
        except ValueError:
            empty_or_invalid_price += 1
            continue
        if price <= 0:
            empty_or_invalid_price += 1
            continue
        key = (date_str, ticker)
        if key in last_seen:
            duplicate_keys[key] = duplicate_keys.get(key, 1) + 1
        last_seen[key] = price

    num_duplicate_pairs = len(duplicate_keys)
    total_duplicate_occurrences = sum(duplicate_keys.values())
    duplicate_rows_dropped = total_duplicate_occurrences - num_duplicate_pairs

    with open(PRICES_CLEAN, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "ticker", "close_price"])
        for (date_str, ticker) in sorted(last_seen.keys()):
            w.writerow([date_str, ticker, last_seen[(date_str, ticker)]])

    rows_written = len(last_seen)
    log.append(f"Read {rows_read} data rows from {PRICES_RAW.name}.")
    if empty_or_invalid_price:
        log.append(f"Removed {empty_or_invalid_price} rows with missing or invalid close_price.")
    if duplicate_rows_dropped:
        log.append(f"Resolved {num_duplicate_pairs} duplicate (date, ticker) pairs by keeping last value ({duplicate_rows_dropped} duplicate rows dropped).")
    log.append(f"Written {rows_written} rows to {PRICES_CLEAN.name}.")
    return rows_written, log


def load_clean_prices():
    """Load clean prices into list of (date, ticker, price)."""
    rows = []
    with open(PRICES_CLEAN, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for rec in r:
            if not rec.get("date") or not rec.get("close_price"):
                continue
            try:
                price = float(rec["close_price"])
            except ValueError:
                continue
            rows.append((rec["date"], rec["ticker"], price))
    return rows


def get_trading_dates_ordered(rows):
    """Unique trading dates in order of appearance."""
    seen = set()
    out = []
    for d, _, _ in rows:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def build_date_to_index(dates):
    """Precompute date -> index for O(1) lookup. Call once per session."""
    return {d: i for i, d in enumerate(dates)}


def compute_top5_momentum_for_date(rows, target_date, dates, date_to_index, window=20):
    """
    For target_date, compute 20-day momentum per ticker; return top 5 (ticker, momentum).
    momentum = (price_today / price_20_days_ago) - 1
    Requires precomputed dates and date_to_index from get_trading_dates_ordered + build_date_to_index.
    Returns None if date not in data, [] if insufficient history, else list of (ticker, momentum).
    """
    idx = date_to_index.get(target_date)
    if idx is None:
        return None
    if idx < window:
        return []

    date_20_ago = dates[idx - window]
    by_ticker = defaultdict(dict)
    for d, ticker, price in rows:
        by_ticker[ticker][d] = price

    momentums = []
    for ticker, day_prices in by_ticker.items():
        p_today = day_prices.get(target_date)
        p_20 = day_prices.get(date_20_ago)
        if p_today is None or p_20 is None or p_20 <= 0:
            continue
        mom = (p_today / p_20) - 1
        momentums.append((ticker, mom))

    momentums.sort(key=lambda x: (-x[1], x[0]))
    return momentums[:5]


def load_results():
    if not RESULTS_FILE.exists():
        return {}
    try:
        with open(RESULTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_results(results):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
