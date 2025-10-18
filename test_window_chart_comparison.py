"""
Test that the new window-based chart generation produces identical output
to the original chart generation.
"""

from database import Database
from components.charts import equity_curve_chart, equity_curve_chart_from_window
import plotly.graph_objects as go


def compare_figures(fig1, fig2, name1="Figure 1", name2="Figure 2"):
    """Compare two Plotly figures for structural similarity."""

    print(f"\nComparing {name1} vs {name2}:")
    print("=" * 70)

    # Compare number of traces
    if len(fig1.data) != len(fig2.data):
        print(f"  [DIFF] Number of traces: {len(fig1.data)} vs {len(fig2.data)}")
        return False
    else:
        print(f"  [OK] Number of traces: {len(fig1.data)}")

    # Compare each trace
    all_match = True
    for i, (trace1, trace2) in enumerate(zip(fig1.data, fig2.data)):
        trace_name = trace1.name
        print(f"\n  Trace {i}: {trace_name}")

        # Compare data points
        if len(trace1.x) != len(trace2.x):
            print(f"    [DIFF] Data points: {len(trace1.x)} vs {len(trace2.x)}")
            all_match = False
        else:
            print(f"    [OK] Data points: {len(trace1.x)}")

        # Compare first and last y values (NAV)
        if len(trace1.y) > 0 and len(trace2.y) > 0:
            y1_first, y1_last = trace1.y[0], trace1.y[-1]
            y2_first, y2_last = trace2.y[0], trace2.y[-1]

            # Allow small floating point differences
            if abs(y1_first - y2_first) < 0.01 and abs(y1_last - y2_last) < 0.01:
                print(f"    [OK] NAV values: Start={y1_first:.2f}, End={y1_last:.2f}")
            else:
                print(f"    [DIFF] NAV values:")
                print(f"      {name1}: Start={y1_first:.2f}, End={y1_last:.2f}")
                print(f"      {name2}: Start={y2_first:.2f}, End={y2_last:.2f}")
                all_match = False

        # Compare trace name
        if trace1.name != trace2.name:
            print(f"    [DIFF] Trace name: '{trace1.name}' vs '{trace2.name}'")
            all_match = False

    # Compare layout elements
    print(f"\n  Layout:")
    if fig1.layout.title.text != fig2.layout.title.text:
        print(f"    [DIFF] Title differs")
        all_match = False
    else:
        print(f"    [OK] Title matches")

    if fig1.layout.width != fig2.layout.width or fig1.layout.height != fig2.layout.height:
        print(f"    [DIFF] Size: {fig1.layout.width}x{fig1.layout.height} vs {fig2.layout.width}x{fig2.layout.height}")
        all_match = False
    else:
        print(f"    [OK] Size: {fig1.layout.width}x{fig1.layout.height}")

    if all_match:
        print(f"\n  [OK] CHARTS ARE IDENTICAL")
    else:
        print(f"\n  [FAIL] CHARTS DIFFER (see details above)")

    return all_match


