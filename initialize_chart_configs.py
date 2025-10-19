"""
Initialize chart configuration database tables and populate with defaults.

This script:
1. Creates chart configuration tables
2. Inserts default style presets
3. Registers chart types with their default configurations
"""

import json
from database import Database
from components.chart_config import (
    DEFAULT_LAYOUT_CONFIG,
    DEFAULT_STYLE_CONFIG,
    DEFAULT_AXES_CONFIG,
    DEFAULT_SERIES_CONFIG,
    DEFAULT_PANEL_CONFIG,
    ROLLING_PERFORMANCE_PANEL_CONFIG
)


def initialize_chart_config_schema(db):
    """Create chart configuration tables."""
    print("\n" + "=" * 70)
    print("INITIALIZING CHART CONFIGURATION SCHEMA")
    print("=" * 70)

    # Read and execute schema
    with open('schema_chart_config.sql', 'r') as f:
        schema = f.read()

    db.connection.executescript(schema)
    print("\n[OK] Chart configuration tables created")


def create_default_style_preset(db):
    """Create the default chart style preset."""
    print("\nCreating default style preset...")

    # Check if already exists
    existing = db.fetch_one("SELECT id FROM chart_style_presets WHERE preset_name = 'default'")
    if existing:
        print("  [SKIP] Default preset already exists (ID: {})".format(existing['id']))
        return existing['id']

    # Insert default preset
    db.execute("""
        INSERT INTO chart_style_presets (
            preset_name,
            description,
            layout_config,
            style_config,
            axes_config,
            series_config,
            panel_config,
            is_default
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'default',
        'Default chart styling with professional appearance',
        json.dumps(DEFAULT_LAYOUT_CONFIG, indent=2),
        json.dumps(DEFAULT_STYLE_CONFIG, indent=2),
        json.dumps(DEFAULT_AXES_CONFIG, indent=2),
        json.dumps(DEFAULT_SERIES_CONFIG, indent=2),
        json.dumps(DEFAULT_PANEL_CONFIG, indent=2),
        1  # is_default
    ))

    preset_id = db.connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"  [OK] Created default preset (ID: {preset_id})")
    return preset_id


def create_rolling_performance_preset(db):
    """Create preset specifically for rolling performance charts."""
    print("\nCreating rolling performance chart preset...")

    # Check if already exists
    existing = db.fetch_one("SELECT id FROM chart_style_presets WHERE preset_name = 'rolling_performance'")
    if existing:
        print("  [SKIP] Rolling performance preset already exists (ID: {})".format(existing['id']))
        return existing['id']

    # Rolling performance uses smaller fonts and A4 paper
    rolling_layout = DEFAULT_LAYOUT_CONFIG.copy()
    rolling_layout['width'] = 595  # A4 width
    rolling_layout['height'] = 842  # A4 height
    rolling_layout['margin'] = {"l": 50, "r": 20, "t": 80, "b": 40}

    rolling_style = DEFAULT_STYLE_CONFIG.copy()
    rolling_style['fonts'] = {
        "family": "Arial, sans-serif",
        "title_size": 14,
        "subtitle_size": 11,
        "axis_title_size": 10,
        "axis_tick_size": 9,
        "legend_size": 8,
        "hover_size": 10
    }

    rolling_series = DEFAULT_SERIES_CONFIG.copy()
    rolling_series['mode'] = 'lines+markers'  # Show markers on non-overlapping
    rolling_series['include_markers'] = True

    # Insert preset
    db.execute("""
        INSERT INTO chart_style_presets (
            preset_name,
            description,
            layout_config,
            style_config,
            axes_config,
            series_config,
            panel_config,
            is_default
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'rolling_performance',
        'Multi-panel rolling performance charts with compact A4 layout',
        json.dumps(rolling_layout, indent=2),
        json.dumps(rolling_style, indent=2),
        json.dumps(DEFAULT_AXES_CONFIG, indent=2),
        json.dumps(rolling_series, indent=2),
        json.dumps(ROLLING_PERFORMANCE_PANEL_CONFIG, indent=2),
        0  # not default
    ))

    preset_id = db.connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"  [OK] Created rolling performance preset (ID: {preset_id})")
    return preset_id


