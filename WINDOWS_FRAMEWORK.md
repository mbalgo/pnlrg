# Windows Framework for Performance Analysis

**File**: `windows.py`

**Purpose**: Sophisticated system for analyzing trading returns across different time periods using daily returns as the primary data source (industry standard).

---

## Overview

The Windows framework provides flexible time-period analysis for trading strategies. It was refactored in October 2025 to use **daily returns as the primary data source**, aligning with CTA/hedge fund industry standards.

### Key Industry Standards

**IMPORTANT**: The CTA/hedge fund industry has specific conventions:

1. **Standard Deviation** = Standard deviation of **DAILY** returns (annualized: daily_std × √252)
2. **Mean Return** = Average of monthly compounded returns
3. **CAGR** = Compound Annual Growth Rate from actual calendar days
4. **Max Drawdown** = Maximum decline from peak NAV (using daily granularity when available)

---

## Core Classes

### `WindowDefinition`

Lightweight specification of a time window:

```python
@dataclass
class WindowDefinition:
    start_date: date              # Window start (inclusive)
    end_date: date                # Window end (inclusive)
    program_ids: List[int]        # Programs to analyze
    benchmark_ids: List[int]      # Benchmarks for comparison
    name: Optional[str]           # Human-readable name
    window_set: Optional[str]     # Group identifier
    index: Optional[int]          # Position in set
    # Borrow mode fields:
    borrowed_data_start_date: Optional[date]  # Start of borrowed period
    borrowed_data_end_date: Optional[date]    # End of borrowed period
```

### `Window`

Materialized window with actual return data:

```python
class Window:
    def __init__(self, definition: WindowDefinition, db: Database):
        self.definition = definition
        self.db = db
        self._manager_data = {}      # Cache for monthly data
        self._benchmark_data = {}    # Cache for benchmark data
        self._daily_manager_data = {}   # Cache for daily data
        self._daily_benchmark_data = {}  # Cache for daily benchmark data
```

**Key Methods**:

#### `get_manager_daily_data(program_id)` → DataFrame
**PRIMARY METHOD** - Fetches daily returns for a program:
- Aggregates across all NON-BENCHMARK markets: `SUM(pr.return)`
- Joins with markets table: `WHERE m.is_benchmark = 0`
- Returns DataFrame with columns `['date', 'return']`
- **Used for std dev calculation** (industry standard)

#### `get_benchmark_daily_data(market_id)` → DataFrame
Fetches daily returns for a benchmark market:
- Single market query
- Returns DataFrame with columns `['date', 'return']`

#### `get_manager_data(program_id)` → DataFrame
**LEGACY FALLBACK** - Fetches monthly returns:
- Used only for Rise CTA (which has monthly-only data)
- Hard-coded filter: `WHERE m.name = 'Rise'`
- Returns DataFrame with columns `['date', 'return']`

### `Statistics`

Statistical measures for a return series:

```python
@dataclass
class Statistics:
    count: int                       # Number of monthly observations
    mean: float                      # Average monthly return
    median: float                    # Median monthly return
    std_dev: float                   # **Annualized std dev of DAILY returns**
    sharpe: float                    # Sharpe ratio (annualized)
    sortino: float                   # Sortino ratio
    cagr: float                      # Compound Annual Growth Rate
    max_drawdown_compounded: float   # Max % decline from peak
    cumulative_return_compounded: float  # Total return
    daily_count: int                 # Number of daily observations
    daily_std_dev_raw: float         # Raw daily std dev (before annualization)
```

---

## Calculation Methodology (Post-Refactor)

### `compute_statistics()` Function Flow

```python
def compute_statistics(window: Window, entity_id: int, entity_type: str) -> Statistics:
    """
    Compute performance statistics using daily data as primary source.

    Args:
        window: Window object
        entity_id: program_id (manager) or market_id (benchmark)
        entity_type: 'manager' or 'benchmark'

    Returns:
        Statistics object with all performance metrics
    """
```

**Algorithm**:

1. **Fetch DAILY data first (preferred)**
   ```python
   daily_df = window.get_manager_daily_data(program_id)
   # Aggregates: SUM(return) WHERE is_benchmark = 0
   ```

2. **Calculate std dev from DAILY returns**
   ```python
   raw_std = daily_df['return'].std(ddof=1)
   annualized_std = raw_std × √252   # Industry standard
   ```

