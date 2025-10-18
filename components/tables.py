"""
Table generation components for brochures.

Each function generates a specific type of table and returns HTML or DataFrame.
"""

import pandas as pd
from datetime import datetime, timedelta


def performance_summary_table(db, program_id, periods=None, **kwargs):
    """
    Generate performance summary table with returns, volatility, Sharpe for different periods.

    Args:
        db: Database instance
        program_id: Program ID to analyze
        periods: List of period labels (e.g., ['1Y', '3Y', '5Y', 'ITD'])
        **kwargs: Additional customization

    Returns:
        HTML table string
    """
    if periods is None:
        periods = ['1Y', '3Y', '5Y', 'ITD']

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

    df = pd.DataFrame(returns_data, columns=['date', 'return'])
    df['date'] = pd.to_datetime(df['date'])

    # Calculate metrics for each period
    results = []
    end_date = df['date'].max()

    for period in periods:
        if period == 'ITD':
            period_df = df
            period_name = 'Inception to Date'
        else:
            # Parse period (e.g., '1Y', '3Y', '5Y')
            years = int(period[:-1])
            start_date = end_date - timedelta(days=years*365)
            period_df = df[df['date'] >= start_date]
            period_name = f'{years} Year'

        if len(period_df) == 0:
            continue

        # Calculate metrics
        total_return = ((1 + period_df['return']).prod() - 1) * 100
        annualized_return = (((1 + period_df['return']).prod()) ** (12/len(period_df)) - 1) * 100
        volatility = period_df['return'].std() * (12 ** 0.5) * 100
        sharpe = annualized_return / volatility if volatility > 0 else 0

        results.append({
            'Period': period_name,
            'Total Return': f'{total_return:.2f}%',
            'Annualized Return': f'{annualized_return:.2f}%',
            'Volatility': f'{volatility:.2f}%',
            'Sharpe Ratio': f'{sharpe:.2f}'
        })

    # Convert to DataFrame
    summary_df = pd.DataFrame(results)

    # Convert to HTML
    html = summary_df.to_html(index=False, border=1, classes='performance-table')

    return html


def monthly_returns_grid(db, program_id, year=None, **kwargs):
    """
    Generate monthly returns grid (12 months x N years).

    Args:
        db: Database instance
        program_id: Program ID to analyze
        year: Specific year to show, or None for all years
        **kwargs: Additional customization

    Returns:
        HTML table string
    """
    # TODO: Implement monthly returns grid
    return "<p>Monthly Returns Grid - Coming Soon</p>"


def benchmark_comparison_table(db, program_id, benchmarks=None, **kwargs):
    """
    Generate table comparing program vs benchmarks.

    Args:
        db: Database instance
        program_id: Program ID to analyze
        benchmarks: List of benchmark names
        **kwargs: Additional customization

    Returns:
        HTML table string
    """
    # TODO: Implement benchmark comparison
    return "<p>Benchmark Comparison Table - Coming Soon</p>"
