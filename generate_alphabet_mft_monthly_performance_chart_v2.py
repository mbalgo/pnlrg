"""
Generate 4-panel monthly rolling performance chart for Alphabet MFT using refactored windows.py.

Creates a PDF with 4 vertically stacked panels showing:
1. Mean monthly return (month-by-month)
2. Standard deviation (annualized from DAILY returns - industry standard!)
3. CAGR (annualized from monthly return)
4. Maximum drawdown (from monthly compounded returns)

Uses the refactored windows.py framework which:
- Fetches daily data for std dev calculation (industry standard)
- Aggregates daily to monthly for other metrics
- Properly calculates std dev from daily returns within each month

This chart type is registered in the database as 'monthly_rolling_performance'.
"""

from database import Database
from windows import WindowDefinition, Window, compute_statistics
from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from components.chart_config import (
    load_chart_config,
    get_series_color,
    get_line_width
)


def main():
    """
    Generate monthly rolling performance chart using windows framework.

    Each "window" is 1 calendar month, so we get month-by-month statistics.
    """
    db = Database('pnlrg.db')
    db.connect()

    print("=" * 70)
    print("ALPHABET MFT - MONTHLY ROLLING PERFORMANCE (WINDOWS FRAMEWORK)")
    print("=" * 70)

    # Get Alphabet MFT program
    program = db.fetch_one("""
        SELECT p.id, p.program_name, p.program_nice_name, p.fund_size, m.manager_name
        FROM programs p
        JOIN managers m ON p.manager_id = m.id
        WHERE m.manager_name = 'Alphabet' AND p.program_name = 'MFT'
    """)

    if not program:
        print("\nError: Could not find Alphabet MFT program!")
        db.close()
        return

    program_id = program['id']
    program_name = program['program_name']
    program_nice_name = program['program_nice_name'] or program_name
    manager_name = program['manager_name']

    print(f"\nManager: {manager_name}")
    print(f"Program: {program_name}")
    print(f"Fund Size: ${program['fund_size']:,.0f}")

    # Get data range
    data_range = db.fetch_one("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM pnl_records
        WHERE program_id = ? AND resolution = 'daily'
    """, (program_id,))

    earliest_date = date.fromisoformat(data_range['min_date'])
    latest_date = date.fromisoformat(data_range['max_date'])

    print(f"\nData Range: {earliest_date} to {latest_date}")

    # Generate monthly windows
    print("\nGenerating monthly windows...")

    windows = []
    current_date = earliest_date

    while current_date <= latest_date:
        # Create window for this month
        month_start = date(current_date.year, current_date.month, 1)
        # End of month
        if current_date.month == 12:
            month_end = date(current_date.year + 1, 1, 1) - relativedelta(days=1)
        else:
            month_end = date(current_date.year, current_date.month + 1, 1) - relativedelta(days=1)

        # Clip to data range
        month_end = min(month_end, latest_date)

        windows.append(WindowDefinition(
            start_date=month_start,
            end_date=month_end,
            program_ids=[program_id],
            benchmark_ids=[],
            name=f"{month_start.strftime('%Y-%m')}"
        ))

        # Move to next month
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)

    print(f"  Generated {len(windows)} monthly windows")

    # Compute statistics for each window
    print("\nComputing statistics for each month...")

    results = []
    for i, win_def in enumerate(windows):
        if (i + 1) % 50 == 0:
            print(f"  Processing window {i+1}/{len(windows)}...")

        window = Window(win_def, db)
        stats = compute_statistics(window, program_id, entity_type='manager')

        # Skip if no data
        if stats.count == 0:
            continue

        results.append({
            'date': win_def.end_date,
            'window_name': win_def.name,
            'prog_mean': stats.mean,
            'prog_std': stats.std_dev,  # Now from daily returns!
            'prog_cagr': stats.cagr,
            'prog_max_dd': stats.max_drawdown_compounded,
            'daily_count': stats.daily_count
        })

    print(f"\nComputed statistics for {len(results)} months")

    if not results:
        print("\nError: No data to plot!")
        db.close()
        return

    # Convert to DataFrame
    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])

    print(f"\nDate range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Total months: {len(df)}")

    # Load chart configuration from database
    print("\nLoading chart configuration from database...")
    config = load_chart_config(db, chart_type='monthly_rolling_performance')

    panel_config = config['panel']
    style_config = config['style']

    print(f"  Using preset: monthly_rolling_performance")
    print(f"  Paper size: {config['layout']['width']}x{config['layout']['height']} (A4)")

    # Create 4-panel stacked chart
    print("\nCreating 4-panel bar chart...")

    panel_titles = panel_config['panel_titles']

    fig = make_subplots(
        rows=4, cols=1,
        subplot_titles=panel_titles,
        vertical_spacing=panel_config['vertical_spacing'],
        row_heights=panel_config['panel_heights']
    )

    # Update subplot title font size from config
    for annotation in fig['layout']['annotations']:
        annotation['font'] = dict(size=panel_config['title_font_size'])

    # Add program traces using configuration
    for row, metric in enumerate([('mean', 'Mean Return (%)'),
                                    ('std', 'Std Dev (%)'),
                                    ('cagr', 'CAGR (%)'),
                                    ('max_dd', 'Max Drawdown (%)')], start=1):
        metric_key, metric_label = metric

        # Add Alphabet MFT as bar chart
        prog_color = get_series_color(config, 'primary', index=0)

        fig.add_trace(
            go.Bar(
                x=df['date'],
                y=df[f'prog_{metric_key}'] * 100,
                name='Alphabet MFT',
                marker=dict(color=prog_color),
                legendgroup='alphabet_mft',
                showlegend=(row == 1)
            ),
            row=row, col=1
        )

    # Update y-axes labels from config
    y_axis_titles = panel_config['y_axis_titles']
    fonts = style_config['fonts']

    for row, y_title in enumerate(y_axis_titles, start=1):
        fig.update_yaxes(
            title_text=y_title,
            title_font=dict(size=fonts['axis_title_size']),
            row=row, col=1
        )

    # X-axis configuration
    axes_config = config['axes']
    x_axis_config = axes_config['x_axis']

    # Overall layout from config
    layout_config = config['layout']
    colors = style_config['colors']

    fig.update_layout(
        title=dict(
            text=f'<b>{manager_name}: {program_nice_name}</b><br><sub>Monthly Rolling Performance (Std Dev & Max DD from Daily Returns)</sub>',
            font=dict(
                size=fonts['title_size'],
                family=fonts['family'],
                color=colors['text']
            ),
            x=0.5,
            xanchor='center',
            y=0.99,
            yanchor='top'
        ),
        height=layout_config['height'],
        width=layout_config['width'],
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            font=dict(size=fonts['legend_size'], family=fonts['family']),
            bgcolor='rgba(255, 255, 255, 0.9)',
            bordercolor=colors['axis_line'],
            borderwidth=1
        ),
        hovermode=layout_config['hovermode'],
        plot_bgcolor=layout_config['plot_bgcolor'],
        paper_bgcolor=layout_config['paper_bgcolor'],
        margin=layout_config['margin']
    )

    # Update all x-axes with date formatting
    print(f"\nApplying x-axis settings to 4 panels...")

    for row in range(1, 5):
        fig.update_xaxes(
            tickfont=dict(
                size=fonts['axis_tick_size'],
                family=fonts['family'],
                color=colors.get('text_secondary', '#7f8c8d')
            ),
            tickangle=-45,
            title_text="Date" if row == 4 else "",
            title_font=dict(size=fonts['axis_title_size']),
            showgrid=x_axis_config['showgrid'],
            gridcolor=colors['grid'],
            gridwidth=x_axis_config['gridwidth'],
            showline=x_axis_config['showline'],
            linewidth=x_axis_config['linewidth'],
            linecolor=colors['axis_line'],
            tickformat='%Y-%m',
            dtick='M12',  # Tick every 12 months
            row=row, col=1
        )

    y_axis_config = axes_config['y_axis']
    fig.update_yaxes(
        showgrid=y_axis_config['showgrid'],
        gridcolor=colors['grid'],
        gridwidth=y_axis_config['gridwidth'],
        showline=y_axis_config['showline'],
        linewidth=y_axis_config['linewidth'],
        linecolor=colors['axis_line'],
        tickfont=dict(size=fonts['axis_tick_size']),
        zeroline=True,
        zerolinewidth=1.5,
        zerolinecolor='#666666'
    )

    # Export to PDF and HTML
    print("\nExporting to PDF and HTML...")

    os.makedirs("export", exist_ok=True)
    output_path_pdf = "export/alphabet_mft_monthly_performance_v2.pdf"
    output_path_html = "export/alphabet_mft_monthly_performance_v2_debug.html"

    fig.write_html(output_path_html)
    print(f"  [OK] Saved HTML to: {output_path_html}")

    fig.write_image(output_path_pdf, format='pdf')
    print(f"  [OK] Saved PDF to: {output_path_pdf}")

    # Print summary statistics
    print("\nSummary Statistics:")
    print("=" * 70)
    print(f"Total Months: {len(df)}")
    print(f"Date Range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"\nMonthly Returns:")
    print(f"  Mean:   {df['prog_mean'].mean()*100:>8.2f}%")
    print(f"  Median: {df['prog_mean'].median()*100:>8.2f}%")
    print(f"  Min:    {df['prog_mean'].min()*100:>8.2f}%")
    print(f"  Max:    {df['prog_mean'].max()*100:>8.2f}%")
    print(f"\nStd Dev (Annualized from Daily Returns - Industry Standard):")
    print(f"  Mean:   {df['prog_std'].mean()*100:>8.2f}%")
    print(f"  Median: {df['prog_std'].median()*100:>8.2f}%")
    print(f"  Min:    {df['prog_std'].min()*100:>8.2f}%")
    print(f"  Max:    {df['prog_std'].max()*100:>8.2f}%")
    print(f"\nAverage Daily Data Points per Month: {df['daily_count'].mean():.1f}")

    print("\n" + "=" * 70)
    print("PDF generated successfully!")
    print("=" * 70)

    db.close()


if __name__ == "__main__":
    main()
