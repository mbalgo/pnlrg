"""
Professional PDF Table Generation for Performance Statistics.

Creates beautifully formatted tables suitable for investor presentations.
Uses ReportLab for high-quality PDF output with proper styling.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import date
from typing import List, Dict, Any
import numpy as np


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format a decimal as percentage (0.0523 -> '5.23%')."""
    if np.isnan(value):
        return 'N/A'
    return f"{value * 100:.{decimals}f}%"


def format_decimal(value: float, decimals: int = 2) -> str:
    """Format a decimal number."""
    if np.isnan(value):
        return 'N/A'
    return f"{value:.{decimals}f}"


def format_number_only(value: float, decimals: int = 2) -> str:
    """Format value as number without % suffix (0.0523 -> '5.23')."""
    if np.isnan(value):
        return 'N/A'
    return f"{value * 100:.{decimals}f}"


def format_integer(value: int) -> str:
    """Format an integer with thousand separators."""
    return f"{value:,}"


def create_windows_performance_table_pdf(
    windows_stats: List[Dict[str, Any]],
    program_name: str,
    manager_name: str,
    output_path: str,
    title: str = None
):
    """
    Create a professional PDF table showing performance statistics for multiple windows.

    Args:
        windows_stats: List of dicts with window statistics
            Each dict should contain:
            - window_name: str (e.g., "2006-01-03 to 2011-01-03")
            - daily_count: int
            - mean_monthly: float (decimal, e.g., 0.0765 for 7.65%)
            - std_daily: float (not annualized, e.g., 0.0104 for 1.04%)
            - max_dd: float (negative decimal, e.g., -0.0422 for -4.22%)
            - sharpe: float (e.g., 1.89)
            - cagr: float (decimal, e.g., 1.3923 for 139.23%)
            - borrowed: bool (optional, indicates if window has borrowed data)
        program_name: Program name for title
        manager_name: Manager name for title
        output_path: Path to save PDF
        title: Optional custom title

    Returns:
        Path to generated PDF
    """
    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    # Container for elements
    elements = []

    # Styles
    styles = getSampleStyleSheet()

    # Custom title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    # Custom subtitle style
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )

    # Add title
    if title:
        title_text = title
    else:
        title_text = f"{manager_name} {program_name}<br/>5-Year Window Performance Statistics"

    title_para = Paragraph(title_text, title_style)
    elements.append(title_para)

    # Add subtitle/description
    subtitle_text = "Daily returns standard deviation (not annualized). Sharpe ratio = √261 × mean / std."
    subtitle_para = Paragraph(subtitle_text, subtitle_style)
    elements.append(subtitle_para)

    # Prepare table data
    header = [
        'Window Period',
        'Trading\nDays',
        'Mean\nMonthly (%)',
        'Std Dev\nDaily (%)',
        'Max\nDrawdown (%)',
        'Sharpe\nRatio',
        'CAGR (%)'
    ]

    table_data = [header]

    for ws in windows_stats:
        row = [
            ws['window_name'],
            format_integer(ws['daily_count']),
            format_number_only(ws['mean_monthly'], 2),  # No % suffix
            format_number_only(ws['std_daily'], 2),     # 2 decimals (was 4)
            format_number_only(ws['max_dd'], 2),        # No % suffix
            format_decimal(ws['sharpe'], 2),
            format_number_only(ws['cagr'], 0)           # 0 decimals (whole number)
        ]

        # Add asterisk if borrowed data
        if ws.get('borrowed', False):
            row[0] += ' *'

        table_data.append(row)

    # Create table
    table = Table(table_data, colWidths=[
        2.2*inch,  # Window Period
        0.8*inch,  # Trading Days
        0.85*inch, # Mean Monthly
        0.85*inch, # Std Dev Daily
        0.85*inch, # Max Drawdown
        0.75*inch, # Sharpe Ratio
        0.8*inch   # CAGR
    ])

    # Professional table styling
    table_style = TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),

        # Data rows styling
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2c3e50')),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Window name left-aligned
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'), # Numbers right-aligned
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),

        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),

        # Grid lines
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#34495e')),

        # Vertical lines between columns
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#2c3e50')),
    ])

    table.setStyle(table_style)
    elements.append(table)

    # Add footnote if any windows have borrowed data
    if any(ws.get('borrowed', False) for ws in windows_stats):
        elements.append(Spacer(1, 12))

        footnote_style = ParagraphStyle(
            'Footnote',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#7f8c8d'),
            fontName='Helvetica-Oblique'
        )

        footnote = Paragraph(
            "* Window contains borrowed data (overlaps with subsequent window to achieve complete 5-year duration)",
            footnote_style
        )
        elements.append(footnote)

    # Build PDF
    doc.build(elements)

    return output_path


def create_summary_statistics_table_pdf(
    stats: Dict[str, Any],
    program_name: str,
    manager_name: str,
    output_path: str,
    period_name: str = "Full History"
):
    """
    Create a professional PDF table showing summary statistics for a single period.

    Args:
        stats: Dict with statistics (mean, std_dev, sharpe, cagr, max_dd, etc.)
        program_name: Program name
        manager_name: Manager name
        output_path: Path to save PDF
        period_name: Name of the period (e.g., "Full History", "Last 5 Years")

    Returns:
        Path to generated PDF
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    title_text = f"{manager_name} {program_name}<br/>Performance Summary - {period_name}"
    title_para = Paragraph(title_text, title_style)
    elements.append(title_para)
    elements.append(Spacer(1, 12))

    # Create two-column table
    table_data = [
        ['Metric', 'Value'],
        ['Trading Days', format_integer(stats.get('daily_count', 0))],
        ['Monthly Observations', format_integer(stats.get('count', 0))],
        ['Mean Monthly Return', format_percentage(stats.get('mean', 0), 2)],
        ['Median Monthly Return', format_percentage(stats.get('median', 0), 2)],
        ['Daily Std Dev (not annualized)', format_percentage(stats.get('daily_std_dev_raw', 0), 4)],
        ['Annualized Std Dev', format_percentage(stats.get('std_dev', 0), 2)],
        ['Sharpe Ratio', format_decimal(stats.get('sharpe', 0), 2)],
        ['CAGR', format_percentage(stats.get('cagr', 0), 2)],
        ['Max Drawdown', format_percentage(stats.get('max_drawdown_compounded', 0), 2)],
        ['Cumulative Return', format_percentage(stats.get('cumulative_return_compounded', 0), 2)],
    ]

    table = Table(table_data, colWidths=[3.5*inch, 2*inch])

    table_style = TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),

        # Data
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2c3e50')),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),

        # Alternating rows
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#34495e')),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#2c3e50')),
    ])

    table.setStyle(table_style)
    elements.append(table)

    doc.build(elements)
    return output_path
