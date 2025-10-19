"""
Generate 4-panel non-overlapping 5-year performance chart comparing Rise CTA vs all benchmarks.

Creates a PDF with 4 vertically stacked panels showing:
1. Mean monthly return (5-year non-overlapping)
2. Standard deviation (5-year non-overlapping)
3. CAGR (5-year non-overlapping)
4. Maximum drawdown compounded (5-year non-overlapping)

Each panel shows Rise CTA 30B program and all available benchmarks (SP500, BTOP50, AREIT, Leading Competitor).
Benchmarks are only included in periods where they have complete data.
"""

from database import Database
from windows import generate_window_definitions_non_overlapping_reverse, Window, compute_statistics
from datetime import date
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from components.chart_config import (
    load_chart_config,
    get_series_color,
    get_line_width
)


def main(fund_size_m=30000):
    """
    Generate non-overlapping 5-year performance chart.

    Args:
        fund_size_m: Fund size in millions (default: 30000 for 30B)
    """
    db = Database('pnlrg.db')
    db.connect()

    print("=" * 70)
    print("NON-OVERLAPPING 5-YEAR PERFORMANCE CHART GENERATOR")
    print("=" * 70)

    # Get CTA program for specified fund size with manager info
    program = db.fetch_one("""
        SELECT p.id, p.program_name, p.program_nice_name, p.fund_size, m.manager_name
        FROM programs p
        JOIN managers m ON p.manager_id = m.id
        WHERE p.program_name LIKE ? OR p.program_name LIKE ?
        LIMIT 1
    """, (f'%{fund_size_m}M%', f'%{fund_size_m//1000}B%'))

    if not program:
        print(f"\nError: Could not find CTA program with fund size {fund_size_m}M!")
        print("Looking for any CTA program with largest fund size...")
        program = db.fetch_one("""
            SELECT p.id, p.program_name, p.program_nice_name, p.fund_size, m.manager_name
            FROM programs p
            JOIN managers m ON p.manager_id = m.id
            WHERE p.program_name != 'Benchmarks'
            ORDER BY p.fund_size DESC
            LIMIT 1
        """)

    program_id = program['id']
    program_name = program['program_name']
    program_nice_name = program['program_nice_name'] or program_name  # Fallback to program_name if nice_name is null
    manager_name = program['manager_name']
    fund_size_actual = program['fund_size']

    print(f"\nManager: {manager_name}")
    print(f"Program: {program_name}")
    print(f"Fund Size: ${program['fund_size']:,.0f}")

    # Get all benchmarks with their date ranges
    benchmarks = db.fetch_all("""
        SELECT m.id, m.name, m.is_benchmark
        FROM markets m
        WHERE m.is_benchmark = 1
        ORDER BY m.name
    """)

    benchmark_info = {}
    benchmark_ids = []

    print("\nBenchmarks:")
    for bm in benchmarks:
        prog = db.fetch_one('SELECT id FROM programs WHERE program_name = "Benchmarks"')
        date_range = db.fetch_one("""
            SELECT MIN(date) as min_date, MAX(date) as max_date
            FROM pnl_records
            WHERE program_id = ? AND market_id = ?
        """, (prog['id'], bm['id']))

        if date_range and date_range['min_date']:
            start = date.fromisoformat(date_range['min_date'])
            end = date.fromisoformat(date_range['max_date'])
            benchmark_info[bm['id']] = {
                'name': bm['name'],
                'start': start,
                'end': end
            }
            benchmark_ids.append(bm['id'])
            print(f"  {bm['name']:20} {start} to {end}")

    # Get data range for program
    data_range = db.fetch_one("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM pnl_records
        WHERE program_id = ?
    """, (program_id,))

    earliest_date = date.fromisoformat(data_range['min_date'])
    latest_date = date.fromisoformat(data_range['max_date'])

    print(f"\nProgram Data Range: {earliest_date} to {latest_date}")

    # Generate non-overlapping 5-year windows working backwards from end date
    # This ensures the most recent 5-year period is fully captured
    print("\nGenerating non-overlapping 5-year windows (reverse from latest date)...")

    windows = generate_window_definitions_non_overlapping_reverse(
        earliest_date=earliest_date,
        latest_date=latest_date,
        window_length_years=5,
        program_ids=[program_id],
        benchmark_ids=benchmark_ids,
        window_set_name="non_overlapping_5yr_reverse"
    )

    print(f"  Generated {len(windows)} windows")
    print(f"  Window periods:")
    for win in windows:
        print(f"    {win.start_date} to {win.end_date}")

    # Compute statistics for each window
    print("\nComputing statistics for each window...")

    results = []
    for i, win_def in enumerate(windows):
        print(f"\n  Window {i+1}/{len(windows)}: {win_def.start_date} to {win_def.end_date}")

        window = Window(win_def, db)

        # Get data for program
        prog_data = window.get_manager_data(program_id)

        if len(prog_data) < 50:  # Need at least 50 months out of 60
            print(f"    Skipped: Insufficient program data ({len(prog_data)} months)")
            continue

        # Compute statistics for program
        prog_stats = compute_statistics(window, program_id, entity_type='manager')

        result = {
            'date': win_def.end_date,  # Use end date for x-axis
            'window_name': win_def.name,
            'prog_mean': prog_stats.mean,
            'prog_std': prog_stats.std_dev,
            'prog_cagr': prog_stats.cagr,
            'prog_max_dd': prog_stats.max_drawdown_compounded,
        }

        # Add benchmark statistics (only if they have complete data for this window)
        for bm_id in benchmark_ids:
            bm_name = benchmark_info[bm_id]['name']
            bm_start = benchmark_info[bm_id]['start']
            bm_end = benchmark_info[bm_id]['end']

            # Check if benchmark covers this window
            if bm_start <= win_def.start_date and bm_end >= win_def.end_date:
                bm_data = window.get_benchmark_data(bm_id)

                if len(bm_data) >= 50:  # Need at least 50 months
                    bm_stats = compute_statistics(window, bm_id, entity_type='benchmark')

                    result[f'{bm_name}_mean'] = bm_stats.mean
                    result[f'{bm_name}_std'] = bm_stats.std_dev
                    result[f'{bm_name}_cagr'] = bm_stats.cagr
                    result[f'{bm_name}_max_dd'] = bm_stats.max_drawdown_compounded

                    print(f"    Included {bm_name}")
                else:
                    result[f'{bm_name}_mean'] = None
                    result[f'{bm_name}_std'] = None
                    result[f'{bm_name}_cagr'] = None
                    result[f'{bm_name}_max_dd'] = None
                    print(f"    Excluded {bm_name}: Insufficient data")
            else:
                # Benchmark doesn't cover this window
                result[f'{bm_name}_mean'] = None
                result[f'{bm_name}_std'] = None
                result[f'{bm_name}_cagr'] = None
                result[f'{bm_name}_max_dd'] = None
                print(f"    Excluded {bm_name}: Outside date range")

        results.append(result)

    print(f"\nComputed statistics for {len(results)} windows")

    # Convert to DataFrame
    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])

    # Create a string version of dates for x-axis (to avoid kaleido PDF rendering bug)
    # Use yyyy-mm-dd format to show exact end dates
    df['date_label'] = df['date'].dt.strftime('%Y-%m-%d')

    print(f"\nWindow end dates: {df['date_label'].tolist()}")

    # Load chart configuration
    print("\nLoading chart configuration from database...")
    config = load_chart_config(db, chart_type='rolling_performance')

    panel_config = config['panel']
    style_config = config['style']

    print(f"  Using preset: rolling_performance")
    print(f"  Paper size: {config['layout']['width']}x{config['layout']['height']} (A4)")

    # Create 4-panel stacked chart using titles from config
    print("\nCreating 4-panel chart...")

    # Get panel titles from config (already updated in database)
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

        # Add Rise CTA with color from config
        rise_color = get_series_color(config, 'primary', index=0)
        line_width = get_line_width(config, 'default')
        marker_size = style_config['markers']['size']

        fig.add_trace(
            go.Scatter(
                x=df['date_label'],  # Use string year labels for kaleido PDF compatibility
                y=df[f'prog_{metric_key}'] * 100,
                name='Rise CTA',
                line=dict(color=rise_color, width=line_width),
                marker=dict(size=marker_size),
                legendgroup='rise',
                showlegend=(row == 1),
                mode=config['series']['mode']  # From config: 'lines+markers'
            ),
            row=row, col=1
        )

        # Add benchmarks with colors from config
        for bm_id in benchmark_ids:
            bm_name = benchmark_info[bm_id]['name']
            col_name = f'{bm_name}_{metric_key}'

            # Only plot if there's at least one non-null value
            if col_name in df.columns and df[col_name].notna().any():
                bm_color = get_series_color(config, bm_name, index=bm_id)

                fig.add_trace(
                    go.Scatter(
                        x=df['date_label'],  # Use string year labels for kaleido PDF compatibility
                        y=df[col_name] * 100,
                        name=bm_name,
                        line=dict(color=bm_color, width=line_width),
                        marker=dict(size=marker_size),
                        legendgroup=bm_name.lower().replace(' ', '_'),
                        showlegend=(row == 1),
                        mode=config['series']['mode'],
                        connectgaps=config['series']['connectgaps']
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

    # X-axis configuration for categorical year labels
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
            y=1.02,  # Position above the title, below top margin
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
    print(f"\nApplying x-axis settings to {4} panels...")

    # Create explicit tick values and text to force display of all dates
    tick_vals = df['date_label'].tolist()
    tick_text = df['date_label'].tolist()  # Use the yyyy-mm-dd strings directly

    print(f"  Setting explicit tick labels: {tick_text}")

    for row in range(1, 5):
        fig.update_xaxes(
            # Explicit tick values to force all labels to show
            tickmode='array',
            tickvals=tick_vals,
            ticktext=tick_text,
            # Font styling with angle for readability
            tickfont=dict(
                size=7,  # Even smaller to fit all yyyy-mm-dd dates
                family=fonts['family'],
                color=colors.get('text_secondary', '#7f8c8d')
            ),
            tickangle=-45,  # Rotate labels for better fit
            # Title (only on bottom panel)
            title_text="Period End Date" if row == 4 else "",
            title_font=dict(size=fonts['axis_title_size']),
            # Grid and axis styling from config
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
        # Add visible zero line
        zeroline=True,
        zerolinewidth=1.5,
        zerolinecolor='#666666'  # Dark gray for visibility
    )

    # Export to PDF and HTML for debugging
    print("\nExporting to PDF and HTML...")

    os.makedirs("export", exist_ok=True)
    # Include fund size in filename
    fund_size_label = f"{fund_size_m}M" if fund_size_m < 1000 else f"{fund_size_m}M"
    output_path_pdf = f"export/non_overlapping_5yr_performance_{fund_size_label}.pdf"
    output_path_html = f"export/non_overlapping_5yr_performance_{fund_size_label}_debug.html"

    fig.write_html(output_path_html)
    print(f"  [OK] Saved HTML to: {output_path_html}")

    fig.write_image(output_path_pdf, format='pdf')
    print(f"  [OK] Saved PDF to: {output_path_pdf}")

    # Print summary statistics for each window
    print("\nSummary Statistics by Period:")
    print("=" * 70)

    for idx, row in df.iterrows():
        print(f"\n{row['window_name']} (ending {row['date'].date()}):")
        print(f"\n  Rise CTA:")
        print(f"    Mean Monthly Return: {row['prog_mean']*100:>8.2f}%")
        print(f"    Std Deviation:       {row['prog_std']*100:>8.2f}%")
        print(f"    CAGR (5yr):          {row['prog_cagr']*100:>8.2f}%")
        print(f"    Max Drawdown (5yr):  {row['prog_max_dd']*100:>8.2f}%")

        # Print available benchmarks for this window
        for bm_id in benchmark_ids:
            bm_name = benchmark_info[bm_id]['name']
            if f'{bm_name}_cagr' in row and pd.notna(row[f'{bm_name}_cagr']):
                print(f"\n  {bm_name}:")
                print(f"    Mean Monthly Return: {row[f'{bm_name}_mean']*100:>8.2f}%")
                print(f"    Std Deviation:       {row[f'{bm_name}_std']*100:>8.2f}%")
                print(f"    CAGR (5yr):          {row[f'{bm_name}_cagr']*100:>8.2f}%")
                print(f"    Max Drawdown (5yr):  {row[f'{bm_name}_max_dd']*100:>8.2f}%")

    print("\n" + "=" * 70)
    print("PDF generated successfully!")
    print("=" * 70)

    db.close()


if __name__ == "__main__":
    import sys

    # Allow specifying fund size as command line argument
    # Usage: python generate_non_overlapping_performance_chart.py [fund_size_in_millions]
    # Example: python generate_non_overlapping_performance_chart.py 1000
    fund_size_m = int(sys.argv[1]) if len(sys.argv) > 1 else 30000

    main(fund_size_m)
