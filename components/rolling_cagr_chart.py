"""
Rolling CAGR Chart Component

Generates line charts showing rolling Compound Annual Growth Rate (CAGR) over time.
Uses overlapping windows with 1-day slide intervals to create smooth curves showing
how annualized returns evolve.

Features:
- Multiple window sizes: 1, 2, 3, 6 months AND 1, 2, 3, 5, 10 years
- 1-day slide intervals for maximum granularity
- Benchmark comparison support (blue=strategy, black=benchmark)
- Smart titles based on window size (years vs months)
- Zero reference line for visual clarity
- Performance optimized: fetches all data once, calculates in memory
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import List, Optional
from datetime import date
from windows import generate_window_definitions_overlapping_by_days


def calculate_cagr(returns: np.ndarray, start_date: date, end_date: date) -> float:
    """
    Calculate Compound Annual Growth Rate (CAGR) from daily returns.

    Args:
        returns: Array of daily returns as decimals (e.g., 0.01 = 1%)
        start_date: Window start date
        end_date: Window end date

    Returns:
        CAGR as decimal (e.g., 0.15 = 15% annualized return)

    Example:
        >>> returns = np.array([0.01, -0.005, 0.02])
        >>> cagr = calculate_cagr(returns, date(2024, 1, 1), date(2025, 1, 1))
        >>> # Returns annualized return
    """
    if len(returns) == 0:
        return np.nan

    # Calculate cumulative return (compounded)
    cumulative_return = np.prod(1 + returns) - 1

    # Calculate years from calendar days
    days = (end_date - start_date).days
    years = days / 365.25

    if years <= 0:
        return np.nan

    # CAGR formula: ((1 + total_return) ^ (1/years)) - 1
    cagr = ((1 + cumulative_return) ** (1.0 / years)) - 1

    return float(cagr)


def get_all_daily_returns(db, program_id: int, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Fetch ALL daily returns for a program within date range.
    Aggregates across all trading markets (excluding benchmarks).

    This is used for performance optimization: fetch once, calculate many windows in memory.

    Args:
        db: Database connection
        program_id: Program ID to query
        start_date: Data range start date
        end_date: Data range end date

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


def get_benchmark_daily_returns(db, benchmark_market_id: int, program_id: int, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Fetch ALL daily returns for a benchmark within date range.

    Args:
        db: Database connection
        benchmark_market_id: Market ID for benchmark (must have is_benchmark=1)
        program_id: Program ID that contains the benchmark data
        start_date: Data range start date
        end_date: Data range end date

    Returns:
        DataFrame with columns: ['date', 'return']
    """
    query = """
        SELECT pr.date, pr.return
        FROM pnl_records pr
        WHERE pr.program_id = ?
          AND pr.market_id = ?
          AND pr.resolution = 'daily'
          AND pr.date >= ?
          AND pr.date <= ?
        ORDER BY pr.date
    """

    data = db.fetch_all(query, (
        program_id,
        benchmark_market_id,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    ))

    if not data:
        return pd.DataFrame(columns=['date', 'return'])

    df = pd.DataFrame(data, columns=['date', 'return'])
    df['date'] = pd.to_datetime(df['date'])

    return df


def calculate_rolling_cagr_series(
    full_returns_df: pd.DataFrame,
    window_definitions: List,
    entity_name: str
) -> pd.DataFrame:
    """
    Calculate rolling CAGR for all windows using in-memory slicing (fast).

    Args:
        full_returns_df: DataFrame with all daily returns for full period
        window_definitions: List of WindowDefinition objects
        entity_name: Name for this series (e.g., "MFT" or "SP500")

    Returns:
        DataFrame with columns: ['date', 'cagr', 'entity']
    """
    results = []

    for window_def in window_definitions:
        # Slice returns for this window (in-memory, fast)
        mask = (
            (full_returns_df['date'] >= pd.Timestamp(window_def.start_date)) &
            (full_returns_df['date'] <= pd.Timestamp(window_def.end_date))
        )
        window_returns = full_returns_df[mask]['return'].values

        # Calculate CAGR for this window
        cagr = calculate_cagr(window_returns, window_def.start_date, window_def.end_date)

        # Store result (use window END date as X-axis value)
        results.append({
            'date': window_def.end_date,
            'cagr': cagr,
            'entity': entity_name
        })

    return pd.DataFrame(results)


