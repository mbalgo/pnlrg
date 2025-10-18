"""
Create professional PDF brochure with equity curve chart.
Uses Plotly for beautiful, presentation-quality charts.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from database import Database
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
import io
from datetime import datetime


def get_equity_curve_data(db, program_name="CTA_50M_30"):
    """
    Extract equity curve data for Rise and SP500 from percentage returns.

    Args:
        db: Database instance
        program_name: Program to analyze (default: CTA_50M_30)

    Returns:
        DataFrame with dates and cumulative equity for Rise and SP500
    """
    # Get the Rise program metadata
    program = db.fetch_one("""
        SELECT id, starting_nav, starting_date
        FROM programs
        WHERE program_name = ?
    """, (program_name,))
    if not program:
        raise ValueError(f"Program {program_name} not found")

    program_id = program['id']
    starting_nav = program['starting_nav']
    starting_date = program['starting_date']

    # Get Rise market percentage returns
    rise_data = db.fetch_all("""
        SELECT pr.date, pr.return
        FROM pnl_records pr
        JOIN markets m ON pr.market_id = m.id
        WHERE pr.program_id = ?
        AND m.name = 'Rise'
        AND pr.resolution = 'monthly'
        ORDER BY pr.date
    """, (program_id,))

    # Convert to DataFrame
    df = pd.DataFrame(rise_data, columns=['date', 'return'])
    df['date'] = pd.to_datetime(df['date'])

    # Calculate NAV from returns using compounding
    df['rise_nav'] = starting_nav * (1 + df['return']).cumprod()

    # Add starting point to beginning of dataframe
    start_row = pd.DataFrame({
        'date': [pd.to_datetime(starting_date)],
        'return': [0.0],
        'rise_nav': [starting_nav]
    })
    df = pd.concat([start_row, df], ignore_index=True)

    # Get SP500 benchmark data
    benchmarks_program = db.fetch_one("SELECT id FROM programs WHERE program_name = 'Benchmarks'")
    if benchmarks_program:
        sp500_data = db.fetch_all("""
            SELECT pr.date, pr.return
            FROM pnl_records pr
            JOIN markets m ON pr.market_id = m.id
            WHERE pr.program_id = ?
            AND m.name = 'SP500'
            AND pr.resolution = 'monthly'
            ORDER BY pr.date
        """, (benchmarks_program['id'],))

        if sp500_data:
            sp500_df = pd.DataFrame(sp500_data, columns=['date', 'sp500_return'])
            sp500_df['date'] = pd.to_datetime(sp500_df['date'])

            # Calculate SP500 NAV starting from same point as Rise
            sp500_df['sp500_nav'] = starting_nav * (1 + sp500_df['sp500_return']).cumprod()

            # Add starting point
            sp500_start = pd.DataFrame({
                'date': [pd.to_datetime(starting_date)],
                'sp500_return': [0.0],
                'sp500_nav': [starting_nav]
            })
            sp500_df = pd.concat([sp500_start, sp500_df], ignore_index=True)

            # Merge with main dataframe
            df = df.merge(sp500_df[['date', 'sp500_nav']], on='date', how='left')

    print(f"Loaded {len(df)} data points for {program_name}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Rise NAV: {df['rise_nav'].iloc[0]:.2f} to {df['rise_nav'].iloc[-1]:.2f}")
    if 'sp500_nav' in df.columns:
        print(f"SP500 NAV: {df['sp500_nav'].iloc[0]:.2f} to {df['sp500_nav'].iloc[-1]:.2f}")

    return df


def create_equity_curve_chart(df, program_name="CTA Fund"):
    """
    Create beautiful equity curve chart using Plotly.

    Args:
        df: DataFrame with date, rise_nav columns
        program_name: Name for chart title

    Returns:
        Plotly figure object
    """
    # Professional color scheme
    # Rise: Deep blue (trust, stability)
    # SP500: Warm orange (benchmark contrast)
    rise_color = '#1f77b4'  # Professional blue
    sp500_color = '#ff7f0e'  # Warm orange
    grid_color = '#e5e5e5'   # Light gray

    # Create figure
    fig = go.Figure()

    # Add Rise equity curve
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['rise_nav'],
        name='Rise CTA Fund',
        line=dict(color=rise_color, width=3),
        mode='lines',
        hovertemplate='<b>Rise CTA</b><br>Date: %{x|%Y-%m-%d}<br>NAV: $%{y:,.0f}<extra></extra>'
    ))

    # Add SP500 benchmark if available
    if 'sp500_nav' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['sp500_nav'],
            name='S&P 500',
            line=dict(color=sp500_color, width=3),
            mode='lines',
            hovertemplate='<b>S&P 500</b><br>Date: %{x|%Y-%m-%d}<br>NAV: $%{y:,.0f}<extra></extra>'
        ))

    # Update layout for professional appearance
    fig.update_layout(
        title=dict(
            text=f'<b>{program_name} Performance vs Benchmark</b><br><sub>January 1973 - December 2017</sub>',
            font=dict(size=24, family='Arial, sans-serif', color='#2c3e50'),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title=dict(
                text='<b>Year</b>',
                font=dict(size=14, family='Arial, sans-serif', color='#34495e')
            ),
            showgrid=True,
            gridcolor=grid_color,
            gridwidth=1,
            zeroline=False,
            tickfont=dict(size=12, color='#2c3e50'),
            showline=True,
            linewidth=2,
            linecolor='#bdc3c7',
            # Show years every 5 years: 1975, 1980, 1985, etc.
            tickmode='array',
            tickvals=pd.date_range(start='1975-01-01', end='2017-01-01', freq='5YS'),
            ticktext=[str(year) for year in range(1975, 2018, 5)],
            tickangle=0
        ),
        yaxis=dict(
            title=dict(
                text='<b>Net Asset Value (NAV)</b>',
                font=dict(size=14, family='Arial, sans-serif', color='#34495e')
            ),
            showgrid=True,
            gridcolor=grid_color,
            gridwidth=1,
            zeroline=False,
            tickfont=dict(size=11, color='#7f8c8d'),
            tickformat='$,.0f',
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
        width=1200,
        height=700
    )

    return fig


def create_pdf_brochure(fig, output_filename="rise_capital_brochure.pdf"):
    """
    Create PDF brochure with the equity curve chart.

    Args:
        fig: Plotly figure object
        output_filename: Output PDF filename
    """
    # Export chart as image
    img_bytes = fig.to_image(format="png", width=1200, height=700, scale=2)

    # Create PDF
    pdf = canvas.Canvas(output_filename, pagesize=letter)
    width, height = letter

    # Add header
    pdf.setFont("Helvetica-Bold", 28)
    pdf.setFillColor(HexColor('#2c3e50'))
    pdf.drawCentredString(width / 2, height - 50, "Rise Capital Management")

    pdf.setFont("Helvetica", 16)
    pdf.setFillColor(HexColor('#7f8c8d'))
    pdf.drawCentredString(width / 2, height - 75, "CTA Program Performance Review")

    # Add date
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(HexColor('#95a5a6'))
    today = datetime.now().strftime("%B %d, %Y")
    pdf.drawCentredString(width / 2, height - 95, f"Report Generated: {today}")

    # Add chart
    # Convert bytes to image and add to PDF
    from reportlab.lib.utils import ImageReader
    img = ImageReader(io.BytesIO(img_bytes))

    # Calculate image dimensions to fit nicely
    img_width = width - 80  # 40pt margins on each side
    img_height = img_width * (700 / 1200)  # Maintain aspect ratio

    x_pos = (width - img_width) / 2
    y_pos = height - 120 - img_height

    pdf.drawImage(img, x_pos, y_pos, width=img_width, height=img_height)

    # Add footer
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.setFillColor(HexColor('#95a5a6'))
    footer_text = "Past performance is not indicative of future results. For institutional investors only."
    pdf.drawCentredString(width / 2, 30, footer_text)

    # Save PDF
    pdf.save()
    print(f"\nPDF saved as: {output_filename}")


if __name__ == "__main__":
    print("Creating Rise Capital brochure...\n")

    # Connect to database
    db = Database("pnlrg.db")
    db.connect()

    # Get data for 50M fund (good representative size)
    df = get_equity_curve_data(db, "CTA_50M_30")

    # Create chart
    fig = create_equity_curve_chart(df, "Rise CTA Fund ($50M)")

    # Save as HTML for preview
    fig.write_html("equity_curve_preview.html")
    print("\nInteractive chart saved as: equity_curve_preview.html")

    # Create PDF brochure
    create_pdf_brochure(fig, "rise_capital_brochure.pdf")

    db.close()

    print("\n" + "="*60)
    print("Brochure creation complete!")
    print("="*60)
    print("\nFiles created:")
    print("  1. equity_curve_preview.html - Interactive preview")
    print("  2. rise_capital_brochure.pdf - Final brochure")
