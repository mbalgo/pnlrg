# Borrow Mode Implementation

## Overview

The `borrow_mode` feature extends the Windows framework to handle incomplete earliest windows by "borrowing" data from the next window. This ensures all windows have the desired duration for consistent visual comparison.

## Implementation Date

2025-10-22

## Problem Statement

When generating non-overlapping reverse windows (starting from the latest date and working backwards), the earliest window may be shorter than the target duration if there isn't enough historical data.

**Example (without borrow_mode):**
- Data: 2006-01-03 to 2025-10-17 (19.79 years)
- Target: 5-year windows
- Result:
  - Window 1: 2006-01-03 to 2010-10-13 (4.77 years) ❌ Incomplete
  - Window 2: 2010-10-15 to 2015-10-15 (5.00 years) ✓
  - Window 3: 2015-10-16 to 2020-10-16 (5.00 years) ✓
  - Window 4: 2020-10-17 to 2025-10-17 (5.00 years) ✓

## Solution

With `borrow_mode=True`, the earliest incomplete window extends its **end_date** to overlap with the next window, making it a full 5-year window.

**Example (with borrow_mode):**
- Window 1: 2006-01-03 to 2011-01-03 (5.00 years) ✓
  - Actual data: 2006-01-03 to 2010-10-13
  - Borrowed data: 2010-10-14 to 2011-01-03 (overlaps with Window 2)
- Window 2: 2010-10-15 to 2015-10-15 (5.00 years) ✓
- Window 3: 2015-10-16 to 2020-10-16 (5.00 years) ✓
- Window 4: 2020-10-17 to 2025-10-17 (5.00 years) ✓

## Changes to Code

### 1. WindowDefinition Class ([windows.py](windows.py))

Added two new optional fields:

```python
@dataclass
class WindowDefinition:
    # ... existing fields ...
    borrowed_data_start_date: Optional[date] = None
    borrowed_data_end_date: Optional[date] = None
```

These fields mark the portion of the window that contains borrowed (overlapped) data.

### 2. generate_window_definitions_non_overlapping_reverse() Function

Added `borrow_mode: bool = False` parameter.

**Logic:**
1. Generate complete windows working backwards from `latest_date`
2. Create an incomplete window starting from `earliest_date` if there's remaining data
3. If `borrow_mode=True` and there's an incomplete earliest window:
   - Calculate how much data needs to be borrowed to reach target duration
   - Extend the window's `end_date` to overlap with the next window
   - Set `borrowed_data_start_date` and `borrowed_data_end_date`

### 3. Chart Generation ([generate_alphabet_mft_cumulative_windows_additive.py](generate_alphabet_mft_cumulative_windows_additive.py))

Updated to visualize borrowed data with dotted lines:

**For windows with borrowed data:**
- **Actual data segment**: Solid line (MFT) or dashed line (benchmark)
- **Borrowed data segment**: Dotted line (both MFT and benchmark)

**Implementation:**
1. Check if window has `borrowed_start_date` and `borrowed_end_date`
2. If yes, split the NAV curve into two traces:
   - Trace 1: Actual data (normal line style)
   - Trace 2: Borrowed data (dotted line style)
3. Both traces use the same color and legend group

## Visual Distinction

The chart subtitle explains the line styles:
> "Solid: MFT. Dashed: SP500. Dotted: Borrowed data (overlap with next window)."

This makes it immediately clear to viewers which portion of Window 1 contains borrowed data.

## Use Cases

1. **Client Presentations**: Show consistent 5-year performance windows even when total data doesn't divide evenly
2. **Performance Analysis**: Compare apples-to-apples across all windows (all same duration)
3. **Visual Clarity**: Dotted lines clearly indicate borrowed data without cluttering the legend

## Testing

Test script: [test_borrow_mode.py](test_borrow_mode.py)

**Test Results:**

### Test 1: 14-year scenario
- `borrow_mode=False`: Window 1 = 3.99 years (incomplete)
- `borrow_mode=True`: Window 1 = 5.00 years (borrowed 1.01 years)

### Test 2: Actual Alphabet MFT (19.79 years)
- `borrow_mode=False`: Window 1 = 4.77 years (incomplete)
- `borrow_mode=True`: Window 1 = 5.00 years (borrowed 0.22 years = ~80 days)

## Backward Compatibility

- Default: `borrow_mode=False` (preserves original behavior)
- Existing scripts continue to work unchanged
- New scripts can opt-in to borrowing

## Future Enhancements

Potential extensions:
1. Support borrowing for other window generation functions (overlapping, snapped, etc.)
2. Allow borrowing from both directions (forward and backward)
3. Add validation to ensure borrowed data doesn't exceed X% of window duration

## Files Modified

1. [windows.py](windows.py) - Core framework
2. [generate_alphabet_mft_cumulative_windows_additive.py](generate_alphabet_mft_cumulative_windows_additive.py) - Chart generation
3. [test_borrow_mode.py](test_borrow_mode.py) - Test script

## Documentation Updated

- Updated [CLAUDE.md](CLAUDE.md) with borrow_mode examples and explanations
