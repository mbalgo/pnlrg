"""
Example demonstrating window-based chart generation.

NOTE: This script generates HTML files for quick visualization and testing.
For production PDF brochures, use example_brochure_workflow.py which exports
to the export/ folder.

Shows how to create charts using the window system for flexible
date range selection and data completeness validation.
"""

from database import Database
from components.charts import equity_curve_chart_from_window, create_full_history_window_def
from datetime import date
import os


def main():
    db = Database('pnlrg.db')
    db.connect()

    # Create export directory
    os.makedirs("export", exist_ok=True)

    print("=" * 70)
    print("WINDOW-BASED CHART GENERATION EXAMPLES")
    print("=" * 70)
    print("\nNote: This generates HTML for quick testing.")
    print("For production PDFs, use example_brochure_workflow.py")

    # Get program and benchmarks
    program = db.fetch_one("SELECT id, program_name FROM programs WHERE program_name != 'Benchmarks' LIMIT 1")
    sp500 = db.fetch_one("SELECT id FROM markets WHERE name = 'SP500'")

    program_id = program['id']
    program_name = program['program_name']

    print(f"\nProgram: {program_name}")
    print(f"Benchmark: SP500")

    # ==========================================================================
    # Example 1: Full History Brochure
    # ==========================================================================
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Full History Brochure")
    print("=" * 70)

    print("\nGenerating full history equity curve...")

    # Method 1: Let the function auto-detect dates
    fig = equity_curve_chart_from_window(
        db,
        program_id=program_id,
        window_def=None,  # Auto-detect full history
    )

    fig.write_html("brochure_full_history.html")
    print("  ✓ Saved to: brochure_full_history.html")

    # Method 2: Explicitly use helper function
    window_def = create_full_history_window_def(
        db,
        program_id=program_id,
        benchmark_ids=[sp500['id']]
    )

    print(f"\n  Window: {window_def.start_date} to {window_def.end_date}")

    fig2 = equity_curve_chart_from_window(
        db,
        program_id=program_id,
        window_def=window_def
    )

    fig2.write_html("brochure_full_history_with_benchmark.html")
    print("  ✓ Saved to: brochure_full_history_with_benchmark.html")

    # ==========================================================================
    # Example 2: Trailing 5 Years
    # ==========================================================================
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Trailing 5 Years Brochure")
    print("=" * 70)

    # Get latest date
    latest = db.fetch_one("SELECT MAX(date) as max_date FROM pnl_records WHERE program_id = ?", (program_id,))
    end_date = date.fromisoformat(latest['max_date'])

    # Calculate 5 years back
    from dateutil.relativedelta import relativedelta
    start_date_5y = end_date - relativedelta(years=5)

    print(f"\nGenerating trailing 5-year equity curve...")
    print(f"  Period: {start_date_5y} to {end_date}")

    fig_5y = equity_curve_chart_from_window(
        db,
        program_id=program_id,
        window_def={
            'start_date': start_date_5y,
            'end_date': end_date,
            'benchmark_ids': [sp500['id']]
        },
        skip_completeness_check=False  # Validate data is complete
    )

    fig_5y.write_html("brochure_trailing_5_years.html")
    print("  ✓ Saved to: brochure_trailing_5_years.html")

    # ==========================================================================
    # Example 3: Specific Period (1990-2010)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Specific Period Brochure (1990-2010)")
    print("=" * 70)

    print("\nGenerating 1990-2010 equity curve...")

    fig_period = equity_curve_chart_from_window(
        db,
        program_id=program_id,
        window_def={
            'start_date': date(1990, 1, 1),
            'end_date': date(2010, 12, 31),
            'benchmark_ids': [sp500['id']]
        },
        skip_completeness_check=False
    )

    fig_period.write_html("brochure_1990_2010.html")
    print("  ✓ Saved to: brochure_1990_2010.html")

    # ==========================================================================
    # Example 4: Using Window Generation Functions
    # ==========================================================================
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Generate Multiple Period Brochures")
    print("=" * 70)

    from windows import generate_window_definitions_non_overlapping_snapped

    print("\nGenerating 5-year period brochures (1990-2010)...")

    windows = generate_window_definitions_non_overlapping_snapped(
        start_date=date(1990, 1, 1),
        end_date=date(2010, 12, 31),
        window_length_years=5,
        program_ids=[program_id],
        benchmark_ids=[sp500['id']],
        window_set_name="5yr_periods"
    )

    print(f"\nGenerated {len(windows)} window definitions:")

    for win_def in windows:
        print(f"\n  Period: {win_def.name}")
        print(f"    Dates: {win_def.start_date} to {win_def.end_date}")

        try:
            fig_win = equity_curve_chart_from_window(
                db,
                program_id=program_id,
                window_def=win_def,
                skip_completeness_check=False
            )

            filename = f"brochure_{win_def.name.replace('-', '_')}.html"
            fig_win.write_html(filename)
            print(f"    ✓ Saved to: {filename}")

        except ValueError as e:
            print(f"    ✗ Skipped: {e}")

    # ==========================================================================
    # Example 5: Data Completeness Handling
    # ==========================================================================
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Handling Incomplete Data")
    print("=" * 70)

    # Try to create a chart with BTOP50 (starts in 1987, so 1973-1980 will be incomplete)
    btop50 = db.fetch_one("SELECT id FROM markets WHERE name = 'BTOP50'")

    print("\nAttempting to create 1973-1980 chart with BTOP50 benchmark...")
    print("(BTOP50 didn't start until 1987, so this should fail)")

    try:
        fig_incomplete = equity_curve_chart_from_window(
            db,
            program_id=program_id,
            window_def={
                'start_date': date(1973, 1, 1),
                'end_date': date(1980, 12, 31),
                'benchmark_ids': [sp500['id'], btop50['id']]
            },
            skip_completeness_check=False  # Strict validation
        )
        print("  ✗ Unexpected: Chart was generated despite incomplete data!")

    except ValueError as e:
        print(f"  ✓ Correctly rejected: {e}")

    print("\nNow generating the same chart with skip_completeness_check=True...")

    fig_skip_check = equity_curve_chart_from_window(
        db,
        program_id=program_id,
        window_def={
            'start_date': date(1973, 1, 1),
            'end_date': date(1980, 12, 31),
            'benchmark_ids': [sp500['id'], btop50['id']]
        },
        skip_completeness_check=True  # Allow incomplete data
    )

    fig_skip_check.write_html("brochure_with_incomplete_data.html")
    print("  ✓ Chart generated (BTOP50 will be missing)")
    print("  ✓ Saved to: brochure_with_incomplete_data.html")

    # ==========================================================================
    # Summary
    # ==========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print("\nWindow-based brochure generation provides:")
    print("  • Consistent data fetching logic across all charts")
    print("  • Automatic data completeness validation")
    print("  • Flexible date range selection")
    print("  • Easy generation of multiple period reports")
    print("  • Better error handling for missing data")

    print("\nKey Benefits over Old Method:")
    print("  • More accurate chart titles (shows actual date range)")
    print("  • Validates benchmarks have complete data")
    print("  • Can generate sets of reports using window generators")
    print("  • Reuses window system for statistics and analysis")

    print("\nExample charts generated as HTML for testing.")
    print("For production PDF brochures with full layout, use example_brochure_workflow.py")
    print("PDFs are exported to the export/ folder.")

    db.close()


if __name__ == "__main__":
    main()