def create_a4_preset(db):
    """Create A4 paper size preset for PDF brochures."""
    print("\nCreating A4 brochure preset...")

    # Check if already exists
    existing = db.fetch_one("SELECT id FROM chart_style_presets WHERE preset_name = 'a4_brochure'")
    if existing:
        print("  [SKIP] A4 brochure preset already exists (ID: {})".format(existing['id']))
        return existing['id']

    # A4 layout
    a4_layout = DEFAULT_LAYOUT_CONFIG.copy()
    a4_layout['width'] = 595  # A4 width in points
    a4_layout['height'] = 842  # A4 height in points

    # Insert preset
    db.execute("""
        INSERT INTO chart_style_presets (
            preset_name,
            description,
            layout_config,
            style_config,
            axes_config,
            series_config,
            panel_config,
            is_default
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'a4_brochure',
        'A4 paper size for PDF brochures (595x842 pt)',
        json.dumps(a4_layout, indent=2),
        json.dumps(DEFAULT_STYLE_CONFIG, indent=2),
        json.dumps(DEFAULT_AXES_CONFIG, indent=2),
        json.dumps(DEFAULT_SERIES_CONFIG, indent=2),
        json.dumps(DEFAULT_PANEL_CONFIG, indent=2),
        0  # not default
    ))

    preset_id = db.connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"  [OK] Created A4 brochure preset (ID: {preset_id})")
    return preset_id


def register_chart_types(db, default_preset_id, rolling_preset_id, a4_preset_id):
    """Register all chart types with their default presets."""
    print("\nRegistering chart types...")

    chart_types = [
        ('equity_curve', a4_preset_id, 'Equity curve showing NAV over time'),
        ('rolling_performance', rolling_preset_id, '4-panel rolling performance metrics'),
        ('monthly_heatmap', a4_preset_id, 'Monthly returns heatmap'),
        ('drawdown_chart', a4_preset_id, 'Drawdown over time'),
        ('performance_summary', default_preset_id, 'Performance statistics table')
    ]

    for chart_type, preset_id, description in chart_types:
        # Check if exists
        existing = db.fetch_one("SELECT id FROM chart_type_configs WHERE chart_type = ?", (chart_type,))

        if existing:
            print(f"  [SKIP] {chart_type} already registered")
            continue

        # Insert
        db.execute("""
            INSERT INTO chart_type_configs (chart_type, default_style_preset_id, description)
            VALUES (?, ?, ?)
        """, (chart_type, preset_id, description))

        print(f"  [OK] Registered '{chart_type}' (preset: {preset_id})")


def main():
    """Main initialization function."""
    db = Database('pnlrg.db')
    db.connect()

    try:
        # Step 1: Create schema
        initialize_chart_config_schema(db)

        # Step 2: Create style presets
        default_preset_id = create_default_style_preset(db)
        rolling_preset_id = create_rolling_performance_preset(db)
        a4_preset_id = create_a4_preset(db)

        # Step 3: Register chart types
        register_chart_types(db, default_preset_id, rolling_preset_id, a4_preset_id)

        print("\n" + "=" * 70)
        print("CHART CONFIGURATION INITIALIZATION COMPLETE")
        print("=" * 70)

        # Show summary
        print("\nStyle Presets:")
        presets = db.fetch_all("SELECT id, preset_name, description FROM chart_style_presets")
        for preset in presets:
            default_marker = " [DEFAULT]" if preset['preset_name'] == 'default' else ""
            print(f"  {preset['id']}: {preset['preset_name']}{default_marker}")
            print(f"      {preset['description']}")

        print("\nChart Type Registrations:")
        types = db.fetch_all("""
            SELECT ct.chart_type, ct.description, csp.preset_name
            FROM chart_type_configs ct
            LEFT JOIN chart_style_presets csp ON ct.default_style_preset_id = csp.id
        """)
        for chart_type in types:
            print(f"  {chart_type['chart_type']}: {chart_type['preset_name']}")
            print(f"      {chart_type['description']}")

        print("\n" + "=" * 70)
        print("You can now use the chart_config module to load configurations!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    main()
