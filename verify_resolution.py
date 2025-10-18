"""Verify resolution field in database."""

from database import Database

db = Database('pnlrg.db')
db.connect()

print('Resolution counts:')
for row in db.fetch_all('SELECT resolution, COUNT(*) as count FROM pnl_records GROUP BY resolution'):
    print(f'  {row["resolution"]}: {row["count"]} records')

print('\nSample records with resolution:')
for row in db.fetch_all('SELECT date, pnl, resolution FROM pnl_records LIMIT 10'):
    print(f'  {row["date"]}: ${row["pnl"]:,.2f} ({row["resolution"]})')

print('\nSchema:')
for row in db.fetch_all('PRAGMA table_info(pnl_records)'):
    print(f'  {row["name"]:15} {row["type"]:10} {"NOT NULL" if row["notnull"] else "NULL":10} default={row["dflt_value"]}')

db.close()
