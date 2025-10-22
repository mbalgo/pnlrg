# Claude Code Context - PnL Report Generator (pnlrg)

**IMPORTANT**: This file MUST be kept up to date whenever you make changes to:
- Database schema or structure
- How data is accessed or queried
- Import/export processes
- Core program functionality

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
Fund manager organizations
- Fields: `id`, `manager_name`

#### 2. `programs`
Trading programs/strategies within managers
- Fields: `id`, `program_name`, `fund_size`, `starting_nav`, `starting_date`, `target_daily_std_dev`, `manager_id`
- `target_daily_std_dev`: Target daily volatility (e.g., 0.01 for 1%)

#### 3. `markets`
Tradable instruments and benchmarks
- Fields: `id`, `name`, `asset_class`, `region`, `currency`, `is_benchmark`
- `is_benchmark`: 1 for benchmarks (SP500, AREIT), 0 for trading markets

#### 4. `sectors`
Market groupings/classifications
- Fields: `id`, `grouping_name`, `sector_name`
- Supports multiple classification schemes (e.g., 'mft_sector', 'cta_sector')
- **Usage**: Query by grouping to avoid empty sectors

#### 5. `market_sector_mapping`
Many-to-many relationship between markets and sectors

####6. `pnl_records`
Core performance data
- Fields: `id`, `date`, `market_id`, `program_id`, `return`, `resolution`, `submission_date`
- `return`: Percentage return as decimal (0.01 = 1%)
- `resolution`: 'daily', 'monthly', 'weekly'
- `submission_date`: When data was submitted (enables tracking revisions)

---

## Current Managers & Programs

### 1. Rise Capital Management
- **Programs**: CTA_50M_30, CTA_100M_30, CTA_500M_30, etc.
- **Markets**: Rise (main equity curve), SP500, BTOP50, AREIT, Winton
- **Data Source**: HTML files from CTA simulation results
- **Resolution**: Monthly only

### 2. Alphabet
- **Programs**: MFT (Managed Futures Trading)
  - Fund Size: $10,000,000
  - Starting NAV: 1000
  - Starting Date: 2006-01-03
  - Target Daily Std Dev: 1.00%
- **Markets**: 17 trading markets + 2 benchmarks
  - Energy: WTI, ULSD Diesel, Brent
  - Base Metal: Ali, Copper, Zinc
  - Fixed Income: 10y bond, T-Bond, Gilts 10y, KTB 10s
  - Foreign Exchange: USDKRW
  - Equity Index: ASX 200, DAX, CAC 40, Kospi 200, TX index, WIG 20
  - Benchmarks: AREIT, SP500
- **Date Range**: 2006-01-03 to 2025-10-17 (5,161 trading days)
- **Total Records**: 97,589 daily records
- **Resolution**: Daily
- **Sector Grouping**: `mft_sector` (5 sectors)

---

## Database Access Layer

**File**: `database.py`

### `Database` Class

Context manager for SQLite operations with auto-commit:

```python
with Database() as db:
    results = db.fetch_all("SELECT * FROM programs WHERE manager_id = ?", (manager_id,))
    db.execute("INSERT INTO programs (...) VALUES (?,...)", (values,))
```

**Key methods**:
- `fetch_all(query, params)` - Return all rows
- `fetch_one(query, params)` - Return single row
- `execute(query, params)` - Execute single query (auto-commits)
- `execute_many(query, params_list)` - Bulk execute (auto-commits)

**Important**: Auto-commits after each `execute()`. No manual `.commit()` required.

---

## Windows Framework

**File**: `windows.py` | **Details**: [WINDOWS_FRAMEWORK.md](WINDOWS_FRAMEWORK.md)

System for analyzing trading returns across time periods using **daily returns as primary data source** (industry standard).

### Quick Reference

**Core Classes**:
- `WindowDefinition` - Specification of a time window
- `Window` - Materialized window with data
- `Statistics` - Performance metrics (mean, std dev, Sharpe, CAGR, max DD)
- `EventProbabilityData` - Tail risk analysis data

**Key Functions**:
- `compute_statistics(window, entity_id, entity_type)` - Calculate all performance metrics
- `generate_window_definitions_non_overlapping_reverse()` - Create 5-year windows working backwards
- `compute_event_probability_analysis()` - Tail risk visualization

**Industry Standards**:
- **Std Dev** = std dev of DAILY returns × √252 (annualized)
- **Mean** = average of monthly compounded returns
- **CAGR** = from calendar days
- **Max DD** = from daily NAV curve

---

## Event Probability Analysis

**Files**: `windows.py`, `components/event_probability_chart.py` | **Details**: [EVENT_PROBABILITY_ANALYSIS.md](EVENT_PROBABILITY_ANALYSIS.md)

Tail risk visualization showing actual vs theoretical probability of extreme events.

### Quick Reference

