"""
Generate Cumulative Windows Overlay Chart (Additive) for Alphabet MFT Strategy.

Creates a single-panel chart showing cumulative NAV curves for multiple
non-overlapping 5-year windows, with SP500 benchmark comparison.

Uses ADDITIVE (non-compounded) returns where each day's gain/loss is based
on the original $10M starting NAV, not the current NAV.

Chart Features:
- X-axis: Trading days since window start (normalized)
- Y-axis: NAV starting from $10,000,000
- Strategy lines: Solid, colored by window
- Benchmark lines: Dashed, matching window color
- Legend: Date ranges only
- Subtitle explains solid vs dashed and additive calculation

This allows visual assessment of strategy consistency across different market periods
using simple additive returns (no geometric compounding).
"""

from database import Database
from datetime import date
from dateutil.relativedelta import relativedelta
import os
import sys
import pandas as pd

# Add components directory to path
sys.path.append(os.path.dirname(__file__))

from components.cumulative_windows_overlay import (
    get_daily_returns_for_window,
    get_benchmark_returns_for_window,
    calculate_cumulative_nav_additive
)
from windows import generate_window_definitions_non_overlapping_reverse
import plotly.graph_objects as go


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


def generate_additive_chart(db, program_id, windows, benchmark_market_id, starting_nav, output_path, title, subtitle):
    """Generate cumulative windows overlay chart using additive returns."""

    # Color palette for windows
    colors = [
        '#1f77b4',  # Blue
        '#ff7f0e',  # Orange
        '#2ca02c',  # Green
        '#d62728',  # Red
        '#9467bd',  # Purple
        '#8c564b',  # Brown
        '#e377c2',  # Pink
        '#7f7f7f',  # Gray
    ]

    fig = go.Figure()

    for i, window in enumerate(windows):
        start_date = window['start_date']
        end_date = window['end_date']
        window_name = window.get('name', f"{start_date} to {end_date}")
        color = colors[i % len(colors)]

        # Check if this window has borrowed data
        borrowed_start = window.get('borrowed_start_date')
        borrowed_end = window.get('borrowed_end_date')
        has_borrowed = borrowed_start is not None and borrowed_end is not None

        # Get program returns
        program_df = get_daily_returns_for_window(db, program_id, start_date, end_date)

        if len(program_df) == 0:
            print(f"Warning: No data for window {window_name}")
            continue

        # Calculate cumulative NAV using ADDITIVE method
        nav_curve = calculate_cumulative_nav_additive(program_df['return'].tolist(), starting_nav)
        trading_days = list(range(len(nav_curve)))

        if has_borrowed:
            # Split into actual and borrowed segments
            # Find the index where borrowed data starts
            borrowed_start_idx = len(program_df[program_df['date'] < pd.Timestamp(borrowed_start)])

            # Actual data segment (solid line)
            actual_days = trading_days[:borrowed_start_idx]
            actual_nav = nav_curve[:borrowed_start_idx]

            # Borrowed data segment (dotted line)
            borrowed_days = trading_days[borrowed_start_idx-1:]  # Overlap by 1 for continuity
            borrowed_nav = nav_curve[borrowed_start_idx-1:]

            # Add actual data trace (solid)
            fig.add_trace(go.Scatter(
                x=actual_days,
                y=actual_nav,
                mode='lines',
                name=window_name,
                line=dict(color=color, width=2),
                legendgroup=f'window_{i}',
                showlegend=True
            ))

            # Add borrowed data trace (dotted)
            fig.add_trace(go.Scatter(
                x=borrowed_days,
                y=borrowed_nav,
                mode='lines',
                name=window_name,
                line=dict(color=color, width=2, dash='dot'),
                legendgroup=f'window_{i}',
                showlegend=False
            ))
        else:
            # No borrowed data - single solid line
            fig.add_trace(go.Scatter(
                x=trading_days,
                y=nav_curve,
                mode='lines',
                name=window_name,
                line=dict(color=color, width=2),
                legendgroup=f'window_{i}',
                showlegend=True
            ))

        # Add benchmark line if provided (dashed, same color)
        if benchmark_market_id:
            benchmark_df = get_benchmark_returns_for_window(db, benchmark_market_id, start_date, end_date)

            if len(benchmark_df) > 0:
                # Calculate benchmark NAV curve using ADDITIVE method
                benchmark_nav_curve = calculate_cumulative_nav_additive(benchmark_df['return'].tolist(), starting_nav)
                benchmark_trading_days = list(range(len(benchmark_nav_curve)))

                if has_borrowed:
                    # Split benchmark into actual and borrowed segments
                    borrowed_start_idx = len(benchmark_df[benchmark_df['date'] < pd.Timestamp(borrowed_start)])

                    # Actual benchmark segment (dashed)
                    actual_days = benchmark_trading_days[:borrowed_start_idx]
                    actual_nav = benchmark_nav_curve[:borrowed_start_idx]

                    # Borrowed benchmark segment (dotted)
                    borrowed_days = benchmark_trading_days[borrowed_start_idx-1:]
                    borrowed_nav = benchmark_nav_curve[borrowed_start_idx-1:]

                    # Add actual benchmark trace (dashed)
                    fig.add_trace(go.Scatter(
                        x=actual_days,
                        y=actual_nav,
                        mode='lines',
                        name=window_name,
                        line=dict(color=color, width=2, dash='dash'),
                        legendgroup=f'window_{i}',
                        showlegend=False
                    ))

                    # Add borrowed benchmark trace (dotted)
                    fig.add_trace(go.Scatter(
                        x=borrowed_days,
                        y=borrowed_nav,
                        mode='lines',
                        name=window_name,
                        line=dict(color=color, width=2, dash='dot'),
                        legendgroup=f'window_{i}',
                        showlegend=False
                    ))
                else:
                    # No borrowed data - single dashed line
                    fig.add_trace(go.Scatter(
                        x=benchmark_trading_days,
                        y=benchmark_nav_curve,
                        mode='lines',
                        name=window_name,  # Same name as strategy
                        line=dict(color=color, width=2, dash='dash'),
                        legendgroup=f'window_{i}',
                        showlegend=False  # Don't duplicate in legend
                    ))

    # Update layout
    fig.update_layout(
        title={
            'text': title,
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20}
        },
        xaxis_title='Trading Days Since Window Start',
        yaxis_title='NAV ($)',
        yaxis=dict(tickformat='$,.0f'),
        hovermode='x unified',
        width=1400,
        height=800,
        template='plotly_white',
        legend=dict(
            orientation='v',
            yanchor='top',
            y=0.99,
            xanchor='left',
            x=0.01,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='gray',
            borderwidth=1
        )
    )

    # Add subtitle as annotation
    if subtitle:
        fig.add_annotation(
            text=subtitle,
            xref='paper',
            yref='paper',
            x=0.5,
            y=1.05,
            xanchor='center',
            yanchor='bottom',
            showarrow=False,
            font=dict(size=12, color='gray')
        )

    # Save to PDF
    if output_path:
        fig.write_image(output_path, format='pdf', width=1400, height=800)
        print(f"Chart saved to: {output_path}")

    return fig


