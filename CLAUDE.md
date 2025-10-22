# Claude Code Context - PnL Report Generator (pnlrg)

**IMPORTANT**: This file MUST be kept up to date whenever you make changes to:
- Database schema or structure
- How data is accessed or queried
- Import/export processes
- Core program functionality
- New managers, programs, or data sources

---

## Project Overview

**pnlrg** is a Performance and Loss (PnL) reporting system for fund managers. It:
- Stores daily/monthly return data for multiple managers and their trading programs
- Tracks performance across markets, sectors, and benchmarks
- Generates professional PDF brochures with charts and tables
- Supports flexible sector groupings and market classifications

---

## Database Architecture

### Core Schema

**Location**: `schema.sql` and `schema_chart_config.sql`

**Database**: SQLite (`pnlrg.db`)

### Main Tables

#### 1. `managers`
- Stores fund manager organizations
- Fields: `id`, `manager_name`
- Unique constraint on `manager_name`

#### 2. `programs`
- Trading programs/strategies within managers
- Fields: `id`, `program_name`, `fund_size`, `starting_nav`, `starting_date`, `manager_id`
- Links to: `managers` (FK: manager_id)
- Unique constraint on `program_name`

#### 3. `markets`
- Tradable instruments and benchmarks
- Fields: `id`, `name`, `asset_class`, `region`, `currency`, `is_benchmark`
- Examples: "Rise", "SP500", "Energy", "Oil Futures"
- Unique constraint on `name`

#### 4. `sectors`
- Market groupings/classifications
- Fields: `id`, `grouping_name`, `sector_name`
- Supports multiple classification schemes per strategy
- **Current groupings**:
  - `'mft_sector'`: 5 sectors (Energy, Base Metal, Fixed Income, Foreign Exchange, Equity Index)
  - `'cta_sector'`: 9 sectors (adds Precious Metal, Crop, Soft, Meat - currently empty)
- Unique constraint on `(grouping_name, sector_name)`
- **Usage**: Query by grouping to avoid empty sectors (e.g., WHERE grouping_name='mft_sector')

#### 5. `market_sector_mapping`
- Many-to-many relationship between markets and sectors
- Fields: `market_id`, `sector_id`
- Allows markets to belong to multiple sectors

#### 6. `pnl_records`
- Core performance data
- Fields: `id`, `date`, `market_id`, `program_id`, `return`, `resolution`, `submission_date`
- `return`: Percentage return as decimal (0.01 = 1%)
- `resolution`: 'daily', 'monthly', 'weekly', etc.
- `submission_date`: When data was submitted/updated (enables tracking revisions)
- Unique constraint on `(date, market_id, program_id, resolution)`
- **Important**: Old constraint handles duplicates; new rows only created when return value changes

#### Brochure System Tables
- `brochure_templates` - Reusable templates
- `brochure_instances` - Manager-specific configurations
- `brochure_components` - Charts, tables, text blocks
- `generated_brochures` - PDF storage
- `component_presets` - Predefined component configs
- `chart_style_presets` - Chart styling
- `chart_type_configs` - Chart type settings
- `brochure_chart_overrides` - Instance-specific customizations

### Key Relationships

```
managers (1:M) programs (1:M) pnl_records (M:1) markets
                                               |
                                               |
                                          (M:M via mapping)
                                               |
                                            sectors
```

### Key Constraints

- `ON DELETE RESTRICT`: managers → programs, programs → pnl_records
- `ON DELETE CASCADE`: markets → market_sector_mapping
- Unique indexes on performance-critical queries

---

## Current Managers & Programs

### 1. Rise Capital Management
- **Programs**: CTA_50M_30, CTA_100M_30, CTA_500M_30, etc.
- **Markets**: Rise (main equity curve), SP500, BTOP50, AREIT, Winton
- **Data Source**: HTML files from CTA simulation results
- **Import Script**: `import_cta_results_v2.py`

### 2. Alphabet
- **Programs**: MFT (Managed Futures Trading)
  - Fund Size: $10,000,000
  - Starting NAV: 1000
  - Starting Date: 2006-01-03
- **Markets** (17 trading markets + 2 benchmarks):
  - **Energy**: WTI, ULSD Diesel, Brent
  - **Base Metal**: Ali (Aluminum), Copper, Zinc
  - **Fixed Income**: 10y bond, T-Bond, Gilts 10y, KTB 10s
  - **Foreign Exchange**: USDKRW
  - **Equity Index**: ASX 200, DAX, CAC 40, Kospi 200, TX index, WIG 20
  - **Benchmarks**: AREIT (to 2025-05-23), SP500 (to 2025-10-08)
- **Data Sources**:
  - Market data: `C:\Users\matth\OneDrive\Documents\MFT Portfolios\MFT_20251021_MARKET_BREAKDOWN.csv`
  - Benchmark data: `C:\Users\matth\OneDrive\Documents\MFT Portfolios\MFT_20251021_BENCHMARKS.csv`
