"""
Yearly Fees Summary Component

Generates a comprehensive PDF report showing annual fee breakdown and investor returns.
Displays each year from inception with:
- Management fees (USD)
- Performance fees (USD)
- Total fees (USD)
- Investor profit (USD)
- Investor CAGR

Features:
- Multi-column layout to fit all years on one page
- Smaller fonts for data density
- Scenario summary panel
- Professional formatting
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import date
from typing import List, Optional
import pandas as pd
from fee_scenarios import load_fee_scenario, calculate_net_nav_series, get_daily_returns


def calculate_cagr(starting_value: float, ending_value: float, years: float) -> float:
    """Calculate CAGR."""
    if years <= 0 or starting_value <= 0 or ending_value <= 0:
        return 0.0
    return ((ending_value / starting_value) ** (1.0 / years)) - 1.0


def generate_yearly_fees_summary(
    db,
    program_id: int,
    scenario_id: int,
    output_path: str,
    fund_size: float = 10_000_000,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    **kwargs
):
    """
    Generate yearly fees summary report.

    Args:
        db: Database connection
        program_id: Program ID to analyze
        scenario_id: Fee scenario ID
        output_path: Path to save PDF
        fund_size: Fund size in USD (default $10M)
        start_date: Start date (if None, uses program start date)
        end_date: End date (if None, uses latest data date)

    Returns:
        Path to generated PDF
    """
    # Get program info
    program = db.fetch_one("""
        SELECT p.program_name, p.starting_date, m.manager_name
        FROM programs p
        JOIN managers m ON p.manager_id = m.id
        WHERE p.id = ?
    """, (program_id,))

    if not program:
        raise ValueError(f"Program {program_id} not found")

    # Load scenario
    scenario = load_fee_scenario(db, scenario_id)

    # Determine date range
    if start_date is None:
        start_date = date.fromisoformat(program['starting_date'])

    if end_date is None:
        latest = db.fetch_one("""
            SELECT MAX(date) as max_date
            FROM pnl_records
            WHERE program_id = ? AND resolution = 'daily'
        """, (program_id,))
        end_date = date.fromisoformat(latest['max_date']) if latest and latest['max_date'] else date.today()

    # Calculate monthly series
    monthly_series = calculate_net_nav_series(
        db, program_id, scenario, start_date, end_date, fund_size
    )

    if len(monthly_series) == 0:
        raise ValueError("No data returned from calculations")

    # Group by year
    yearly_data = []
    current_year_data = {
        'year': monthly_series[0].date.year,
        'months': [],
        'start_cumulative_return_pct': 0.0,  # Start of year cumulative return
    }

    for i, calc in enumerate(monthly_series):
        year = calc.date.year

        if year != current_year_data['year']:
            # Process completed year
            yearly_data.append(current_year_data)
            # Start new year
            current_year_data = {
                'year': year,
                'months': [],
                'start_cumulative_return_pct': monthly_series[i-1].cumulative_return_pct if i > 0 else 0.0,
            }

        current_year_data['months'].append(calc)

    # Add last year
    if current_year_data['months']:
        yearly_data.append(current_year_data)

    # Calculate yearly aggregates
    yearly_summary = []
    inception_date = monthly_series[0].date

    for year_data in yearly_data:
        year = year_data['year']
        months = year_data['months']
        start_cumulative_return_pct = year_data['start_cumulative_return_pct']
        end_cumulative_return_pct = months[-1].cumulative_return_pct

        # Calculate year return
        year_return_pct = end_cumulative_return_pct - start_cumulative_return_pct

        # Calculate fees in USD
        mgmt_fee_pct = sum(m.management_fee_pct for m in months)
        perf_fee_pct = sum(m.performance_fee_pct for m in months)
        total_fee_pct = sum(m.total_fee_pct for m in months)

        # Convert percentages to USD
        # Fees are applied to the fund, so we calculate based on fund_size
        mgmt_fee_usd = mgmt_fee_pct * fund_size
        perf_fee_usd = perf_fee_pct * fund_size
        total_fee_usd = total_fee_pct * fund_size

        # Investor profit for the year (year return minus fees)
        investor_profit_usd = (year_return_pct - total_fee_pct) * fund_size

        # Calculate CAGR from inception
        years_from_inception = (months[-1].date - inception_date).days / 365.25
        inception_to_now_return_pct = end_cumulative_return_pct
        # Investor's net return
        total_fees_to_date_pct = sum(m.total_fee_pct for m in monthly_series[:monthly_series.index(months[-1])+1])
        investor_net_return_pct = inception_to_now_return_pct - total_fees_to_date_pct

        investor_end_value = fund_size * (1.0 + investor_net_return_pct)
        investor_cagr = calculate_cagr(fund_size, investor_end_value, years_from_inception)

        yearly_summary.append({
            'year': year,
            'mgmt_fee_usd': mgmt_fee_usd,
            'perf_fee_usd': perf_fee_usd,
            'total_fee_usd': total_fee_usd,
            'investor_profit_usd': investor_profit_usd,
            'investor_cagr': investor_cagr,
            'months_count': len(months)
        })

    # Create PDF (A4 portrait format)
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                           leftMargin=0.5*inch, rightMargin=0.5*inch,
                           topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        alignment=TA_CENTER
    )
    title = Paragraph(f"{program['manager_name']} {program['program_name']} - Annual Fee Summary", title_style)
    elements.append(title)

    # Subtitle
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        spaceAfter=8,
        alignment=TA_CENTER
    )
    subtitle = Paragraph(
        f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} | "
        f"Fund Size: ${fund_size:,.0f}",
        subtitle_style
    )
    elements.append(subtitle)

    # Scenario summary panel
    scenario_panel_data = [
        ['Fee Scenario Summary', ''],
        ['Scenario Name', scenario.name],
        ['Deflation Factor', f'{scenario.deflation_factor} ({(1-scenario.deflation_factor)*100:.1f}% reduction)'],
        ['Management Fee', f"{scenario.management_bands[0].annual_percentage*100:.1f}% annual" if scenario.management_bands else "N/A"],
    ]

    # Performance fee description
    if scenario.performance_bands and len(scenario.performance_bands) == 2 and scenario.performance_bands[0].interpolation_type == 'linear':
        low = scenario.performance_bands[0]
        high = scenario.performance_bands[1]
        perf_desc = f"{low.fee_percentage*100:.0f}%-{high.fee_percentage*100:.0f}% (linear interpolation @ {low.performance_min*100:.0f}%-{high.performance_min*100:.0f}% return)"
    elif scenario.performance_bands:
        perf_desc = f"{scenario.performance_bands[0].fee_percentage*100:.0f}% flat"
    else:
        perf_desc = "N/A"

    scenario_panel_data.append(['Performance Fee', perf_desc])
    scenario_panel_data.append(['Performance Basis', scenario.performance_tier_basis.replace('_', ' ').title()])
    scenario_panel_data.append(['High Water Mark', 'Yes' if scenario.use_high_water_mark else 'No'])

    scenario_table = Table(scenario_panel_data, colWidths=[1.8*inch, 4.5*inch])
    scenario_table.setStyle(TableStyle([
        # Header row
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (1, 0), 9),

        # Data rows
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F5F5')),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    elements.append(scenario_table)
    elements.append(Spacer(1, 0.15*inch))

    # Build single-column table (optimized column widths for A4)
    table_data = []

    # Header (with units)
    table_data.append([
        'Year',
        'Mgmt Fee\n($)',
        'Perf Fee\n($)',
        'Total Fee\n($)',
        'Investor Profit\n($)',
        'CAGR\n(%)'
    ])

    # Add all yearly data (no units in cells)
    for year_info in yearly_summary:
        table_data.append([
            str(year_info['year']),
            f"{year_info['mgmt_fee_usd']:,.0f}",
            f"{year_info['perf_fee_usd']:,.0f}",
            f"{year_info['total_fee_usd']:,.0f}",
            f"{year_info['investor_profit_usd']:,.0f}",
            f"{year_info['investor_cagr']*100:.1f}"
        ])

    # Optimized column widths for A4 (total width ~7 inches for content area)
    col_widths = [
        0.5*inch,   # Year (narrow)
        1.0*inch,   # Mgmt Fee
        1.0*inch,   # Perf Fee
        1.0*inch,   # Total Fee
        1.3*inch,   # Investor Profit (slightly wider)
        0.7*inch    # CAGR (narrow)
    ]

    yearly_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Table style
    yearly_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Year centered
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),  # Numbers right-aligned
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),

        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9F9')]),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(yearly_table)

    # Add summary statistics
    elements.append(Spacer(1, 0.15*inch))

    total_mgmt = sum(y['mgmt_fee_usd'] for y in yearly_summary)
    total_perf = sum(y['perf_fee_usd'] for y in yearly_summary)
    total_fees = sum(y['total_fee_usd'] for y in yearly_summary)

    # Calculate final investor value
    final_calc = monthly_series[-1]
    total_fees_pct = sum(m.total_fee_pct for m in monthly_series)
    investor_net_return_pct = final_calc.cumulative_return_pct - total_fees_pct
    final_investor_value = fund_size * (1.0 + investor_net_return_pct)
    total_investor_profit = final_investor_value - fund_size

    # Use actual start_date and end_date for precise CAGR calculation
    years_total = (end_date - start_date).days / 365.25
    overall_investor_cagr = calculate_cagr(fund_size, final_investor_value, years_total)

    summary_data = [
        ['Period Summary', '', '', ''],
        ['Total Management Fees', f'${total_mgmt:,.0f}', 'Final Investor Value', f'${final_investor_value:,.0f}'],
        ['Total Performance Fees', f'${total_perf:,.0f}', 'Total Investor Profit', f'${total_investor_profit:,.0f}'],
        ['Total Fees (All Years)', f'${total_fees:,.0f}', 'Overall Investor CAGR', f'{overall_investor_cagr*100:.2f}%'],
    ]

    summary_table = Table(summary_data, colWidths=[1.8*inch, 1.3*inch, 1.8*inch, 1.3*inch])
    summary_table.setStyle(TableStyle([
        # Header
        ('SPAN', (0, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (3, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (3, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (3, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (3, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (3, 0), 9),

        # Data
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F5F5')),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    elements.append(summary_table)

    # Build PDF
    doc.build(elements)

    return output_path
