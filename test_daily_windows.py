"""
Test script to verify the refactored windows.py framework with daily data.

Tests:
1. Window creation with Alphabet MFT data
2. Daily data fetching
3. Statistics calculation with daily std dev
"""

from database import Database
from windows import WindowDefinition, Window, compute_statistics
from datetime import date

def main():
    db = Database('pnlrg.db')
    db.connect()

    print("=" * 70)
    print("TESTING REFACTORED WINDOWS FRAMEWORK WITH DAILY DATA")
    print("=" * 70)

    # Get Alphabet MFT program
    program = db.fetch_one("""
        SELECT p.id, p.program_name, m.manager_name
        FROM programs p
        JOIN managers m ON p.manager_id = m.id
        WHERE m.manager_name = 'Alphabet' AND p.program_name = 'MFT'
    """)

    if not program:
        print("\nError: Alphabet MFT not found!")
        db.close()
        return

    program_id = program['id']
    print(f"\nTesting with: {program['manager_name']} - {program['program_name']}")
    print(f"Program ID: {program_id}")

    # Create a test window: 1 month (Jan 2015)
    print("\n" + "-" * 70)
    print("TEST 1: Monthly Window (Jan 2015)")
    print("-" * 70)

    win_def = WindowDefinition(
        start_date=date(2015, 1, 1),
        end_date=date(2015, 1, 31),
        program_ids=[program_id],
        benchmark_ids=[],
        name="Jan_2015"
    )

    window = Window(win_def, db)

    # Fetch daily data
    daily_df = window.get_manager_daily_data(program_id)
    print(f"\nDaily data points: {len(daily_df)}")
    if len(daily_df) > 0:
        print(f"Date range: {daily_df['date'].min().date()} to {daily_df['date'].max().date()}")
        print(f"First 3 daily returns: {daily_df['return'].head(3).values}")

    # Compute statistics
    stats = compute_statistics(window, program_id, entity_type='manager')

    print(f"\nStatistics:")
    print(f"  Monthly count: {stats.count}")
    print(f"  Daily count: {stats.daily_count}")
    print(f"  Mean monthly return: {stats.mean*100:.2f}%")
    print(f"  Std dev (annualized from daily): {stats.std_dev*100:.2f}%")
    print(f"  Std dev (raw daily): {stats.daily_std_dev_raw*100:.4f}%")
    print(f"  CAGR: {stats.cagr*100:.2f}%")
    print(f"  Max DD: {stats.max_drawdown_compounded*100:.2f}%")

    # Test a 5-year window
    print("\n" + "-" * 70)
    print("TEST 2: 5-Year Window (2015-2020)")
    print("-" * 70)

    win_def_5yr = WindowDefinition(
        start_date=date(2015, 1, 1),
        end_date=date(2019, 12, 31),
        program_ids=[program_id],
        benchmark_ids=[],
        name="2015-2020"
    )

    window_5yr = Window(win_def_5yr, db)

    # Fetch daily data
    daily_df_5yr = window_5yr.get_manager_daily_data(program_id)
    print(f"\nDaily data points: {len(daily_df_5yr)}")

    # Compute statistics
    stats_5yr = compute_statistics(window_5yr, program_id, entity_type='manager')

    print(f"\nStatistics:")
    print(f"  Monthly count: {stats_5yr.count}")
    print(f"  Daily count: {stats_5yr.daily_count}")
    print(f"  Mean monthly return: {stats_5yr.mean*100:.2f}%")
    print(f"  Std dev (annualized from daily): {stats_5yr.std_dev*100:.2f}%")
    print(f"  Std dev (raw daily): {stats_5yr.daily_std_dev_raw*100:.4f}%")
    print(f"  CAGR (5yr): {stats_5yr.cagr*100:.2f}%")
    print(f"  Max DD: {stats_5yr.max_drawdown_compounded*100:.2f}%")

    print("\n" + "=" * 70)
    print("TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

    db.close()


if __name__ == "__main__":
    main()