- **Import Script**: `import_alphabet_mft_markets.py`
- **Verification Script**: `verify_alphabet_mft_markets.py`
- **Date Range**: 2006-01-03 to 2025-10-17 (5,161 trading days)
- **Total Records**: 97,589 (87,737 market + 9,852 benchmark)
- **Sector Grouping**: `mft_sector` (5 sectors, fully mapped)

---

## Database Access Layer

**File**: `database.py`

### `Database` Class

Key methods:
- `connect()` - Establish SQLite connection
- `close()` - Close connection
- `execute(query, params)` - Execute single query (auto-commits)
- `execute_many(query, params_list)` - Bulk execute (auto-commits)
- `fetch_all(query, params)` - Return all rows
- `fetch_one(query, params)` - Return single row

**Important**: The Database class auto-commits after each `execute()` and `execute_many()` call. No manual `.commit()` required.

**Connection Details**:
- `row_factory = sqlite3.Row` - Enables column access by name
- Context manager support (`with Database() as db:`)

---

## Windows Framework for Performance Analysis

**File**: `windows.py`

### Overview

The Windows framework provides a sophisticated system for analyzing trading returns across different time periods. It was refactored in October 2025 to use **daily returns as the primary data source**, aligning with industry standards.

### Key Industry Standards

**IMPORTANT**: The CTA/hedge fund industry has specific conventions for performance statistics:

1. **Standard Deviation** = Standard deviation of **DAILY** returns
2. **Mean Return** = Average of monthly compounded returns
3. **CAGR** = Compound Annual Growth Rate from actual calendar days
4. **Max Drawdown** = Maximum decline from peak NAV (using daily granularity when available)

### Core Classes

#### `WindowDefinition`
Lightweight specification of a time window and participants:
- `start_date`, `end_date`: Date range (inclusive)
- `program_ids`: List of program IDs to analyze
- `benchmark_ids`: List of benchmark market IDs
- `name`, `window_set`, `index`: Metadata

#### `Window`
Materialized window with actual return data:
- Fetches data from database on-demand
- Caches results for performance
- **NEW**: Fetches daily data first, aggregates to monthly as needed

Key methods:
- `get_manager_daily_data(program_id)` - Fetch daily returns (NEW, primary method)
- `get_benchmark_daily_data(market_id)` - Fetch daily benchmark returns (NEW)
- `get_manager_data(program_id)` - Fetch monthly returns (legacy fallback)
- `get_benchmark_data(market_id)` - Fetch monthly benchmark returns (legacy)

#### `Statistics`
Statistical measures for a return series:
- `count`: Number of monthly observations
- `mean`: Average monthly return
- `std_dev`: **Annualized std dev of DAILY returns** (industry standard!)
- `cagr`: Compound Annual Growth Rate
- `max_drawdown_compounded`: Maximum % decline from peak
- `daily_count`: Number of daily observations used
- `daily_std_dev_raw`: Raw daily std dev (before annualization)

### Calculation Methodology (Post-Refactor)

#### `compute_statistics()` Function Flow

```python
1. Fetch DAILY data first (preferred)
   - Aggregates across all markets: SUM(daily_return)

2. Calculate std dev from DAILY returns
   - raw_std = std(daily_returns)
   - annualized_std = raw_std × √252   # Industry standard

3. Aggregate daily to monthly
   - Group by calendar month
   - Compound: monthly_return = ∏(1 + daily_return) - 1

4. Calculate other statistics from MONTHLY returns
   - mean = average(monthly_returns)
   - CAGR = (1 + total_return)^(1/years) - 1
   - Max DD = from compounded monthly NAV curve

5. FALLBACK: If no daily data, use monthly only
   - For legacy data (e.g., Rise CTA with monthly-only)
   - Std dev calculated from monthly returns (NOT industry standard)
```

### Helper Functions

#### `aggregate_daily_to_monthly(daily_df)`
Compounds daily returns within each calendar month:
```python
monthly_return = (1 + r₁) × (1 + r₂) × ... × (1 + rₙ) - 1
```

#### `annualize_daily_std(daily_std, trading_days=252)`
Industry standard annualization:
```python
annualized_std = daily_std × √252
```

### Example Usage

```python
from windows import WindowDefinition, Window, compute_statistics
from datetime import date

# Create a 1-month window
win_def = WindowDefinition(
    start_date=date(2015, 1, 1),
    end_date=date(2015, 1, 31),
    program_ids=[11],  # Alphabet MFT
    benchmark_ids=[],
    name="Jan_2015"
)

# Materialize the window
window = Window(win_def, db)

# Compute statistics (uses daily data automatically!)
stats = compute_statistics(window, program_id=11, entity_type='manager')

print(f"Mean monthly return: {stats.mean*100:.2f}%")
print(f"Std dev (from {stats.daily_count} daily returns): {stats.std_dev*100:.2f}%")
print(f"CAGR: {stats.cagr*100:.2f}%")
```

