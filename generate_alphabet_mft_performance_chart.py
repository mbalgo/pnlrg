"""
Generate 4-panel non-overlapping 5-year performance chart for Alphabet MFT program.

Creates a PDF with 4 vertically stacked panels showing:
1. Mean monthly return (5-year non-overlapping)
2. Standard deviation (5-year non-overlapping)
3. CAGR (5-year non-overlapping)
4. Maximum drawdown compounded (5-year non-overlapping)

Shows the aggregate Alphabet MFT program performance (sum of all sectors).
Handles daily data by aggregating to monthly returns.
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
    Generate non-overlapping 5-year performance chart for Alphabet MFT.
    """
    db = Database('pnlrg.db')
    db.connect()

    print("=" * 70)
    print("ALPHABET MFT - NON-OVERLAPPING 5-YEAR PERFORMANCE CHART")
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

    earliest_date = monthly_df['date'].min().date()
    latest_date = monthly_df['date'].max().date()

    # Generate non-overlapping 5-year windows working backwards from end date
    print("\nGenerating non-overlapping 5-year windows (reverse from latest date)...")

    # Calculate windows manually (5 years = 60 months)
    window_length_months = 60
    windows = []

    current_end = latest_date
    window_num = 1

    while True:
        window_start = date(current_end.year - 5, current_end.month, 1)

        if window_start < earliest_date:
            break

        windows.append({
            'name': f'Window_{window_num}',
            'start_date': window_start,
            'end_date': current_end
        })

        # Move to next window (5 years earlier, minus 1 day to avoid overlap)
        current_end = window_start - relativedelta(days=1)
        window_num += 1

    # Reverse to show oldest first
    windows.reverse()

    print(f"  Generated {len(windows)} windows")
    print(f"  Window periods:")
    for win in windows:
        print(f"    {win['start_date']} to {win['end_date']}")

    # Compute statistics for each window
    print("\nComputing statistics for each window...")

    results = []
    for i, win in enumerate(windows):
        print(f"\n  Window {i+1}/{len(windows)}: {win['start_date']} to {win['end_date']}")

        # Filter monthly data to window
        window_data = monthly_df[
            (monthly_df['date'].dt.date >= win['start_date']) &
            (monthly_df['date'].dt.date <= win['end_date'])
        ].copy()

        if len(window_data) < 50:  # Need at least 50 months out of 60
            print(f"    Skipped: Insufficient data ({len(window_data)} months)")
            continue

        returns = window_data['return'].values

        # Calculate statistics
        mean = float(returns.mean())
        std_dev = float(returns.std(ddof=1))

        # CAGR
        cumulative_return = float((1 + pd.Series(returns)).prod() - 1)
        years = len(returns) / 12.0
        cagr = float(((1 + cumulative_return) ** (1.0 / years)) - 1) if years > 0 else 0.0

        # Max drawdown
        max_dd = calculate_max_drawdown(returns)

        result = {
            'date': win['end_date'],
            'window_name': win['name'],
            'prog_mean': mean,
            'prog_std': std_dev,
            'prog_cagr': cagr,
            'prog_max_dd': max_dd,
        }

        results.append(result)
        print(f"    Mean: {mean*100:.2f}%, Std: {std_dev*100:.2f}%, "
              f"CAGR: {cagr*100:.2f}%, MaxDD: {max_dd*100:.2f}%")

    print(f"\nComputed statistics for {len(results)} windows")

    if not results:
        print("\nError: No windows with sufficient data!")
        db.close()
        return

    # Convert to DataFrame
    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])

    # Create a string version of dates for x-axis (to avoid kaleido PDF rendering bug)
    df['date_label'] = df['date'].dt.strftime('%Y-%m-%d')

    print(f"\nWindow end dates: {df['date_label'].tolist()}")

    # Load chart configuration
    print("\nLoading chart configuration from database...")
    config = load_chart_config(db, chart_type='rolling_performance')

    panel_config = config['panel']
    style_config = config['style']

    print(f"  Using preset: rolling_performance")
    print(f"  Paper size: {config['layout']['width']}x{config['layout']['height']} (A4)")

    # Create 4-panel stacked chart
    print("\nCreating 4-panel chart...")

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
                x=df['date_label'],
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
            text=f'<b>{manager_name}: {program_nice_name}</b><br><sub>5-Year Non-Overlapping Performance</sub>',
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

    # Update all x-axes with styling and explicit tick labels
    print(f"\nApplying x-axis settings to 4 panels...")

    tick_vals = df['date_label'].tolist()
    tick_text = df['date_label'].tolist()

    print(f"  Setting explicit tick labels: {tick_text}")

    for row in range(1, 5):
        fig.update_xaxes(
            tickmode='array',
            tickvals=tick_vals,
            ticktext=tick_text,
            tickfont=dict(
                size=7,
                family=fonts['family'],
                color=colors.get('text_secondary', '#7f8c8d')
            ),
            tickangle=-45,
            title_text="Period End Date" if row == 4 else "",
            title_font=dict(size=fonts['axis_title_size']),
            showgrid=x_axis_config['showgrid'],
            gridcolor=colors['grid'],
            gridwidth=x_axis_config['gridwidth'],
            showline=x_axis_config['showline'],
            linewidth=x_axis_config['linewidth'],
            linecolor=colors['axis_line'],
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
    output_path_pdf = "export/alphabet_mft_5yr_performance.pdf"
    output_path_html = "export/alphabet_mft_5yr_performance_debug.html"

    fig.write_html(output_path_html)
    print(f"  [OK] Saved HTML to: {output_path_html}")

    fig.write_image(output_path_pdf, format='pdf')
    print(f"  [OK] Saved PDF to: {output_path_pdf}")

    # Print summary statistics for each window
    print("\nSummary Statistics by Period:")
    print("=" * 70)

    for idx, row in df.iterrows():
        print(f"\n{row['window_name']} (ending {row['date'].date()}):")
        print(f"\n  Alphabet MFT:")
        print(f"    Mean Monthly Return: {row['prog_mean']*100:>8.2f}%")
        print(f"    Std Deviation:       {row['prog_std']*100:>8.2f}%")
        print(f"    CAGR (5yr):          {row['prog_cagr']*100:>8.2f}%")
        print(f"    Max Drawdown (5yr):  {row['prog_max_dd']*100:>8.2f}%")

    print("\n" + "=" * 70)
    print("PDF generated successfully!")
    print("=" * 70)

    db.close()


if __name__ == "__main__":
    main()
