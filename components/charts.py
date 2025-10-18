"""
Chart generation components for brochures.

Each function generates a specific type of chart and returns a Plotly figure object.
"""

import pandas as pd
import plotly.graph_objects as go
from datetime import datetime


def equity_curve_chart(db, program_id, benchmarks=None, date_range=None, **kwargs):
    """
    Generate equity curve chart comparing program performance vs benchmarks.

    Args:
        db: Database instance
        program_id: Program ID to chart
        benchmarks: List of benchmark market names (e.g., ['SP500', 'BTOP50'])
        date_range: Dict with 'start' and/or 'end' dates (YYYY-MM-DD)
        **kwargs: Additional chart customization
            - title: Custom chart title
            - width: Chart width in pixels (default 1200)
            - height: Chart height in pixels (default 700)
            - colors: Dict mapping series names to colors

    Returns:
        Plotly Figure object
    """
    # Get program metadata
    program = db.fetch_one("""
        SELECT p.id, p.program_name, p.starting_nav, p.starting_date, m.manager_name
        FROM programs p
        JOIN managers m ON p.manager_id = m.id
        WHERE p.id = ?
    """, (program_id,))

    if not program:
        raise ValueError(f"Program ID {program_id} not found")

    starting_nav = program['starting_nav']
    starting_date = program['starting_date']
    manager_name = program['manager_name']

    # Get program returns
    returns_data = db.fetch_all("""
        SELECT pr.date, pr.return
        FROM pnl_records pr
        JOIN markets m ON pr.market_id = m.id
        WHERE pr.program_id = ?
        AND m.name = 'Rise'
        AND pr.resolution = 'monthly'
        ORDER BY pr.date
    """, (program_id,))

    # Convert to DataFrame
    df = pd.DataFrame(returns_data, columns=['date', 'return'])
    df['date'] = pd.to_datetime(df['date'])

    # Apply date range filter if specified
    if date_range:
        if 'start' in date_range:
            df = df[df['date'] >= pd.to_datetime(date_range['start'])]
        if 'end' in date_range:
            df = df[df['date'] <= pd.to_datetime(date_range['end'])]

    # Calculate NAV in thousands
    df['nav'] = (starting_nav * (1 + df['return']).cumprod()) / 1000

    # Add starting point (in thousands)
    start_row = pd.DataFrame({
        'date': [pd.to_datetime(starting_date)],
        'return': [0.0],
        'nav': [starting_nav / 1000]
    })
    df = pd.concat([start_row, df], ignore_index=True)

    # Professional color scheme
    default_colors = {
        'program': '#1f77b4',  # Professional blue
        'SP500': '#ff7f0e',    # Warm orange
        'BTOP50': '#2ca02c',   # Green
        'AREIT': '#d62728',    # Red
        'Leading Competitor': '#9467bd'  # Purple
    }
    colors = kwargs.get('colors', default_colors)

    # Create figure
    fig = go.Figure()

    # Add program line
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['nav'],
        name=manager_name,
        line=dict(color=colors.get('program', default_colors['program']), width=3),
        mode='lines',
        hovertemplate=f'<b>{manager_name}</b><br>Date: %{{x|%Y-%m-%d}}<br>NAV: $%{{y:,.1f}}K<extra></extra>'
    ))

    # Add benchmark lines if specified
    if benchmarks:
        benchmarks_program = db.fetch_one("SELECT id FROM programs WHERE program_name = 'Benchmarks'")

        if benchmarks_program:
            for benchmark in benchmarks:
                bm_data = db.fetch_all("""
                    SELECT pr.date, pr.return
                    FROM pnl_records pr
                    JOIN markets m ON pr.market_id = m.id
                    WHERE pr.program_id = ?
                    AND m.name = ?
                    AND pr.resolution = 'monthly'
                    ORDER BY pr.date
                """, (benchmarks_program['id'], benchmark))

                if bm_data:
                    bm_df = pd.DataFrame(bm_data, columns=['date', 'return'])
                    bm_df['date'] = pd.to_datetime(bm_df['date'])

                    # Check if benchmark has data in the program's date range
                    bm_start_date = bm_df['date'].min()
                    program_start_date = df['date'].min()

                    # Only include benchmark if it has data from program start (or user-specified start)
                    effective_start = program_start_date
                    if date_range and 'start' in date_range:
                        effective_start = pd.to_datetime(date_range['start'])

                    # Compare year-month only (allow same month even if different day)
                    bm_start_ym = (bm_start_date.year, bm_start_date.month)
                    effective_start_ym = (effective_start.year, effective_start.month)

                    if bm_start_ym > effective_start_ym:
                        # Benchmark starts after the effective start month - skip it
                        print(f"  Warning: {benchmark} data starts {bm_start_date.strftime('%Y-%m')}, "
                              f"after chart start {effective_start.strftime('%Y-%m')} - skipping")
                        continue

                    # Apply date range filter
                    if date_range:
                        if 'start' in date_range:
                            bm_df = bm_df[bm_df['date'] >= pd.to_datetime(date_range['start'])]
                        if 'end' in date_range:
                            bm_df = bm_df[bm_df['date'] <= pd.to_datetime(date_range['end'])]

                    if len(bm_df) == 0:
                        continue

                    # Calculate benchmark NAV in thousands
                    bm_df['nav'] = (starting_nav * (1 + bm_df['return']).cumprod()) / 1000

                    # Add starting point (use same starting date as program, in thousands)
                    bm_start = pd.DataFrame({
                        'date': [effective_start],
                        'return': [0.0],
                        'nav': [starting_nav / 1000]
                    })
                    bm_df = pd.concat([bm_start, bm_df], ignore_index=True)

                    fig.add_trace(go.Scatter(
                        x=bm_df['date'],
                        y=bm_df['nav'],
                        name=benchmark,
                        line=dict(color=colors.get(benchmark, default_colors.get(benchmark, '#999999')), width=3),
                        mode='lines',
                        hovertemplate=f'<b>{benchmark}</b><br>Date: %{{x|%Y-%m-%d}}<br>NAV: $%{{y:,.1f}}K<extra></extra>'
                    ))

    # Determine date range for title
    date_start = df['date'].min().strftime('%B %Y')
    date_end = df['date'].max().strftime('%B %Y')

    # Update layout
    title_text = kwargs.get('title', f'<b>{manager_name} Compound NAV</b><br><sub>{date_start} - {date_end}</sub>')

    # Calculate x-axis tick values for year labels (every 5 years)
    chart_start_year = df['date'].min().year
    chart_end_year = df['date'].max().year

    # Find first year divisible by 5 after start
    first_tick_year = ((chart_start_year + 4) // 5) * 5

    # Generate tick dates every 5 years using pd.date_range
    tick_dates = pd.date_range(
        start=f'{first_tick_year}-01-01',
        end=f'{chart_end_year}-01-01',
        freq='5YS'
    )
    tick_labels = [str(d.year) for d in tick_dates]

    fig.update_layout(
        title=dict(
            text=title_text,
            font=dict(size=24, family='Arial, sans-serif', color='#2c3e50'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor='#e5e5e5',
            gridwidth=1,
            zeroline=False,
            tickfont=dict(size=12, color='#2c3e50'),
            showline=True,
            linewidth=2,
            linecolor='#bdc3c7',
            # Show years every 5 years
            tickmode='array',
            tickvals=tick_dates,
            ticktext=tick_labels,
            tickangle=0
        ),
        yaxis=dict(
            title=dict(
                text='<b>NAV ($1K)</b>',
                font=dict(size=14, family='Arial, sans-serif', color='#34495e')
            ),
            showgrid=True,
            gridcolor='#e5e5e5',
            gridwidth=1,
            zeroline=False,
            tickfont=dict(size=11, color='#7f8c8d'),
            tickformat=',.0f',
            showline=True,
            linewidth=2,
            linecolor='#bdc3c7'
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='white',
            font_size=12,
            font_family='Arial, sans-serif',
            bordercolor='#bdc3c7'
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            font=dict(size=12, family='Arial, sans-serif', color='#2c3e50'),
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='#bdc3c7',
            borderwidth=1
        ),
        margin=dict(l=80, r=40, t=100, b=60),
        width=kwargs.get('width', 1200),
        height=kwargs.get('height', 700)
    )

    return fig


def drawdown_chart(db, program_id, date_range=None, **kwargs):
    """
    Generate drawdown chart showing peak-to-trough declines.

    Args:
        db: Database instance
        program_id: Program ID to chart
        date_range: Dict with 'start' and/or 'end' dates
        **kwargs: Additional chart customization

    Returns:
        Plotly Figure object
    """
    # TODO: Implement drawdown calculation
    # For now, return a placeholder
    fig = go.Figure()
    fig.add_annotation(
        text="Drawdown Chart - Coming Soon",
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=20)
    )
    return fig


def monthly_returns_heatmap(db, program_id, years=None, **kwargs):
    """
    Generate monthly returns heatmap.

    Args:
        db: Database instance
        program_id: Program ID to chart
        years: List of years to include, or None for all
        **kwargs: Additional chart customization

    Returns:
        Plotly Figure object
    """
    # TODO: Implement monthly returns heatmap
    fig = go.Figure()
    fig.add_annotation(
        text="Monthly Returns Heatmap - Coming Soon",
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=20)
    )
    return fig