### Typical Results Comparison

**Monthly Window (January 2015) - Alphabet MFT:**

| Metric | OLD (Monthly-only) | NEW (Daily-based) |
|--------|-------------------|-------------------|
| Daily observations | N/A | 22 |
| Monthly observations | 1 | 1 |
| Mean monthly return | 4.37% | 4.37% ✓ |
| Std dev | 0.00% ❌ | 22.11% ✓ |
| CAGR | 68.26% | 68.26% ✓ |

**5-Year Window (2015-2020) - Alphabet MFT:**

| Metric | Value |
|--------|-------|
| Daily observations | 1,303 |
| Monthly observations | 60 |
| Mean monthly return | 7.65% |
| Std dev (annualized from daily) | 16.52% |
| CAGR (5yr) | 139.23% |
| Max Drawdown | -4.22% |

### Window Generation Functions

#### `generate_window_definitions_non_overlapping_reverse()`
Generates non-overlapping windows working **backwards** from the latest date:
- Ensures the most recent period is fully captured
- Example: 5-year windows for 2006-2025 data → [2020-2025], [2015-2020], [2010-2015]

#### `generate_window_definitions_non_overlapping_snapped()`
Calendar-aligned windows:
- Snaps to clean year boundaries (e.g., 1970, 1975, 1980)
- Useful for industry-standard reporting periods

### Migration Notes

**Backward Compatibility:**
- Old scripts using `get_manager_data()` (monthly-only) still work
- New scripts should use `compute_statistics()` which auto-fetches daily data
- For managers with only monthly data (Rise CTA), framework falls back gracefully

**Best Practices:**
- Always import daily data when available (`resolution='daily'`)
- Use `compute_statistics()` instead of manual calculations
- Std dev should always be calculated from daily returns when possible

---

## Event Probability Analysis

**File**: `windows.py` (functions), `components/event_probability_chart.py` (visualization)

### Overview

Event Probability Analysis is a tail risk visualization technique that reveals the "heavy-tailed" nature of trading returns. It compares the actual probability of extreme events (large gains/losses) to what would be expected from a normal distribution.

### Purpose

- **Identify Fat Tails**: Shows that extreme events occur more frequently than normal distribution predicts
- **Risk Assessment**: Quantifies tail risk for investors and risk managers
- **Strategy Characterization**: Different strategies have different tail behaviors
- **Regulatory Compliance**: Demonstrates understanding of extreme risk scenarios

### Key Concepts

#### Normalized Returns (X)
Returns are normalized by dividing daily P&L by the standard deviation:
```
X = daily_pnl / std_dev_dollars
```

Where:
- `daily_pnl = daily_return × fund_size` (e.g., $10M × 0.015 = $150K)
- `std_dev_dollars = (target_std_dev / √252) × fund_size` (de-annualized daily std dev in dollars)
- `X` represents "how many standard deviations" the event was

#### Normalization Methods
1. **Target Std Dev** (preferred): Uses `target_daily_std_dev` from programs table
   - Manager's risk target (e.g., 1% daily vol)
   - Shows performance vs target
2. **Realized Std Dev** (fallback): Uses actual std dev from data
   - Used when no target is set
   - Shows historical distribution

#### Probability Calculations
For each threshold `x` (e.g., 0.5, 1.0, 1.5, 2.0...):
- **P[X > x] for gains**: Probability of a gain exceeding x standard deviations
- **P[X < -x] for losses**: Probability of a loss exceeding x standard deviations
- **P[X > x] for normal**: Theoretical probability from N(0,1) distribution

### Core Functions

#### `EventProbabilityData` Dataclass
Stores computed probabilities and metadata:
```python
@dataclass
class EventProbabilityData:
    x_values: List[float]              # Threshold values [0, 0.1, ..., 2.0]
    p_gains: List[float]               # Actual gain probabilities
    p_losses: List[float]              # Actual loss probabilities
    p_normal: List[float]              # Normal distribution probabilities
    total_gain_days: int               # Number of positive return days
    total_loss_days: int               # Number of negative return days
    total_days: int                    # Total days analyzed
    realized_std_dev: float            # Annualized realized std dev
    target_std_dev: Optional[float]    # Target std dev from database
    used_target_std_dev: bool          # Whether target was used
    fund_size: float                   # Fund size for P&L calculations
```

#### `generate_x_values(x_min, x_max, num_points)`
Generates evenly-spaced threshold values:
```python
x_vals_short = generate_x_values(0, 2, 20)   # 20 points from 0 to 2
x_vals_long = generate_x_values(0, 8, 80)    # 80 points from 0 to 8
```

