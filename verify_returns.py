"""Verify percentage returns are stored correctly."""

from database import Database

db = Database('pnlrg.db')
db.connect()

# Check program metadata
print("Program metadata:")
print("="*70)
program = db.fetch_one("""
    SELECT program_name, fund_size, starting_nav, starting_date
    FROM programs
    WHERE program_name = 'CTA_50M_30'
""")
print(f"Program: {program['program_name']}")
print(f"Fund Size: ${program['fund_size']:,.0f}")
print(f"Starting NAV: ${program['starting_nav']:,.0f}")
print(f"Starting Date: {program['starting_date']}")

print("\n\nFirst 15 percentage returns for CTA_50M_30:")
print("="*70)

data = db.fetch_all("""
    SELECT pr.date, pr.return
    FROM pnl_records pr
    JOIN programs p ON pr.program_id = p.id
    JOIN markets m ON pr.market_id = m.id
    WHERE p.program_name = 'CTA_50M_30'
    AND m.name = 'Rise'
    AND pr.resolution = 'monthly'
    ORDER BY pr.date
    LIMIT 15
""")

for row in data:
    return_pct = row['return'] * 100  # Convert to percentage
    print(f"{row['date']:12}  Return: {return_pct:7.4f}%")

# Calculate NAV from returns to verify
print("\n\nRecalculated NAV from returns (first 15):")
print("="*70)
nav = program['starting_nav']
print(f"1973-01-03    NAV: ${nav:12,.2f}  (starting point)")

for row in data:
    nav = nav * (1 + row['return'])
    return_pct = row['return'] * 100
    print(f"{row['date']:12}  NAV: ${nav:12,.2f}  (return: {return_pct:6.3f}%)")

db.close()
