"""
PDF assembly and rendering.

Combines charts, tables, and text into professional PDF documents.
"""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
import io


def assemble_pdf(components, title="Performance Report", manager_name="", **kwargs):
    """
    Assemble components into a PDF document.

    Args:
        components: List of (type, content) tuples
            - ('chart', plotly_figure)
            - ('table', html_string)
            - ('text', html_string)
        title: Document title
        manager_name: Manager name for header
        **kwargs: Additional rendering options

    Returns:
        PDF bytes
    """
    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter

    # Track vertical position
    y_position = height - 50

    # Add header
    pdf.setFont("Helvetica-Bold", 28)
    pdf.setFillColor(HexColor('#2c3e50'))
    pdf.drawCentredString(width / 2, y_position, manager_name or "Performance Report")
    y_position -= 30

    pdf.setFont("Helvetica", 16)
    pdf.setFillColor(HexColor('#7f8c8d'))
    pdf.drawCentredString(width / 2, y_position, title)
    y_position -= 40

    # Process components
    for comp_type, content in components:
        if comp_type == 'chart':
            # Convert Plotly chart to image
            try:
                img_bytes = content.to_image(format="png", width=1200, height=700, scale=2)
                img = ImageReader(io.BytesIO(img_bytes))

                # Calculate dimensions
                img_width = width - 80  # 40pt margins
                img_height = img_width * (700 / 1200)

                # Check if we need a new page
                if y_position - img_height < 100:
                    pdf.showPage()
                    y_position = height - 50

                x_pos = (width - img_width) / 2
                y_pos = y_position - img_height

                pdf.drawImage(img, x_pos, y_pos, width=img_width, height=img_height)
                y_position = y_pos - 20

            except Exception as e:
                print(f"Error rendering chart: {e}")
                pdf.setFont("Helvetica", 10)
                pdf.setFillColor(HexColor('#e74c3c'))
                pdf.drawString(40, y_position, f"Error rendering chart: {e}")
                y_position -= 30

        elif comp_type == 'table':
            # For now, simple text rendering
            # TODO: Implement proper HTML table rendering
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(HexColor('#2c3e50'))

            # Check if we need a new page
            if y_position < 200:
                pdf.showPage()
                y_position = height - 50

            pdf.drawString(40, y_position, "Table (HTML rendering coming soon)")
            y_position -= 100

        elif comp_type == 'text':
            # Simple text rendering
            # TODO: Implement proper HTML text rendering
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(HexColor('#2c3e50'))

            # Check if we need a new page
            if y_position < 150:
                pdf.showPage()
                y_position = height - 50

            # For now, just indicate text block
            pdf.drawString(40, y_position, "Text block")
            y_position -= 50

        elif comp_type == 'error':
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(HexColor('#e74c3c'))
            pdf.drawString(40, y_position, f"Error: {content}")
            y_position -= 30

    # Add footer
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.setFillColor(HexColor('#95a5a6'))
    footer_text = "Past performance is not indicative of future results. For institutional investors only."
    pdf.drawCentredString(width / 2, 30, footer_text)

    # Save PDF
    pdf.save()

    # Get PDF bytes
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    return pdf_bytes