#### `compute_event_probability_analysis(window, program_id, x_values, db)`
Main computation function:
```python
from windows import Window, WindowDefinition, compute_event_probability_analysis, generate_x_values
from database import Database

with Database() as db:
    # Create full-history window
    window_def = WindowDefinition(
        start_date=date(2006, 1, 3),
        end_date=date(2025, 10, 17),
        program_ids=[11],  # Alphabet MFT
        benchmark_ids=[]
    )
    window = Window(window_def, db)

    # Generate analysis
    x_vals = generate_x_values(0, 2, 20)
    epa_data = compute_event_probability_analysis(window, 11, x_vals, db)

    print(f"Total days: {epa_data.total_days:,}")
    print(f"Gain days: {epa_data.total_gain_days:,}")
    print(f"Loss days: {epa_data.total_loss_days:,}")
```

### Visualization

#### `render_event_probability_chart(epa_data, config, output_path)`
Creates a single chart (PNG format):
- **Y-axis**: Log scale (10^-5 to 1.0 typical range)
- **X-axis**: Normalized return (X = P&L / std dev)
- **Black line**: Normal distribution P[X > x]
- **Blue squares**: Actual gains P[X > x]
- **Red circles**: Actual losses P[X < -x]

#### `render_event_probability_chart_pair(epa_short, epa_long, config, path_short, path_long)`
Convenience function to create both standard views:
- **Short range (0-2)**: Standard view for typical events
- **Long range (0-8)**: Extended view revealing extreme tail events

### Example Usage

**Complete workflow** (see `generate_alphabet_mft_event_probability.py`):
```python
from database import Database
from windows import WindowDefinition, Window, generate_x_values, compute_event_probability_analysis
from components.event_probability_chart import render_event_probability_chart_pair

with Database() as db:
    # Get program and date range
    program = db.fetch_one("SELECT id FROM programs WHERE program_name = 'MFT'")
    date_range = db.fetch_one("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM pnl_records
        WHERE program_id = ? AND resolution = 'daily'
    """, (program['id'],))

    # Create window
    window_def = WindowDefinition(
        start_date=date.fromisoformat(date_range['min_date']),
        end_date=date.fromisoformat(date_range['max_date']),
        program_ids=[program['id']],
        benchmark_ids=[]
    )
    window = Window(window_def, db)

    # Compute probabilities
    x_short = generate_x_values(0, 2, 20)
    x_long = generate_x_values(0, 8, 80)
    epa_short = compute_event_probability_analysis(window, program['id'], x_short, db)
    epa_long = compute_event_probability_analysis(window, program['id'], x_long, db)

    # Render charts
    config = {'title': 'Event Probability Analysis - Alphabet MFT'}
    render_event_probability_chart_pair(
        epa_short, epa_long, config,
        'event_prob_0_2.png', 'event_prob_0_8.png'
    )
```

### Typical Results (Alphabet MFT Full History)

**Data Summary:**
- Total Days: 5,161
- Gain Days: 3,042 (58.9%)
- Loss Days: 2,119 (41.1%)
- Realized Std Dev: 33.28% (annualized)
- Target Std Dev: 1.0% (used for normalization)

**Tail Probabilities (0-2 range):**

| X (std dev) | P[Gain > X] Actual | P[Gain > X] Normal | Ratio |
|-------------|-------------------|-------------------|-------|
| 0.5 | 100.00% | 50.00% | 2.0x |
| 1.0 | 98.52% | 29.93% | 3.3x |
| 1.5 | 96.81% | 14.63% | 6.6x |
| 2.0 | 94.54% | 5.72% | 16.5x |

**Interpretation:**
- The strategy shows **heavy tails**: extreme events occur much more frequently than normal
- At 2.0 std dev, actual probability is 16.5× higher than normal distribution predicts
- This is typical for systematic trading strategies and reflects genuine tail risk

### Integration with Component System

**Registered Component**: `'event_probability'`
```python
from component_registry import get_registry

registry = get_registry()
component = registry.get('event_probability')

# Generate for a program
component.function(
    db=db,
    program_id=11,
    output_path='export/alphabet/mft/charts/alphabet_mft_event_probability.pdf'
)
# Creates: *_0_2.png and *_0_8.png
```

### Database Requirements

**Programs table** must have `target_daily_std_dev` field:
```sql
ALTER TABLE programs ADD COLUMN target_daily_std_dev REAL;
UPDATE programs SET target_daily_std_dev = 0.01 WHERE program_name = 'MFT';  -- 1%
```

**PnL records** must have daily resolution data:
```sql
SELECT COUNT(*) FROM pnl_records
WHERE program_id = 11 AND resolution = 'daily';  -- Must be > 0
```

### Use Cases

1. **Investor Due Diligence**: Show sophisticated understanding of tail risk
2. **Risk Management**: Quantify probability of drawdown scenarios
3. **Strategy Comparison**: Compare tail behavior across different strategies
4. **Regulatory Reporting**: Demonstrate awareness of extreme risk events
5. **Client Education**: Visualize why "normal" assumptions fail in trading

