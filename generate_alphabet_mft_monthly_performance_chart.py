"""
Generate 4-panel non-overlapping 1-month (monthly) rolling performance chart for Alphabet MFT.

Creates a PDF with 4 vertically stacked panels showing:
1. Mean monthly return (1-month rolling windows)
2. Standard deviation (1-month rolling windows)
3. CAGR (1-month rolling windows)
4. Maximum drawdown compounded (1-month rolling windows)

Uses line charts (no markers) for visualizing the many data points.
Shows the aggregate Alphabet MFT program performance (sum of all sectors).
Handles daily data by aggregating to monthly returns.

This chart type is registered in the database as 'monthly_rolling_performance'.
"""

from database import Database
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


def calculate_max_drawdown(returns):
    """Calculate maximum drawdown from compounded returns."""
    if len(returns) == 0:
        return 0.0

    # Compound returns to get NAV curve
    nav = (1 + pd.Series(returns)).cumprod()

    # Calculate running maximum
    running_max = nav.expanding().max()

    # Calculate drawdown at each point
    drawdown = (nav - running_max) / running_max

    # Return the most negative drawdown
    return float(drawdown.min())


def aggregate_daily_to_monthly(daily_returns_df):
    """
    Aggregate daily returns to monthly returns.

    Args:
        daily_returns_df: DataFrame with 'date' and 'return' columns

    Returns:
        DataFrame with monthly returns
    """
    if len(daily_returns_df) == 0:
        return pd.DataFrame(columns=['date', 'return'])

    # Ensure date is datetime
    df = daily_returns_df.copy()
    df['date'] = pd.to_datetime(df['date'])

    # Group by year-month and compound returns within each month
    df['year_month'] = df['date'].dt.to_period('M')

    monthly_returns = []
    for period, group in df.groupby('year_month'):
        # Compound daily returns to get monthly return
        monthly_return = (1 + group['return']).prod() - 1
        # Use last day of the month as the date
        month_end_date = group['date'].max()
        monthly_returns.append({
            'date': month_end_date,
            'return': monthly_return
        })

    return pd.DataFrame(monthly_returns)


def main():
    """
    Generate non-overlapping monthly (1-month) rolling performance chart for Alphabet MFT.

    Since each window is 1 month, this essentially shows month-by-month statistics
    where each month's statistics are based on that single month's return.
    """
    db = Database('pnlrg.db')
    db.connect()

    print("=" * 70)
    print("ALPHABET MFT - MONTHLY ROLLING PERFORMANCE CHART")
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

    # Get all daily returns for the program (sum across all markets/sectors)
    print("\nFetching daily returns and aggregating across all sectors...")
    daily_data = db.fetch_all("""
        SELECT pr.date, SUM(pr.return) as total_return
        FROM pnl_records pr
        WHERE pr.program_id = ?
        AND pr.resolution = 'daily'
        GROUP BY pr.date
        ORDER BY pr.date
    """, (program_id,))

    if not daily_data:
        print("\nError: No daily data found for Alphabet MFT!")
        db.close()
        return

    # Convert to DataFrame
    daily_df = pd.DataFrame(daily_data, columns=['date', 'return'])
    daily_df['date'] = pd.to_datetime(daily_df['date'])

    print(f"  Found {len(daily_df)} days of data")
    print(f"  Date range: {daily_df['date'].min().date()} to {daily_df['date'].max().date()}")

    # Aggregate to monthly returns
    print("\nAggregating daily returns to monthly...")
    monthly_df = aggregate_daily_to_monthly(daily_df)
    print(f"  Generated {len(monthly_df)} months of data")

    # For monthly windows, each month becomes its own "window"
    # Statistics for a single month:
    # - Mean: The return itself (average of 1 value)
    # - Std: 0 (only one value)
    # - CAGR: Annualized return (return * 12 for approximation, or proper annualization)
    # - Max DD: 0 or the negative return if it's negative

    print("\nComputing statistics for each month...")

    results = []
    for idx, row in monthly_df.iterrows():
        month_return = row['return']
        month_date = row['date']

        # For a single month:
        # Mean is just the return itself
        mean = month_return

        # Std dev is 0 (only one data point)
        std_dev = 0.0

        # CAGR: Annualize the monthly return
        # CAGR = (1 + monthly_return)^12 - 1
        cagr = (1 + month_return) ** 12 - 1

        # Max drawdown: If the return is negative, it's the drawdown; otherwise 0
        max_dd = min(0.0, month_return)

        results.append({
            'date': month_date,
            'prog_mean': mean,
            'prog_std': std_dev,
            'prog_cagr': cagr,
            'prog_max_dd': max_dd,
        })

    print(f"\nComputed statistics for {len(results)} months")

    if not results:
        print("\nError: No data to plot!")
        db.close()
        return

    # Convert to DataFrame
    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])

    # Create date labels for x-axis (use year-month format)
    df['date_label'] = df['date'].dt.strftime('%Y-%m')

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
    print("\nCreating 4-panel line chart...")

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

        # Add Alphabet MFT as line chart (no markers)
        prog_color = get_series_color(config, 'primary', index=0)
        line_width = get_line_width(config, 'default')

        fig.add_trace(
            go.Scatter(
                x=df['date'],  # Use actual date for x-axis
                y=df[f'prog_{metric_key}'] * 100,
                name='Alphabet MFT',
                line=dict(color=prog_color, width=line_width),
                mode='lines',  # Lines only, no markers
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
            text=f'<b>{manager_name}: {program_nice_name}</b><br><sub>Monthly Rolling Performance</sub>',
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
            # Use default date formatting
            tickformat='%Y-%m',
            dtick='M12',  # Tick every 12 months (yearly)
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
    output_path_pdf = "export/alphabet_mft_monthly_performance.pdf"
    output_path_html = "export/alphabet_mft_monthly_performance_debug.html"

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
    print(f"  Std:    {df['prog_mean'].std()*100:>8.2f}%")
    print(f"  Min:    {df['prog_mean'].min()*100:>8.2f}%")
    print(f"  Max:    {df['prog_mean'].max()*100:>8.2f}%")
    print(f"\nAnnualized (CAGR):")
    print(f"  Mean:   {df['prog_cagr'].mean()*100:>8.2f}%")
    print(f"  Median: {df['prog_cagr'].median()*100:>8.2f}%")
    print(f"  Min:    {df['prog_cagr'].min()*100:>8.2f}%")
    print(f"  Max:    {df['prog_cagr'].max()*100:>8.2f}%")

    print("\n" + "=" * 70)
    print("PDF generated successfully!")
    print("=" * 70)

    db.close()


if __name__ == "__main__":
    main()
