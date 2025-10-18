# Window-Based Time Series Analysis System

## Overview

The window system provides a sophisticated framework for analyzing trading returns across different time periods and market conditions. It separates window **definitions** (what/when to analyze) from window **instances** (materialized data), enabling lazy evaluation of potentially thousands of analysis windows.

## Core Concepts

### WindowDefinition
Lightweight specification of a time window and participants:
- `start_date`, `end_date`: Time period boundaries
- `program_ids`: List of programs to include
- `benchmark_ids`: List of benchmarks to include
- `name`, `window_set`, `index`: Optional metadata

**Key feature**: JSON-serializable for storage/transmission

### Window
Materialized window containing actual return data:
- Fetches data from database on-demand (lazy loading)
- Caches data for the session
- Validates data completeness

### Statistics
Computed performance metrics:
- **Compounded statistics**: Start with $1000, compound all returns
  - `cumulative_return_compounded`: Total compounded return
  - `max_drawdown_compounded`: Maximum % decline from peak
- **Simple (non-compounded) statistics**: Invest $1000 each period
  - `cumulative_return_simple`: Sum of all returns
  - `max_drawdown_simple`: Maximum decline in cumulative P&L
- **Standard statistics**: count, mean, median, std_dev

## Window Generation Types

### 1. Non-Overlapping Snapped
```python
windows = generate_window_definitions_non_overlapping_snapped(
    start_date=date(1973, 1, 1),
    end_date=date(2017, 12, 31),
    window_length_years=5,
    program_ids=[1, 2],
    benchmark_ids=[5, 6]
)
# Returns: [1970-1975], [1975-1980], [1980-1985], ...
```

**Purpose**: Calendar-aligned analysis (e.g., "the 2010s")
- Windows aligned to clean year boundaries
- Statistically independent (no data sharing)
- Human-interpretable periods

### 2. Non-Overlapping Not Snapped
```python
windows = generate_window_definitions_non_overlapping_not_snapped(
    start_date=date(1973, 6, 1),
    end_date=date(2017, 5, 31),
    window_length_months=60,
    program_ids=[1],
    benchmark_ids=[5]
)
# Returns: [1973-06 to 1978-05], [1978-06 to 1983-05], ...
```

**Purpose**: Maximize data utilization
- Start exactly at first data point
- No artificial calendar alignment
- Each window exactly N months

### 3. Overlapping (Rolling)
```python
windows = generate_window_definitions_overlapping(
    start_date=date(1973, 6, 1),
    end_date=date(2017, 5, 31),
    window_length_months=12,
    slide_months=1,
    program_ids=[1],
    benchmark_ids=[5]
)
# Returns: [1973-06 to 1974-05], [1973-07 to 1974-06], ...
```

**Purpose**: Smooth temporal analysis
- Detect trends and regime changes
- See how metrics evolve month-by-month
- Hundreds/thousands of windows for long time series

### 4. Overlapping Reverse (Trailing)
```python
windows = generate_window_definitions_overlapping_reverse(
    end_date=date(2017, 5, 31),  # Latest data date
    earliest_date=date(1973, 6, 1),
    window_length_months=12,
    slide_months=1,
    program_ids=[1],
    benchmark_ids=[5]
)
# Returns: [2016-06 to 2017-05], [2016-05 to 2017-04], ...
```

**Purpose**: "As of" analysis
- Answer "What are the trailing 12-month returns as of today?"
- All windows include latest data
- Different from forward rolling windows

### 5. Bespoke (Custom Events)
```python
windows = generate_window_definitions_bespoke(
    windows_spec=[
        {'name': '2008 Crisis', 'start_date': '2007-06-01', 'end_date': '2009-03-31'},
        {'name': 'COVID Crash', 'start_date': '2020-02-01', 'end_date': '2020-04-30'},
    ],
    program_ids=[1],
    benchmark_ids=[5]
)
```

**Purpose**: Event-driven analysis
- Study specific market regimes
- Compare performance during crises
- Custom reporting periods

