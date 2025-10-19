# Chart Configuration System

## Overview

The chart configuration system provides centralized, database-backed chart formatting to eliminate hardcoded styling scattered across chart generation functions. This ensures consistency, makes customization easy, and supports brochure-specific overrides.

## Architecture

### Database Schema

Three main tables support the configuration system:

1. **`chart_style_presets`** - Reusable style configurations
   - Layout config (width, height, margins, paper size)
   - Style config (colors, fonts, line widths, grid styles)
   - Axes config (titles, ticks, formats)
   - Series config (default series settings)
   - Panel config (multi-panel chart settings)

2. **`chart_type_configs`** - Maps chart types to default presets
   - Links chart types (equity_curve, rolling_performance, etc.) to style presets

3. **`brochure_chart_overrides`** - Instance-specific customizations
   - Allows brochure components to override specific settings

### Configuration Hierarchy

```
Default Preset (base styling)
    ↓
Chart Type Preset (chart-specific adjustments)
    ↓
Brochure Override (instance-specific customizations)
```

## Available Presets

### 1. Default Preset (ID: 1)
- **Use case**: General charts, screen display
- **Size**: 1200x700 px
- **Fonts**: Professional sizes (title: 24pt, axes: 14pt)
- **Colors**: Full color scheme including benchmarks

### 2. Rolling Performance Preset (ID: 2)
- **Use case**: Multi-panel rolling performance charts
- **Size**: A4 (595x842 pt)
- **Fonts**: Compact (title: 14pt, axes: 10pt, legend: 8pt)
- **Panels**: 4 equal panels with 10% spacing
- **Series**: Lines + markers for non-overlapping data

### 3. A4 Brochure Preset (ID: 3)
- **Use case**: PDF brochures, equity curves
- **Size**: A4 (595x842 pt)
- **Fonts**: Standard sizes for print
- **Series**: Lines only (no markers)

## Chart Types

Registered chart types and their default presets:

| Chart Type | Default Preset | Description |
|------------|---------------|-------------|
| `equity_curve` | a4_brochure | Equity curve showing NAV over time |
| `rolling_performance` | rolling_performance | 4-panel rolling performance metrics |
| `monthly_heatmap` | a4_brochure | Monthly returns heatmap |
| `drawdown_chart` | a4_brochure | Drawdown over time |
| `performance_summary` | default | Performance statistics table |

## Usage

### Basic Usage

```python
from database import Database
from components.chart_config import (
    load_chart_config,
    apply_layout_config,
    apply_axes_config,
    get_series_color
)
import plotly.graph_objects as go

# 1. Load configuration
db = Database('pnlrg.db')
db.connect()
config = load_chart_config(db, chart_type='equity_curve')

# 2. Create figure and add data
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=dates,
    y=values,
    name='My Series',
    line=dict(
        color=get_series_color(config, 'My Series', index=0),
        width=config['style']['lines']['width']
    ),
    mode='lines'
))

# 3. Apply configuration
apply_layout_config(fig, config, chart_type='equity_curve',
                   title='My Chart Title')
apply_axes_config(fig, config, y_title='NAV ($1K)')

# 4. Export
fig.write_image('export/my_chart.pdf')
```

### Multi-Panel Charts

```python
from plotly.subplots import make_subplots

# Load rolling performance config
config = load_chart_config(db, chart_type='rolling_performance')

# Get panel configuration
panel_config = config['panel']
panel_titles = panel_config['panel_titles']
panel_heights = panel_config['panel_heights']

# Create subplots
fig = make_subplots(
    rows=4, cols=1,
    subplot_titles=panel_titles,
    vertical_spacing=panel_config['vertical_spacing'],
    row_heights=panel_heights
)

# Add traces to each panel
for row in range(1, 5):
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            name='Series',
            line=dict(
                color=get_series_color(config, 'Series'),
                width=config['style']['lines']['width']
            ),
            mode=config['series']['mode']
        ),
        row=row, col=1
    )

# Apply layout (single call for all panels)
apply_layout_config(fig, config, chart_type='rolling_performance',
                   title='Rolling Performance')

# Apply axes to each panel
for row in range(1, 5):
    y_title = panel_config['y_axis_titles'][row-1]
    fig.update_yaxes(title_text=y_title, row=row, col=1)
```

### Color Mapping

The configuration system includes predefined colors for common series:

```python
colors = {
    'primary': '#1f77b4',      # Blue (Rise CTA)
    'SP500': '#ff7f0e',        # Orange
    'BTOP50': '#2ca02c',       # Green
    'AREIT': '#d62728',        # Red
    'Leading Competitor': '#9467bd',  # Purple
}

# Get color by name
color = get_series_color(config, 'SP500')  # Returns '#ff7f0e'

# Or by index (falls back to color cycle)
color = get_series_color(config, 'Unknown Series', index=2)
```

