"""
Brochure generation engine.

Main module for generating brochures from database configurations.
"""

import json
from datetime import datetime
import importlib


def generate_brochure(db, brochure_instance_id):
    """
    Generate a brochure from a brochure instance configuration.

    Args:
        db: Database instance
        brochure_instance_id: ID of the brochure instance to generate

    Returns:
        PDF bytes

    Example:
        pdf_bytes = generate_brochure(db, instance_id=1)
        # PDF automatically saved to database
    """
    # Get instance details
    instance = db.fetch_one("""
        SELECT bi.id, bi.instance_name, bi.manager_id, bi.program_id,
               m.manager_name, p.program_name
        FROM brochure_instances bi
        JOIN managers m ON bi.manager_id = m.id
        JOIN programs p ON bi.program_id = p.id
        WHERE bi.id = ?
    """, (brochure_instance_id,))

    if not instance:
        raise ValueError(f"Brochure instance ID {brochure_instance_id} not found")

    print(f"Generating brochure: {instance['instance_name']}")
    print(f"Manager: {instance['manager_name']}, Program: {instance['program_name']}")

    # Get components
    components = db.fetch_all("""
        SELECT component_type, component_name, config_json
        FROM brochure_components
        WHERE parent_id = ? AND parent_type = 'instance'
        ORDER BY display_order
    """, (brochure_instance_id,))

    if not components:
        raise ValueError(f"No components defined for instance ID {brochure_instance_id}")

    # Generate each component
    rendered_components = []

    for component in components:
        comp_type = component['component_type']
        comp_name = component['component_name']
        config = json.loads(component['config_json']) if component['config_json'] else {}

        print(f"  Generating {comp_type}: {comp_name}")

        try:
            # Dynamically import and call the component function
            if comp_type == 'chart':
                from components import charts
                func = getattr(charts, comp_name)
                result = func(db, instance['program_id'], **config)
                rendered_components.append(('chart', result))

            elif comp_type == 'table':
                from components import tables
                func = getattr(tables, comp_name)
                result = func(db, instance['program_id'], **config)
                rendered_components.append(('table', result))

            elif comp_type == 'text':
                from components import text_blocks
                func = getattr(text_blocks, comp_name)
                # Text blocks might need manager_id
                if 'manager_id' in func.__code__.co_varnames:
                    result = func(db, instance['manager_id'], instance['program_id'], **config)
                else:
                    result = func(**config)
                rendered_components.append(('text', result))

        except Exception as e:
            print(f"    Error generating {comp_name}: {e}")
            rendered_components.append(('error', f"Error: {e}"))

    # Assemble PDF
    from .renderer import assemble_pdf
    pdf_bytes = assemble_pdf(
        rendered_components,
        title=instance['instance_name'],
        manager_name=instance['manager_name']
    )

    # Save to database
    file_size = len(pdf_bytes)

    # Check if brochure already exists
    existing = db.fetch_one("""
        SELECT id FROM generated_brochures
        WHERE brochure_instance_id = ?
    """, (brochure_instance_id,))

    if existing:
        # Update existing
        db.execute("""
            UPDATE generated_brochures
            SET pdf_data = ?, file_size = ?, generated_date = ?
            WHERE brochure_instance_id = ?
        """, (pdf_bytes, file_size, datetime.now(), brochure_instance_id))
        print(f"  Updated existing brochure (ID: {existing['id']})")
    else:
        # Insert new
        cursor = db.execute("""
            INSERT INTO generated_brochures
            (brochure_instance_id, pdf_data, file_size)
            VALUES (?, ?, ?)
        """, (brochure_instance_id, pdf_bytes, file_size))
        print(f"  Saved new brochure (ID: {cursor.lastrowid})")

    # Update last_generated timestamp
    db.execute("""
        UPDATE brochure_instances
        SET last_generated = ?
        WHERE id = ?
    """, (datetime.now(), brochure_instance_id))

    print(f"Brochure generated successfully ({file_size:,} bytes)")

    return pdf_bytes


def retrieve_brochure(db, brochure_instance_id):
    """
    Retrieve the latest generated brochure PDF.

    Args:
        db: Database instance
        brochure_instance_id: ID of the brochure instance

    Returns:
        PDF bytes, or None if not found
    """
    brochure = db.fetch_one("""
        SELECT pdf_data, generated_date, file_size
        FROM generated_brochures
        WHERE brochure_instance_id = ?
    """, (brochure_instance_id,))

    if not brochure:
        return None

    return brochure['pdf_data']


def export_brochure(db, brochure_instance_id, output_path):
    """
    Export a generated brochure to a file.

    Args:
        db: Database instance
        brochure_instance_id: ID of the brochure instance
        output_path: File path to write PDF

    Returns:
        True if successful, False otherwise
    """
    pdf_bytes = retrieve_brochure(db, brochure_instance_id)

    if not pdf_bytes:
        print(f"No brochure found for instance ID {brochure_instance_id}")
        return False

    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)

    print(f"Brochure exported to: {output_path}")
    return True
