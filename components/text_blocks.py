"""
Text block generation components for brochures.

Each function generates narrative text content.
"""


def strategy_description(db, manager_id, program_id, **kwargs):
    """
    Generate strategy description text.

    Args:
        db: Database instance
        manager_id: Manager ID
        program_id: Program ID
        **kwargs: Additional customization

    Returns:
        String with HTML formatting
    """
    program = db.fetch_one("""
        SELECT p.program_name, p.fund_size, m.manager_name
        FROM programs p
        JOIN managers m ON p.manager_id = m.id
        WHERE p.id = ?
    """, (program_id,))

    if not program:
        return "<p>Program not found</p>"

    text = f"""
    <h2>Strategy Overview</h2>
    <p><strong>Manager:</strong> {program['manager_name']}</p>
    <p><strong>Program:</strong> {program['program_name']}</p>
    <p><strong>Fund Size:</strong> ${program['fund_size']:,.0f}</p>
    <p>This is a systematic trend-following CTA strategy that trades a diversified
    portfolio of global futures markets across multiple asset classes including
    equities, fixed income, currencies, and commodities.</p>
    """

    return text


def performance_commentary(db, program_id, **kwargs):
    """
    Generate performance commentary text.

    Args:
        db: Database instance
        program_id: Program ID
        **kwargs: Additional customization

    Returns:
        String with HTML formatting
    """
    # TODO: Implement automated performance commentary
    return """
    <h2>Performance Commentary</h2>
    <p>The strategy has demonstrated consistent performance across multiple market cycles...</p>
    """


def disclaimer_text(**kwargs):
    """
    Generate standard disclaimer text.

    Args:
        **kwargs: Additional customization

    Returns:
        String with HTML formatting
    """
    return """
    <div style="font-size: 10px; color: #666; margin-top: 20px;">
    <p><strong>DISCLAIMER:</strong> Past performance is not indicative of future results.
    This material is for institutional investors only and should not be construed as
    investment advice or a recommendation.</p>
    </div>
    """