## Usage Example

```python
from database import Database
from windows import (
    WindowDefinition,
    Window,
    compute_statistics,
    generate_window_definitions_non_overlapping_snapped
)
from datetime import date

# Connect to database
db = Database('pnlrg.db')
db.connect()

# Generate 5-year calendar windows
windows = generate_window_definitions_non_overlapping_snapped(
    start_date=date(1990, 1, 1),
    end_date=date(2010, 12, 31),
    window_length_years=5,
    program_ids=[1],  # Your CTA program
    benchmark_ids=[2],  # SP500
    window_set_name="5yr_calendar"
)

# Analyze each window
for win_def in windows:
    window = Window(win_def, db)

    # Skip windows with incomplete data
    if not window.data_is_complete:
        print(f"{win_def.name}: Incomplete data - skipping")
        continue

    # Compute statistics for program
    prog_stats = compute_statistics(window, program_id=1, entity_type='manager')

    # Compute statistics for benchmark
    bm_stats = compute_statistics(window, market_id=2, entity_type='benchmark')

    # Calculate outperformance
    outperf = prog_stats.cumulative_return_compounded - bm_stats.cumulative_return_compounded

    print(f"{win_def.name}:")
    print(f"  Program:    {prog_stats.cumulative_return_compounded:.2%}")
    print(f"  Benchmark:  {bm_stats.cumulative_return_compounded:.2%}")
    print(f"  Outperf:    {outperf:.2%}")

db.close()
```

## Data Completeness Validation

Windows validate that all requested programs and benchmarks have **complete data** for the window period:

- Data must start in or before the window start month
- Data must end in or after the window end month
- Validation uses year-month comparison (not day) for monthly data

**Strict behavior**: By default, most analytics skip windows with incomplete data. This ensures apples-to-apples comparisons.

## Design Decisions

✅ **On-the-fly generation**: Window definitions generated in memory when needed
✅ **Program-level granularity**: Reference specific program IDs
✅ **Strict completeness**: Skip windows with incomplete data by default
✅ **Lazy data loading**: Only fetch returns when window methods are called
✅ **Monthly resolution**: Focus on monthly data (daily support can be added later)

## Performance Considerations

- **Window definitions**: Lightweight (just dates + IDs), can generate thousands
- **Window instances**: Heavier (contains data), created on-demand
- **Caching**: Data cached within window instance for session lifetime
- **Database**: Uses indexed queries for fast data retrieval

Example: 45 years of monthly data with 12-month rolling windows = 527 window definitions, but only materializes windows when actually analyzed.

## Future Enhancements

- **Conditional windows**: Generate windows based on market indicators (VIX > 30, drawdown periods, etc.)
- **Daily resolution**: Support daily returns for high-frequency analysis
- **Statistics caching**: Optionally cache computed statistics in database
- **Additional statistics**: Sharpe ratio, Sortino ratio, Calmar ratio, etc.
- **Brochure integration**: Use windows to generate dynamic brochures

## Files

- `windows.py` - Core window system implementation
- `example_windows.py` - Comprehensive demo of all window types
- `test_complete_window.py` - Example of analyzing complete windows
- `debug_window.py` - Debugging tool for window data

## Testing

Run the comprehensive demo:
```bash
python example_windows.py
```

Test with complete data:
```bash
python test_complete_window.py
```

Expected output:
```
1990-1994: 1990-01-01 to 1994-12-31
  Data Complete: YES

  === COMPLETE WINDOW FOUND ===

  CTA_100000M_30:
    Observations:              60
    Cumulative (Compounded):     26.42%
    Max DD (Compounded):         -4.35%

  SP500:
    Observations:              60
    Cumulative (Compounded):     29.93%
    Max DD (Compounded):        -15.85%

  Outperformance:   -3.50%
```

## Summary

The window system is now fully implemented and tested with real data. It provides a powerful, flexible framework for analyzing trading returns across different time periods, with strict validation and comprehensive statistics computation.
