# Event Probability Analysis

**Purpose**: Tail risk visualization showing how actual probability of extreme events compares to normal distribution assumptions.

**Files**: `windows.py` (computation), `components/event_probability_chart.py` (visualization)

---

## Overview

Event Probability Analysis reveals the "heavy-tailed" nature of trading returns by comparing actual probabilities of extreme gains/losses to theoretical normal distribution probabilities.

### Why This Matters

- **Identify Fat Tails**: Extreme events occur more frequently than normal distribution predicts
- **Risk Assessment**: Quantifies tail risk for investors and risk managers
- **Strategy Characterization**: Different strategies have different tail behaviors
- **Regulatory Compliance**: Demonstrates understanding of extreme risk scenarios

---

## Key Concepts

### Normalized Returns (X)

Returns are normalized WITHOUT subtracting the mean (critical for showing where profits come from):

```
X = daily_pnl / std_dev_dollars
```

Where:
- `daily_pnl = daily_return × fund_size`
- `std_dev_dollars = realized_daily_std_dev × fund_size`
- `X` represents "how many standard deviations" the event was

**IMPORTANT**: We do NOT subtract the mean. Subtracting mean would center the distribution and hide where the strategy makes its money.

### Normalization Method

The system ALWAYS uses **realized standard deviation** for normalization:
- Uses actual std dev from data
- Shows historical tail behavior
- Proper z-scores for tail events

Target std dev (if set in database) is shown in the info box for reference but not used for normalization.

### Probability Calculations

For each threshold `x` (e.g., 0.5, 1.0, 1.5, 2.0...):
- **P[X > x] for gains**: `(count of days where X > x) / total_days`
- **P[X < -x] for losses**: `(count of days where X < -x) / total_days`
- **P[X > x] for normal**: Theoretical probability from N(0,1) distribution using `scipy.stats.norm.sf(x)`

---

## Core Functions

### `EventProbabilityData` Dataclass

Stores computed probabilities and metadata:

```python
@dataclass
class EventProbabilityData:
    x_values: List[float]              # Threshold values [0, 0.1, ..., 8.0]
    p_gains: List[float]               # Actual gain probabilities
    p_losses: List[float]              # Actual loss probabilities
    p_normal: List[float]              # Normal distribution probabilities
    total_gain_days: int               # Number of positive return days
    total_loss_days: int               # Number of negative return days
    total_days: int                    # Total days analyzed
    realized_std_dev: float            # Annualized realized std dev
    target_std_dev: Optional[float]    # Target std dev from database (reference only)
    used_target_std_dev: bool          # Always False (we use realized)
    fund_size: float                   # Fund size for P&L calculations
```

### `generate_x_values(x_min, x_max, num_points)`

Generates evenly-spaced threshold values:

```python
x_vals_short = generate_x_values(0, 2, 20)   # 20 points from 0 to 2
x_vals_long = generate_x_values(0, 8, 80)    # 80 points from 0 to 8
```

### `compute_event_probability_analysis(window, program_id, x_values, db)`

