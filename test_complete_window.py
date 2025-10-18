"""
Quick test to find and analyze a window with complete data.
"""

from database import Database
from windows import (
    WindowDefinition,
    Window,
    compute_statistics,
    generate_window_definitions_non_overlapping_snapped
)
from datetime import date


def main():
    db = Database('pnlrg.db')
    db.connect()

    # Get first program
    program = db.fetch_one("SELECT id, program_name FROM programs WHERE program_name != 'Benchmarks' LIMIT 1")
    program_id = program['id']
    program_name = program['program_name']

    # Get SP500 benchmark only (starts in 1973)
    sp500 = db.fetch_one("SELECT id, name FROM markets WHERE name = 'SP500'")

    print(f"Program: {program_name}")
    print(f"Benchmark: {sp500['name']}")

    # Get actual data range
    data_range = db.fetch_one("SELECT MAX(date) as max_date FROM pnl_records WHERE program_id = ?", (program_id,))
    max_date = date.fromisoformat(data_range['max_date'])

    print(f"Data goes to: {max_date}")

    # Generate 5-year windows from 1990 to 2010 (ensure windows don't extend past data)
    windows = generate_window_definitions_non_overlapping_snapped(
        start_date=date(1990, 1, 1),
        end_date=date(2010, 12, 31),  # Windows end before data ends
        window_length_years=5,
        program_ids=[program_id],
        benchmark_ids=[sp500['id']],
        window_set_name="complete_5yr"
    )

    print(f"\nGenerated {len(windows)} windows from 1990-2015\n")

    # Find first complete window
    for win_def in windows:
        window = Window(win_def, db)

        print(f"{win_def.name}: {win_def.start_date} to {win_def.end_date}")
        print(f"  Data Complete: {'YES' if window.data_is_complete else 'NO'}")

        if window.data_is_complete:
            print("\n  === COMPLETE WINDOW FOUND ===\n")

            # Program statistics
            prog_stats = compute_statistics(window, program_id, entity_type='manager')
            print(f"  {program_name}:")
            print(f"    Observations:              {prog_stats.count}")
            print(f"    Mean Monthly Return:       {prog_stats.mean:>8.2%}")
            print(f"    Median Monthly Return:     {prog_stats.median:>8.2%}")
            print(f"    Std Dev:                   {prog_stats.std_dev:>8.2%}")
            print(f"    Cumulative (Compounded):   {prog_stats.cumulative_return_compounded:>8.2%}")
            print(f"    Cumulative (Simple):       {prog_stats.cumulative_return_simple:>8.2%}")
            print(f"    Max DD (Compounded):       {prog_stats.max_drawdown_compounded:>8.2%}")
            print(f"    Max DD (Simple):          ${prog_stats.max_drawdown_simple:>8,.2f}")

            # Benchmark statistics
            bm_stats = compute_statistics(window, sp500['id'], entity_type='benchmark')
            print(f"\n  {sp500['name']}:")
            print(f"    Observations:              {bm_stats.count}")
            print(f"    Mean Monthly Return:       {bm_stats.mean:>8.2%}")
            print(f"    Median Monthly Return:     {bm_stats.median:>8.2%}")
            print(f"    Std Dev:                   {bm_stats.std_dev:>8.2%}")
            print(f"    Cumulative (Compounded):   {bm_stats.cumulative_return_compounded:>8.2%}")
            print(f"    Cumulative (Simple):       {bm_stats.cumulative_return_simple:>8.2%}")
            print(f"    Max DD (Compounded):       {bm_stats.max_drawdown_compounded:>8.2%}")
            print(f"    Max DD (Simple):          ${bm_stats.max_drawdown_simple:>8,.2f}")

            # Calculate outperformance
            outperf = prog_stats.cumulative_return_compounded - bm_stats.cumulative_return_compounded
            print(f"\n  Outperformance: {outperf:>8.2%}")

            break

    db.close()


if __name__ == "__main__":
    main()