def main():
    db = Database('pnlrg.db')
    db.connect()

    print("=" * 70)
    print("WINDOW-BASED CHART COMPARISON TEST")
    print("=" * 70)

    # Get SP500 benchmark
    sp500 = db.fetch_one("SELECT id, name FROM markets WHERE name = 'SP500'")
    if not sp500:
        print("Error: SP500 benchmark not found!")
        db.close()
        return

    # Get first CTA program
    program = db.fetch_one("SELECT id, program_name FROM programs WHERE program_name != 'Benchmarks' LIMIT 1")
    if not program:
        print("Error: No CTA program found!")
        db.close()
        return

    program_id = program['id']
    program_name = program['program_name']

    print(f"\nTesting with Program: {program_name} (ID: {program_id})")
    print(f"Benchmark: {sp500['name']} (ID: {sp500['id']})")

    # ==========================================================================
    # Test 1: Full history chart with SP500 benchmark
    # ==========================================================================
    print("\n" + "=" * 70)
    print("TEST 1: Full History Chart with SP500 Benchmark")
    print("=" * 70)

    # Generate with OLD method
    print("\nGenerating with OLD method (equity_curve_chart)...")
    fig_old = equity_curve_chart(
        db,
        program_id=program_id,
        benchmarks=['SP500'],  # String list
        date_range=None  # Full range
    )

    # Generate with NEW method
    print("Generating with NEW method (equity_curve_chart_from_window)...")
    fig_new = equity_curve_chart_from_window(
        db,
        program_id=program_id,
        window_def={
            'start_date': '1973-01-31',  # First date in database
            'end_date': '2017-12-22',     # Last date in database
            'benchmark_ids': [sp500['id']]  # Integer list of market IDs
        },
        skip_completeness_check=False  # Validate data is complete
    )

    # Compare
    match1 = compare_figures(fig_old, fig_new, "Old Method", "New Method")

    # ==========================================================================
    # Test 2: Full history using helper function (no explicit dates)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("TEST 2: Full History Using Helper (Auto-detect dates)")
    print("=" * 70)

    print("\nGenerating with NEW method + helper function...")
    from components.charts import create_full_history_window_def

    window_def = create_full_history_window_def(
        db,
        program_id=program_id,
        benchmark_ids=[sp500['id']]
    )

    print(f"  Auto-detected date range: {window_def.start_date} to {window_def.end_date}")

    fig_auto = equity_curve_chart_from_window(
        db,
        program_id=program_id,
        window_def=window_def,
        skip_completeness_check=False
    )

    # Compare with old method
    match2 = compare_figures(fig_old, fig_auto, "Old Method", "Auto-detect Method")

    # ==========================================================================
    # Test 3: Specific time period (1990-2010)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("TEST 3: Specific Period (1990-2010)")
    print("=" * 70)

    # OLD method with date_range
    print("\nGenerating with OLD method (date_range filter)...")
    fig_old_period = equity_curve_chart(
        db,
        program_id=program_id,
        benchmarks=['SP500'],
        date_range={'start': '1990-01-01', 'end': '2010-12-31'}
    )

    # NEW method with window
    print("Generating with NEW method (window definition)...")
    fig_new_period = equity_curve_chart_from_window(
        db,
        program_id=program_id,
        window_def={
            'start_date': '1990-01-01',
            'end_date': '2010-12-31',
            'benchmark_ids': [sp500['id']]
        },
        skip_completeness_check=False
    )

    match3 = compare_figures(fig_old_period, fig_new_period, "Old Period", "New Period")

    # Note: Title difference is expected - new method shows actual chart dates
    print("\n  Note: Title difference is EXPECTED and is actually an IMPROVEMENT.")
    print("  - Old method shows program start date (1973) even when filtered to 1990-2010")
    print("  - New method correctly shows actual chart date range (1990-2010)")
    print("  This is more accurate for the user!")

    # ==========================================================================
    # Summary
    # ==========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    results = [
        ("Full History", match1),
        ("Auto-detect Dates", match2),
        ("Specific Period", match3)
    ]

    all_passed = all(match for _, match in results)

    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {test_name}")

    if all_passed:
        print("\n[SUCCESS] ALL TESTS PASSED")
        print("\nThe window-based chart generation produces identical output to")
        print("the original implementation. The integration is successful!")
    else:
        print("\n[ERROR] SOME TESTS FAILED")
        print("\nPlease review the differences above.")

    # Note: We skip exporting HTML files - only PDFs go to export/ folder
    print("\n" + "=" * 70)
    print("CHART COMPARISON COMPLETE")
    print("=" * 70)

    print("\nNote: Charts are validated programmatically.")
    print("For visual inspection, use the brochure generation examples which export PDFs.")

    db.close()


if __name__ == "__main__":
    main()