Main computation function. See [windows.py:1207-1350](windows.py#L1207-L1350) for implementation.

**Algorithm**:
1. Fetch daily returns for program (excludes benchmarks)
2. Calculate realized std dev from daily returns
3. Convert returns to dollar P&L
4. Normalize P&L by realized std dev (NO mean subtraction!)
5. Split into gains (X > 0) and losses (X < 0)
6. For each threshold x, calculate probabilities
7. Compare to normal distribution

---

## Visualization

### Chart Configuration

**File**: `components/event_probability_chart.py`

#### Standard Output
- **Two PDF files**: `*_0_2.pdf` (0-2 std dev range), `*_0_8.pdf` (0-8 std dev range)
- **Y-axis**: Log scale, starts at 0.001 (0.1%) for 0-2 chart, 0.0000001 for 0-8 chart
- **X-axis**: "Amount lost or gained overnight divided by the Realized Standard Deviation of Daily Returns"
- **Black line**: Normal distribution P[X > x]
- **Blue line**: Actual gains P[X > x]
- **Red line**: Actual losses P[X < -x]

#### Info Box (bottom right)
Shows:
- Total Days
- Gain Days (count and %)
- Loss Days (count and %)
- Fund Size
- Target Std Dev (if set in database)

### Chart Functions

#### `render_event_probability_chart(epa_data, config, output_path)`
Creates a single PDF chart with specified configuration.

#### `render_event_probability_chart_pair(epa_short, epa_long, config, path_short, path_long)`
Convenience function to create both standard views (0-2 and 0-8 ranges).

---

## Example Usage

**Complete workflow** (see `generate_alphabet_mft_event_probability.py`):

```python
from database import Database
from windows import WindowDefinition, Window, generate_x_values, compute_event_probability_analysis
from components.event_probability_chart import render_event_probability_chart_pair

with Database() as db:
    # Get program and date range
    program = db.fetch_one("SELECT id, fund_size FROM programs WHERE program_name = 'MFT'")
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

    # Compute probabilities for both ranges
    x_short = generate_x_values(0, 2, 20)
    x_long = generate_x_values(0, 8, 80)
    epa_short = compute_event_probability_analysis(window, program['id'], x_short, db)
    epa_long = compute_event_probability_analysis(window, program['id'], x_long, db)

    # Render charts
    config = {'title': 'Event Probability Analysis'}
    render_event_probability_chart_pair(
        epa_short, epa_long, config,
        'output/event_prob_0_2.pdf', 'output/event_prob_0_8.pdf'
    )
```

---

## Typical Results (Alphabet MFT)

**Data Summary:**
- Total Days: 5,161
- Gain Days: 3,090 (59.9%)
- Loss Days: 2,071 (40.1%)
- Realized Daily Std Dev: 1.0671% (16.94% annualized)
- Target Std Dev: 1.00% daily

**Key Insights:**

| X (std dev) | P[Gain > X] | P[Loss < -X] | P[Normal] | Interpretation |
|-------------|-------------|--------------|-----------|----------------|
| 0.5 | 34.59% | 17.01% | 30.63% | Clear asymmetry: gains > losses |
| 1.0 | 18.10% | 6.10% | 15.56% | Gains slightly higher than normal |
| 2.0 | 5.12% | 0.66% | 2.14% | Gains 2.4× normal, losses 0.3× normal |
| 3.0 | 1.41% | 0.14% | 0.12% | Gains 11.9× normal, losses 1.1× normal |
| 4.0 | 0.62% | 0.04% | 0.004% | Gains 158× normal! Fat tails evident |

**Interpretation**:
- **Positive drift preserved**: Gains consistently higher probability than losses at all levels
- **Fat tails on gains**: 4-sigma gain events occur 158× more than normal distribution predicts
- **Strategy edge visible**: Clear separation between blue (gains) and red (losses) lines
- **High Sharpe ratio**: Visible in the consistent separation (Sharpe ~2.6 annualized)

---

## Integration with Component System

**Registered Component**: `'event_probability'` in `register_components.py`

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
# Creates: alphabet_mft_event_probability_0_2.pdf and alphabet_mft_event_probability_0_8.pdf
```

---

## Database Requirements

### Required Fields

**Programs table** needs `target_daily_std_dev` field (optional, for display only):
```sql
ALTER TABLE programs ADD COLUMN target_daily_std_dev REAL;
UPDATE programs SET target_daily_std_dev = 0.01 WHERE program_name = 'MFT';  -- 1% daily
```

**PnL records** must have daily resolution data:
```sql
SELECT COUNT(*) FROM pnl_records
WHERE program_id = 11 AND resolution = 'daily';  -- Must be > 0
```

---

## Common Issues and Solutions

### Issue: Blue and Red Lines Nearly Identical
**Cause**: Mean was subtracted during normalization (z-score approach)
**Solution**: We now normalize WITHOUT subtracting mean: `X = daily_pnl / std_dev_dollars`

### Issue: Extremely Fat Tails (8-sigma events every 100 days)
**Cause 1**: Dividing by `total_gain_days` instead of `total_days` in probability calculation
**Cause 2**: Including benchmark returns in portfolio aggregation
**Solution**: Always divide by `total_days`, and exclude benchmarks with `WHERE m.is_benchmark = 0`

### Issue: Standard Deviation Mismatch with Source Data
**Cause**: Benchmarks were included in SUM(return) aggregation
**Solution**: Join with markets table and filter `WHERE m.is_benchmark = 0`

---

## Use Cases

1. **Investor Due Diligence**: Show sophisticated understanding of tail risk
2. **Risk Management**: Quantify probability of drawdown scenarios
3. **Strategy Comparison**: Compare tail behavior across different strategies
4. **Regulatory Reporting**: Demonstrate awareness of extreme risk events
5. **Client Education**: Visualize why "normal" assumptions fail in trading
6. **Alpha Visualization**: Clear separation between gains and losses shows where strategy makes money

---

## Related Files

| File | Purpose | Lines |
|------|---------|-------|
| [windows.py](windows.py#L121-L153) | EventProbabilityData dataclass | 121-153 |
| [windows.py](windows.py#L1189-L1204) | generate_x_values() | 1189-1204 |
| [windows.py](windows.py#L1207-L1350) | compute_event_probability_analysis() | 1207-1350 |
| [components/event_probability_chart.py](components/event_probability_chart.py) | Visualization functions | Full file |
| [register_components.py](register_components.py#L290-L374) | Component registration | 290-374 |
| [generate_alphabet_mft_event_probability.py](generate_alphabet_mft_event_probability.py) | Example script | Full file |

---

**Last Updated**: 2025-10-22
**Version**: 1.1 (Post-refactor with realized std dev normalization)
