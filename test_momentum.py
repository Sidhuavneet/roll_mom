"""
Tests for edge cases identified in the stock price data.
Covers: date not in data, insufficient history, momentum formula, missing ticker,
zero price 20d ago, ties, and cleaning (empty price, duplicate, empty line, non-numeric).
"""

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from momentum_engine import (
    build_date_to_index,
    clean_and_save_prices,
    compute_top5_momentum_for_date,
    get_trading_dates_ordered,
)


# --- In-memory fixtures for compute_top5_momentum_for_date (no file I/O) ---

def make_rows(dates, tickers_with_prices):
    """tickers_with_prices: list of (ticker, [(date, price), ...])."""
    rows = []
    for ticker, day_prices in tickers_with_prices:
        for d, p in day_prices:
            rows.append((d, ticker, p))
    return sorted(rows, key=lambda x: (x[0], x[1]))


class TestComputeTop5EdgeCases(unittest.TestCase):
    """Edge cases 5, 6, 7, 1, 2, 8, 10, 9."""

    def test_date_not_in_data_returns_none(self):
        """Date outside range or not a trading day → None (edge 5, 6)."""
        rows = make_rows(
            ["2023-01-03", "2023-01-04"],
            [("TICK01", [("2023-01-03", 100.0), ("2023-01-04", 101.0)])],
        )
        dates = get_trading_dates_ordered(rows)
        date_to_index = build_date_to_index(dates)
        result = compute_top5_momentum_for_date(
            rows, "2023-01-05", dates, date_to_index, window=1
        )
        self.assertIsNone(result)
        result = compute_top5_momentum_for_date(
            rows, "2022-12-01", dates, date_to_index, window=1
        )
        self.assertIsNone(result)

    def test_insufficient_history_returns_empty_list(self):
        """Fewer than 20 trading days before date → [] (edge 7)."""
        # 5 dates, window=20: index 0..4, so no date has 20 days before it
        dates = [f"2023-01-0{i}" for i in range(3, 8)]
        tickers_with_prices = [
            ("TICK01", [(d, 100.0) for d in dates]),
        ]
        rows = make_rows(dates, tickers_with_prices)
        date_to_index = build_date_to_index(dates)
        # Ask for last date: index 4, need index >= 20 for window=20
        result = compute_top5_momentum_for_date(
            rows, "2023-01-07", dates, date_to_index, window=20
        )
        self.assertEqual(result, [])

    def test_valid_date_returns_top5_momentum_formula(self):
        """Valid date → list of (ticker, momentum); formula (price_today/price_20d_ago)-1 (edge 8)."""
        # 22 dates so we have index 20 and 21; window=20 so date at 21 has 20d ago at 0
        dates = [f"2023-01-{i:02d}" for i in range(1, 24)]  # 01..23
        tickers_with_prices = [
            ("TICK01", [(d, 100.0) for d in dates]),
            ("TICK02", [(d, 50.0 if d != "2023-01-22" else 60.0) for d in dates]),  # 60/50 - 1 = 0.2
        ]
        rows = make_rows(dates, tickers_with_prices)
        date_to_index = build_date_to_index(dates)
        result = compute_top5_momentum_for_date(
            rows, "2023-01-22", dates, date_to_index, window=20
        )
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result), 1)
        # TICK02: price today 60, 20d ago 50 → momentum 0.2
        tick02 = next((r for r in result if r[0] == "TICK02"), None)
        self.assertIsNotNone(tick02)
        self.assertAlmostEqual(tick02[1], (60.0 / 50.0) - 1, places=6)

    def test_missing_ticker_on_date_excluded(self):
        """Ticker missing on target date or 20d ago → excluded (edge 1, 2)."""
        # Need 21+ dates so index(target) >= 20; target at index 20, 20d ago at index 0
        dates = [f"2023-01-{i:02d}" for i in range(1, 23)]  # 01..22 (22 days)
        # TICK01 has all dates; TICK02 missing on last date (2023-01-22)
        tickers_with_prices = [
            ("TICK01", [(d, 100.0) for d in dates]),
            ("TICK02", [(d, 50.0) for d in dates[:-1]]),  # no 2023-01-22
        ]
        rows = make_rows(dates, tickers_with_prices)
        date_to_index = build_date_to_index(dates)
        result = compute_top5_momentum_for_date(
            rows, "2023-01-22", dates, date_to_index, window=20
        )
        tickers = [r[0] for r in result]
        self.assertIn("TICK01", tickers)
        self.assertNotIn("TICK02", tickers)

    def test_zero_price_20d_ago_ticker_excluded(self):
        """Zero (or negative) price 20 days ago → that ticker skipped (edge 10)."""
        dates = [f"2023-01-{i:02d}" for i in range(1, 23)]
        # For target 2023-01-22 (index 21), 20d ago is dates[1] = 2023-01-02
        date_20_ago = dates[1]
        # TICK01: price 0 on date_20_ago → skip; TICK02: valid
        tickers_with_prices = [
            ("TICK01", [(d, 0.0 if d == date_20_ago else 100.0) for d in dates]),
            ("TICK02", [(d, 50.0 if d == date_20_ago else 60.0) for d in dates]),
        ]
        rows = make_rows(dates, tickers_with_prices)
        date_to_index = build_date_to_index(dates)
        result = compute_top5_momentum_for_date(
            rows, "2023-01-22", dates, date_to_index, window=20
        )
        tickers = [r[0] for r in result]
        self.assertNotIn("TICK01", tickers)
        self.assertIn("TICK02", tickers)

    def test_ties_broken_by_ticker(self):
        """Same momentum → deterministic order by ticker (edge 9)."""
        dates = [f"2023-01-{i:02d}" for i in range(1, 23)]
        # Both tickers: 110/100 - 1 = 0.1 on last date vs 20d ago
        tickers_with_prices = [
            ("TICK_B", [(dates[0], 100.0)] + [(d, 110.0) for d in dates[1:]]),
            ("TICK_A", [(dates[0], 100.0)] + [(d, 110.0) for d in dates[1:]]),
        ]
        rows = make_rows(dates, tickers_with_prices)
        date_to_index = build_date_to_index(dates)
        result = compute_top5_momentum_for_date(
            rows, "2023-01-22", dates, date_to_index, window=20
        )
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0][1], result[1][1], places=6)
        # Tie-break: ticker ascending → TICK_A before TICK_B
        self.assertEqual(result[0][0], "TICK_A")
        self.assertEqual(result[1][0], "TICK_B")


