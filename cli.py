"""
CLI for momentum app: prompts for dates and displays top 5 tickers by 20-day momentum.
Uses momentum_engine for all logic.
"""

from momentum_engine import (
    clean_and_save_prices,
    load_clean_prices,
    get_trading_dates_ordered,
    build_date_to_index,
    compute_top5_momentum_for_date,
    load_results,
    save_results,
)


def main():
    # --- Step 1: One-time clean and save ---
    print("Step 1: Cleaning data (stock_prices_1 -> stock_prices_2)...")
    try:
        rows_written, log = clean_and_save_prices()
        for msg in log:
            print(f"  {msg}")
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        return
    print()

    rows = load_clean_prices()
    if not rows:
        print("No clean data to work with.")
        return

    # Precompute date -> index once for O(1) lookups in the loop
    dates = get_trading_dates_ordered(rows)
    date_to_index = build_date_to_index(dates)

    print("Enter a date (YYYY-MM-DD) for top 5 tickers by 20-day momentum.")
    print("Type 'quit', 'exit', or 'q' to stop.\n")
    results = load_results()

    while True:
        date_input = input("Date: ").strip()
        if not date_input:
            continue
        if date_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        if date_input in results:
            print(f"\nResult for {date_input} (from cache):")
            cached = results[date_input]
            if isinstance(cached, list):
                for i, item in enumerate(cached, 1):
                    if isinstance(item, dict):
                        print(f"  {i}. {item.get('ticker', item)}  momentum: {item.get('momentum', '')}")
                    else:
                        print(f"  {i}. {item}")
            else:
                print(f"  {cached}")
        else:
            top5 = compute_top5_momentum_for_date(
                rows, date_input, dates, date_to_index
            )
            if top5 is None:
                print(f"\nNo data for date {date_input}. Use a trading day between 2023-01-03 and 2024-12-31.")
            elif len(top5) == 0:
                print(f"\nInsufficient history for {date_input}. Need at least 20 trading days before this date (e.g. use from late Jan 2023 onward).")
            else:
                to_store = [{"ticker": t, "momentum": round(m, 6)} for t, m in top5]
                results[date_input] = to_store
                save_results(results)
                print(f"\nResult for {date_input} (computed and saved):")
                for i, (ticker, mom) in enumerate(top5, 1):
                    print(f"  {i}. {ticker}  momentum: {mom:.6f}")
                if len(top5) < 5:
                    print(f"  (Only {len(top5)} tickers had valid momentum for this date.)")
        print()


if __name__ == "__main__":
    main()
