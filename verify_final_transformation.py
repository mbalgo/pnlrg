"""Verify the transformation to percentage returns is complete and correct."""

from database import Database
import pandas as pd

db = Database('pnlrg.db')
db.connect()

print("="*70)
print("VERIFICATION OF PERCENTAGE RETURNS TRANSFORMATION")
print("="*70)

# 1. Check schema
print("\n1. Database Schema Check:")
print("-"*70)
schema = db.fetch_all("PRAGMA table_info(pnl_records)")
print("pnl_records columns:")
for col in schema:
    print(f"  {col['name']:15} {col['type']:10} {'NOT NULL' if col['notnull'] else ''}")

programs_schema = db.fetch_all("PRAGMA table_info(programs)")
print("\nprograms columns:")
for col in programs_schema:
    print(f"  {col['name']:15} {col['type']:10} {'NOT NULL' if col['notnull'] else ''}")

# 2. Check programs metadata
print("\n\n2. Programs Metadata:")
print("-"*70)
programs = db.fetch_all("""
    SELECT program_name, fund_size, starting_nav, starting_date
    FROM programs
    ORDER BY fund_size
""")
for prog in programs:
    if prog['starting_nav']:
        print(f"{prog['program_name']:20} Fund: ${prog['fund_size']:15,.0f}  Start: ${prog['starting_nav']:8,.0f} on {prog['starting_date']}")

# 3. Verify percentage returns
print("\n\n3. Sample Percentage Returns (CTA_50M_30):")
print("-"*70)
returns = db.fetch_all("""
    SELECT pr.date, pr.return
    FROM pnl_records pr
    JOIN programs p ON pr.program_id = p.id
    JOIN markets m ON pr.market_id = m.id
    WHERE p.program_name = 'CTA_50M_30'
    AND m.name = 'Rise'
    AND pr.resolution = 'monthly'
    ORDER BY pr.date
    LIMIT 10
""")
for ret in returns:
    return_pct = ret['return'] * 100
    print(f"{ret['date']:12}  Return: {return_pct:7.4f}%")

# 4. Verify NAV can be reconstructed
print("\n\n4. NAV Reconstruction Test (CTA_50M_30):")
print("-"*70)
program = db.fetch_one("""
    SELECT starting_nav, starting_date
    FROM programs
    WHERE program_name = 'CTA_50M_30'
""")

all_returns = db.fetch_all("""
    SELECT pr.date, pr.return
    FROM pnl_records pr
    JOIN programs p ON pr.program_id = p.id
    JOIN markets m ON pr.market_id = m.id
    WHERE p.program_name = 'CTA_50M_30'
    AND m.name = 'Rise'
    AND pr.resolution = 'monthly'
    ORDER BY pr.date
""")

df = pd.DataFrame(all_returns, columns=['date', 'return'])
df['nav'] = program['starting_nav'] * (1 + df['return']).cumprod()

print(f"Starting NAV: ${program['starting_nav']:,.2f} on {program['starting_date']}")
print(f"First NAV:    ${df['nav'].iloc[0]:,.2f} on {df['date'].iloc[0]}")
print(f"Final NAV:    ${df['nav'].iloc[-1]:,.2f} on {df['date'].iloc[-1]}")
print(f"Total Return: {(df['nav'].iloc[-1] / program['starting_nav'] - 1) * 100:.2f}%")
print(f"CAGR:         {((df['nav'].iloc[-1] / program['starting_nav']) ** (1/45) - 1) * 100:.2f}%")

# 5. Record counts
print("\n\n5. Record Counts:")
print("-"*70)
count = db.fetch_one("SELECT COUNT(*) as count FROM pnl_records")
print(f"Total return records: {count['count']}")

programs_with_data = db.fetch_all("""
    SELECT p.program_name, COUNT(pr.id) as record_count
    FROM programs p
    JOIN pnl_records pr ON p.id = pr.program_id
    GROUP BY p.program_name
    ORDER BY p.fund_size
""")
for prog in programs_with_data:
    print(f"  {prog['program_name']:20} {prog['record_count']} records")

print("\n" + "="*70)
print("VERIFICATION COMPLETE")
print("="*70)

db.close()