### Related Files

| File | Purpose |
|------|---------|
| `windows.py` | Core analysis functions |
| `components/event_probability_chart.py` | Visualization functions |
| `register_components.py` | Component registration |
| `generate_alphabet_mft_event_probability.py` | Example script |

---

## Data Import Workflows

### General Import Pattern

1. **Manager Setup**
   ```python
   manager = db.fetch_one("SELECT id FROM managers WHERE manager_name = ?", (name,))
   if not manager:
       cursor = db.execute("INSERT INTO managers (manager_name) VALUES (?)", (name,))
       manager_id = cursor.lastrowid
   ```

2. **Program Creation**
   ```python
   cursor = db.execute(
       "INSERT INTO programs (program_name, fund_size, starting_nav, manager_id) VALUES (?, ?, ?, ?)",
       (prog_name, fund_size, starting_nav, manager_id)
   )
   program_id = cursor.lastrowid
   ```

3. **Market Creation**
   ```python
   cursor = db.execute(
       "INSERT INTO markets (name, asset_class, region, currency, is_benchmark) VALUES (?, ?, ?, ?, ?)",
       (market_name, asset_class, region, currency, is_benchmark)
   )
   market_id = cursor.lastrowid
   ```

4. **PnL Import**
   ```python
   pnl_records = [(date, market_id, program_id, return_decimal, 'daily'), ...]
   db.execute_many(
       "INSERT INTO pnl_records (date, market_id, program_id, return, resolution) VALUES (?, ?, ?, ?, ?)",
       pnl_records
   )
   ```

### Return Conversion

**Storage Format**: Returns stored as decimals where `0.01 = 1%`

**Conversion from Absolute PnL**:
```python
return_decimal = pnl_dollars / fund_size
# Example: $21,496 PnL / $10,000,000 fund = 0.00214960 (0.21496%)
```

**Conversion from Equity Curve**:
```python
# Method used in Rise Capital imports
monthly_return = (ending_nav - starting_nav) / starting_nav
```

### Date Handling

- **Storage**: ISO format `YYYY-MM-DD` (e.g., "2006-01-03")
- **CSV Parsing**: Handle various formats (DD/MM/YYYY, D/M/YYYY, etc.)
- **Example**:
  ```python
  from datetime import datetime
  date_obj = datetime.strptime('3/01/2006', '%d/%m/%Y').date()
  db_date = date_obj.strftime('%Y-%m-%d')  # "2006-01-03"
  ```

---

## Import Scripts

### `import_cta_results_v2.py`
- **Purpose**: Import Rise Capital CTA simulation results from HTML files
- **Source**: HTML files with equity curves and benchmark data
- **Features**:
  - Parses fund size from folder names (e.g., "100M_30" → $100M)
  - Extracts complete historical data
  - Calculates monthly returns from equity curves
  - Imports multiple benchmarks (SP500, BTOP50, AREIT, Winton)
  - Batch processes multiple fund size variations

### `import_alphabet_mft_markets.py`
- **Purpose**: Import Alphabet MFT market-level daily PnL and benchmark data
- **Sources**:
  - Market data: `MFT_20251021_MARKET_BREAKDOWN.csv`
  - Benchmark data: `MFT_20251021_BENCHMARKS.csv`
- **Configuration**:
  - Fund Size: $10,000,000
  - Starting NAV: 1000
  - Resolution: daily
  - Submission Date: 2025-10-21
- **Process**:
  1. Creates 17 trading markets (WTI, Copper, DAX, etc.)
  2. Creates/updates 2 benchmark markets (AREIT, SP500)
  3. Parses market CSV (DD/MM/YYYY dates, comma-separated USD PnL)
  4. Converts absolute USD PnL to percentage returns
  5. Parses benchmark CSV (returns already in decimal format)
  6. Bulk inserts 97,589 pnl_records with submission_date tracking
- **CSV Format**:
  ```
  Date,WTI,ULSD Diesel,Brent,Ali,Copper,...
  03/01/2006,0,0,0,0,0,...
  ```

### `verify_alphabet_mft_markets.py`
- **Purpose**: Verify Alphabet market-level import integrity
- **Checks**:
  - All 19 markets created (17 trading + 2 benchmarks)
  - Record counts: 97,589 total
  - Date range: 2006-01-03 to 2025-10-17
  - Sample data cross-check against CSV
  - Return statistics by market
  - Submission date tracking

### `create_sector_structure.py`
- **Purpose**: Create sector definitions and market-sector mappings
- **Creates**:
  - `mft_sector` grouping: 5 sectors, 17 market mappings
  - `cta_sector` grouping: 9 sectors, 0 mappings (future-ready)
- **Verification**: Shows sector details and market assignments

