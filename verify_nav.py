"""Verify NAV values are stored correctly."""

from database import Database

db = Database('pnlrg.db')
db.connect()

print("First 15 records with NAV for CTA_50M_30:")
print("="*70)

data = db.fetch_all("""
    SELECT pr.date, pr.pnl, pr.nav
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
    print(f"{row['date']:12}  PnL: ${row['pnl']:10,.2f}  NAV: ${row['nav']:12,.2f}")

db.close()
