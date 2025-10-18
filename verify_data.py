"""Quick script to verify imported data."""

from database import Database

db = Database('pnlrg.db')
db.connect()

print('Managers:')
for row in db.fetch_all('SELECT * FROM managers'):
    print(f'  {row["id"]}: {row["manager_name"]}')

print('\nPrograms:')
for row in db.fetch_all('SELECT id, program_name, fund_size FROM programs ORDER BY fund_size DESC'):
    print(f'  {row["id"]}: {row["program_name"]} (${row["fund_size"]:,.0f})')

print('\nMarkets:')
for row in db.fetch_all('SELECT * FROM markets'):
    print(f'  {row["id"]}: {row["name"]} ({row["asset_class"]}, {row["currency"]})')

print('\nP&L Records Count by Program:')
for row in db.fetch_all('''
    SELECT p.program_name, COUNT(*) as count, MIN(pr.date) as start_date, MAX(pr.date) as end_date
    FROM pnl_records pr
    JOIN programs p ON pr.program_id = p.id
    GROUP BY p.program_name
    ORDER BY p.fund_size DESC
'''):
    print(f'  {row["program_name"]}: {row["count"]} records ({row["start_date"]} to {row["end_date"]})')

print('\nSample P&L records (50M_30):')
for row in db.fetch_all('''
    SELECT pr.date, pr.pnl
    FROM pnl_records pr
    JOIN programs p ON pr.program_id = p.id
    WHERE p.program_name = 'CTA_50M_30'
    ORDER BY pr.date
    LIMIT 10
'''):
    print(f'  {row["date"]}: ${row["pnl"]:,.2f}')

db.close()
