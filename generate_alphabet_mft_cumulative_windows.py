"""
Generate Cumulative Windows Overlay Chart for Alphabet MFT Strategy.

Creates a single-panel chart showing cumulative NAV curves for multiple
non-overlapping 5-year windows, with SP500 benchmark comparison.

Chart Features:
- X-axis: Trading days since window start (normalized)
- Y-axis: NAV starting from $10,000,000
- Strategy lines: Solid, colored by window
- Benchmark lines: Dashed, matching window color
- Legend: Date ranges only
- Subtitle explains solid vs dashed

This allows visual assessment of strategy consistency across different market periods.
"""

from database import Database
from datetime import date
from dateutil.relativedelta import relativedelta
import os
import sys

# Add components directory to path
sys.path.append(os.path.dirname(__file__))

from components.cumulative_windows_overlay import generate_cumulative_windows_overlay


def generate_non_overlapping_windows(start_date: date, end_date: date, window_years: int = 5):
    """
    Generate non-overlapping windows working backwards from end date.

    Args:
        start_date: Earliest possible date
        end_date: Latest date (anchor point)
        window_years: Window size in years

    Returns:
        List of window dicts with 'start_date', 'end_date', 'name'
    """
    windows = []
    current_end = end_date

    while current_end >= start_date:
        # Calculate window start (window_years before current_end)
        window_start = current_end - relativedelta(years=window_years)

        # Don't go before the earliest date
        if window_start < start_date:
            window_start = start_date

        windows.append({
            'start_date': window_start,
            'end_date': current_end,
            'name': f"{window_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}"
        })

        # Move to next window (end before current start)
        current_end = window_start - relativedelta(days=1)

    return windows


def main():
    """Generate cumulative windows overlay chart for Alphabet MFT."""
    print("=" * 70)
    print("ALPHABET MFT - CUMULATIVE WINDOWS OVERLAY CHART")
    print("=" * 70)

    db = Database()

    try:
        # Get Alphabet MFT program
        program = db.fetch_one("""
            SELECT p.id, p.program_name, m.manager_name
            FROM programs p
            JOIN managers m ON p.manager_id = m.id
            WHERE m.manager_name = 'Alphabet' AND p.program_name = 'MFT'
        """)

        if not program:
            print("\nError: Could not find Alphabet MFT program!")
            return

        program_id = program['id']
        print(f"\nProgram: {program['manager_name']} - {program['program_name']}")

        # Get SP500 benchmark market ID
        sp500 = db.fetch_one("""
            SELECT id FROM markets
            WHERE name = 'SP500' AND is_benchmark = 1
        """)

        if not sp500:
            print("\nWarning: SP500 benchmark not found, proceeding without benchmark")
            benchmark_id = None
        else:
            benchmark_id = sp500['id']
            print(f"Benchmark: SP500 (market_id={benchmark_id})")

        # Get date range for MFT program
        date_range = db.fetch_one("""
            SELECT MIN(date) as min_date, MAX(date) as max_date
            FROM pnl_records
            WHERE program_id = ? AND resolution = 'daily'
        """, (program_id,))

        if not date_range or not date_range['min_date']:
            print("\nError: No daily data found for Alphabet MFT!")
            return

        min_date = date.fromisoformat(date_range['min_date'])
        max_date = date.fromisoformat(date_range['max_date'])

        print(f"Date Range: {min_date} to {max_date}")

        # Generate 5-year non-overlapping windows (reverse from end)
        print("\nGenerating 5-year non-overlapping windows (reverse from latest date)...")
        windows = generate_non_overlapping_windows(min_date, max_date, window_years=5)

        print(f"Generated {len(windows)} windows:")
        for i, window in enumerate(windows, 1):
            trading_days_query = db.fetch_one("""
                SELECT COUNT(DISTINCT date) as days
                FROM pnl_records
                WHERE program_id = ?
                  AND resolution = 'daily'
                  AND date >= ?
                  AND date <= ?
            """, (program_id, window['start_date'].strftime('%Y-%m-%d'), window['end_date'].strftime('%Y-%m-%d')))
            trading_days = trading_days_query['days'] if trading_days_query else 0
            print(f"  {i}. {window['name']} ({trading_days} trading days)")

        # Create output directory
        output_dir = 'export'
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'alphabet_mft_cumulative_windows_5yr.pdf')

        # Generate chart
        print(f"\nGenerating chart...")
        starting_nav = 10_000_000

        title = "Alphabet MFT - Cumulative Performance by 5-Year Window"
        subtitle = f"Starting NAV: ${starting_nav:,.0f}. Solid lines: MFT strategy. Dashed lines: SP500 benchmark over same period."

        fig = generate_cumulative_windows_overlay(
            db=db,
            program_id=program_id,
            windows=windows,
            benchmark_market_id=benchmark_id,
            starting_nav=starting_nav,
            output_path=output_path,
            title=title,
            subtitle=subtitle
        )

        print(f"\n[OK] Chart generated successfully!")
        print(f"  Output: {output_path}")
        print(f"  Windows: {len(windows)}")
        print(f"  Starting NAV: ${starting_nav:,.0f}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
