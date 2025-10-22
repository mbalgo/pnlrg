"""
Complete Component Registration with All Implementations

This module contains fully implemented component wrappers for charts, tables, and text blocks.
All components conform to the standardized interface for batch generation.
"""

from component_registry import register_component
from components.cumulative_windows_overlay import (
    get_daily_returns_for_window,
    get_benchmark_returns_for_window,
    calculate_cumulative_nav,
    calculate_cumulative_nav_additive
)
from components.pdf_tables import (
    create_windows_performance_table_pdf,
    create_summary_statistics_table_pdf
)
from windows import generate_window_definitions_non_overlapping_reverse, compute_statistics
import plotly.graph_objects as go
from database import Database
from datetime import date
import pandas as pd


# =============================================================================
# Chart Component Implementations
# =============================================================================

def _get_benchmark_ids(db, benchmarks):
    """Helper to convert benchmark names to IDs."""
    if not benchmarks:
        return []

    benchmark_ids = []
    for bm_name in benchmarks:
        bm = db.fetch_one(
            "SELECT id FROM markets WHERE name = ? AND is_benchmark = 1",
            (bm_name.upper(),)
        )
        if bm:
            benchmark_ids.append(bm['id'])

    return benchmark_ids


def _generate_cumulative_windows_chart(
    db, program_id, output_path, benchmarks, compounded=True
):
    """
    Shared implementation for cumulative windows charts.

    Args:
        compounded: If True, use compounded returns. If False, use additive.
    """
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

    # Get benchmark IDs
    benchmark_ids = _get_benchmark_ids(db, benchmarks)
    benchmark_id = benchmark_ids[0] if benchmark_ids else None

    # Generate windows with borrow_mode
    window_defs = generate_window_definitions_non_overlapping_reverse(
        earliest_date=min_date,
        latest_date=max_date,
        window_length_years=5,
        program_ids=[program_id],
        benchmark_ids=benchmark_ids,
        window_set_name="5yr_non_overlapping",
        borrow_mode=True
    )

    # Color palette
    colors_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    fig = go.Figure()

    for i, wd in enumerate(window_defs):
        color = colors_palette[i % len(colors_palette)]

        # Get program returns
        program_df = get_daily_returns_for_window(
            db, program_id, wd.start_date, wd.end_date
        )

        if len(program_df) == 0:
            continue

        # Calculate NAV curve
        calc_func = calculate_cumulative_nav if compounded else calculate_cumulative_nav_additive
        nav_curve = calc_func(program_df['return'].tolist(), program['starting_nav'])
        trading_days = list(range(len(nav_curve)))

        window_name = f"{wd.start_date.strftime('%Y-%m-%d')} to {wd.end_date.strftime('%Y-%m-%d')}"

        # Check for borrowed data
        has_borrowed = wd.borrowed_data_start_date is not None

        if has_borrowed:
            # Split into actual and borrowed segments
            borrowed_start_idx = len(program_df[program_df['date'] < pd.Timestamp(wd.borrowed_data_start_date)])

            # Actual segment (solid)
            fig.add_trace(go.Scatter(
                x=trading_days[:borrowed_start_idx],
                y=nav_curve[:borrowed_start_idx],
                mode='lines',
                name=window_name,
                line=dict(color=color, width=2),
                legendgroup=f'window_{i}',
                showlegend=True
            ))

            # Borrowed segment (dotted)
            fig.add_trace(go.Scatter(
                x=trading_days[borrowed_start_idx-1:],
                y=nav_curve[borrowed_start_idx-1:],
                mode='lines',
                name=window_name,
                line=dict(color=color, width=2, dash='dot'),
                legendgroup=f'window_{i}',
                showlegend=False
            ))
        else:
            # Single trace
            fig.add_trace(go.Scatter(
                x=trading_days,
                y=nav_curve,
                mode='lines',
                name=window_name,
                line=dict(color=color, width=2),
                legendgroup=f'window_{i}',
                showlegend=True
            ))

        # Add benchmark if provided
        if benchmark_id:
            benchmark_df = get_benchmark_returns_for_window(
                db, benchmark_id, wd.start_date, wd.end_date
            )

            if len(benchmark_df) > 0:
                benchmark_nav = calc_func(benchmark_df['return'].tolist(), program['starting_nav'])
                benchmark_days = list(range(len(benchmark_nav)))

                if has_borrowed:
                    borrowed_start_idx = len(benchmark_df[benchmark_df['date'] < pd.Timestamp(wd.borrowed_data_start_date)])

                    # Actual (dashed)
                    fig.add_trace(go.Scatter(
                        x=benchmark_days[:borrowed_start_idx],
                        y=benchmark_nav[:borrowed_start_idx],
                        mode='lines',
                        name=window_name,
                        line=dict(color=color, width=2, dash='dash'),
                        legendgroup=f'window_{i}',
                        showlegend=False
                    ))

                    # Borrowed (dotted)
                    fig.add_trace(go.Scatter(
                        x=benchmark_days[borrowed_start_idx-1:],
                        y=benchmark_nav[borrowed_start_idx-1:],
                        mode='lines',
                        name=window_name,
                        line=dict(color=color, width=2, dash='dot'),
                        legendgroup=f'window_{i}',
                        showlegend=False
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=benchmark_days,
                        y=benchmark_nav,
                        mode='lines',
                        name=window_name,
                        line=dict(color=color, width=2, dash='dash'),
                        legendgroup=f'window_{i}',
                        showlegend=False
                    ))

    # Layout
    calc_type = "Compounded" if compounded else "Additive (Non-Compounded)"
    title = f"{program['manager_name']} {program['program_name']} - Cumulative Performance by 5-Year Window ({calc_type})"

    benchmark_desc = f" {benchmarks[0].upper()}" if benchmarks else ""
    subtitle = f"Starting NAV: ${program['starting_nav']:,.0f}. {calc_type} returns. Solid: Strategy. Dashed:{benchmark_desc} Benchmark. Dotted: Borrowed data."

    fig.update_layout(
        title={'text': title, 'x': 0.5, 'xanchor': 'center', 'font': {'size': 20}},
        xaxis_title='Trading Days Since Window Start',
        yaxis_title='NAV ($)',
        yaxis=dict(tickformat='$,.0f'),
        hovermode='x unified',
        width=1400,
        height=800,
        template='plotly_white',
        legend=dict(orientation='v', yanchor='top', y=0.99, xanchor='left', x=0.01,
                   bgcolor='rgba(255,255,255,0.8)', bordercolor='gray', borderwidth=1)
    )

    if subtitle:
        fig.add_annotation(
            text=subtitle, xref='paper', yref='paper',
            x=0.5, y=1.05, xanchor='center', yanchor='bottom',
            showarrow=False, font=dict(size=12, color='gray')
        )

    # Save
    fig.write_image(output_path, format='pdf', width=1400, height=800)
    return fig


