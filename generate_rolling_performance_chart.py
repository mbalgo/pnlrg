"""
Generate 4-panel rolling performance chart comparing Rise CTA vs SP500.

Creates a PDF with 4 vertically stacked panels showing:
1. Mean monthly return (5-year rolling)
2. Standard deviation (5-year rolling)
3. Cumulative return compounded (5-year rolling)
4. Maximum drawdown compounded (5-year rolling)

Each panel shows two series: Rise CTA 30B program and SP500 benchmark.
"""

from database import Database
from windows import generate_window_definitions_overlapping_reverse, Window, compute_statistics
from datetime import date
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os


def main():
    db = Database('pnlrg.db')
    db.connect()

    print("=" * 70)
    print("ROLLING 5-YEAR PERFORMANCE CHART GENERATOR")
    print("=" * 70)

    # Get CTA program at 30 billion
    program = db.fetch_one("""
        SELECT id, program_name, fund_size
        FROM programs
        WHERE program_name LIKE '%30000M%' OR program_name LIKE '%30B%'
        LIMIT 1
    """)

    if not program:
        print("\nError: Could not find CTA 30 billion program!")
        print("Looking for any CTA program with largest fund size...")
        program = db.fetch_one("""
            SELECT id, program_name, fund_size
            FROM programs
            WHERE program_name != 'Benchmarks'
            ORDER BY fund_size DESC
            LIMIT 1
        """)

    program_id = program['id']
    program_name = program['program_name']

    print(f"\nProgram: {program_name}")
    print(f"Fund Size: ${program['fund_size']:,.0f}")

    # Get SP500 benchmark
    sp500 = db.fetch_one("SELECT id, name FROM markets WHERE name = 'SP500'")
    if not sp500:
        print("\nError: SP500 benchmark not found!")
        db.close()
        return

    print(f"Benchmark: {sp500['name']}")

    # Get data range
    data_range = db.fetch_one("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM pnl_records
        WHERE program_id = ?
    """, (program_id,))

    earliest_date = date.fromisoformat(data_range['min_date'])
    latest_date = date.fromisoformat(data_range['max_date'])

    print(f"Data Range: {earliest_date} to {latest_date}")

    # Start windows 5 years after earliest date to ensure we have enough data
    # This gives us complete 5-year windows throughout
    from dateutil.relativedelta import relativedelta
    window_start = earliest_date + relativedelta(years=5)

    print(f"Window Range: {window_start} to {latest_date}")

    # Generate overlapping reverse 5-year windows
    print("\nGenerating 5-year trailing windows...")

    windows = generate_window_definitions_overlapping_reverse(
        end_date=latest_date,
        earliest_date=window_start,  # Start 5 years in, not from beginning
        window_length_months=60,  # 5 years
        slide_months=1,  # Slide by 1 month
        program_ids=[program_id],
        benchmark_ids=[sp500['id']],
        window_set_name="trailing_5yr"
    )

    print(f"Generated {len(windows)} windows")

    # Compute statistics for each window
    print("\nComputing statistics for each window...")

    results = []
    skipped = 0
    for i, win_def in enumerate(windows):
        if i % 50 == 0:
            print(f"  Processing window {i+1}/{len(windows)}...")

        window = Window(win_def, db)

        # Get data for both series
        prog_data = window.get_manager_data(program_id)
        sp500_data = window.get_benchmark_data(sp500['id'])

        # Skip if either series has no data or very little data
        # (Allow some flexibility - need at least 50 months out of 60)
        if len(prog_data) < 50 or len(sp500_data) < 50:
            skipped += 1
            continue

        # Compute statistics for program
        prog_stats = compute_statistics(window, program_id, entity_type='manager')

        # Compute statistics for SP500
        sp500_stats = compute_statistics(window, sp500['id'], entity_type='benchmark')

        # Store results
        results.append({
            'date': win_def.end_date,  # Use end date for x-axis
            'prog_mean': prog_stats.mean,
            'prog_std': prog_stats.std_dev,
            'prog_cagr': prog_stats.cagr,
            'prog_max_dd': prog_stats.max_drawdown_compounded,
            'sp500_mean': sp500_stats.mean,
            'sp500_std': sp500_stats.std_dev,
            'sp500_cagr': sp500_stats.cagr,
            'sp500_max_dd': sp500_stats.max_drawdown_compounded
        })

    print(f"Computed statistics for {len(results)} windows (skipped {skipped} with insufficient data)")

    # Convert to DataFrame
    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])

    # Create a formatted date string for x-axis display
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')

    print(f"\nDate range of complete windows: {df['date'].min().date()} to {df['date'].max().date()}")

    # Create 4-panel stacked chart
    print("\nCreating 4-panel chart...")

    fig = make_subplots(
        rows=4, cols=1,
        subplot_titles=(
            '<b>Mean Monthly Return (5-Year Trailing)</b>',
            '<b>Standard Deviation (5-Year Trailing)</b>',
            '<b>CAGR (5-Year Trailing)</b>',
            '<b>Maximum Drawdown - Compounded (5-Year Trailing)</b>'
        ),
        vertical_spacing=0.10,
        row_heights=[0.25, 0.25, 0.25, 0.25]
    )

    # Update subplot title font size
    for annotation in fig['layout']['annotations']:
        annotation['font'] = dict(size=11)

    # Color scheme
    rise_color = '#1f77b4'  # Blue
    sp500_color = '#ff7f0e'  # Orange

    # Panel 1: Mean Return
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['prog_mean'] * 100,  # Convert to percentage
            name='Rise CTA',
            line=dict(color=rise_color, width=2),
            legendgroup='rise',
            showlegend=True,
            mode='lines'
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['sp500_mean'] * 100,
            name='SP500',
            line=dict(color=sp500_color, width=2),
            legendgroup='sp500',
            showlegend=True,
            mode='lines'
        ),
        row=1, col=1
    )

    # Panel 2: Standard Deviation
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['prog_std'] * 100,
            name='Rise CTA',
            line=dict(color=rise_color, width=2),
            legendgroup='rise',
            showlegend=False,
            mode='lines'
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['sp500_std'] * 100,
            name='SP500',
            line=dict(color=sp500_color, width=2),
            legendgroup='sp500',
            showlegend=False,
            mode='lines'
        ),
        row=2, col=1
    )

    # Panel 3: CAGR
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['prog_cagr'] * 100,
            name='Rise CTA',
            line=dict(color=rise_color, width=2),
            legendgroup='rise',
            showlegend=False,
            mode='lines'
        ),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['sp500_cagr'] * 100,
            name='SP500',
            line=dict(color=sp500_color, width=2),
            legendgroup='sp500',
            showlegend=False,
            mode='lines'
        ),
        row=3, col=1
    )

    # Panel 4: Maximum Drawdown
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['prog_max_dd'] * 100,
            name='Rise CTA',
            line=dict(color=rise_color, width=2),
            legendgroup='rise',
            showlegend=False,
            mode='lines'
        ),
        row=4, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['sp500_max_dd'] * 100,
            name='SP500',
            line=dict(color=sp500_color, width=2),
            legendgroup='sp500',
            showlegend=False,
            mode='lines'
        ),
        row=4, col=1
    )

    # Update y-axes labels (smaller font)
    fig.update_yaxes(title_text="Mean Return (%)", title_font=dict(size=10), row=1, col=1)
    fig.update_yaxes(title_text="Std Dev (%)", title_font=dict(size=10), row=2, col=1)
    fig.update_yaxes(title_text="CAGR (%)", title_font=dict(size=10), row=3, col=1)
    fig.update_yaxes(title_text="Max Drawdown (%)", title_font=dict(size=10), row=4, col=1)

    # Update x-axes - show year labels at 5-year intervals
    # Get years for tick positions
    years = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq='5YS')
    year_labels = [d.strftime('%Y') for d in years]

    for row in range(1, 5):
        fig.update_xaxes(
            title_text="Date" if row == 4 else "",
            title_font=dict(size=10),
            tickmode='array',
            tickvals=years,
            ticktext=year_labels,
            tickfont=dict(size=9),
            row=row, col=1
        )

    # Overall layout - A4 size (595pt x 842pt)
    fig.update_layout(
        title=dict(
            text=f'<b>Rolling 5-Year Performance: {program_name} vs SP500</b>',
            font=dict(size=14, family='Arial, sans-serif', color='#2c3e50'),
            x=0.5,
            xanchor='center',
            y=0.99,  # Move title higher
            yanchor='top'
        ),
        height=842,  # A4 height in points
        width=595,   # A4 width in points
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='top',
            y=0.97,  # Position legend below title with more space
            xanchor='center',
            x=0.5,
            font=dict(size=8, family='Arial, sans-serif'),
            bgcolor='rgba(255, 255, 255, 0.9)',
            bordercolor='#bdc3c7',
            borderwidth=1
        ),
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=50, r=20, t=80, b=40)  # More top margin for title and legend
    )

    # Update all axes styling (smaller fonts, cleaner grid)
    fig.update_xaxes(
        showgrid=True,
        gridcolor='#e5e5e5',
        showline=True,
        linewidth=1,
        linecolor='#bdc3c7'
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor='#e5e5e5',
        showline=True,
        linewidth=1,
        linecolor='#bdc3c7',
        tickfont=dict(size=9)  # Smaller y-axis tick labels
    )

    # Export to PDF
    print("\nExporting to PDF...")

    os.makedirs("export", exist_ok=True)
    output_path = "export/rolling_5yr_performance.pdf"

    fig.write_image(output_path, format='pdf')
    print(f"  [OK] Saved to: {output_path}")

    # Also save summary statistics
    print("\nSummary Statistics (Most Recent 5-Year Window):")
    print("=" * 70)

    latest = df.iloc[-1]
    print(f"\nWindow ending: {latest['date'].date()}")
    print(f"\nRise CTA:")
    print(f"  Mean Monthly Return:     {latest['prog_mean']*100:>8.2f}%")
    print(f"  Standard Deviation:      {latest['prog_std']*100:>8.2f}%")
    print(f"  CAGR (5yr):              {latest['prog_cagr']*100:>8.2f}%")
    print(f"  Maximum Drawdown (5yr):  {latest['prog_max_dd']*100:>8.2f}%")

    print(f"\nSP500:")
    print(f"  Mean Monthly Return:     {latest['sp500_mean']*100:>8.2f}%")
    print(f"  Standard Deviation:      {latest['sp500_std']*100:>8.2f}%")
    print(f"  CAGR (5yr):              {latest['sp500_cagr']*100:>8.2f}%")
    print(f"  Maximum Drawdown (5yr):  {latest['sp500_max_dd']*100:>8.2f}%")

    print("\n" + "=" * 70)
    print("PDF generated successfully!")
    print("=" * 70)

    db.close()


if __name__ == "__main__":
    main()
