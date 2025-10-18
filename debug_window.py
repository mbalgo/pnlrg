from database import Database
from windows import Window, WindowDefinition
from datetime import date

db = Database('pnlrg.db')
db.connect()

sp500 = db.fetch_one('SELECT id FROM markets WHERE name = "SP500"')

win_def = WindowDefinition(
    start_date=date(1990, 1, 1),
    end_date=date(1994, 12, 31),
    program_ids=[1],
    benchmark_ids=[sp500['id']]
)

window = Window(win_def, db)

prog_data = window.get_manager_data(1)
bm_data = window.get_benchmark_data(sp500['id'])

print(f'Window: 1990-01-01 to 1994-12-31')
print(f'\nProgram data: {len(prog_data)} rows')
if len(prog_data) > 0:
    print(f'  Range: {prog_data["date"].min()} to {prog_data["date"].max()}')

print(f'\nBenchmark data: {len(bm_data)} rows')
if len(bm_data) > 0:
    print(f'  Range: {bm_data["date"].min()} to {bm_data["date"].max()}')

print(f'\nData complete: {window.data_is_complete}')
print(f'Program complete: {window._has_complete_coverage(prog_data)}')
print(f'Benchmark complete: {window._has_complete_coverage(bm_data)}')

db.close()
