"""
Example demonstrating how to use the chart configuration system.

Shows:
1. Loading chart configurations from database
2. Applying configurations to Plotly figures
3. Customizing specific charts with overrides
"""

from database import Database
from components.chart_config import (
    load_chart_config,
    apply_layout_config,
    apply_axes_config,
    get_series_color,
    get_line_width
)
import plotly.graph_objects as go


def example_basic_usage():
    """Example 1: Basic usage - load and apply config."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Configuration Usage")
    print("=" * 70)

    db = Database('pnlrg.db')
    db.connect()

    # Load configuration for equity curve chart
    config = load_chart_config(db, chart_type='equity_curve')

    print("\nLoaded configuration for 'equity_curve' chart:")
    print(f"  Width: {config['layout']['width']}")
    print(f"  Height: {config['layout']['height']}")
    print(f"  Title font size: {config['style']['fonts']['title_size']}")
    print(f"  Line width: {config['style']['lines']['width']}")

    # Create a simple figure
    fig = go.Figure()

    # Add some sample data
    import pandas as pd
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    values = [1000 * (1.01 ** i) for i in range(100)]

    # Get color from config
    line_color = get_series_color(config, 'primary', index=0)
    line_width = get_line_width(config, 'default')

    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        name='Example Series',
        line=dict(color=line_color, width=line_width),
        mode='lines'
    ))

    # Apply configuration
    apply_layout_config(fig, config, chart_type='equity_curve', title='Example Equity Curve')
    apply_axes_config(fig, config, y_title='NAV ($1K)')

    print("\n[OK] Configuration applied to figure")
    print(f"  Figure size: {fig.layout.width}x{fig.layout.height}")

    db.close()


def example_multi_series():
    """Example 2: Multi-series chart with benchmark colors."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Multi-Series with Benchmark Colors")
    print("=" * 70)

    db = Database('pnlrg.db')
    db.connect()

    config = load_chart_config(db, chart_type='equity_curve')

    # Create figure
    fig = go.Figure()

    # Sample data
    import pandas as pd
    dates = pd.date_range('2020-01-01', periods=100, freq='D')

    series_data = [
        ('Rise CTA', [1000 * (1.01 ** i) for i in range(100)]),
        ('SP500', [1000 * (1.015 ** i) for i in range(100)]),
        ('BTOP50', [1000 * (1.008 ** i) for i in range(100)])
    ]

    print("\nApplying colors from configuration:")
    for idx, (name, values) in enumerate(series_data):
        color = get_series_color(config, name, index=idx)
        print(f"  {name}: {color}")

        fig.add_trace(go.Scatter(
            x=dates,
            y=values,
            name=name,
            line=dict(color=color, width=get_line_width(config)),
            mode='lines'
        ))

    # Apply configuration
    apply_layout_config(fig, config, chart_type='equity_curve',
                       title='Multi-Series Example')
    apply_axes_config(fig, config, y_title='NAV ($1K)')

    print("\n[OK] Multi-series chart configured")

    db.close()


def example_rolling_performance():
    """Example 3: Rolling performance chart with multi-panel config."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Rolling Performance Multi-Panel Chart")
    print("=" * 70)

    db = Database('pnlrg.db')
    db.connect()

    # Load rolling performance config
    config = load_chart_config(db, chart_type='rolling_performance')

    print("\nRolling performance configuration:")
    print(f"  Paper size: {config['layout']['width']}x{config['layout']['height']} (A4)")
    print(f"  Title font: {config['style']['fonts']['title_size']}pt")
    print(f"  Axis font: {config['style']['fonts']['axis_title_size']}pt")
    print(f"  Legend font: {config['style']['fonts']['legend_size']}pt")
    print(f"  Panel spacing: {config['panel']['vertical_spacing']}")
    print(f"  Panel heights: {config['panel']['panel_heights']}")

    panel_config = config['panel']
    print(f"\n  Panel titles:")
    for i, title in enumerate(panel_config['panel_titles'], 1):
        print(f"    {i}. {title}")

    print("\n[OK] Rolling performance config loaded")
    print("  Use this config with plotly.subplots.make_subplots for multi-panel charts")

    db.close()


def example_view_all_presets():
    """Example 4: View all available presets."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: View All Available Presets")
    print("=" * 70)

    db = Database('pnlrg.db')
    db.connect()

    presets = db.fetch_all("""
        SELECT id, preset_name, description, is_default
        FROM chart_style_presets
        ORDER BY is_default DESC, id
    """)

    print("\nAvailable Chart Style Presets:")
    print("-" * 70)

    for preset in presets:
        default_marker = " [DEFAULT]" if preset['is_default'] else ""
        print(f"\n  ID: {preset['id']} - {preset['preset_name']}{default_marker}")
        print(f"  Description: {preset['description']}")

    # Show chart type mappings
    print("\n" + "=" * 70)
    print("Chart Type to Preset Mappings:")
    print("-" * 70)

    mappings = db.fetch_all("""
        SELECT ct.chart_type, csp.preset_name
        FROM chart_type_configs ct
        LEFT JOIN chart_style_presets csp ON ct.default_style_preset_id = csp.id
        ORDER BY ct.chart_type
    """)

    for mapping in mappings:
        print(f"  {mapping['chart_type']:25} -> {mapping['preset_name']}")

    db.close()


def main():
    """Run all examples."""
    print("=" * 70)
    print("CHART CONFIGURATION SYSTEM EXAMPLES")
    print("=" * 70)

    example_basic_usage()
    example_multi_series()
    example_rolling_performance()
    example_view_all_presets()

    print("\n" + "=" * 70)
    print("EXAMPLES COMPLETE")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("  1. Use load_chart_config(db, 'chart_type') to get configuration")
    print("  2. Use apply_layout_config() and apply_axes_config() to apply to figures")
    print("  3. Use get_series_color() to get consistent colors across charts")
    print("  4. Presets are stored in database and can be customized per brochure")
    print("=" * 70)


if __name__ == "__main__":
    main()
