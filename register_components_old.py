"""
Component Registration

This module registers all available components with the component registry.
Each component is wrapped in a standardized interface that the batch generator can call.

Components registered here will appear in `list_components.py` and can be batch-generated
via `generate_all_components.py`.
"""

from component_registry import register_component
from components.cumulative_windows_overlay import (
    get_daily_returns_for_window,
    get_benchmark_returns_for_window,
    calculate_cumulative_nav_additive
)
import plotly.graph_objects as go
from database import Database
from datetime import date


# =============================================================================
# Chart Component Wrappers
# =============================================================================

def generate_cumulative_windows_5yr_compounded(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """
    Generate 5-year cumulative windows overlay chart with compounded returns.

    This is a wrapper function that conforms to the component interface.
    """
    from generate_alphabet_mft_cumulative_windows import main as generate_main
    # TODO: Adapt existing script to work with component interface
    # For now, this is a placeholder
    raise NotImplementedError("Component wrapper needs implementation")


def generate_cumulative_windows_5yr_additive(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """
    Generate 5-year cumulative windows overlay chart with additive (non-compounded) returns.

    This is the borrow_mode chart we just created.
    """
    from windows import generate_window_definitions_non_overlapping_reverse
    from components.cumulative_windows_overlay import calculate_cumulative_nav_additive

    # Get program metadata
    program = db.fetch_one("""
        SELECT p.id, p.program_name, p.starting_nav, m.manager_name
        FROM programs p
        JOIN managers m ON p.manager_id = m.id
        WHERE p.id = ?
    """, (program_id,))

    if not program:
        raise ValueError(f"Program ID {program_id} not found")

    # Get data range
    date_range = db.fetch_one("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM pnl_records
        WHERE program_id = ? AND resolution = 'daily'
    """, (program_id,))

    if not date_range or not date_range['min_date']:
        raise ValueError(f"No daily data found for program {program_id}")

    min_date = date.fromisoformat(date_range['min_date'])
    max_date = date.fromisoformat(date_range['max_date'])

    # Get benchmark ID if specified
    benchmark_id = None
    if benchmarks and len(benchmarks) > 0:
        # For now, only support first benchmark
        # TODO: Support multiple benchmarks
        benchmark_name = benchmarks[0].upper()
        benchmark = db.fetch_one(
            "SELECT id FROM markets WHERE name = ? AND is_benchmark = 1",
            (benchmark_name,)
        )
        if benchmark:
            benchmark_id = benchmark['id']

    # Generate windows with borrow_mode
    window_defs = generate_window_definitions_non_overlapping_reverse(
        earliest_date=min_date,
        latest_date=max_date,
        window_length_years=5,
        program_ids=[program_id],
        benchmark_ids=[benchmark_id] if benchmark_id else [],
        window_set_name="5yr_non_overlapping",
        borrow_mode=True
    )

    # Convert to dict format
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

    # Generate chart
    from generate_alphabet_mft_cumulative_windows_additive import generate_additive_chart

    title = f"{program['manager_name']} {program['program_name']} - Cumulative Performance by 5-Year Window (Additive)"
    subtitle = f"Starting NAV: ${program['starting_nav']:,.0f}. Additive returns (no compounding). Solid: Strategy. Dashed: Benchmark. Dotted: Borrowed data."

    fig = generate_additive_chart(
        db=db,
        program_id=program_id,
        windows=windows,
        benchmark_market_id=benchmark_id,
        starting_nav=program['starting_nav'],
        output_path=output_path,
        title=title,
        subtitle=subtitle
    )

    return fig


def generate_equity_curve_full_history(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """
    Generate full history equity curve chart.

    TODO: Implement using components/charts.py equity_curve_chart
    """
    raise NotImplementedError("Component wrapper needs implementation")


def generate_monthly_performance_chart(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """
    Generate monthly performance chart.

    TODO: Implement wrapper for existing monthly performance scripts
    """
    raise NotImplementedError("Component wrapper needs implementation")


# =============================================================================
# Table Component Wrappers
# =============================================================================

def generate_performance_summary_table(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """
    Generate performance summary table.

    TODO: Implement using components/tables.py
    """
    raise NotImplementedError("Component wrapper needs implementation")


# =============================================================================
# Component Registration
# =============================================================================

def register_all_components():
    """
    Register all available components with the global registry.

    This function is called at module import to populate the registry.
    """

    # =========================================================================
    # CHARTS
    # =========================================================================

    register_component(
        id='cumulative_windows_5yr_additive',
        name='Cumulative Windows Overlay (5-Year, Additive)',
        category='chart',
        description='5-year non-overlapping windows with additive (non-compounded) returns, using borrow_mode for complete windows',
        function=generate_cumulative_windows_5yr_additive,
        benchmark_support=True,
        benchmark_combinations=[
            [],              # No benchmark
            ['sp500'],       # SP500 only
            ['areit'],       # AREIT only
            ['sp500', 'areit']  # Both benchmarks
        ],
        version='1.0.0'
    )

    register_component(
        id='cumulative_windows_5yr_compounded',
        name='Cumulative Windows Overlay (5-Year, Compounded)',
        category='chart',
        description='5-year non-overlapping windows with compounded returns, using borrow_mode for complete windows',
        function=generate_cumulative_windows_5yr_compounded,
        benchmark_support=True,
        benchmark_combinations=[
            [],
            ['sp500'],
            ['areit'],
            ['sp500', 'areit']
        ],
        version='1.0.0'
    )

    register_component(
        id='equity_curve_full_history',
        name='Equity Curve (Full History)',
        category='chart',
        description='Complete NAV history from inception to latest date',
        function=generate_equity_curve_full_history,
        benchmark_support=True,
        benchmark_combinations=[
            [],
            ['sp500'],
            ['btop50'],
            ['areit'],
            ['sp500', 'btop50'],
            ['sp500', 'areit']
        ],
        version='1.0.0'
    )

    register_component(
        id='monthly_performance',
        name='Monthly Performance Chart',
        category='chart',
        description='Monthly bar chart showing returns by month',
        function=generate_monthly_performance_chart,
        benchmark_support=False,
        version='1.0.0'
    )

    # =========================================================================
    # TABLES
    # =========================================================================

    register_component(
        id='performance_summary_table',
        name='Performance Summary Table',
        category='table',
        description='Summary statistics table with returns, volatility, Sharpe ratio for different periods',
        function=generate_performance_summary_table,
        benchmark_support=False,
        version='1.0.0'
    )

    # =========================================================================
    # TEXT BLOCKS
    # =========================================================================

    # TODO: Add text block components


# Register all components at module import
register_all_components()