def main():
    """Generate cumulative windows overlay chart (additive) for Alphabet MFT."""
    print("=" * 70)
    print("ALPHABET MFT - CUMULATIVE WINDOWS OVERLAY CHART (ADDITIVE)")
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

        # Generate 5-year non-overlapping windows (reverse from end) with borrow_mode
        print("\nGenerating 5-year non-overlapping windows (reverse from latest date, borrow_mode=True)...")
        window_defs = generate_window_definitions_non_overlapping_reverse(
            earliest_date=min_date,
            latest_date=max_date,
            window_length_years=5,
            program_ids=[program_id],
            benchmark_ids=[benchmark_id] if benchmark_id else [],
            window_set_name="5yr_non_overlapping",
            borrow_mode=True
        )

        # Convert WindowDefinition objects to dict format for existing chart code
        windows = []
        for wd in window_defs:
            window_dict = {
                'start_date': wd.start_date,
                'end_date': wd.end_date,
                'name': f"{wd.start_date.strftime('%Y-%m-%d')} to {wd.end_date.strftime('%Y-%m-%d')}",
                'borrowed_start_date': wd.borrowed_data_start_date,
                'borrowed_end_date': wd.borrowed_data_end_date
            }
            windows.append(window_dict)

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
            borrowed_info = ""
            if window['borrowed_start_date'] and window['borrowed_end_date']:
                borrowed_info = f" [BORROWED: {window['borrowed_start_date'].strftime('%Y-%m-%d')} to {window['borrowed_end_date'].strftime('%Y-%m-%d')}]"
            print(f"  {i}. {window['name']} ({trading_days} trading days){borrowed_info}")

        # Create output directory
        output_dir = 'export'
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'alphabet_mft_cumulative_windows_5yr_additive.pdf')

        # Generate chart
        print(f"\nGenerating chart (additive returns)...")
        starting_nav = 10_000_000

        title = "Alphabet MFT - Cumulative Performance by 5-Year Window (Additive)"
        subtitle = f"Starting NAV: ${starting_nav:,.0f}. Additive returns (no compounding). Solid: MFT. Dashed: SP500. Dotted: Borrowed data (overlap with next window)."

        fig = generate_additive_chart(
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
        print(f"  Calculation: Additive (non-compounded)")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