## Customization

### Creating Custom Presets

```python
import json

# Define custom configuration
custom_layout = {
    "width": 800,
    "height": 600,
    "margin": {"l": 60, "r": 30, "t": 80, "b": 50}
}

custom_style = {
    "colors": {
        "primary": "#0066cc",  # Custom blue
        "SP500": "#ff9900"      # Custom orange
    },
    "fonts": {
        "family": "Helvetica, sans-serif",
        "title_size": 20
    }
}

# Insert into database
db.execute("""
    INSERT INTO chart_style_presets (
        preset_name, description, layout_config, style_config, is_default
    ) VALUES (?, ?, ?, ?, ?)
""", (
    'custom_preset',
    'My custom chart styling',
    json.dumps(custom_layout),
    json.dumps(custom_style),
    0  # Not default
))
```

### Brochure-Specific Overrides

```python
# Override specific settings for a brochure component
override_config = {
    "style": {
        "fonts": {
            "title_size": 18  # Smaller title for this brochure
        }
    },
    "layout": {
        "width": 500,
        "height": 400
    }
}

db.execute("""
    INSERT INTO brochure_chart_overrides (brochure_component_id, override_config)
    VALUES (?, ?)
""", (component_id, json.dumps(override_config)))

# Load with override
config = load_chart_config(db, chart_type='equity_curve',
                          brochure_component_id=component_id)
# Now config has merged settings from preset + override
```

## Configuration Reference

### Layout Config

```json
{
    "width": 1200,
    "height": 700,
    "margin": {"l": 80, "r": 40, "t": 100, "b": 60},
    "paper_size": {
        "a4": {"width": 595, "height": 842},
        "letter": {"width": 612, "height": 792}
    },
    "plot_bgcolor": "white",
    "paper_bgcolor": "white",
    "hovermode": "x unified"
}
```

### Style Config

```json
{
    "colors": {
        "primary": "#1f77b4",
        "SP500": "#ff7f0e",
        "BTOP50": "#2ca02c",
        "AREIT": "#d62728",
        "Leading Competitor": "#9467bd",
        "grid": "#e5e5e5",
        "axis_line": "#bdc3c7",
        "text": "#2c3e50"
    },
    "fonts": {
        "family": "Arial, sans-serif",
        "title_size": 24,
        "subtitle_size": 14,
        "axis_title_size": 14,
        "axis_tick_size": 11,
        "legend_size": 12
    },
    "lines": {
        "width": 3,
        "grid_width": 1,
        "axis_width": 2
    },
    "markers": {
        "size": 8
    }
}
```

### Axes Config

```json
{
    "x_axis": {
        "showgrid": true,
        "gridcolor": "#e5e5e5",
        "zeroline": false,
        "showline": true,
        "linewidth": 2,
        "linecolor": "#bdc3c7",
        "date_tick_interval": 5,
        "tick_format": "%Y"
    },
    "y_axis": {
        "showgrid": true,
        "zeroline": false,
        "tickformat": ",.0f"
    }
}
```

### Panel Config (Multi-Panel Charts)

```json
{
    "vertical_spacing": 0.10,
    "panel_heights": [0.25, 0.25, 0.25, 0.25],
    "title_font_size": 11,
    "show_legend_on_panel": 1,
    "panel_titles": [
        "<b>Mean Monthly Return</b>",
        "<b>Standard Deviation</b>",
        "<b>CAGR</b>",
        "<b>Maximum Drawdown - Compounded</b>"
    ],
    "y_axis_titles": [
        "Mean Return (%)",
        "Std Dev (%)",
        "CAGR (%)",
        "Max Drawdown (%)"
    ]
}
```

## Initialization

To initialize the chart configuration system in a new database:

```bash
python initialize_chart_configs.py
```

This creates:
- Chart configuration tables
- Default style presets
- Chart type registrations

## Examples

See `example_chart_config_usage.py` for complete working examples:

```bash
python example_chart_config_usage.py
```

## Benefits

1. **Consistency** - All charts use same styling automatically
2. **Centralized** - Change colors/fonts in one place
3. **Customizable** - Easy per-brochure overrides
4. **Database-backed** - No config files to manage
5. **Type-specific** - Different defaults for different chart types
6. **Maintainable** - Clear separation of data vs presentation

## Migration

To update existing chart generation code:

### Before (Hardcoded)
```python
fig.update_layout(
    title='My Chart',
    width=595,
    height=842,
    margin=dict(l=50, r=20, t=80, b=40),
    # ... 50 more lines of hardcoded styling
)
```

### After (Config-based)
```python
config = load_chart_config(db, chart_type='equity_curve')
apply_layout_config(fig, config, chart_type='equity_curve', title='My Chart')
apply_axes_config(fig, config, y_title='NAV ($1K)')
```

Much cleaner and consistent!
