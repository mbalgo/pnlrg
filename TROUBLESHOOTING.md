# Troubleshooting Guide

Common issues and their solutions.

---

## Database Issues

### Issue: "AttributeError: 'Database' object has no attribute 'commit'"
**Cause**: Database class auto-commits in execute() methods

**Fix**: Remove manual `.commit()` calls

```python
# DON'T DO THIS:
db.execute("INSERT ...")
db.commit()  # ❌ Not needed!

# DO THIS:
db.execute("INSERT ...")  # ✓ Auto-commits
```

---

### Issue: Foreign key constraint violations
**Cause**: Attempting to delete parent records with dependent children

**Fix**: Delete in correct order (pnl_records → programs → managers)

```python
# Correct order:
db.execute("DELETE FROM pnl_records WHERE program_id = ?", (program_id,))
db.execute("DELETE FROM programs WHERE id = ?", (program_id,))
db.execute("DELETE FROM managers WHERE id = ?", (manager_id,))
```

---

## Data Import Issues

### Issue: Unicode encoding errors in console output
**Cause**: Windows console doesn't support all Unicode characters

**Fix**: Use ASCII-safe symbols

```python
# DON'T: print("✓ Success")
# DO: print("[OK] Success")
```

---

### Issue: Date parsing errors
**Cause**: Inconsistent date formats in source data

**Fix**: Explicitly specify format in `datetime.strptime()`

```python
# Handle DD/MM/YYYY format
date_obj = datetime.strptime('03/01/2006', '%d/%m/%Y').date()
```

---

## Performance Statistics Issues

### Issue: Standard deviation is 2× too high
**Cause**: Benchmarks included in portfolio aggregation

**Fix**: Exclude benchmarks with `WHERE m.is_benchmark = 0`

```python
# WRONG:
SELECT SUM(return) FROM pnl_records WHERE program_id = ?

# CORRECT:
SELECT SUM(pr.return)
FROM pnl_records pr
JOIN markets m ON pr.market_id = m.id
WHERE pr.program_id = ? AND m.is_benchmark = 0
```

---

### Issue: Std dev is 0 for single-month windows
**Cause**: Using monthly-only data (only 1 observation)

**Fix**: Use daily data for std dev calculation

```python
# Get daily data instead
daily_df = window.get_manager_daily_data(program_id)
daily_std = daily_df['return'].std(ddof=1)
annualized_std = daily_std * np.sqrt(252)
```

---

## Event Probability Analysis Issues

### Issue: Blue and red lines nearly identical
**Cause**: Mean was subtracted during normalization

**Fix**: Don't subtract mean - preserve drift

```python
# WRONG: X = (daily_pnl - mean_pnl) / std_dev_dollars
# CORRECT:
X = daily_pnl / std_dev_dollars
```

---

### Issue: Extremely fat tails (8-sigma events every 100 days)
**Cause 1**: Dividing by `total_gain_days` instead of `total_days`

**Fix**:
```python
# WRONG: p_gain = (gains > x).sum() / total_gain_days
# CORRECT:
p_gain = (gains > x).sum() / total_days
```

**Cause 2**: Benchmarks included in portfolio

**Fix**: See "Standard deviation is 2× too high" above

---

### Issue: Standard deviation doesn't match Excel source
**Cause**: Benchmarks included in aggregation

**Fix**: Verify with:
```python
# Check what's being aggregated
results = db.fetch_all("""
    SELECT m.name, m.is_benchmark, pr.return
    FROM pnl_records pr
    JOIN markets m ON pr.market_id = m.id
    WHERE pr.program_id = ? AND pr.date = '2006-01-03'
""", (program_id,))
```

---

## Component Generation Issues

### Issue: Component not generating
**Cause**: Not registered or commented out

**Fix**: Check `register_components.py` for `register_component()` call

---

### Issue: Charts showing wrong title/subtitle
**Cause**: Hard-coded strings in component function

**Fix**: Update title/subtitle generation logic in `register_components.py`

---

## Git/Version Control Issues

### Issue: "warning: LF will be replaced by CRLF"
**Cause**: Git line ending normalization on Windows

**Fix**: This is normal and harmless on Windows. Can be ignored.

---

## General Debugging Tips

### 1. Verify Database Content
```python
with Database() as db:
    # Check what's in the database
    results = db.fetch_all("SELECT * FROM programs")
    for r in results:
        print(dict(r))
```

### 2. Check Sample Data
```python
# Always verify first and last rows
results = db.fetch_all("SELECT * FROM pnl_records ORDER BY date LIMIT 5")
results_last = db.fetch_all("SELECT * FROM pnl_records ORDER BY date DESC LIMIT 5")
```

### 3. Compare with Source
```python
# Cross-check against Excel/CSV
import pandas as pd
df = pd.read_excel('source.xlsx')
excel_std = df['column'].std(ddof=1)
print(f"Excel: {excel_std}, DB: {db_std}")
```

### 4. Use Print Debugging
```python
print(f"Count: {len(data)}")
print(f"Sample: {data[:5]}")
print(f"Stats: mean={data.mean():.4f}, std={data.std():.4f}")
```

---

**Last Updated**: 2025-10-22
