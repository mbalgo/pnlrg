"""
Example workflow demonstrating the modular brochure generation system.

This script shows how to:
1. Create a brochure template
2. Instantiate the template for a specific manager/program
3. Generate the brochure
4. Retrieve and export the PDF
"""

from database import Database
from brochures.templates import create_template, instantiate_template, list_templates, list_instances
from brochures.generator import generate_brochure, export_brochure


def main():
    # Connect to database
    db = Database("pnlrg.db")
    db.connect()

    print("="*70)
    print("MODULAR BROCHURE GENERATION SYSTEM - Example Workflow")
    print("="*70)

    # Step 1: Create a template (or use existing)
    print("\n1. Creating brochure template...")
    print("-"*70)

    # Check if template already exists
    existing_template = db.fetch_one(
        "SELECT id FROM brochure_templates WHERE template_name = ?",
        ("Standard CTA Performance Report",)
    )

    if existing_template:
        template_id = existing_template['id']
        print(f"Using existing template (ID: {template_id})")
    else:
        template_id = create_template(
            db,
            template_name="Standard CTA Performance Report",
            description="Standard performance report with equity curve, performance summary, and disclaimers",
            components=[
            {
                "type": "text",
                "name": "strategy_description",
                "order": 1
            },
            {
                "type": "chart",
                "name": "equity_curve_chart",
                "config": {
                    "benchmarks": ["SP500"],  # Only SP500 has data from 1973
                    "width": 1200,
                    "height": 700
                },
                "order": 2
            },
            {
                "type": "table",
                "name": "performance_summary_table",
                "config": {
                    "periods": ["1Y", "3Y", "5Y", "ITD"]
                },
                "order": 3
            },
            {
                "type": "text",
                "name": "disclaimer_text",
                "order": 4
            }
        ]
        )

    # Step 2: List available templates
    print("\n2. Available templates:")
    print("-"*70)
    templates = list_templates(db)
    for t in templates:
        print(f"  [{t['id']}] {t['template_name']}")
        print(f"      {t['description']}")
        print(f"      Created: {t['created_date']}")

    # Step 3: Get manager and program IDs
    print("\n3. Finding Rise Capital Management program...")
    print("-"*70)

    manager = db.fetch_one("SELECT id, manager_name FROM managers WHERE manager_name = 'Rise Capital Management'")
    program = db.fetch_one("SELECT id, program_name FROM programs WHERE program_name = 'CTA_50M_30'")

    if not manager or not program:
        print("  Error: Rise Capital Management or CTA_50M_30 not found!")
        print("  Make sure you've imported the CTA data first.")
        db.close()
        return

    print(f"  Manager: {manager['manager_name']} (ID: {manager['id']})")
    print(f"  Program: {program['program_name']} (ID: {program['id']})")

    # Step 4: Instantiate template
    print("\n4. Creating brochure instance...")
    print("-"*70)

    instance_id = instantiate_template(
        db,
        template_id=template_id,
        manager_id=manager['id'],
        program_id=program['id'],
        instance_name="Rise CTA 50M Performance Report - Full History"
        # No overrides - show full date range from 1973
    )

    # Step 5: List instances
    print("\n5. Brochure instances for Rise Capital:")
    print("-"*70)
    instances = list_instances(db, manager_id=manager['id'])
    for inst in instances:
        print(f"  [{inst['id']}] {inst['instance_name']}")
        print(f"      Program: {inst['program_name']}")
        print(f"      Template: {inst['template_name'] or 'Custom'}")
        print(f"      Last Generated: {inst['last_generated'] or 'Never'}")

    # Step 6: Generate brochure
    print("\n6. Generating brochure...")
    print("-"*70)

    try:
        pdf_bytes = generate_brochure(db, instance_id)
        print(f"  Success! Generated {len(pdf_bytes):,} bytes")
    except Exception as e:
        print(f"  Error generating brochure: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return

    # Step 7: Export to file
    print("\n7. Exporting brochure to file...")
    print("-"*70)

    import os
    os.makedirs("export", exist_ok=True)

    output_path = "export/rise_cta_50m_report.pdf"
    success = export_brochure(db, instance_id, output_path)

    if success:
        print(f"  Brochure saved to: {output_path}")

    # Step 8: Show how to regenerate
    print("\n8. How to regenerate after data updates:")
    print("-"*70)
    print(f"  # After importing new data, simply run:")
    print(f"  pdf_bytes = generate_brochure(db, instance_id={instance_id})")
    print(f"  # The same configuration will be used with updated data")

    print("\n" + "="*70)
    print("WORKFLOW COMPLETE!")
    print("="*70)
    print("\nKey Benefits:")
    print("  - Template reusable across programs")
    print("  - Instance stores exact configuration")
    print("  - Regenerate with same config, updated data")
    print("  - PDF stored in database (no file clutter)")
    print("  - Export to file when needed")

    db.close()


if __name__ == "__main__":
    main()
