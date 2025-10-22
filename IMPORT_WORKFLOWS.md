# Data Import Workflows

**Purpose**: Standard procedures for importing PnL data from various sources into the database.

---

## General Import Pattern

### 1. Manager Setup
```python
manager = db.fetch_one("SELECT id FROM managers WHERE manager_name = ?", (name,))
if not manager:
    cursor = db.execute("INSERT INTO managers (manager_name) VALUES (?)", (name,))
    manager_id = cursor.lastrowid
```

### 2. Program Creation
```python
cursor = db.execute(
    "INSERT INTO programs (program_name, fund_size, starting_nav, manager_id) VALUES (?, ?, ?, ?)",
    (prog_name, fund_size, starting_nav, manager_id)
)
program_id = cursor.lastrowid
```

### 3. Market Creation
```python
cursor = db.execute(
    "INSERT INTO markets (name, asset_class, region, currency, is_benchmark) VALUES (?, ?, ?, ?, ?)",
    (market_name, asset_class, region, currency, is_benchmark)
)
market_id = cursor.lastrowid
```

### 4. PnL Bulk Insert
```python
pnl_records = [(date, market_id, program_id, return_decimal, 'daily'), ...]
db.execute_many(
    "INSERT INTO pnl_records (date, market_id, program_id, return, resolution) VALUES (?, ?, ?, ?, ?)",
    pnl_records
)
```

---

## Return Storage Format

**IMPORTANT**: Returns stored as decimals where `0.01 = 1%`

### Conversion from Absolute PnL
```python
return_decimal = pnl_dollars / fund_size
# Example: $21,496 PnL / $10,000,000 fund = 0.00214960 (0.21496%)
```

### Conversion from Equity Curve
```python
monthly_return = (ending_nav - starting_nav) / starting_nav
```

---

## Date Handling

- **Storage**: ISO format `YYYY-MM-DD` (e.g., "2006-01-03")
- **CSV Parsing**: Handle various formats (DD/MM/YYYY, D/M/YYYY, etc.)

```python
from datetime import datetime
date_obj = datetime.strptime('3/01/2006', '%d/%m/%Y').date()
db_date = date_obj.strftime('%Y-%m-%d')  # "2006-01-03"
```

---

## Import Scripts

### `import_cta_results_v2.py`
**Purpose**: Import Rise Capital CTA simulation results from HTML files

**Source**: HTML files with equity curves and benchmark data

**Features**:
- Parses fund size from folder names (e.g., "100M_30" → $100M)
- Extracts complete historical data
- Calculates monthly returns from equity curves
- Imports multiple benchmarks (SP500, BTOP50, AREIT, Winton)
- Batch processes multiple fund size variations

### `import_alphabet_mft_markets.py`
**Purpose**: Import Alphabet MFT market-level daily PnL and benchmark data

**Sources**:
- Market data: `MFT_20251021_MARKET_BREAKDOWN.csv`
- Benchmark data: `MFT_20251021_BENCHMARKS.csv`

**Configuration**:
- Fund Size: $10,000,000
- Starting NAV: 1000
- Resolution: daily
- Submission Date: 2025-10-21

**Process**:
1. Creates 17 trading markets (WTI, Copper, DAX, etc.)
2. Creates/updates 2 benchmark markets (AREIT, SP500)
3. Parses market CSV (DD/MM/YYYY dates, comma-separated USD PnL)
4. Converts absolute USD PnL to percentage returns
5. Parses benchmark CSV (returns already in decimal format)
6. Bulk inserts 97,589 pnl_records with submission_date tracking

**CSV Format**:
```csv
Date,WTI,ULSD Diesel,Brent,Ali,Copper,...
03/01/2006,0,0,0,0,0,...
04/01/2006,13344.31,2592.30,...
```

### `verify_alphabet_mft_markets.py`
**Purpose**: Verify Alphabet market-level import integrity

**Checks**:
- All 19 markets created (17 trading + 2 benchmarks)
- Record counts: 97,589 total
- Date range: 2006-01-03 to 2025-10-17
- Sample data cross-check against CSV
- Return statistics by market
- Submission date tracking

---

## Testing Imports

1. **Always create a verification script** alongside import script
2. **Cross-check sample data** (first/last rows)
3. **Verify record counts**
4. **Check date ranges**
5. **Validate return statistics** (min, max, avg, std dev)

### Example Verification
```python
# Check record count
result = db.fetch_one("""
    SELECT COUNT(*) as count FROM pnl_records
    WHERE program_id = ? AND resolution = 'daily'
""", (program_id,))
print(f"Total records: {result['count']:,}")

# Check date range
result = db.fetch_one("""
    SELECT MIN(date) as min_date, MAX(date) as max_date
    FROM pnl_records WHERE program_id = ? AND resolution = 'daily'
""", (program_id,))
print(f"Date range: {result['min_date']} to {result['max_date']}")

# Sample first day
results = db.fetch_all("""
    SELECT m.name, pr.return
    FROM pnl_records pr
    JOIN markets m ON pr.market_id = m.id
    WHERE pr.program_id = ? AND pr.date = ?
    ORDER BY m.name
""", (program_id, '2006-01-03'))
```

---

## Common Queries

### Get all programs for a manager
```sql
SELECT p.* FROM programs p
JOIN managers m ON p.manager_id = m.id
WHERE m.manager_name = 'Alphabet'
```

### Get PnL data for a program
```sql
SELECT date, m.name as market, return
FROM pnl_records pr
JOIN markets m ON pr.market_id = m.id
WHERE pr.program_id = ?
ORDER BY date
```

---

**Last Updated**: 2025-10-22
