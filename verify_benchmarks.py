"""Verify benchmark data is imported correctly."""

from database import Database
import pandas as pd

db = Database('pnlrg.db')
db.connect()

print("="*70)
print("BENCHMARK DATA VERIFICATION")
print("="*70)

# 1. Check benchmark markets
print("\n1. Benchmark Markets:")
print("-"*70)
benchmarks = db.fetch_all("""
    SELECT name, asset_class, is_benchmark
    FROM markets
    WHERE is_benchmark = 1
""")
if benchmarks:
    for bm in benchmarks:
        print(f"  {bm['name']:20} {bm['asset_class']:20} is_benchmark={bm['is_benchmark']}")
else:
    print("  No benchmark markets found")

# 2. Check Benchmarks program
print("\n\n2. Benchmarks Program:")
print("-"*70)
benchmarks_prog = db.fetch_one("""
    SELECT p.id, p.program_name, m.manager_name
    FROM programs p
    JOIN managers m ON p.manager_id = m.id
    WHERE p.program_name = 'Benchmarks'
""")
if benchmarks_prog:
    print(f"  Program: {benchmarks_prog['program_name']}")
    print(f"  Manager: {benchmarks_prog['manager_name']}")
else:
    print("  Benchmarks program not found!")

# 3. Check SP500 data
print("\n\n3. SP500 Benchmark Returns:")
print("-"*70)
sp500_count = db.fetch_one("""
    SELECT COUNT(*) as count
    FROM pnl_records pr
    JOIN markets m ON pr.market_id = m.id
    JOIN programs p ON pr.program_id = p.id
    WHERE m.name = 'SP500'
    AND p.program_name = 'Benchmarks'
""")
print(f"  Total SP500 records: {sp500_count['count']}")

# First 10 returns
sp500_sample = db.fetch_all("""
    SELECT pr.date, pr.return
    FROM pnl_records pr
    JOIN markets m ON pr.market_id = m.id
    JOIN programs p ON pr.program_id = p.id
    WHERE m.name = 'SP500'
    AND p.program_name = 'Benchmarks'
    ORDER BY pr.date
    LIMIT 10
""")
print("\n  First 10 SP500 returns:")
for row in sp500_sample:
    return_pct = row['return'] * 100
    print(f"    {row['date']:12}  Return: {return_pct:7.4f}%")

# 4. Calculate SP500 performance
print("\n\n4. SP500 Performance (1973-2017):")
print("-"*70)
all_sp500 = db.fetch_all("""
    SELECT pr.date, pr.return
    FROM pnl_records pr
    JOIN markets m ON pr.market_id = m.id
    JOIN programs p ON pr.program_id = p.id
    WHERE m.name = 'SP500'
    AND p.program_name = 'Benchmarks'
    ORDER BY pr.date
""")

df = pd.DataFrame(all_sp500, columns=['date', 'return'])
starting_nav = 1000.0
df['nav'] = starting_nav * (1 + df['return']).cumprod()

print(f"  Starting NAV:  ${starting_nav:,.2f} (1973-01-03)")
print(f"  Ending NAV:    ${df['nav'].iloc[-1]:,.2f} ({df['date'].iloc[-1]})")
print(f"  Total Return:  {(df['nav'].iloc[-1] / starting_nav - 1) * 100:.2f}%")
print(f"  CAGR:          {((df['nav'].iloc[-1] / starting_nav) ** (1/45) - 1) * 100:.2f}%")

# 5. Compare Rise vs SP500
print("\n\n5. Rise CTA vs SP500 Comparison:")
print("-"*70)
rise_final = db.fetch_one("""
    SELECT pr.return
    FROM pnl_records pr
    JOIN markets m ON pr.market_id = m.id
    JOIN programs p ON pr.program_id = p.id
    WHERE m.name = 'Rise'
    AND p.program_name = 'CTA_50M_30'
    ORDER BY pr.date DESC
    LIMIT 1
""")

# Calculate final NAV for Rise
all_rise = db.fetch_all("""
    SELECT pr.return
    FROM pnl_records pr
    JOIN markets m ON pr.market_id = m.id
    JOIN programs p ON pr.program_id = p.id
    WHERE m.name = 'Rise'
    AND p.program_name = 'CTA_50M_30'
    ORDER BY pr.date
""")
rise_df = pd.DataFrame(all_rise, columns=['return'])
rise_nav = starting_nav * (1 + rise_df['return']).cumprod().iloc[-1]

print(f"  Rise CTA Final NAV:  ${rise_nav:,.2f}")
print(f"  SP500 Final NAV:     ${df['nav'].iloc[-1]:,.2f}")
print(f"  Outperformance:      {((rise_nav / df['nav'].iloc[-1]) - 1) * 100:+.2f}%")

print("\n" + "="*70)
print("VERIFICATION COMPLETE")
print("="*70)

db.close()
