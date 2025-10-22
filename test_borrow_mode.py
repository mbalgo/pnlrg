"""Test script to verify borrow_mode functionality in Windows framework."""

from database import Database
from datetime import date
from windows import generate_window_definitions_non_overlapping_reverse

def main():
    db = Database()

    try:
        # Get Alphabet MFT program
        program = db.fetch_one("""
            SELECT p.id
            FROM programs p
            JOIN managers m ON p.manager_id = m.id
            WHERE m.manager_name = 'Alphabet' AND p.program_name = 'MFT'
        """)

        if not program:
            print("Error: Could not find Alphabet MFT program!")
            return

        program_id = program['id']

        # Get date range
        date_range = db.fetch_one("""
            SELECT MIN(date) as min_date, MAX(date) as max_date
            FROM pnl_records
            WHERE program_id = ? AND resolution = 'daily'
        """, (program_id,))

        min_date = date.fromisoformat(date_range['min_date'])
        max_date = date.fromisoformat(date_range['max_date'])

        print(f"Actual Data Range: {min_date} to {max_date}")
        print(f"Total span: {(max_date - min_date).days / 365.25:.2f} years")
        print()

        # Test 1: Simulated scenario with ~14 years (should show borrowing)
        test_min_date = date(2006, 1, 1)
        test_max_date = date(2019, 12, 31)  # ~14 years

        print("TEST 1: Simulated 14-year scenario")
        print(f"  Date Range: {test_min_date} to {test_max_date}")
        print(f"  Span: {(test_max_date - test_min_date).days / 365.25:.2f} years")
        print()

        run_test(db, program_id, test_min_date, test_max_date)

        print("\n" + "=" * 70)
        print()

        # Test 2: Actual Alphabet data (may or may not show borrowing depending on total span)
        print("TEST 2: Actual Alphabet MFT data")
        print(f"  Date Range: {min_date} to {max_date}")
        print(f"  Span: {(max_date - min_date).days / 365.25:.2f} years")
        print()

        run_test(db, program_id, min_date, max_date)

    finally:
        db.close()


def run_test(db, program_id, min_date, max_date):
    """Run test with given date range."""
    # Test borrow_mode=False
    print("  borrow_mode=False:")
    print("  " + "-" * 66)
    windows_no_borrow = generate_window_definitions_non_overlapping_reverse(
        earliest_date=min_date,
        latest_date=max_date,
        window_length_years=5,
        program_ids=[program_id],
        benchmark_ids=[],
        borrow_mode=False
    )

    for i, win in enumerate(windows_no_borrow, 1):
        years = (win.end_date - win.start_date).days / 365.25
        print(f"    Window {i}: {win.start_date} to {win.end_date} ({years:.2f} years)")

    print()

    # Test borrow_mode=True
    print("  borrow_mode=True:")
    print("  " + "-" * 66)
    windows_with_borrow = generate_window_definitions_non_overlapping_reverse(
        earliest_date=min_date,
        latest_date=max_date,
        window_length_years=5,
        program_ids=[program_id],
        benchmark_ids=[],
        borrow_mode=True
    )

    for i, win in enumerate(windows_with_borrow, 1):
        years = (win.end_date - win.start_date).days / 365.25
        borrowed_msg = ""
        if win.borrowed_data_start_date and win.borrowed_data_end_date:
            borrowed_years = (win.borrowed_data_end_date - win.borrowed_data_start_date).days / 365.25
            borrowed_msg = f" [BORROWED: {win.borrowed_data_start_date} to {win.borrowed_data_end_date} ({borrowed_years:.2f} years)]"
        print(f"    Window {i}: {win.start_date} to {win.end_date} ({years:.2f} years){borrowed_msg}")


if __name__ == "__main__":
    main()
