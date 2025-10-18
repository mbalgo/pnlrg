"""Verify all benchmark data is imported correctly."""

from database import Database
import pandas as pd

db = Database('pnlrg.db')
db.connect()

print("="*80)
print("ALL BENCHMARKS VERIFICATION")
print("="*80)

# Get all benchmark markets
benchmarks = db.fetch_all("""
    SELECT name, asset_class
    FROM markets
    WHERE is_benchmark = 1
    ORDER BY name
""")

print("\n1. Benchmark Markets:")
print("-"*80)
for bm in benchmarks:
    print(f"  {bm['name']:25} {bm['asset_class']}")

# Get Benchmarks program
benchmarks_prog = db.fetch_one("""
    SELECT id FROM programs WHERE program_name = 'Benchmarks'
""")

if not benchmarks_prog:
    print("\nError: Benchmarks program not found!")
    db.close()
    exit(1)

benchmarks_program_id = benchmarks_prog['id']

# Analyze each benchmark
print("\n\n2. Benchmark Performance Summary:")
print("="*80)

starting_nav = 1000.0

for bm in benchmarks:
    market_name = bm['name']

    # Get all returns for this benchmark
    returns = db.fetch_all("""
        SELECT pr.date, pr.return
        FROM pnl_records pr
        JOIN markets m ON pr.market_id = m.id
        WHERE m.name = ?
        AND pr.program_id = ?
        ORDER BY pr.date
    """, (market_name, benchmarks_program_id))

    if not returns:
        print(f"\n{market_name}:")
        print("  No data found!")
        continue

    df = pd.DataFrame(returns, columns=['date', 'return'])
    df['nav'] = starting_nav * (1 + df['return']).cumprod()

    start_date = df['date'].iloc[0]
    end_date = df['date'].iloc[-1]
    final_nav = df['nav'].iloc[-1]
    total_return = (final_nav / starting_nav - 1) * 100

    # Calculate years for CAGR
    start_year = pd.to_datetime(start_date).year
    end_year = pd.to_datetime(end_date).year
    years = end_year - start_year + (pd.to_datetime(end_date).month - pd.to_datetime(start_date).month) / 12

    cagr = ((final_nav / starting_nav) ** (1/years) - 1) * 100 if years > 0 else 0

    print(f"\n{market_name}:")
    print(f"  Records:       {len(returns)}")
    print(f"  Date Range:    {start_date} to {end_date}")
    print(f"  Starting NAV:  ${starting_nav:,.2f}")
    print(f"  Ending NAV:    ${final_nav:,.2f}")
    print(f"  Total Return:  {total_return:,.2f}%")
    print(f"  CAGR:          {cagr:.2f}%")

# Compare all benchmarks to Rise CTA
print("\n\n3. Rise CTA vs All Benchmarks (Aligned Start Dates):")
print("="*80)

# Get Rise data
rise_returns = db.fetch_all("""
    SELECT pr.date, pr.return
    FROM pnl_records pr
    JOIN markets m ON pr.market_id = m.id
    JOIN programs p ON pr.program_id = p.id
    WHERE m.name = 'Rise'
    AND p.program_name = 'CTA_50M_30'
    ORDER BY pr.date
""")

rise_df = pd.DataFrame(rise_returns, columns=['date', 'return'])
rise_df['date'] = pd.to_datetime(rise_df['date'])
rise_df['nav'] = starting_nav * (1 + rise_df['return']).cumprod()

for bm in benchmarks:
    market_name = bm['name']

    # Get benchmark returns
    bm_returns = db.fetch_all("""
        SELECT pr.date, pr.return
        FROM pnl_records pr
        JOIN markets m ON pr.market_id = m.id
        WHERE m.name = ?
        AND pr.program_id = ?
        ORDER BY pr.date
    """, (market_name, benchmarks_program_id))

    if not bm_returns:
        continue

    bm_df = pd.DataFrame(bm_returns, columns=['date', 'return'])
    bm_df['date'] = pd.to_datetime(bm_df['date'])

    # Find common date range
    bm_start = bm_df['date'].min()
    bm_end = bm_df['date'].max()

    # Filter Rise to same date range
    rise_aligned = rise_df[(rise_df['date'] >= bm_start) & (rise_df['date'] <= bm_end)].copy()

    if len(rise_aligned) == 0:
        continue

    # Calculate NAV from aligned start
    rise_aligned['nav'] = starting_nav * (1 + rise_aligned['return']).cumprod()
    bm_df['nav'] = starting_nav * (1 + bm_df['return']).cumprod()

    rise_final = rise_aligned['nav'].iloc[-1]
    bm_final = bm_df['nav'].iloc[-1]

    outperformance = ((rise_final / bm_final) - 1) * 100

    print(f"\n{market_name} ({bm_start.strftime('%Y-%m-%d')} to {bm_end.strftime('%Y-%m-%d')}):")
    print(f"  Rise Final NAV:       ${rise_final:,.2f}")
    print(f"  {market_name} Final NAV:  ${bm_final:,.2f}")
    print(f"  Outperformance:       {outperformance:+.2f}%")

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80)

db.close()