3. **Aggregate daily to monthly**
   ```python
   monthly_df = aggregate_daily_to_monthly(daily_df)
   # Compounds: (1 + r₁) × (1 + r₂) × ... × (1 + rₙ) - 1
   ```

4. **Calculate other statistics from MONTHLY returns**
   ```python
   mean = monthly_df['return'].mean()
   CAGR = (1 + total_return)^(1/years) - 1
   Max DD = from compounded monthly NAV curve
   ```

5. **FALLBACK**: If no daily data, use monthly only
   - For legacy data (e.g., Rise CTA with monthly-only)
   - Std dev calculated from monthly returns (NOT industry standard)
   - Warning logged

---

## Helper Functions

### `aggregate_daily_to_monthly(daily_df)` → DataFrame

Compounds daily returns within each calendar month:

```python
monthly_return = (1 + r₁) × (1 + r₂) × ... × (1 + rₙ) - 1
```

**Example**:
```python
# Daily returns in January: [0.01, -0.005, 0.02]
# Monthly return = (1.01) × (0.995) × (1.02) - 1 = 0.02495 (2.495%)
```

### `annualize_daily_std(daily_std, trading_days=252)` → float

Industry standard annualization:

```python
annualized_std = daily_std × √252
```

**Why 252?** Average number of trading days per year.

---

## Window Generation Functions

### `generate_window_definitions_non_overlapping_reverse()`

Generates non-overlapping windows working **backwards** from the latest date:

```python
def generate_window_definitions_non_overlapping_reverse(
    earliest_date: date,
    latest_date: date,
    window_length_years: int,
    program_ids: List[int],
    benchmark_ids: List[int],
    window_set_name: Optional[str] = None,
    borrow_mode: bool = False
) -> List[WindowDefinition]:
```

**Key Features**:
- Works backwards to ensure most recent period is fully captured
- Example: 5-year windows for 2006-2025 data → [2020-2025], [2015-2020], [2010-2015], [2006-2011]
- **Borrow mode**: If earliest window is incomplete, extends it forward to overlap with next window

**Borrow Mode Example**:
```
Without borrow mode:
  Window 1: 2006-01-03 to 2010-10-13 (1,215 days - incomplete!)
  Window 2: 2010-10-14 to 2015-10-14 (1,827 days)

With borrow_mode=True:
  Window 1: 2006-01-03 to 2011-01-03 (1,826 days ✓)
    - borrowed_data_start_date: 2010-10-14
    - borrowed_data_end_date: 2011-01-03
  Window 2: 2010-10-14 to 2015-10-14 (1,827 days)
```

### `generate_window_definitions_non_overlapping_snapped()`

Calendar-aligned windows:

```python
def generate_window_definitions_non_overlapping_snapped(
    earliest_date: date,
    latest_date: date,
    window_length_years: int,
    program_ids: List[int],
    benchmark_ids: List[int],
    window_set_name: Optional[str] = None
) -> List[WindowDefinition]:
```

**Key Features**:
- Snaps to clean year boundaries (e.g., 1970, 1975, 1980)
- Useful for industry-standard reporting periods
- Example: 5-year windows → [1970-1975], [1975-1980], [1980-1985]

---

## Example Usage

### Basic Statistics Calculation

```python
from windows import WindowDefinition, Window, compute_statistics
from database import Database
from datetime import date

with Database() as db:
    # Create a window
    win_def = WindowDefinition(
        start_date=date(2015, 1, 1),
        end_date=date(2020, 12, 31),
        program_ids=[11],  # Alphabet MFT
        benchmark_ids=[],
        name="5yr_2015_2020"
    )

    # Materialize window
    window = Window(win_def, db)

    # Compute statistics (uses daily data automatically!)
    stats = compute_statistics(window, program_id=11, entity_type='manager')

    print(f"Daily observations: {stats.daily_count}")
    print(f"Monthly observations: {stats.count}")
    print(f"Mean monthly return: {stats.mean*100:.2f}%")
    print(f"Std dev (from daily): {stats.std_dev*100:.2f}%")
    print(f"CAGR: {stats.cagr*100:.2f}%")
    print(f"Max Drawdown: {stats.max_drawdown_compounded*100:.2f}%")
```

### Multi-Window Analysis

