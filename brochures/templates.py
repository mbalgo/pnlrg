"""
Brochure template management.

Functions for creating, managing, and instantiating brochure templates.
"""

import json
from datetime import datetime


def create_template(db, template_name, description, components):
    """
    Create a new brochure template.

    Args:
        db: Database instance
        template_name: Unique name for the template
        description: Description of the template
        components: List of dicts, each containing:
            - type: 'chart', 'table', or 'text'
            - name: Component function name (e.g., 'equity_curve_chart')
            - config: Dict of parameters (optional)
            - order: Display order (optional, defaults to list order)

    Returns:
        Template ID

    Example:
        template_id = create_template(
            db,
            "Standard CTA Performance",
            "Standard performance report with equity curve and summary table",
            [
                {"type": "text", "name": "strategy_description"},
                {"type": "chart", "name": "equity_curve_chart",
                 "config": {"benchmarks": ["SP500", "BTOP50"]}},
                {"type": "table", "name": "performance_summary_table",
                 "config": {"periods": ["1Y", "3Y", "5Y", "ITD"]}},
                {"type": "text", "name": "disclaimer_text"}
            ]
        )
    """
    # Insert template
    cursor = db.execute(
        "INSERT INTO brochure_templates (template_name, description, created_date) VALUES (?, ?, ?)",
        (template_name, description, datetime.now().strftime('%Y-%m-%d'))
    )
    template_id = cursor.lastrowid

    # Insert components
    for idx, component in enumerate(components):
        config_json = json.dumps(component.get('config', {}))
        display_order = component.get('order', idx)

        db.execute("""
            INSERT INTO brochure_components
            (parent_id, parent_type, component_type, component_name, config_json, display_order)
            VALUES (?, 'template', ?, ?, ?, ?)
        """, (template_id, component['type'], component['name'], config_json, display_order))

    print(f"Created template '{template_name}' with ID {template_id}")
    return template_id


def instantiate_template(db, template_id, manager_id, program_id, instance_name=None, overrides=None):
    """
    Create a brochure instance from a template.

    Args:
        db: Database instance
        template_id: Template to use
        manager_id: Manager for this instance
        program_id: Program to generate for
        instance_name: Custom name (optional, will auto-generate if None)
        overrides: Dict of component_name -> config overrides (optional)

    Returns:
        Instance ID

    Example:
        instance_id = instantiate_template(
            db,
            template_id=1,
            manager_id=rise_manager_id,
            program_id=cta_50m_id,
            overrides={
                "equity_curve_chart": {"date_range": {"start": "2010-01-01"}}
            }
        )
    """
    # Get template info
    template = db.fetch_one(
        "SELECT template_name FROM brochure_templates WHERE id = ?",
        (template_id,)
    )

    if not template:
        raise ValueError(f"Template ID {template_id} not found")

    # Get program info for auto-naming
    program = db.fetch_one(
        "SELECT program_name FROM programs WHERE id = ?",
        (program_id,)
    )

    if not instance_name:
        instance_name = f"{template['template_name']} - {program['program_name']}"

    # Create instance
    cursor = db.execute("""
        INSERT INTO brochure_instances
        (instance_name, manager_id, template_id, program_id, created_date)
        VALUES (?, ?, ?, ?, ?)
    """, (instance_name, manager_id, template_id, program_id, datetime.now().strftime('%Y-%m-%d')))

    instance_id = cursor.lastrowid

    # Copy components from template
    template_components = db.fetch_all("""
        SELECT component_type, component_name, config_json, display_order
        FROM brochure_components
        WHERE parent_id = ? AND parent_type = 'template'
        ORDER BY display_order
    """, (template_id,))

    for component in template_components:
        config = json.loads(component['config_json']) if component['config_json'] else {}

        # Apply overrides if specified
        if overrides and component['component_name'] in overrides:
            config.update(overrides[component['component_name']])

        config_json = json.dumps(config)

        db.execute("""
            INSERT INTO brochure_components
            (parent_id, parent_type, component_type, component_name, config_json, display_order)
            VALUES (?, 'instance', ?, ?, ?, ?)
        """, (instance_id, component['component_type'], component['component_name'],
              config_json, component['display_order']))

    print(f"Created instance '{instance_name}' with ID {instance_id}")
    return instance_id


def list_templates(db):
    """
    List all available templates.

    Args:
        db: Database instance

    Returns:
        List of template dicts
    """
    templates = db.fetch_all("""
        SELECT id, template_name, description, created_date
        FROM brochure_templates
        ORDER BY template_name
    """)

    return templates


def list_instances(db, manager_id=None):
    """
    List brochure instances, optionally filtered by manager.

    Args:
        db: Database instance
        manager_id: Filter by manager (optional)

    Returns:
        List of instance dicts
    """
    if manager_id:
        instances = db.fetch_all("""
            SELECT bi.id, bi.instance_name, bi.last_generated,
                   m.manager_name, p.program_name, bt.template_name
            FROM brochure_instances bi
            JOIN managers m ON bi.manager_id = m.id
            JOIN programs p ON bi.program_id = p.id
            LEFT JOIN brochure_templates bt ON bi.template_id = bt.id
            WHERE bi.manager_id = ?
            ORDER BY bi.instance_name
        """, (manager_id,))
    else:
        instances = db.fetch_all("""
            SELECT bi.id, bi.instance_name, bi.last_generated,
                   m.manager_name, p.program_name, bt.template_name
            FROM brochure_instances bi
            JOIN managers m ON bi.manager_id = m.id
            JOIN programs p ON bi.program_id = p.id
            LEFT JOIN brochure_templates bt ON bi.template_id = bt.id
            ORDER BY m.manager_name, bi.instance_name
        """)

    return instances
