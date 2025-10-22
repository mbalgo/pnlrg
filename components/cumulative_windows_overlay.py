"""
Cumulative Windows Overlay Chart Component

Generates charts showing cumulative NAV curves for multiple non-overlapping time windows,
overlaid on a single chart. This visualizes consistency of returns across different periods.

Features:
- Multiple windows displayed as overlaid lines
- X-axis normalized to trading days since window start
- Y-axis shows NAV starting from initial capital (e.g., $10M)
- Benchmark comparison with matched colors (solid = strategy, dashed = benchmark)
- Compounded returns (NAV grows/shrinks based on cumulative performance)
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import List, Dict, Optional
from datetime import date


def calculate_cumulative_nav(daily_returns: List[float], starting_nav: float = 10_000_000) -> List[float]:
    """
    Calculate cumulative NAV from daily returns using compounding.

    Args:
        daily_returns: List of daily returns as decimals (0.01 = 1%)
        starting_nav: Initial NAV value (default: $10M)

    Returns:
        List of NAV values, including day 0 (starting NAV)

    Example:
        returns = [0.01, -0.005, 0.02]
        nav = calculate_cumulative_nav(returns, 10_000_000)
        # Returns: [10_000_000, 10_100_000, 10_049_500, 10_250_490]
    """
    if not daily_returns:
        return [starting_nav]

    # Start with initial NAV
    nav_curve = [starting_nav]

    # Compound each day's return
    current_nav = starting_nav
    for daily_return in daily_returns:
        current_nav = current_nav * (1 + daily_return)
        nav_curve.append(current_nav)

    return nav_curve


def calculate_cumulative_nav_additive(daily_returns: List[float], starting_nav: float = 10_000_000) -> List[float]:
    """
    Calculate cumulative NAV from daily returns using additive (non-compounded) method.

    Each day's dollar gain/loss is based on the original starting NAV, not the current NAV.
    This shows the simple sum of returns without geometric compounding.

    Args:
        daily_returns: List of daily returns as decimals (0.01 = 1%)
        starting_nav: Initial NAV value (default: $10M)

    Returns:
        List of NAV values, including day 0 (starting NAV)

    Example:
        returns = [0.01, -0.005, 0.02]
        nav = calculate_cumulative_nav_additive(returns, 10_000_000)
        # Returns: [10_000_000, 10_100_000, 10_150_000, 10_350_000]
        # Day 1: $10M + ($10M × 0.01) = $10.1M
        # Day 2: $10.1M + ($10M × -0.005) = $10.05M
        # Day 3: $10.05M + ($10M × 0.02) = $10.25M
    """
    if not daily_returns:
        return [starting_nav]

    # Start with initial NAV
    nav_curve = [starting_nav]

    # Add each day's dollar return (based on original starting NAV)
    current_nav = starting_nav
    for daily_return in daily_returns:
        dollar_change = starting_nav * daily_return
        current_nav = current_nav + dollar_change
        nav_curve.append(current_nav)

    return nav_curve


def get_daily_returns_for_window(db, program_id: int, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Fetch daily returns for a program within a date window.
    Aggregates across all trading markets (SUM of returns), excluding benchmarks.

    Args:
        db: Database connection
        program_id: Program ID to query
        start_date: Window start date (inclusive)
        end_date: Window end date (inclusive)

    Returns:
        DataFrame with columns: ['date', 'return']
    """
    query = """
        SELECT pr.date, SUM(pr.return) as total_return
        FROM pnl_records pr
        JOIN markets m ON pr.market_id = m.id
        WHERE pr.program_id = ?
          AND pr.resolution = 'daily'
          AND pr.date >= ?
          AND pr.date <= ?
          AND m.is_benchmark = 0
        GROUP BY pr.date
        ORDER BY pr.date
    """

    data = db.fetch_all(query, (program_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

    if not data:
        return pd.DataFrame(columns=['date', 'return'])

    df = pd.DataFrame(data, columns=['date', 'return'])
    df['date'] = pd.to_datetime(df['date'])

    return df


def get_benchmark_returns_for_window(db, benchmark_market_id: int, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Fetch daily benchmark returns within a date window.

    Args:
        db: Database connection
        benchmark_market_id: Market ID for benchmark (e.g., SP500)
        start_date: Window start date (inclusive)
        end_date: Window end date (inclusive)

    Returns:
        DataFrame with columns: ['date', 'return']
    """
    query = """
        SELECT pr.date, pr.return
        FROM pnl_records pr
        WHERE pr.market_id = ?
          AND pr.resolution = 'daily'
          AND pr.date >= ?
          AND pr.date <= ?
        ORDER BY pr.date
    """

    data = db.fetch_all(query, (benchmark_market_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

    if not data:
        return pd.DataFrame(columns=['date', 'return'])

    df = pd.DataFrame(data, columns=['date', 'return'])
    df['date'] = pd.to_datetime(df['date'])

    return df


def generate_cumulative_windows_overlay(
    db,
    program_id: int,
    windows: List[Dict],
    benchmark_market_id: Optional[int] = None,
    starting_nav: float = 10_000_000,
    output_path: str = None,
    title: str = None,
    subtitle: str = None
) -> go.Figure:
    """
    Generate cumulative windows overlay chart.

    Args:
        db: Database connection
        program_id: Program ID to analyze
        windows: List of window dicts with 'start_date', 'end_date', 'name'
        benchmark_market_id: Optional benchmark market ID (e.g., SP500)
        starting_nav: Initial NAV for each window
        output_path: Path to save PDF (if None, returns figure only)
        title: Chart title
        subtitle: Chart subtitle

    Returns:
        Plotly Figure object
    """
    # Color palette for windows (up to 8 distinct colors)
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

        # Get program returns
        program_df = get_daily_returns_for_window(db, program_id, start_date, end_date)

        if len(program_df) == 0:
            print(f"Warning: No data for window {window_name}")
            continue

        # Calculate cumulative NAV
        nav_curve = calculate_cumulative_nav(program_df['return'].tolist(), starting_nav)
        trading_days = list(range(len(nav_curve)))

        # Add strategy line (solid)
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
                # Calculate benchmark NAV curve directly (don't merge with program dates)
                # Benchmark may have different trading days, so we plot it independently
                benchmark_nav_curve = calculate_cumulative_nav(benchmark_df['return'].tolist(), starting_nav)
                benchmark_trading_days = list(range(len(benchmark_nav_curve)))

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
            'text': title or 'Cumulative Performance by Window',
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

    # Save to PDF if path provided
    if output_path:
        fig.write_image(output_path, format='pdf', width=1400, height=800)
        print(f"Chart saved to: {output_path}")

    return fig