**Core Concept**: Normalize returns WITHOUT subtracting mean to preserve drift:
```python
X = daily_pnl / (realized_daily_std_dev * fund_size)
```

**Output**: Two PDF charts (0-2 and 0-8 std dev ranges) showing:
- Blue line: P[Gain > x]
- Red line: P[Loss < -x]
- Black line: Normal distribution (theoretical)

**Key Insight**: Separation between blue and red lines shows where strategy makes money.

---

## Data Import

**Details**: [IMPORT_WORKFLOWS.md](IMPORT_WORKFLOWS.md)

### Standard Pattern

1. Create/fetch manager
2. Create program
3. Create markets
4. Bulk insert PnL records

**Return Format**: Stored as decimals (0.01 = 1%)

**Date Format**: ISO `YYYY-MM-DD`

### Import Scripts

- `import_cta_results_v2.py` - Rise Capital HTML files
- `import_alphabet_mft_markets.py` - Alphabet market CSV files
- `verify_alphabet_mft_markets.py` - Verification utility

---

## Key File Locations

| File | Purpose |
|------|---------|
| `schema.sql` | Main database schema |
| `database.py` | Database connection layer |
| `windows.py` | Performance analysis framework |
| `components/event_probability_chart.py` | Tail risk visualization |
| `components/pdf_tables.py` | Table generation |
| `components/cumulative_windows_overlay.py` | Window overlay charts |
| `register_components.py` | Component registration |
| `generate_all_components.py` | Batch component generation |
| `pnlrg.db` | SQLite database |

---

## Standards & Conventions

### Naming
- **Managers**: Full legal name (e.g., "Rise Capital Management")
- **Programs**: Descriptive names (e.g., "CTA_100M_30", "MFT")
- **Markets**: Clear instrument names (e.g., "WTI", "SP500")
- **Sectors**: Singular form (e.g., "Energy", "Base Metal")

### Data Standards
- **Starting NAV**: Always `1000`
- **Dates**: ISO format `YYYY-MM-DD`
- **Returns**: Decimals `0.01 = 1%`
- **Resolution**: 'daily', 'monthly', 'weekly' (lowercase)

### Performance Calculations
- **Std Dev**: From DAILY returns, annualized (× √252)
- **CAGR**: From calendar days
- **Sharpe**: √252 × (daily_mean / daily_std)
- **Benchmarks**: EXCLUDED from portfolio aggregation

---

## Current Status (as of 2025-10-22)

### Recently Completed

**Chart and Table Improvements**:
- Changed titles: "by 5-Year Window" → "in 5-Year Windows"
- Tables show two rows for borrowed windows (actual + extended)
- Table headers include units; numbers without % suffix
- Event probability charts show target std dev in info box

**Critical Bug Fix**:
- Fixed benchmark exclusion in portfolio aggregation
- Std dev now correct: 1.0671% daily (was 2.0966%)
- All performance statistics now accurate

**Event Probability Analysis**:
- Implemented tail risk visualization system
- Normalizes by realized std dev WITHOUT subtracting mean
- Generates dual PDF charts (0-2 and 0-8 std dev ranges)
- Shows where strategy generates profits via curve separation

**Windows Framework Refactor**:
- Daily returns now primary data source (industry standard)
- Std dev calculated from daily returns, then annualized
- Backward compatible with monthly-only data

### Data Quality (Alphabet MFT)
- Date Range: 2006-01-03 to 2025-10-17
- Total Records: 97,589
- Markets: 17 trading + 2 benchmarks
- Daily Std Dev: 1.0671% (16.94% annualized)
- CAGR (full period): ~280%

---

## Troubleshooting

**Details**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

Common issues:
- Std dev 2× too high → Benchmarks in aggregation
- Blue/red lines identical → Mean subtraction issue
- Foreign key errors → Delete order: pnl_records → programs → managers
- No auto-commit → Database class auto-commits, remove manual `.commit()`

---

## Historical Decisions

**Details**: [DECISIONS.md](DECISIONS.md)

Key decisions:
- Use daily returns for std dev (industry standard)
- Don't subtract mean in event probability (preserves drift)
- Always use realized std dev for normalization
- Exclude benchmarks from portfolio aggregation
- Singular sector names ("Energy" not "Energies")

---

## Documentation Structure

- **CLAUDE.md** (this file): Core essentials and quick reference
- **[WINDOWS_FRAMEWORK.md](WINDOWS_FRAMEWORK.md)**: Detailed windows implementation
- **[EVENT_PROBABILITY_ANALYSIS.md](EVENT_PROBABILITY_ANALYSIS.md)**: Tail risk analysis methodology
- **[IMPORT_WORKFLOWS.md](IMPORT_WORKFLOWS.md)**: Data import procedures
- **[DECISIONS.md](DECISIONS.md)**: Historical decisions log
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**: Common issues and solutions

---

**Last Updated**: 2025-10-22
**Version**: 2.0 (Condensed with detailed documentation split into separate files)