def generate_rolling_cagr_chart(
    db,
    program_id: int,
    output_path: str,
    window_months: int,
    benchmarks: Optional[List[str]] = None,
    **kwargs
) -> go.Figure:
    """
    Generate rolling CAGR chart with 1-day slide intervals.

    Args:
        db: Database connection
        program_id: Program ID to analyze
        output_path: Path to save PDF chart
        window_months: Window size in months (e.g., 12 for 1-year rolling)
        benchmarks: Optional list of benchmark names (e.g., ['sp500', 'areit'])
        **kwargs: Additional arguments (ignored)

    Returns:
        Plotly Figure object

    Example:
        >>> with Database() as db:
        ...     fig = generate_rolling_cagr_chart(
        ...         db, program_id=11, output_path='rolling_cagr_1yr.pdf',
        ...         window_months=12, benchmarks=['sp500']
        ...     )
    """
    # Get program metadata
    program = db.fetch_one("""
        SELECT p.id, p.program_name, m.manager_name
        FROM programs p
        JOIN managers m ON p.manager_id = m.id
        WHERE p.id = ?
    """, (program_id,))

    if not program:
        raise ValueError(f"Program ID {program_id} not found")

    # Get data range
    date_range = db.fetch_one("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM pnl_records pr
        JOIN markets m ON pr.market_id = m.id
        WHERE pr.program_id = ?
          AND pr.resolution = 'daily'
          AND m.is_benchmark = 0
    """, (program_id,))

    if not date_range or not date_range['min_date']:
        raise ValueError(f"No daily data found for program {program_id}")

    min_date = date.fromisoformat(date_range['min_date'])
    max_date = date.fromisoformat(date_range['max_date'])

    # Generate window definitions (1-day slide)
    window_defs = generate_window_definitions_overlapping_by_days(
        start_date=min_date,
        end_date=max_date,
        window_length_months=window_months,
        slide_days=1,
        program_ids=[program_id],
        benchmark_ids=[],
        window_set_name=f"rolling_{window_months}m"
    )

    print(f"Generated {len(window_defs)} rolling windows ({window_months} months, 1-day slide)")

    # Fetch ALL returns once (performance optimization)
    print("Fetching all daily returns...")
    program_returns_df = get_all_daily_returns(db, program_id, min_date, max_date)

    if len(program_returns_df) == 0:
        raise ValueError(f"No daily returns found for program {program_id}")

    # Calculate rolling CAGR for program
    print("Calculating rolling CAGR for program...")
    program_cagr_df = calculate_rolling_cagr_series(
        program_returns_df,
        window_defs,
        entity_name=program['program_name']
    )

    # Create figure
    fig = go.Figure()

    # Add program line (blue, solid)
    fig.add_trace(go.Scatter(
        x=program_cagr_df['date'],
        y=program_cagr_df['cagr'] * 100,  # Convert to percentage
        mode='lines',
        name=program['program_name'],
        line=dict(color='blue', width=2),
        hovertemplate='%{x|%Y-%m-%d}<br>CAGR: %{y:.2f}%<extra></extra>'
    ))

    # Add benchmark lines if provided
    # All benchmarks use solid black lines (no dashing)
    benchmark_colors = ['black', 'black', 'gray']

    if benchmarks:
        for i, bm_name in enumerate(benchmarks):
            # Get benchmark market ID
            bm = db.fetch_one(
                "SELECT id, name FROM markets WHERE name = ? AND is_benchmark = 1",
                (bm_name.upper(),)
            )

            if not bm:
                print(f"Warning: Benchmark '{bm_name}' not found, skipping...")
                continue

            # Fetch benchmark returns
            print(f"Fetching benchmark returns for {bm['name']}...")
            bm_returns_df = get_benchmark_daily_returns(db, bm['id'], program_id, min_date, max_date)

            if len(bm_returns_df) == 0:
                print(f"Warning: No data for benchmark {bm['name']}, skipping...")
                continue

            # Calculate rolling CAGR for benchmark
            print(f"Calculating rolling CAGR for {bm['name']}...")
            bm_cagr_df = calculate_rolling_cagr_series(
                bm_returns_df,
                window_defs,
                entity_name=bm['name']
            )

            # Add benchmark line (solid black)
            color = benchmark_colors[i % len(benchmark_colors)]

            fig.add_trace(go.Scatter(
                x=bm_cagr_df['date'],
                y=bm_cagr_df['cagr'] * 100,  # Convert to percentage
                mode='lines',
                name=bm['name'],
                line=dict(color=color, width=2),  # Solid line (no dash parameter)
                hovertemplate='%{x|%Y-%m-%d}<br>CAGR: %{y:.2f}%<extra></extra>'
            ))

    # Add zero reference line (solid grey)
    fig.add_hline(
        y=0,
        line=dict(color='grey', width=1),  # Solid grey line
        opacity=0.7
    )

    # Determine title based on window size
    if window_months % 12 == 0:
        # Window is whole years
        years = window_months // 12
        title = f"{program['manager_name']} {program['program_name']} - Rolling {years}-Year CAGR"
    else:
        # Window is months
        title = f"{program['manager_name']} {program['program_name']} - Rolling {window_months}-Month CAGR"

    # Update layout
    fig.update_layout(
        title={
            'text': title,
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        xaxis_title='Date',
        yaxis_title='Annualized Return (%)',
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
        ),
        yaxis=dict(
            ticksuffix='%',
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor='lightgray'
        )
    )

    # Save to PDF
    fig.write_image(output_path, format='pdf', width=1400, height=800)
    print(f"Rolling CAGR chart saved to: {output_path}")

    return fig
