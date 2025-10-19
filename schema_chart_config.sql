-- Chart Configuration System
-- Extends the existing schema to support database-stored chart formatting

-- Chart Style Presets: Reusable chart styling configurations
CREATE TABLE IF NOT EXISTS chart_style_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preset_name TEXT NOT NULL UNIQUE,
    description TEXT,

    -- Layout Configuration
    layout_config TEXT,  -- JSON: {width, height, margins, paper_size, etc.}

    -- Styling Configuration
    style_config TEXT,   -- JSON: {colors, fonts, line_widths, grid_styles, etc.}

    -- Axes Configuration
    axes_config TEXT,    -- JSON: {x_axis, y_axis configs including titles, ticks, formats}

    -- Series Configuration
    series_config TEXT,  -- JSON: {default_series_settings, benchmark_visibility, etc.}

    -- Multi-panel Configuration (for stacked charts)
    panel_config TEXT,   -- JSON: {panel_count, heights, spacing, titles, etc.}

    created_date DATE DEFAULT CURRENT_DATE,
    is_default BOOLEAN DEFAULT 0  -- Only one preset can be default
);

-- Chart Type Configurations: Specific settings per chart type
-- Links chart types (equity_curve, rolling_performance, etc.) to style presets
CREATE TABLE IF NOT EXISTS chart_type_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_type TEXT NOT NULL UNIQUE,  -- 'equity_curve', 'rolling_performance', 'monthly_heatmap', etc.
    default_style_preset_id INTEGER,
    description TEXT,
    FOREIGN KEY (default_style_preset_id) REFERENCES chart_style_presets(id) ON DELETE SET NULL
);

-- Brochure Chart Overrides: Instance-specific chart customizations
-- Allows brochure instances to override specific chart settings
CREATE TABLE IF NOT EXISTS brochure_chart_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brochure_component_id INTEGER NOT NULL,
    override_config TEXT,  -- JSON: Partial config to merge with preset
    FOREIGN KEY (brochure_component_id) REFERENCES brochure_components(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chart_type ON chart_type_configs(chart_type);
CREATE INDEX IF NOT EXISTS idx_brochure_chart_overrides ON brochure_chart_overrides(brochure_component_id);
