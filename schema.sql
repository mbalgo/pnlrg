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

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_pnl_date ON pnl_records(date);
CREATE INDEX IF NOT EXISTS idx_pnl_program ON pnl_records(program_id);
CREATE INDEX IF NOT EXISTS idx_pnl_market ON pnl_records(market_id);
CREATE INDEX IF NOT EXISTS idx_pnl_resolution ON pnl_records(resolution);
CREATE INDEX IF NOT EXISTS idx_pnl_date_program ON pnl_records(date, program_id);
CREATE INDEX IF NOT EXISTS idx_pnl_program_resolution ON pnl_records(program_id, resolution);
CREATE INDEX IF NOT EXISTS idx_programs_manager ON programs(manager_id);
CREATE INDEX IF NOT EXISTS idx_sectors_grouping ON sectors(grouping_name);
