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
- Supports multiple classification schemes (e.g., 'asset_class', 'geography')
- Unique constraint on `(grouping_name, sector_name)`

#### 5. `market_sector_mapping`
- Many-to-many relationship between markets and sectors
- Fields: `market_id`, `sector_id`
- Allows markets to belong to multiple sectors

#### 6. `pnl_records`
- Core performance data
- Fields: `id`, `date`, `market_id`, `program_id`, `return`, `resolution`
- `return`: Percentage return as decimal (0.01 = 1%)
- `resolution`: 'daily', 'monthly', 'weekly', etc.
- Unique constraint on `(date, market_id, program_id, resolution)`

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
- **Programs**: MFT
  - Fund Size: $10,000,000
  - Starting NAV: 1000
  - Starting Date: 2006-01-03
- **Markets** (temporary sector-level structure):
  - Energy
  - Base Metals
  - Bonds
  - FX
  - Equity Indices
- **Data Source**: CSV file `C:\Users\matth\alphabet_backtest\20251020_sectors_only.csv`
- **Import Script**: `import_alphabet_mft.py`
- **Verification Script**: `verify_alphabet_data.py`
- **Date Range**: 2006-01-03 to 2025-10-17 (5,161 trading days)
- **Total Records**: 25,805 (5 sectors × 5,161 days)

**NOTE**: Alphabet currently has sector-level data stored as "markets". When market-level breakdown becomes available:
1. Convert these to proper sectors
2. Create individual markets
3. Link markets to sectors via `market_sector_mapping`
4. Migrate PnL records to new market structure

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

1. **Standard Deviation** = Standard deviation of **DAILY** returns, annualized by √252
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

### `import_alphabet_mft.py`
- **Purpose**: Import Alphabet manager's MFT program sector-level data
- **Source**: CSV file with daily PnL by sector
- **Configuration**:
  - Fund Size: $10,000,000
  - Starting NAV: 1000
  - Resolution: daily
- **Process**:
  1. Creates/verifies Alphabet manager
  2. Creates MFT program
  3. Creates 5 sector markets (Energy, Base Metals, Bonds, FX, Equity Indices)
  4. Parses CSV (DD/MM/YYYY dates, comma-separated PnL values)
  5. Converts absolute USD PnL to percentage returns
  6. Bulk inserts pnl_records
  7. Updates program starting_date
- **CSV Format**:
  ```
  Date,Energy,Base Metals,Bonds,FX,Equity Indices,MFT
  3/01/2006,0,0,"-13,064","21,496","4,912",13344
  ```

### `verify_alphabet_data.py`
- **Purpose**: Verify Alphabet import integrity
- **Checks**:
  - Manager/program existence
  - Market creation
  - Record counts match CSV
  - Date range validation
  - Sample data cross-check (first 3 rows)
  - Return statistics

---

## Key File Locations

| File | Purpose |
|------|---------|
| `schema.sql` | Main database schema |
| `schema_chart_config.sql` | Chart configuration schema |
| `database.py` | Database connection layer |
| `import_cta_results_v2.py` | Rise Capital HTML import |
| `import_cta_results.py` | Rise Capital import (v1, legacy) |
| `import_alphabet_mft.py` | Alphabet CSV import |
| `verify_alphabet_data.py` | Alphabet data verification |
| `example_brochure_workflow.py` | Brochure generation examples |
| `pnlrg.db` | SQLite database file |

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

## Future Enhancements Planned

### For Alphabet Manager
1. **Market-Level Data**: When Alphabet provides individual market breakdown:
   - Create proper sector records in `sectors` table
   - Create individual markets
   - Link via `market_sector_mapping`
   - Migrate existing sector-level PnL records to market level

### General
2. **Sector Grouping System**: Fully utilize the flexible sector grouping
3. **Additional Resolutions**: Weekly, quarterly reporting
4. **Performance Analytics**: Sharpe ratios, drawdowns, correlations
5. **Brochure Automation**: Scheduled generation and distribution

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

## Current Status (as of 2025-10-20)

### Recently Completed

#### Windows Framework Refactor (October 2025)
- ✅ Refactored `windows.py` to use daily returns as primary data source
- ✅ Added `get_manager_daily_data()` and `get_benchmark_daily_data()` methods
- ✅ Updated `compute_statistics()` to calculate std dev from daily returns (industry standard)
- ✅ Added helper functions: `aggregate_daily_to_monthly()`, `annualize_daily_std()`
- ✅ Expanded `Statistics` dataclass with daily fields
- ✅ Tested with Alphabet MFT data (5,161 days, 238 months)
- ✅ Created `generate_alphabet_mft_monthly_performance_chart_v2.py` using new framework
- ✅ Backward compatibility maintained for Rise CTA monthly-only data

#### Chart Configuration System
- ✅ Added `monthly_rolling_performance` chart type to database
- ✅ Configured for line charts (no markers) with A4 layout
- ✅ Preset ID: 4 in `chart_style_presets` table

#### Alphabet Manager Setup
- ✅ Alphabet manager created
- ✅ MFT program set up with $10M fund size
- ✅ 5 sector markets created (Energy, Base Metals, Bonds, FX, Equity Indices)
- ✅ Imported 25,805 daily PnL records (2006-01-03 to 2025-10-17)
- ✅ Verified data integrity (100% match with CSV source)
- ✅ Created import and verification scripts
- ✅ Generated performance charts (5-year, 1-year, monthly windows)

### Data Quality Metrics (Alphabet MFT)
- Date Range: 2006-01-03 to 2025-10-17
- Trading Days: 5,161
- Total Records: 25,805
- Win Rate: 51.8% (13,371 positive days / 25,805 total)
- Avg Daily Return: +0.06%
- Best Day: +6.72%
- Worst Day: -3.62%

### Key Metrics (Monthly Rolling Performance)
- Total Months: 238
- Mean Monthly Return: 6.89%
- **Std Dev (annualized from daily)**: 16.19% (industry standard!)
- Median Std Dev: 15.40%
- Std Dev Range: 8.21% to 36.35%

### Chart Outputs Generated
1. **5-Year Windows**: `export/alphabet_mft_5yr_performance.pdf` (3 windows, bar charts)
2. **1-Year Windows**: `export/alphabet_mft_1yr_performance.pdf` (18 windows, bar charts)
3. **Monthly Windows v2**: `export/alphabet_mft_monthly_performance_v2.pdf` (238 windows, line charts, **with correct std dev!**)

### Next Steps
- Apply refactored framework to Rise CTA when daily data becomes available
- Await market-level breakdown from Alphabet for proper sector structure
- Add Alphabet to automated reporting workflows
- Consider refactoring other chart generation scripts to use new framework

---

## Questions & Decisions Log

### 2025-10-20: Alphabet Import Decisions
- **Q**: How to handle sector-level data without market breakdown?
- **A**: Create sectors as temporary "markets" with `asset_class='future'`, convert later
- **Q**: What fund size to use?
- **A**: $10,000,000 (provided by user)
- **Q**: Date format in CSV?
- **A**: DD/MM/YYYY (e.g., "3/01/2006" = January 3, 2006)
- **Q**: How to store returns?
- **A**: As decimals where 0.01 = 1% (consistent with existing data)
- **Q**: Starting NAV?
- **A**: 1000 (standard across all programs)

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

**Last Updated**: 2025-10-20
**Updated By**: Claude (via user request)
**Change Summary**: Major refactor of Windows framework to use daily returns as primary data source. Added comprehensive documentation for industry-standard statistics calculations. Created monthly rolling performance charts with correct std dev calculations.