class TestCleaningEdgeCases(unittest.TestCase):
    """Edge cases 3, 4, 11, 12: cleaning step."""

    def _run_clean_with_fixture(self, csv_content):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f_raw:
            f_raw.write(csv_content)
            f_raw.flush()
            raw_path = Path(f_raw.name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f_clean:
            clean_path = Path(f_clean.name)
        try:
            import momentum_engine as eng
            with patch.object(eng, "PRICES_RAW", raw_path), patch.object(eng, "PRICES_CLEAN", clean_path):
                rows_written, log = clean_and_save_prices()
            with open(clean_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            return rows_written, log, rows
        finally:
            raw_path.unlink(missing_ok=True)
            clean_path.unlink(missing_ok=True)

    def test_clean_drops_empty_or_invalid_price(self):
        """Empty or invalid close_price dropped; logged (edge 3)."""
        content = """date,ticker,close_price
2023-01-03,TICK01,100.5
2023-01-03,TICK02,
2023-01-03,TICK03,50.0
"""
        _, log, rows = self._run_clean_with_fixture(content)
        self.assertEqual(len(rows), 2)
        tickers = {r["ticker"] for r in rows}
        self.assertIn("TICK01", tickers)
        self.assertIn("TICK03", tickers)
        self.assertNotIn("TICK02", tickers)
        log_str = " ".join(log).lower()
        self.assertIn("removed", log_str)
        self.assertTrue("invalid" in log_str or "missing" in log_str)

    def test_clean_keeps_last_on_duplicate_date_ticker(self):
        """Duplicate (date, ticker) → keep last occurrence (edge 4)."""
        content = """date,ticker,close_price
2023-01-03,TICK01,100.0
2023-01-03,TICK01,200.0
"""
        _, log, rows = self._run_clean_with_fixture(content)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["close_price"], "200.0")
        log_str = " ".join(log)
        self.assertIn("duplicate", log_str.lower())

    def test_clean_skips_empty_line(self):
        """Trailing or empty line skipped (edge 11)."""
        content = """date,ticker,close_price
2023-01-03,TICK01,100.0

2023-01-04,TICK01,101.0
"""
        _, _, rows = self._run_clean_with_fixture(content)
        self.assertEqual(len(rows), 2)

    def test_clean_drops_non_numeric_price(self):
        """Non-numeric close_price dropped (edge 12)."""
        content = """date,ticker,close_price
2023-01-03,TICK01,100.0
2023-01-03,TICK02,abc
2023-01-03,TICK03,50.0
"""
        _, log, rows = self._run_clean_with_fixture(content)
        self.assertEqual(len(rows), 2)
        tickers = {r["ticker"] for r in rows}
        self.assertNotIn("TICK02", tickers)
        log_str = " ".join(log)
        self.assertIn("Removed", log_str)


if __name__ == "__main__":
    unittest.main()