### `query_by_sector.py`
- **Purpose**: Utility functions for sector-based queries
- **Functions**:
  - `list_markets_by_sector()` - List markets grouped by sector
  - `get_markets_in_sector()` - Get market IDs for a specific sector
  - `aggregate_pnl_by_sector()` - Sector-level performance aggregation
  - `sector_performance_summary()` - High-level sector statistics

---

## Key File Locations

| File | Purpose |
|------|---------|
| `schema.sql` | Main database schema |
| `schema_chart_config.sql` | Chart configuration schema |
| `database.py` | Database connection layer |
| `windows.py` | Performance analysis framework (daily/monthly, event probability) |
| `components/event_probability_chart.py` | Event probability visualization |
| `register_components.py` | Component registration (charts, tables, text) |
| `component_registry.py` | Component registry system |
| `import_cta_results_v2.py` | Rise Capital HTML import |
| `import_alphabet_mft_markets.py` | Alphabet market-level CSV import |
| `verify_alphabet_mft_markets.py` | Alphabet data verification |
| `create_sector_structure.py` | Sector definitions and mappings |
| `query_by_sector.py` | Sector-based query utilities |
| `generate_alphabet_mft_event_probability.py` | Event probability analysis example |
| `add_submission_date_column.py` | Schema migration for submission tracking |
| `cleanup_alphabet_old_data.py` | Data cleanup utility |
| `example_brochure_workflow.py` | Brochure generation examples |
| `pnlrg.db` | SQLite database file |
| `pnlrg_YYYYMMDD.db` | Database backups |

---

## Standards & Conventions

### Naming Conventions
- **Managers**: Full legal name (e.g., "Rise Capital Management", "Alphabet")
- **Programs**: Descriptive names (e.g., "CTA_100M_30", "MFT")
- **Markets**: Clear instrument names (e.g., "Energy", "SP500", "Oil Futures")
- **Sectors**: Descriptive within grouping context

### Data Standards
- **Starting NAV**: Always use `1000` as standard
- **Dates**: Always store in ISO format (`YYYY-MM-DD`)
- **Returns**: Always store as decimals (`0.01 = 1%`)
- **Resolution**: Use 'daily', 'monthly', 'weekly' (lowercase)
- **Currency**: Default to 'USD' unless specified
- **Region**: Use standard names ('US', 'Global', 'Europe', 'Asia')

### Asset Classes
Current values in use:
- `future` - Futures contracts
- `equity` - Stock indices
- `option` - Options
- `forex` - Foreign exchange
- `CTA Fund` - Managed futures funds
- `REIT` - Real estate investment trusts

---

## Sector Grouping System

### Overview
The database supports **multiple classification schemes** via the `grouping_name` field in the `sectors` table. This allows the same market to be classified in different ways simultaneously.

### Current Groupings

#### `mft_sector` (MFT Strategy-Specific)
- **Purpose**: Alphabet MFT strategy sectors for client pitches
- **Sectors** (5 total, all populated):
  1. **Energy** (3 markets): WTI, ULSD Diesel, Brent
  2. **Base Metal** (3 markets): Ali, Copper, Zinc
  3. **Fixed Income** (4 markets): 10y bond, T-Bond, Gilts 10y, KTB 10s
  4. **Foreign Exchange** (1 market): USDKRW
  5. **Equity Index** (6 markets): ASX 200, DAX, CAC 40, Kospi 200, TX index, WIG 20
- **Total**: 17 market mappings
- **Usage**: `WHERE grouping_name='mft_sector'` for clean, no-empty-sector queries

#### `cta_sector` (CTA Strategy Framework)
- **Purpose**: Comprehensive sector framework for future CTA data imports
- **Sectors** (9 total, currently empty):
  1. Energy (0 markets - ready for expansion)
  2. Base Metal (0 markets)
  3. **Precious Metal** (0 markets - Gold, Silver, Platinum)
  4. **Crop** (0 markets - Corn, Wheat, Soybeans)
  5. **Soft** (0 markets - Coffee, Sugar, Cotton, Cocoa)
  6. **Meat** (0 markets - Live Cattle, Lean Hogs, Feeder Cattle)
  7. Fixed Income (0 markets)
  8. Foreign Exchange (0 markets)
  9. Equity Index (0 markets)
- **Total**: 0 market mappings (future-ready)
- **Usage**: Will be populated when CTA strategy data is imported

### Naming Conventions
- **Sectors**: Singular form (e.g., "Energy", "Base Metal", "Crop")
  - Reads naturally: "WTI is an Energy", "Copper is a Base Metal"
- **Groupings**: Strategy-specific (e.g., "mft_sector", "cta_sector")
  - Future examples: "geography", "liquidity", "strategy_type"

### Querying by Sector

```python
from query_by_sector import get_markets_in_sector, aggregate_pnl_by_sector

# Get all Energy markets for MFT
energy_markets = get_markets_in_sector(db, 'Energy', grouping_name='mft_sector')

# Aggregate performance by sector
aggregate_pnl_by_sector(db, program_id=11, grouping_name='mft_sector')
```

