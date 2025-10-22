# Historical Decisions Log

This document tracks key architectural and implementation decisions made during development.

---

## 2025-10-22: Chart and Table Formatting

**Decision**: Multiple formatting improvements for professional output

**Changes**:
- Chart titles: "by 5-Year Window" → "in 5-Year Windows"
- Removed dual benchmark combinations (kept single benchmarks only)
- Disabled compounded variant generation (keeping code for future use)
- Table shows two rows for borrowed windows (actual + extended periods)
- Table headers include units; numbers without % suffix
- Std dev to 2dp, CAGR to whole numbers
- Event probability charts show target std dev in info box

**Rationale**: Cleaner, more professional output with better information density

---

## 2025-10-22: Benchmark Exclusion Fix

**Q**: Why was std dev 2× too high (2.0966% vs 1.0671%)?

**A**: Benchmarks (SP500, AREIT) were included in portfolio aggregation

**Decision**: ALWAYS exclude benchmarks from manager performance
- Added JOIN with markets table
- Filter: `WHERE m.is_benchmark = 0`
- Applied to `get_manager_daily_data()` in windows.py

**Impact**: Fixed std dev calculation, all performance statistics now accurate

---

## 2025-10-21: Sector Structure Decisions

**Q**: What should `grouping_name` be called - 'asset_class' or 'sector'?

**A**: Strategy-specific groupings: 'mft_sector', 'cta_sector', etc.

**Rationale**: Allows multiple sector frameworks per strategy

**Q**: Singular or plural sector names?

**A**: **Singular** (e.g., "Energy", "Base Metal", "Crop")

**Rationale**: Reads more naturally: "WTI is an Energy"

**Q**: Should empty sectors be created?

**A**: Create in `cta_sector` grouping (future-ready), omit from `mft_sector` (clean queries)

**Q**: Should benchmarks be mapped to sectors?

**A**: No - benchmarks are for comparison, not strategy composition

---

## 2025-10-21: Data Versioning Decisions

**Q**: How to track data revisions from managers?

**A**: Added `submission_date` column to `pnl_records`

**Q**: Create new row for every submission?

**A**: No - only create new row when actual return value changes

**Q**: How to query latest data?

**A**: Use `MAX(submission_date)` or default to latest

---

## 2025-10-21: Alphabet Market-Level Import Decisions

**Q**: Market names from CSV headers?

**A**: Use exact names (WTI, ULSD Diesel, Ali, etc.) with `asset_class='future'`

**Q**: Delete old sector-level data?

**A**: Yes - market-level data replaces temporary sector data

**Q**: Handle benchmark data cutoff (AREIT ends 2025-05-23)?

**A**: Only import records where data exists; skip empty/future dates

---

## 2025-10-20: Windows Framework Refactor Decisions

**Q**: Should std dev be calculated from daily or monthly returns?

**A**: **DAILY** returns (industry standard: std(daily) × √252)

**Rationale**: CTA/hedge fund industry uses daily std dev annualized

**Q**: For monthly windows, what should std dev show?

**A**: Std dev of the ~20-22 daily returns within that month, annualized

**Q**: Backward compatibility with Rise CTA monthly-only data?

**A**: Yes - fallback to monthly std dev with warning/note

**Q**: Should CAGR use trading days or calendar days?

**A**: Calendar days for accurate annualization

**Q**: Provide both raw and annualized std dev?

**A**: Yes - added `daily_std_dev_raw` field to Statistics dataclass

---

## Event Probability Analysis Decisions

### Mean Subtraction Decision (CRITICAL)

**Q**: Should we subtract mean when normalizing returns?

**A**: **NO** - Do NOT subtract mean

**Before** (wrong):
```python
X = (daily_pnl - mean_pnl) / std_dev_dollars  # Z-score
```

**After** (correct):
```python
X = daily_pnl / std_dev_dollars  # Preserves drift
```

**Rationale**:
- Subtracting mean centers the distribution
- Hides where strategy makes money
- Blue (gains) and red (losses) lines become identical
- Need to preserve positive drift to show strategy edge

### Normalization Method Decision

**Q**: Use target std dev or realized std dev for normalization?

**A**: **ALWAYS use realized std dev**

**Rationale**:
- Event probability shows ACTUAL tail behavior
- Must normalize by ACTUAL std dev for proper z-scores
- Target is shown in info box for reference only

### Probability Denominator Decision

**Q**: Divide by total_days or total_gain_days?

**A**: **total_days** (all days)

**Wrong**:
```python
p_gain = (gains > x).sum() / total_gain_days  # Makes probabilities ~100%!
```

**Correct**:
```python
p_gain = (gains > x).sum() / total_days  # Proper probability
```

---

## Future Considerations

### Planned Enhancements
1. Additional sector groupings: geography, liquidity, strategy-type
2. Additional resolutions: weekly, quarterly reporting
3. Performance analytics: Sharpe ratios, Sortino ratios, correlations, beta
4. Brochure automation: scheduled generation and distribution
5. Data revision tracking: leverage submission_date for audit trails

---

**Last Updated**: 2025-10-22
