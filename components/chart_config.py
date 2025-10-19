"""
Chart configuration system for centralized chart formatting.

This module provides a database-backed configuration system that:
- Stores default chart styling presets
- Allows per-chart-type configuration
- Supports brochure-specific overrides
- Eliminates hardcoded formatting scattered across chart functions
"""

import json
from typing import Dict, Any, Optional


# =============================================================================
# Default Configuration Presets (JSON)
# =============================================================================

DEFAULT_LAYOUT_CONFIG = {
    "width": 1200,
    "height": 700,
    "margin": {"l": 80, "r": 40, "t": 100, "b": 60},
    "paper_size": {
        "a4": {"width": 595, "height": 842},  # Points
        "letter": {"width": 612, "height": 792},
        "custom": None
    },
    "plot_bgcolor": "white",
    "paper_bgcolor": "white",
    "hovermode": "x unified"
}

DEFAULT_STYLE_CONFIG = {
    "colors": {
        "primary": "#1f77b4",      # Blue (Rise CTA)
        "SP500": "#ff7f0e",        # Orange
        "BTOP50": "#2ca02c",       # Green
        "AREIT": "#d62728",        # Red
        "Leading Competitor": "#9467bd",  # Purple
        "grid": "#e5e5e5",
        "axis_line": "#bdc3c7",
        "text": "#2c3e50",
        "text_secondary": "#7f8c8d"
    },
    "fonts": {
        "family": "Arial, sans-serif",
        "title_size": 24,
        "subtitle_size": 14,
        "axis_title_size": 14,
        "axis_tick_size": 11,
        "legend_size": 12,
        "hover_size": 12
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

DEFAULT_AXES_CONFIG = {
    "x_axis": {
        "showgrid": True,
        "gridcolor": "#e5e5e5",
        "gridwidth": 1,
        "zeroline": False,
        "showline": True,
        "linewidth": 2,
        "linecolor": "#bdc3c7",
        "tickangle": 0,
        "date_tick_interval": 5,  # Years between ticks for date axes
        "tick_format": "%Y"
    },
    "y_axis": {
        "showgrid": True,
        "gridcolor": "#e5e5e5",
        "gridwidth": 1,
        "zeroline": False,
        "showline": True,
        "linewidth": 2,
        "linecolor": "#bdc3c7",
        "tickformat": ",.0f"  # Thousand separator, no decimals
    }
}

DEFAULT_SERIES_CONFIG = {
    "mode": "lines",
    "connectgaps": False,
    "include_markers": False,  # Set to True for non-overlapping charts
    "hovertemplate": "<b>{name}</b><br>Date: %{x|%Y-%m-%d}<br>Value: %{y:,.2f}<extra></extra>"
}

DEFAULT_PANEL_CONFIG = {
    "vertical_spacing": 0.10,
    "panel_heights": None,  # Auto-equal if None, otherwise list of fractions
    "title_font_size": 11,
    "show_legend_on_panel": 1  # Which panel (1-indexed) shows legend
}

# Multi-panel chart specific settings
ROLLING_PERFORMANCE_PANEL_CONFIG = {
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


# =============================================================================
# Configuration Loading Functions
# =============================================================================

def load_chart_config(db, chart_type: str, brochure_component_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Load complete chart configuration with hierarchy:
    1. Start with default preset
    2. Apply chart-type-specific overrides
    3. Apply brochure-component-specific overrides (if provided)

    Args:
        db: Database instance
        chart_type: Chart type ('equity_curve', 'rolling_performance', etc.)
        brochure_component_id: Optional brochure component ID for custom overrides

    Returns:
        Complete configuration dictionary with all settings merged
    """
    # Start with defaults
    config = {
        "layout": DEFAULT_LAYOUT_CONFIG.copy(),
        "style": DEFAULT_STYLE_CONFIG.copy(),
        "axes": DEFAULT_AXES_CONFIG.copy(),
        "series": DEFAULT_SERIES_CONFIG.copy(),
        "panel": DEFAULT_PANEL_CONFIG.copy()
    }

    # Load chart type configuration from database
    chart_type_config = db.fetch_one("""
        SELECT csc.*
        FROM chart_type_configs ctc
        LEFT JOIN chart_style_presets csc ON ctc.default_style_preset_id = csc.id
        WHERE ctc.chart_type = ?
    """, (chart_type,))

    if chart_type_config:
        # Merge chart type preset
        config = merge_config(config, parse_preset_config(chart_type_config))

    # Load brochure-specific overrides if provided
    if brochure_component_id:
        override = db.fetch_one("""
            SELECT override_config
            FROM brochure_chart_overrides
            WHERE brochure_component_id = ?
        """, (brochure_component_id,))

        if override and override['override_config']:
            override_config = json.loads(override['override_config'])
            config = merge_config(config, override_config)

    return config


def parse_preset_config(preset_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse database preset row into config dictionary.

    Args:
        preset_row: Row from chart_style_presets table

    Returns:
        Configuration dictionary
    """
    config = {}

    if preset_row['layout_config']:
        config['layout'] = json.loads(preset_row['layout_config'])

    if preset_row['style_config']:
        config['style'] = json.loads(preset_row['style_config'])

    if preset_row['axes_config']:
        config['axes'] = json.loads(preset_row['axes_config'])

    if preset_row['series_config']:
        config['series'] = json.loads(preset_row['series_config'])

    if preset_row['panel_config']:
        config['panel'] = json.loads(preset_row['panel_config'])

    return config


def merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge override config into base config.

    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary

    Returns:
        Merged configuration dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value

    return result


# =============================================================================
# Chart Application Functions
# =============================================================================

def apply_layout_config(fig, config: Dict[str, Any], chart_type: str, title: str = None):
    """
    Apply layout configuration to a Plotly figure.

    Args:
        fig: Plotly Figure object
        config: Configuration dictionary from load_chart_config()
        chart_type: Chart type for title generation
        title: Optional custom title (overrides default)
    """
    layout = config.get('layout', DEFAULT_LAYOUT_CONFIG)
    style = config.get('style', DEFAULT_STYLE_CONFIG)

    # Determine paper size
    paper_size = layout.get('paper_size', {}).get('a4', {"width": 595, "height": 842})
    width = layout.get('width', paper_size.get('width', 1200))
    height = layout.get('height', paper_size.get('height', 700))

    # Build layout update
    layout_update = {
        'width': width,
        'height': height,
        'plot_bgcolor': layout.get('plot_bgcolor', 'white'),
        'paper_bgcolor': layout.get('paper_bgcolor', 'white'),
        'hovermode': layout.get('hovermode', 'x unified'),
        'margin': layout.get('margin', {"l": 80, "r": 40, "t": 100, "b": 60})
    }

    # Add title if provided
    if title:
        fonts = style.get('fonts', DEFAULT_STYLE_CONFIG['fonts'])
        layout_update['title'] = {
            'text': title,
            'font': {
                'size': fonts.get('title_size', 24),
                'family': fonts.get('family', 'Arial, sans-serif'),
                'color': style.get('colors', {}).get('text', '#2c3e50')
            },
            'x': 0.5,
            'xanchor': 'center'
        }

    # Add legend configuration
    fonts = style.get('fonts', DEFAULT_STYLE_CONFIG['fonts'])
    layout_update['legend'] = {
        'orientation': 'h',
        'yanchor': 'bottom',
        'y': 1.02,
        'xanchor': 'right',
        'x': 1,
        'font': {
            'size': fonts.get('legend_size', 12),
            'family': fonts.get('family', 'Arial, sans-serif'),
            'color': style.get('colors', {}).get('text', '#2c3e50')
        },
        'bgcolor': 'rgba(255, 255, 255, 0.8)',
        'bordercolor': style.get('colors', {}).get('axis_line', '#bdc3c7'),
        'borderwidth': 1
    }

    # Hoverlabel
    layout_update['hoverlabel'] = {
        'bgcolor': 'white',
        'font_size': fonts.get('hover_size', 12),
        'font_family': fonts.get('family', 'Arial, sans-serif'),
        'bordercolor': style.get('colors', {}).get('axis_line', '#bdc3c7')
    }

    fig.update_layout(**layout_update)


def apply_axes_config(fig, config: Dict[str, Any], x_title: str = None, y_title: str = None):
    """
    Apply axes configuration to a Plotly figure.

    Args:
        fig: Plotly Figure object
        config: Configuration dictionary from load_chart_config()
        x_title: Optional x-axis title
        y_title: Optional y-axis title
    """
    axes = config.get('axes', DEFAULT_AXES_CONFIG)
    style = config.get('style', DEFAULT_STYLE_CONFIG)
    fonts = style.get('fonts', DEFAULT_STYLE_CONFIG['fonts'])

    x_config = axes.get('x_axis', DEFAULT_AXES_CONFIG['x_axis'])
    y_config = axes.get('y_axis', DEFAULT_AXES_CONFIG['y_axis'])

    # X-axis
    x_update = {
        'showgrid': x_config.get('showgrid', True),
        'gridcolor': style.get('colors', {}).get('grid', '#e5e5e5'),
        'gridwidth': x_config.get('gridwidth', 1),
        'zeroline': x_config.get('zeroline', False),
        'showline': x_config.get('showline', True),
        'linewidth': x_config.get('linewidth', 2),
        'linecolor': style.get('colors', {}).get('axis_line', '#bdc3c7'),
        'tickfont': {
            'size': fonts.get('axis_tick_size', 11),
            'color': style.get('colors', {}).get('text_secondary', '#7f8c8d')
        },
        'tickangle': x_config.get('tickangle', 0)
    }

    if x_title:
        x_update['title'] = {
            'text': x_title,
            'font': {
                'size': fonts.get('axis_title_size', 14),
                'family': fonts.get('family', 'Arial, sans-serif'),
                'color': style.get('colors', {}).get('text', '#2c3e50')
            }
        }

    # Y-axis
    y_update = {
        'showgrid': y_config.get('showgrid', True),
        'gridcolor': style.get('colors', {}).get('grid', '#e5e5e5'),
        'gridwidth': y_config.get('gridwidth', 1),
        'zeroline': y_config.get('zeroline', False),
        'showline': y_config.get('showline', True),
        'linewidth': y_config.get('linewidth', 2),
        'linecolor': style.get('colors', {}).get('axis_line', '#bdc3c7'),
        'tickfont': {
            'size': fonts.get('axis_tick_size', 11),
            'color': style.get('colors', {}).get('text_secondary', '#7f8c8d')
        },
        'tickformat': y_config.get('tickformat', ',.0f')
    }

    if y_title:
        y_update['title'] = {
            'text': y_title,
            'font': {
                'size': fonts.get('axis_title_size', 14),
                'family': fonts.get('family', 'Arial, sans-serif'),
                'color': style.get('colors', {}).get('text', '#2c3e50')
            }
        }

    fig.update_xaxes(**x_update)
    fig.update_yaxes(**y_update)


def get_series_color(config: Dict[str, Any], series_name: str, index: int = 0) -> str:
    """
    Get color for a series from configuration.

    Args:
        config: Configuration dictionary
        series_name: Name of the series (e.g., 'SP500', 'Rise CTA')
        index: Fallback index for default color cycle

    Returns:
        Color string (hex code)
    """
    colors = config.get('style', {}).get('colors', DEFAULT_STYLE_CONFIG['colors'])

    # Check if series has a named color
    if series_name in colors:
        return colors[series_name]

    # Use primary color for index 0
    if index == 0:
        return colors.get('primary', '#1f77b4')

    # Fallback to a default color cycle
    default_cycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    return default_cycle[index % len(default_cycle)]


def get_line_width(config: Dict[str, Any], series_type: str = 'default') -> float:
    """
    Get line width from configuration.

    Args:
        config: Configuration dictionary
        series_type: Type of series ('default', 'grid', 'axis')

    Returns:
        Line width
    """
    lines = config.get('style', {}).get('lines', DEFAULT_STYLE_CONFIG['lines'])

    type_map = {
        'default': 'width',
        'grid': 'grid_width',
        'axis': 'axis_width'
    }

    key = type_map.get(series_type, 'width')
    return lines.get(key, 3)
