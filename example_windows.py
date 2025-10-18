"""
Example usage of the window-based analysis system.

Demonstrates all window generation types and statistics computation.
"""

from database import Database
from windows import (
    WindowDefinition,
    Window,
    compute_statistics,
    generate_window_definitions_non_overlapping_snapped,
    generate_window_definitions_non_overlapping_not_snapped,
    generate_window_definitions_overlapping,
    generate_window_definitions_overlapping_reverse,
    generate_window_definitions_bespoke
)
from datetime import date


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_statistics(stats, entity_name):
    """Print formatted statistics."""
    print(f"\n{entity_name}:")
    print(f"  Observations:              {stats.count}")
    print(f"  Mean Return:               {stats.mean:>8.2%}")
    print(f"  Median Return:             {stats.median:>8.2%}")
    print(f"  Std Dev:                   {stats.std_dev:>8.2%}")
    print(f"  Cumulative (Compounded):   {stats.cumulative_return_compounded:>8.2%}")
    print(f"  Cumulative (Simple):       {stats.cumulative_return_simple:>8.2%}")
    print(f"  Max DD (Compounded):       {stats.max_drawdown_compounded:>8.2%}")
    print(f"  Max DD (Simple):          ${stats.max_drawdown_simple:>8,.2f}")


def main():
    """Demonstrate all window types and analysis capabilities."""

    # Connect to database
    db = Database('pnlrg.db')
    db.connect()

    print_section("Window-Based Analysis System - Comprehensive Demo")

    # Get available programs and benchmarks
    programs = db.fetch_all("SELECT id, program_name FROM programs WHERE program_name != 'Benchmarks'")
    benchmarks = db.fetch_all("SELECT id, name FROM markets WHERE is_benchmark = 1")

    print("Available Programs:")
    for prog in programs:
        print(f"  {prog['id']}: {prog['program_name']}")

    print("\nAvailable Benchmarks:")
    for bm in benchmarks:
        print(f"  {bm['id']}: {bm['name']}")

    # For this demo, use the first program and a couple benchmarks
    if len(programs) == 0:
        print("\nError: No programs found in database!")
        return

    program_id = programs[0]['id']
    program_name = programs[0]['program_name']

    benchmark_ids = [bm['id'] for bm in benchmarks[:2]]  # First 2 benchmarks
    benchmark_names = {bm['id']: bm['name'] for bm in benchmarks}

    # Determine data range
    data_range = db.fetch_one("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM pnl_records
        WHERE program_id = ?
    """, (program_id,))

    start_date = date.fromisoformat(data_range['min_date'])
    end_date = date.fromisoformat(data_range['max_date'])

    print(f"\nData Range: {start_date} to {end_date}")
    print(f"Analyzing Program: {program_name}")
    print(f"Benchmarks: {', '.join([benchmark_names[bid] for bid in benchmark_ids])}")

    # ==========================================================================
    # 1. NON-OVERLAPPING SNAPPED WINDOWS
    # ==========================================================================
    print_section("1. Non-Overlapping Snapped Windows (5-Year Calendar Periods)")

    windows_5yr = generate_window_definitions_non_overlapping_snapped(
        start_date=start_date,
        end_date=end_date,
        window_length_years=5,
        program_ids=[program_id],
        benchmark_ids=benchmark_ids,
        window_set_name="5yr_calendar"
    )

    print(f"Generated {len(windows_5yr)} windows:")
    for win_def in windows_5yr:
        print(f"  {win_def.name}: {win_def.start_date} to {win_def.end_date}")

    # Analyze first complete 5-year window
    print("\nAnalyzing first complete 5-year window:")
    for win_def in windows_5yr:
        window = Window(win_def, db)
        if window.data_is_complete:
            print(f"\nWindow: {win_def.name}")

            # Program statistics
            prog_stats = compute_statistics(window, program_id, entity_type='manager')
            print_statistics(prog_stats, program_name)

            # Benchmark statistics
            for bm_id in benchmark_ids:
                bm_stats = compute_statistics(window, bm_id, entity_type='benchmark')
                print_statistics(bm_stats, benchmark_names[bm_id])

            break  # Just show first complete window

    # ==========================================================================
    # 2. NON-OVERLAPPING NOT SNAPPED WINDOWS
    # ==========================================================================
    print_section("2. Non-Overlapping Not Snapped Windows (60-Month Periods)")

    windows_60m = generate_window_definitions_non_overlapping_not_snapped(
        start_date=start_date,
        end_date=end_date,
        window_length_months=60,
        program_ids=[program_id],
        benchmark_ids=benchmark_ids,
        window_set_name="60m_unsnapped"
    )

    print(f"Generated {len(windows_60m)} windows:")
    for win_def in windows_60m[:5]:  # Show first 5
        print(f"  {win_def.name}")
    if len(windows_60m) > 5:
        print(f"  ... and {len(windows_60m) - 5} more")

    # ==========================================================================
    # 3. OVERLAPPING ROLLING WINDOWS
    # ==========================================================================
    print_section("3. Overlapping Rolling Windows (12-Month Rolling)")

    windows_12m_rolling = generate_window_definitions_overlapping(
        start_date=start_date,
        end_date=end_date,
        window_length_months=12,
        slide_months=1,
        program_ids=[program_id],
        benchmark_ids=benchmark_ids,
        window_set_name="12m_rolling"
    )

    print(f"Generated {len(windows_12m_rolling)} rolling windows")
    print(f"First window: {windows_12m_rolling[0].name}")
    print(f"Last window:  {windows_12m_rolling[-1].name}")

    # Compute statistics for all rolling windows (demonstrate trend analysis)
    print("\nComputing rolling 12-month returns (first 10 and last 10):")
    print("\n{:20} {:>15} {:>15}".format("Window", "Program Return", "Data Complete"))
    print("-" * 52)

    # Show first 10
    for win_def in windows_12m_rolling[:10]:
        window = Window(win_def, db)
        stats = compute_statistics(window, program_id, entity_type='manager')
        complete = "YES" if window.data_is_complete else "NO"
        print("{:20} {:>14.2%} {:>15}".format(
            win_def.start_date.strftime('%Y-%m'),
            stats.cumulative_return_compounded,
            complete
        ))

    print("...")

    # Show last 10
    for win_def in windows_12m_rolling[-10:]:
        window = Window(win_def, db)
        stats = compute_statistics(window, program_id, entity_type='manager')
        complete = "YES" if window.data_is_complete else "NO"
        print("{:20} {:>14.2%} {:>15}".format(
            win_def.start_date.strftime('%Y-%m'),
            stats.cumulative_return_compounded,
            complete
        ))

    # ==========================================================================
    # 4. OVERLAPPING REVERSE (TRAILING) WINDOWS
    # ==========================================================================
    print_section("4. Overlapping Reverse Windows (Trailing 12/36/60 Months)")

    # Generate trailing windows of different lengths
    for months in [12, 36, 60]:
        windows_trailing = generate_window_definitions_overlapping_reverse(
            end_date=end_date,
            earliest_date=start_date,
            window_length_months=months,
            slide_months=1,
            program_ids=[program_id],
            benchmark_ids=benchmark_ids,
            window_set_name=f"trailing_{months}m"
        )

        # Get the most recent trailing window (first in list)
        if windows_trailing:
            win_def = windows_trailing[0]
            window = Window(win_def, db)
            stats = compute_statistics(window, program_id, entity_type='manager')

            print(f"\nTrailing {months}-Month Return (as of {end_date}):")
            print(f"  Period: {win_def.start_date} to {win_def.end_date}")
            print(f"  Cumulative Return (Compounded): {stats.cumulative_return_compounded:>8.2%}")
            print(f"  Data Complete: {'Yes' if window.data_is_complete else 'No'}")

    # ==========================================================================
    # 5. BESPOKE (CUSTOM EVENT) WINDOWS
    # ==========================================================================
    print_section("5. Bespoke Windows (Custom Event Analysis)")

    # Define custom analysis periods (adjust dates based on your data)
    custom_periods = [
        {'name': 'First Year', 'start_date': start_date,
         'end_date': date(start_date.year + 1, start_date.month, start_date.day)},
        {'name': 'Last Year', 'start_date': date(end_date.year - 1, end_date.month, 1),
         'end_date': end_date},
    ]

    windows_custom = generate_window_definitions_bespoke(
        windows_spec=custom_periods,
        program_ids=[program_id],
        benchmark_ids=benchmark_ids,
        window_set_name="custom_events"
    )

    print(f"Analyzing {len(windows_custom)} custom periods:\n")

    for win_def in windows_custom:
        window = Window(win_def, db)

        print(f"{win_def.name}: {win_def.start_date} to {win_def.end_date}")
        print(f"Data Complete: {'Yes' if window.data_is_complete else 'No'}")

        if window.data_is_complete:
            # Program statistics
            prog_stats = compute_statistics(window, program_id, entity_type='manager')
            print_statistics(prog_stats, program_name)

            # First benchmark
            if benchmark_ids:
                bm_stats = compute_statistics(window, benchmark_ids[0], entity_type='benchmark')
                print_statistics(bm_stats, benchmark_names[benchmark_ids[0]])
        else:
            print("  (Skipping due to incomplete data)")

    # ==========================================================================
    # 6. WINDOW SERIALIZATION DEMO
    # ==========================================================================
    print_section("6. Window Definition Serialization")

    # Demonstrate that windows can be serialized to/from JSON
    win_def = windows_5yr[0]
    serialized = win_def.to_dict()

    print("Original window:")
    print(f"  {win_def.name}: {win_def.start_date} to {win_def.end_date}")

    print("\nSerialized to dict:")
    import json
    print(json.dumps(serialized, indent=2))

    print("\nDeserialized back to WindowDefinition:")
    restored = WindowDefinition.from_dict(serialized)
    print(f"  {restored.name}: {restored.start_date} to {restored.end_date}")

    # ==========================================================================
    # 7. COMPLETENESS VALIDATION DEMO
    # ==========================================================================
    print_section("7. Data Completeness Validation")

    print("Checking data completeness across all 5-year windows:\n")
    print("{:20} {:>15} {:>15} {:>15}".format(
        "Window", "Program", "Benchmarks", "Complete"
    ))
    print("-" * 67)

    for win_def in windows_5yr:
        window = Window(win_def, db)

        # Check program data
        prog_data = window.get_manager_data(program_id)
        prog_ok = window._has_complete_coverage(prog_data)

        # Check benchmark data
        bm_ok = all(
            window._has_complete_coverage(window.get_benchmark_data(bm_id))
            for bm_id in benchmark_ids
        )

        overall = "YES" if window.data_is_complete else "NO"

        print("{:20} {:>15} {:>15} {:>15}".format(
            win_def.name,
            "YES" if prog_ok else "NO",
            "YES" if bm_ok else "NO",
            overall
        ))

    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    print_section("Summary")

    print("Window system successfully demonstrated:")
    print(f"  [OK] Non-overlapping snapped windows:     {len(windows_5yr)} windows")
    print(f"  [OK] Non-overlapping not-snapped windows: {len(windows_60m)} windows")
    print(f"  [OK] Overlapping rolling windows:         {len(windows_12m_rolling)} windows")
    print(f"  [OK] Overlapping reverse (trailing):      Flexible (12/36/60 month)")
    print(f"  [OK] Bespoke custom windows:              {len(windows_custom)} windows")
    print(f"  [OK] Statistics computation:              Compounded & Simple")
    print(f"  [OK] Data completeness validation:        Strict validation")
    print(f"  [OK] Serialization support:               JSON compatible")

    print("\nAll window types working correctly!")

    db.close()


if __name__ == "__main__":
    main()
