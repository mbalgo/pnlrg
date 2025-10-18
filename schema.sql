-- PnL Report Generator Database Schema
-- SQLite Database Schema for storing trading P&L data

-- Managers table: stores information about fund managers
CREATE TABLE IF NOT EXISTS managers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_name TEXT NOT NULL UNIQUE
);

-- Programs table: stores trading programs/strategies
CREATE TABLE IF NOT EXISTS programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_name TEXT NOT NULL UNIQUE,
    fund_size REAL,
    starting_nav REAL,      -- Starting NAV for the equity curve (e.g., 1000)
    starting_date DATE,     -- First date of the equity curve
    manager_id INTEGER NOT NULL,
    FOREIGN KEY (manager_id) REFERENCES managers(id) ON DELETE RESTRICT
);

-- Markets table: stores information about tradable markets
CREATE TABLE IF NOT EXISTS markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    asset_class TEXT,  -- equity, future, option, forex, etc.
    region TEXT,       -- US, Canada, EU, Asia, etc.
    currency TEXT,     -- USD, CAD, EUR, JPY, etc.
    is_benchmark BOOLEAN DEFAULT 0  -- TRUE for benchmarks, FALSE for traded markets
);

-- Sectors table: defines sector groupings
-- grouping_name allows multiple classification schemes (e.g., 'metals', 'commodities', 'geography')
CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grouping_name TEXT NOT NULL,
    sector_name TEXT NOT NULL,
    UNIQUE(grouping_name, sector_name)
);

-- Market-Sector mapping: allows many-to-many relationship
-- A market can belong to multiple sectors across different groupings
CREATE TABLE IF NOT EXISTS market_sector_mapping (
    market_id INTEGER NOT NULL,
    sector_id INTEGER NOT NULL,
    PRIMARY KEY (market_id, sector_id),
    FOREIGN KEY (market_id) REFERENCES markets(id) ON DELETE CASCADE,
    FOREIGN KEY (sector_id) REFERENCES sectors(id) ON DELETE CASCADE
);

-- PnL Records table: stores percentage returns at various resolutions
CREATE TABLE IF NOT EXISTS pnl_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    market_id INTEGER NOT NULL,
    program_id INTEGER NOT NULL,
    return REAL NOT NULL,  -- Percentage return as decimal (e.g., 0.003 for 0.3%)
    resolution TEXT NOT NULL DEFAULT 'daily',  -- 'daily', 'monthly', 'weekly', etc.
    FOREIGN KEY (market_id) REFERENCES markets(id) ON DELETE RESTRICT,
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE RESTRICT,
    UNIQUE(date, market_id, program_id, resolution)
);

-- Brochure Templates table: reusable templates for brochures
CREATE TABLE IF NOT EXISTS brochure_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_date DATE DEFAULT CURRENT_DATE
);

-- Brochure Instances table: manager-specific brochure configurations
CREATE TABLE IF NOT EXISTS brochure_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_name TEXT NOT NULL,
    manager_id INTEGER NOT NULL,
    template_id INTEGER,  -- NULL for custom brochures
    program_id INTEGER,   -- Which program to generate for
    created_date DATE DEFAULT CURRENT_DATE,
    last_generated TIMESTAMP,
    FOREIGN KEY (manager_id) REFERENCES managers(id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES brochure_templates(id) ON DELETE SET NULL,
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE
);

-- Brochure Components table: charts, tables, text blocks
CREATE TABLE IF NOT EXISTS brochure_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    parent_type TEXT NOT NULL CHECK(parent_type IN ('template', 'instance')),
    component_type TEXT NOT NULL CHECK(component_type IN ('chart', 'table', 'text')),
    component_name TEXT NOT NULL,  -- e.g., 'equity_curve', 'performance_summary'
    config_json TEXT,  -- JSON parameters (preset + overrides)
    display_order INTEGER NOT NULL DEFAULT 0
);

-- Generated Brochures table: stores PDF blobs
CREATE TABLE IF NOT EXISTS generated_brochures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brochure_instance_id INTEGER NOT NULL,
    generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pdf_data BLOB,
    file_size INTEGER,
    FOREIGN KEY (brochure_instance_id) REFERENCES brochure_instances(id) ON DELETE CASCADE
);

-- Component Presets table: predefined component configurations
CREATE TABLE IF NOT EXISTS component_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preset_name TEXT NOT NULL UNIQUE,
    component_type TEXT NOT NULL,
    default_config_json TEXT,
    description TEXT
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_pnl_date ON pnl_records(date);
CREATE INDEX IF NOT EXISTS idx_pnl_program ON pnl_records(program_id);
CREATE INDEX IF NOT EXISTS idx_pnl_market ON pnl_records(market_id);
CREATE INDEX IF NOT EXISTS idx_pnl_resolution ON pnl_records(resolution);
CREATE INDEX IF NOT EXISTS idx_pnl_date_program ON pnl_records(date, program_id);
CREATE INDEX IF NOT EXISTS idx_pnl_program_resolution ON pnl_records(program_id, resolution);
CREATE INDEX IF NOT EXISTS idx_programs_manager ON programs(manager_id);
CREATE INDEX IF NOT EXISTS idx_sectors_grouping ON sectors(grouping_name);
CREATE INDEX IF NOT EXISTS idx_brochure_instances_manager ON brochure_instances(manager_id);
CREATE INDEX IF NOT EXISTS idx_brochure_components_parent ON brochure_components(parent_id, parent_type);
CREATE INDEX IF NOT EXISTS idx_generated_brochures_instance ON generated_brochures(brochure_instance_id);