### Future Groupings (Planned)
- `'geography'`: US, Europe, Asia, Global
- `'liquidity'`: High, Medium, Low
- `'strategy_type'`: Trend Following, Mean Reversion, Arbitrage
- `'exchange'`: CME, ICE, EUREX, etc.

---

## Future Enhancements Planned

### General
1. **Additional Sector Groupings**: Geography, liquidity, strategy-type classifications
2. **Additional Resolutions**: Weekly, quarterly reporting
3. **Performance Analytics**: Sharpe ratios, Sortino ratios, correlations, beta
4. **Brochure Automation**: Scheduled generation and distribution
5. **Data Revision Tracking**: Leverage submission_date for audit trails

---

## Development Notes

### Working with the Database

**Always verify before destructive operations**:
```python
# Check if program exists before deleting
program = db.fetch_one("SELECT id FROM programs WHERE program_name = ?", (name,))
if program:
    response = input("Delete existing? (yes/no): ")
```

**Use bulk inserts for large datasets**:
```python
# Don't do this:
for record in records:
    db.execute("INSERT ...", record)  # Slow!

# Do this instead:
db.execute_many("INSERT ...", records)  # Fast!
```

**Remember foreign key constraints**:
- Delete `pnl_records` before deleting `programs`
- Delete `programs` before deleting `managers`
- Use `ON DELETE CASCADE` where appropriate

### Testing Imports

1. Always create a verification script alongside import script
2. Cross-check sample data (first/last rows)
3. Verify record counts
4. Check date ranges
5. Validate return statistics (min, max, avg)

### Common Queries

**Get all programs for a manager**:
```sql
SELECT p.* FROM programs p
JOIN managers m ON p.manager_id = m.id
WHERE m.manager_name = 'Alphabet'
```

**Get PnL data for a program**:
```sql
SELECT date, m.name as market, return
FROM pnl_records pr
JOIN markets m ON pr.market_id = m.id
WHERE pr.program_id = ?
ORDER BY date
```

**Calculate cumulative returns**:
```sql
-- This requires window functions or application-level calculation
-- See existing chart generation code for examples
```

---

## Current Status (as of 2025-10-22)

### Recently Completed

#### Event Probability Analysis Implementation (October 22, 2025)
- ✅ Added `target_daily_std_dev` field to `programs` table
- ✅ Set target daily std dev to 1% for Alphabet MFT and Rise CTA programs
- ✅ Created `EventProbabilityData` dataclass in `windows.py`
- ✅ Implemented `compute_event_probability_analysis()` function
- ✅ Implemented `generate_x_values()` helper function
- ✅ Created `components/event_probability_chart.py` visualization module
- ✅ Registered `'event_probability'` component in component registry
- ✅ Generated example charts for Alphabet MFT (0-2 and 0-8 ranges)
- ✅ Verified heavy-tailed nature: 2σ events occur 16.5× more than normal
- ✅ Created `generate_alphabet_mft_event_probability.py` example script
- ✅ Updated CLAUDE.md with comprehensive documentation

#### Alphabet MFT Market-Level Data Import (October 21, 2025)
- ✅ Created database backup (`pnlrg_20251021.db`)
- ✅ Added `submission_date` column to `pnl_records` for data versioning
- ✅ Deleted old sector-level temporary data (25,805 records)
- ✅ Imported 17 trading markets (WTI, Copper, DAX, etc.)
- ✅ Imported 2 benchmark markets (AREIT to 2025-05-23, SP500 to 2025-10-08)
- ✅ Imported 97,589 daily PnL records (87,737 market + 9,852 benchmark)
- ✅ Created sector structure with two groupings:
  - `mft_sector`: 5 sectors, 17 market mappings
  - `cta_sector`: 9 sectors, 0 mappings (future-ready)
- ✅ Verified data integrity (100% match with CSV sources)
- ✅ Created sector query utilities

#### Windows Framework Refactor (October 2025)
- ✅ Refactored `windows.py` to use daily returns as primary data source
- ✅ Added `get_manager_daily_data()` and `get_benchmark_daily_data()` methods
- ✅ Updated `compute_statistics()` to calculate std dev from daily returns (industry standard)
- ✅ Added helper functions: `aggregate_daily_to_monthly()`, `annualize_daily_std()`
- ✅ Expanded `Statistics` dataclass with daily fields
- ✅ Backward compatibility maintained for Rise CTA monthly-only data

### Data Quality Metrics (Alphabet MFT - Market Level)
- **Date Range**: 2006-01-03 to 2025-10-17 (5,161 trading days)
- **Total Records**: 97,589 (87,737 market + 9,852 benchmark)
- **Markets**: 17 trading + 2 benchmarks
- **Avg Daily Return**: 0.0184% (across all markets/benchmarks)
- **Best Day**: +11.59%
- **Worst Day**: -14.83%
- **Win Rate**: 48.2% positive days

