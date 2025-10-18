"""Verify final NAV values."""

from database import Database

db = Database('pnlrg.db')
db.connect()

print("Last 5 NAV values for CTA_50M_30:")
print("="*50)

data = db.fetch_all("""
    SELECT pr.date, pr.nav
    FROM pnl_records pr
    JOIN programs p ON pr.program_id = p.id
    JOIN markets m ON pr.market_id = m.id
    WHERE p.program_name = 'CTA_50M_30'
    AND m.name = 'Rise'
    AND pr.resolution = 'monthly'
    ORDER BY pr.date DESC
    LIMIT 5
""")

for row in data:
    print(f"{row['date']}: ${row['nav']:,.2f}")

db.close()