def generate_cumulative_windows_5yr_compounded(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """Generate 5-year cumulative windows with COMPOUNDED returns."""
    return _generate_cumulative_windows_chart(db, program_id, output_path, benchmarks, compounded=True)


def generate_cumulative_windows_5yr_additive(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """Generate 5-year cumulative windows with ADDITIVE returns."""
    return _generate_cumulative_windows_chart(db, program_id, output_path, benchmarks, compounded=False)


def generate_equity_curve_full_history(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """Generate full history equity curve chart."""
    from components.charts import equity_curve_chart

    # Get data range
    data_range = db.fetch_one("""
        SELECT MIN(date) as start_date, MAX(date) as end_date
        FROM pnl_records pr
        JOIN markets m ON pr.market_id = m.id
        WHERE pr.program_id = ?
        AND m.is_benchmark = 0
        AND pr.resolution = 'monthly'
    """, (program_id,))

    if not data_range or not data_range['start_date']:
        raise ValueError(f"No monthly data found for program {program_id}")

    # Use components/charts.py equity_curve_chart function
    fig = equity_curve_chart(
        db=db,
        program_id=program_id,
        benchmarks=[bm.upper() for bm in benchmarks] if benchmarks else None,
        date_range=None  # Full history
    )

    # Save to PDF
    fig.write_image(output_path, format='pdf', width=1200, height=700)
    return fig


def generate_monthly_performance(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """Generate monthly performance bar chart."""
    # TODO: Implement monthly performance chart
    # This would show monthly returns as bars, possibly colored by positive/negative
    raise NotImplementedError("Monthly performance chart not yet implemented")


# =============================================================================
# Table Component Implementations
# =============================================================================

def generate_windows_performance_table(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """
    Generate performance statistics table for 5-year windows.

    Shows: Trading days, mean monthly return, daily std dev, max drawdown, Sharpe, CAGR.
    """
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

    # Generate windows
    window_defs = generate_window_definitions_non_overlapping_reverse(
        earliest_date=min_date,
        latest_date=max_date,
        window_length_years=5,
        program_ids=[program_id],
        benchmark_ids=[],
        borrow_mode=True
    )

    # Compute statistics for each window
    from windows import Window
    windows_stats = []

    for wd in window_defs:
        window = Window(wd, db)
        stats = compute_statistics(window, program_id, entity_type='manager')

        # Calculate Sharpe ratio: sqrt(261) * mean / std_daily
        # We have annualized std, so we need to de-annualize it first
        # annualized_std = daily_std * sqrt(252)
        # daily_std = annualized_std / sqrt(252)
        # Sharpe = sqrt(261) * mean_monthly / daily_std
        # But actually, for monthly Sharpe:
        # Sharpe = sqrt(12) * mean_monthly / std_monthly
        # Let's use the standard formula: sqrt(252) * daily_mean / daily_std

        # Get daily returns for proper Sharpe calculation
        daily_df = window.get_manager_daily_data(program_id)
        if len(daily_df) > 0:
            daily_mean = daily_df['return'].mean()
            daily_std = daily_df['return'].std()
            sharpe = (daily_mean / daily_std * (261 ** 0.5)) if daily_std > 0 else 0.0
        else:
            daily_std = 0.0
            sharpe = 0.0

        window_stats = {
            'window_name': f"{wd.start_date.strftime('%Y-%m-%d')} to {wd.end_date.strftime('%Y-%m-%d')}",
            'daily_count': stats.daily_count if stats.daily_count > 0 else stats.count * 21,  # Estimate
            'mean_monthly': stats.mean,
            'std_daily': daily_std,  # Not annualized
            'max_dd': stats.max_drawdown_compounded,
            'sharpe': sharpe,
            'cagr': stats.cagr,
            'borrowed': wd.borrowed_data_start_date is not None
        }

        windows_stats.append(window_stats)

    # Generate PDF table
    create_windows_performance_table_pdf(
        windows_stats=windows_stats,
        program_name=program['program_name'],
        manager_name=program['manager_name'],
        output_path=output_path,
        title=None
    )

    return output_path


# =============================================================================
# Text Block Components
# =============================================================================

def generate_strategy_description(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """Generate strategy description text block as PDF."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    program = db.fetch_one("""
        SELECT p.program_name, p.fund_size, p.starting_date, m.manager_name
        FROM programs p
        JOIN managers m ON p.manager_id = m.id
        WHERE p.id = ?
    """, (program_id,))

    if not program:
        raise ValueError(f"Program ID {program_id} not found")

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title = Paragraph(f"<b>{program['manager_name']} - {program['program_name']}</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Description
    description = f"""
    <b>Program:</b> {program['program_name']}<br/>
    <b>Fund Size:</b> ${program['fund_size']:,.0f}<br/>
    <b>Inception Date:</b> {program['starting_date']}<br/><br/>

    This is a systematic trading program that employs quantitative strategies
    across multiple asset classes. The strategy focuses on risk-adjusted returns
    through diversified market exposure and disciplined risk management.
    """

    desc_para = Paragraph(description, styles['BodyText'])
    elements.append(desc_para)

    doc.build(elements)
    return output_path


def generate_disclaimer(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """Generate standard disclaimer as PDF."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_JUSTIFY

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()

    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_JUSTIFY
    )

    disclaimer_text = """
    <b>IMPORTANT DISCLAIMER</b><br/><br/>

    Past performance is not indicative of future results. This material is for informational
    purposes only and does not constitute investment advice or a recommendation to buy or sell
    any security. The information contained herein has been prepared solely for informational
    purposes and is not an offer to buy or sell or a solicitation of an offer to buy or sell
    any security or to participate in any trading strategy.<br/><br/>

    Any investment involves substantial risks, including complete loss of capital. There can
    be no assurance that any investment strategy will be successful. All investments involve
    risk and may lose value. Diversification does not guarantee profit or protect against loss.<br/><br/>

    This document is confidential and intended solely for the use of the intended recipient.
    Distribution to third parties without prior written consent is strictly prohibited.
    """

    disclaimer_para = Paragraph(disclaimer_text, disclaimer_style)

    doc.build([disclaimer_para])
    return output_path


# =============================================================================
# Component Registration
# =============================================================================

def register_all_components():
    """Register all available components with the global registry."""

    # CHARTS
    register_component(
        id='cumulative_windows_5yr_compounded',
        name='Cumulative Windows Overlay (5-Year, Compounded)',
        category='chart',
        description='5-year non-overlapping windows with compounded returns, using borrow_mode',
        function=generate_cumulative_windows_5yr_compounded,
        benchmark_support=True,
        benchmark_combinations=[[], ['sp500'], ['areit'], ['sp500', 'areit']],
        version='1.0.0'
    )

    register_component(
        id='cumulative_windows_5yr_additive',
        name='Cumulative Windows Overlay (5-Year, Additive)',
        category='chart',
        description='5-year non-overlapping windows with additive returns, using borrow_mode',
        function=generate_cumulative_windows_5yr_additive,
        benchmark_support=True,
        benchmark_combinations=[[], ['sp500'], ['areit'], ['sp500', 'areit']],
        version='1.0.0'
    )

    register_component(
        id='equity_curve_full_history',
        name='Equity Curve (Full History)',
        category='chart',
        description='Complete NAV history from inception to latest date',
        function=generate_equity_curve_full_history,
        benchmark_support=True,
        benchmark_combinations=[[], ['sp500'], ['btop50'], ['areit']],
        version='1.0.0'
    )

    # TABLES
    register_component(
        id='windows_performance_table',
        name='5-Year Windows Performance Table',
        category='table',
        description='Statistics table for 5-year windows (days, mean, std, max DD, Sharpe, CAGR)',
        function=generate_windows_performance_table,
        benchmark_support=False,
        version='1.0.0'
    )

    # TEXT BLOCKS
    register_component(
        id='strategy_description',
        name='Strategy Description',
        category='text',
        description='Program overview with key details',
        function=generate_strategy_description,
        benchmark_support=False,
        version='1.0.0'
    )

    register_component(
        id='disclaimer',
        name='Legal Disclaimer',
        category='text',
        description='Standard legal disclaimer for performance reports',
        function=generate_disclaimer,
        benchmark_support=False,
        version='1.0.0'
    )


# Auto-register on import
register_all_components()