### Sector Performance Insights (MFT Strategy)
- **Best Performer**: Base Metal (0.0339% avg daily, 53.3% win rate)
- **Most Stable**: Energy (0.0263% avg daily, 49.1% win rate)
- **Most Diversified**: Equity Index (6 markets, 0.0051% avg daily)
- **Lowest Volatility**: Fixed Income (0.0207% avg daily, 49.6% win rate)

### Database Structure
- **Managers**: 2 (Rise Capital Management, Alphabet)
- **Programs**: Multiple (Rise CTA variants, Alphabet MFT)
- **Markets**: 27 total (trading + benchmarks)
- **Sectors**: 14 total (5 mft_sector + 9 cta_sector)
- **Market-Sector Mappings**: 17 (all for mft_sector)
- **PnL Records**: 100,000+ across all programs

### Next Steps
- Generate client pitch materials for Alphabet MFT using sector framework
- Create sector-level performance charts and analysis
- Apply Windows framework to sector aggregations
- Prepare brochure templates with sector breakdowns
- Import CTA strategy data when available (using cta_sector framework)

---

## Questions & Decisions Log

### 2025-10-21: Sector Structure Decisions
- **Q**: What should `grouping_name` be called - 'asset_class' or 'sector'?
- **A**: Strategy-specific groupings: 'mft_sector', 'cta_sector', etc. This allows multiple sector frameworks per strategy.
- **Q**: Singular or plural sector names?
- **A**: **Singular** (e.g., "Energy", "Base Metal", "Crop") - reads more naturally: "WTI is an Energy"
- **Q**: Should empty sectors be created?
- **A**: Create in `cta_sector` grouping (future-ready), omit from `mft_sector` (clean queries)
- **Q**: Should benchmarks be mapped to sectors?
- **A**: No - benchmarks remain unmapped as they're for comparison, not strategy composition

### 2025-10-21: Data Versioning Decisions
- **Q**: How to track data revisions from managers?
- **A**: Added `submission_date` column to `pnl_records`
- **Q**: Create new row for every submission?
- **A**: No - only create new row when actual return value changes (not just submission date)
- **Q**: How to query latest data?
- **A**: Use `MAX(submission_date)` or default to latest; old constraint handles duplicates programmatically

### 2025-10-21: Alphabet Market-Level Import Decisions
- **Q**: Market names from CSV headers?
- **A**: Use exact names (WTI, ULSD Diesel, Ali, etc.) with `asset_class='future'`, `region='US'`, `currency='USD'`
- **Q**: Delete old sector-level data?
- **A**: Yes - market-level data replaces temporary sector data
- **Q**: Handle benchmark data cutoff (AREIT ends 2025-05-23)?
- **A**: Only import records where data exists; skip empty/future dates

### 2025-10-20: Windows Framework Refactor Decisions
- **Q**: Should std dev be calculated from daily or monthly returns?
- **A**: **DAILY** returns (industry standard: std(daily) × √252)
- **Q**: For monthly windows, what should std dev show?
- **A**: Std dev of the ~20-22 daily returns within that month, annualized
- **Q**: Backward compatibility with Rise CTA monthly-only data?
- **A**: Yes - fallback to monthly std dev with warning/note
- **Q**: Should CAGR use trading days or calendar days?
- **A**: Calendar days for accurate annualization
- **Q**: Provide both raw and annualized std dev?
- **A**: Yes - added `daily_std_dev_raw` field to Statistics dataclass

---

## Troubleshooting

### Common Issues

**Issue**: "AttributeError: 'Database' object has no attribute 'commit'"
- **Cause**: Database class auto-commits in execute() methods
- **Fix**: Remove manual `.commit()` calls

**Issue**: Unicode encoding errors in console output
- **Cause**: Windows console doesn't support all Unicode characters
- **Fix**: Use ASCII-safe symbols like `[OK]`, `[ERROR]` instead of ✓, ✗

**Issue**: Date parsing errors
- **Cause**: Inconsistent date formats in source data
- **Fix**: Explicitly specify format in `datetime.strptime()`

**Issue**: Foreign key constraint violations
- **Cause**: Attempting to delete parent records with dependent children
- **Fix**: Delete in correct order (pnl_records → programs → managers)

---

**Last Updated**: 2025-10-22
**Updated By**: Claude (via user request)
**Change Summary**:
- Implemented Event Probability Analysis system for tail risk visualization
- Added `target_daily_std_dev` field to programs table (1% for MFT and CTA)
- Created `EventProbabilityData` dataclass and `compute_event_probability_analysis()` function
- Built visualization components for log-scale probability charts (0-2 and 0-8 ranges)
- Registered 'event_probability' component in component registry
- Generated and verified Alphabet MFT tail analysis (16.5× heavier tails than normal at 2σ)
- Created comprehensive documentation and example script
- Updated file references and current status sections
