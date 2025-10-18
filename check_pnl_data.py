"""Check the actual PnL data to understand the format."""

from database import Database

db = Database('pnlrg.db')
db.connect()

print("First 15 PnL records for CTA_50M_30:")
print("="*50)

data = db.fetch_all("""
    SELECT pr.date, pr.pnl
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
    print(f"{row['date']}: ${row['pnl']:,.2f}")

db.close()