```python
from windows import generate_window_definitions_non_overlapping_reverse

with Database() as db:
    # Get data range
    date_range = db.fetch_one("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM pnl_records WHERE program_id = 11 AND resolution = 'daily'
    """)

    # Generate 5-year windows
    window_defs = generate_window_definitions_non_overlapping_reverse(
        earliest_date=date.fromisoformat(date_range['min_date']),
        latest_date=date.fromisoformat(date_range['max_date']),
        window_length_years=5,
        program_ids=[11],
        benchmark_ids=[],
        borrow_mode=True
    )

    # Analyze each window
    for win_def in window_defs:
        window = Window(win_def, db)
        stats = compute_statistics(window, 11, 'manager')

        print(f"{win_def.name}:")
        print(f"  CAGR: {stats.cagr*100:.1f}%")
        print(f"  Std Dev: {stats.std_dev*100:.1f}%")
        print(f"  Sharpe: {stats.sharpe:.2f}")
        print()
```

---

## Typical Results Comparison

### Monthly Window (January 2015) - Alphabet MFT

| Metric | OLD (Monthly-only) | NEW (Daily-based) |
|--------|-------------------|-------------------|
| Daily observations | N/A | 22 |
| Monthly observations | 1 | 1 |
| Mean monthly return | 4.37% | 4.37% ✓ |
| Std dev | 0.00% ❌ | 22.11% ✓ |
| CAGR | 68.26% | 68.26% ✓ |

**Insight**: Single-month std dev now reflects intra-month volatility!

### 5-Year Window (2015-2020) - Alphabet MFT

| Metric | Value |
|--------|-------|
| Daily observations | 1,303 |
| Monthly observations | 60 |
| Mean monthly return | 7.65% |
| Std dev (annualized from daily) | 16.52% |
| CAGR (5yr) | 139.23% |
| Max Drawdown | -4.22% |
| Sharpe Ratio | 2.57 |

---

## Migration Notes

### Backward Compatibility

- Old scripts using `get_manager_data()` (monthly-only) still work
- New scripts should use `compute_statistics()` which auto-fetches daily data
- For managers with only monthly data (Rise CTA), framework falls back gracefully

### Best Practices

1. **Always import daily data when available** (`resolution='daily'`)
2. **Use `compute_statistics()`** instead of manual calculations
3. **Std dev should always be calculated from daily returns** when possible
4. **Exclude benchmarks** from portfolio aggregation (`WHERE m.is_benchmark = 0`)

---

## Common Patterns

### Pattern 1: Full History Analysis

```python
# Get full date range
date_range = db.fetch_one("""
    SELECT MIN(date) as min_date, MAX(date) as max_date
    FROM pnl_records WHERE program_id = ? AND resolution = 'daily'
""", (program_id,))

# Create full-history window
window_def = WindowDefinition(
    start_date=date.fromisoformat(date_range['min_date']),
    end_date=date.fromisoformat(date_range['max_date']),
    program_ids=[program_id],
    benchmark_ids=[]
)
```

### Pattern 2: Rolling Windows

```python
# Generate overlapping 1-year windows, stepping monthly
windows = []
current_start = earliest_date
while current_start <= latest_date - relativedelta(years=1):
    win_end = current_start + relativedelta(years=1) - relativedelta(days=1)
    windows.append(WindowDefinition(
        start_date=current_start,
        end_date=win_end,
        program_ids=[program_id],
        benchmark_ids=[]
    ))
    current_start += relativedelta(months=1)
```

### Pattern 3: Benchmark Comparison

```python
# Create window with benchmarks
window_def = WindowDefinition(
    start_date=date(2015, 1, 1),
    end_date=date(2020, 12, 31),
    program_ids=[11],        # Alphabet MFT
    benchmark_ids=[2, 4],    # SP500, AREIT
    name="5yr_with_benchmarks"
)

window = Window(window_def, db)

# Get manager stats
manager_stats = compute_statistics(window, 11, 'manager')

# Get benchmark stats
sp500_stats = compute_statistics(window, 2, 'benchmark')
areit_stats = compute_statistics(window, 4, 'benchmark')

# Compare
print(f"Manager CAGR: {manager_stats.cagr*100:.1f}%")
print(f"SP500 CAGR: {sp500_stats.cagr*100:.1f}%")
print(f"AREIT CAGR: {areit_stats.cagr*100:.1f}%")
```

---

## Related Files

| File | Purpose |
|------|---------|
| [windows.py](windows.py) | Core framework implementation |
| [test_daily_windows.py](test_daily_windows.py) | Test suite for daily windows |
| [example_windows.py](example_windows.py) | Usage examples |
| [register_components.py](register_components.py) | Component generation using windows |

---

**Last Updated**: 2025-10-22
**Version**: 2.0 (Daily returns as primary data source)
