"""
Import Alphabet MFT market-level daily PnL data and benchmarks.

Data sources:
- MFT_20251021_MARKET_BREAKDOWN.csv: Daily PnL by market (17 markets)
- MFT_20251021_BENCHMARKS.csv: Daily benchmark returns (AREIT, SP500)

Fund parameters:
- Fund Size: $10,000,000
- Starting NAV: 1000
- Resolution: daily
- Submission Date: 2025-10-21
"""

import csv
from datetime import datetime, date
from database import Database

# Configuration
FUND_SIZE = 10_000_000
STARTING_NAV = 1000
SUBMISSION_DATE = date(2025, 10, 21).strftime('%Y-%m-%d')

# File paths
MFT_CSV = r"C:\Users\matth\OneDrive\Documents\MFT Portfolios\MFT_20251021_MARKET_BREAKDOWN.csv"
BENCHMARK_CSV = r"C:\Users\matth\OneDrive\Documents\MFT Portfolios\MFT_20251021_BENCHMARKS.csv"

# Market definitions (from CSV headers)
MARKET_NAMES = [
    "WTI", "ULSD Diesel", "Brent", "Ali", "Copper", "Zinc",
    "10y bond", "T-Bond", "Gilts 10y", "KTB 10s", "USDKRW",
    "ASX 200", "DAX", "CAC 40", "Kospi 200", "TX index", "WIG 20"
]


def parse_date(date_str):
    """Parse DD/MM/YYYY format to YYYY-MM-DD."""
    try:
        dt = datetime.strptime(date_str.strip(), '%d/%m/%Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        # Try alternate format
        dt = datetime.strptime(date_str.strip(), '%d/%m/%y')
        return dt.strftime('%Y-%m-%d')


def parse_pnl(pnl_str):
    """Parse PnL string with potential thousands separators."""
    if not pnl_str or pnl_str.strip() == '':
        return None
    try:
        # Remove quotes and commas
        cleaned = pnl_str.replace('"', '').replace(',', '').strip()
        return float(cleaned)
    except ValueError:
        return None


def parse_percent(percent_str):
    """Parse percentage already in decimal format (0.01 = 1%)."""
    if not percent_str or percent_str.strip() == '':
        return None
    try:
        return float(percent_str.strip())
    except ValueError:
        return None


def create_or_get_market(db, market_name, is_benchmark=False):
    """Create market if doesn't exist, return market_id."""
    market = db.fetch_one(
        "SELECT id FROM markets WHERE name = ?",
        (market_name,)
    )

    if market:
        print(f"[INFO] Market '{market_name}' already exists (ID: {market['id']})")
        return market['id']

    # Create new market
    cursor = db.execute(
        "INSERT INTO markets (name, asset_class, region, currency, is_benchmark) VALUES (?, ?, ?, ?, ?)",
        (market_name, 'future', 'US', 'USD', 1 if is_benchmark else 0)
    )
    market_id = cursor.lastrowid
    print(f"[OK] Created market: {market_name} (ID: {market_id}, Benchmark: {is_benchmark})")
    return market_id


def import_mft_market_data(db, program_id):
    """Import MFT market-level daily PnL data."""
    print("\n=== Importing MFT Market Data ===")

    # Create markets
    market_ids = {}
    for market_name in MARKET_NAMES:
        market_ids[market_name] = create_or_get_market(db, market_name, is_benchmark=False)

    # Read CSV and prepare records
    pnl_records = []
    row_count = 0

    with open(MFT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            row_count += 1
            date_str = parse_date(row['Date'])

            for market_name in MARKET_NAMES:
                pnl_usd = parse_pnl(row[market_name])

                if pnl_usd is not None:
                    # Convert USD PnL to percentage return
                    return_decimal = pnl_usd / FUND_SIZE
                    market_id = market_ids[market_name]

                    pnl_records.append((
                        date_str,
                        market_id,
                        program_id,
                        return_decimal,
                        'daily',
                        SUBMISSION_DATE
                    ))

    # Bulk insert
    print(f"[INFO] Read {row_count} dates from CSV")
    print(f"[INFO] Inserting {len(pnl_records)} pnl_records...")

    db.execute_many(
        """INSERT INTO pnl_records (date, market_id, program_id, return, resolution, submission_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        pnl_records
    )

    print(f"[OK] Imported {len(pnl_records)} pnl_records for MFT markets")
    return len(pnl_records)


def import_benchmark_data(db, program_id):
    """Import benchmark data (AREIT, SP500) - daily returns already in decimal %."""
    print("\n=== Importing Benchmark Data ===")

    # Create benchmark markets
    areit_id = create_or_get_market(db, "AREIT", is_benchmark=True)
    sp500_id = create_or_get_market(db, "SP500", is_benchmark=True)

    # Read CSV
    areit_records = []
    sp500_records = []
    areit_end_date = date(2025, 5, 23).strftime('%Y-%m-%d')

    with open(BENCHMARK_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            date_str = parse_date(row['Date'])

            # AREIT (only up to 23/05/2025)
            if date_str <= areit_end_date:
                areit_return = parse_percent(row['AREIT'])
                if areit_return is not None:
                    areit_records.append((
                        date_str,
                        areit_id,
                        program_id,
                        areit_return,
                        'daily',
                        SUBMISSION_DATE
                    ))

            # SP500 (all dates)
            sp500_return = parse_percent(row['SP500'])
            if sp500_return is not None:
                sp500_records.append((
                    date_str,
                    sp500_id,
                    program_id,
                    sp500_return,
                    'daily',
                    SUBMISSION_DATE
                ))

    # Insert benchmarks
    if areit_records:
        db.execute_many(
            """INSERT INTO pnl_records (date, market_id, program_id, return, resolution, submission_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            areit_records
        )
        print(f"[OK] Imported {len(areit_records)} AREIT benchmark records (up to {areit_end_date})")

    if sp500_records:
        db.execute_many(
            """INSERT INTO pnl_records (date, market_id, program_id, return, resolution, submission_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            sp500_records
        )
        print(f"[OK] Imported {len(sp500_records)} SP500 benchmark records")

    return len(areit_records) + len(sp500_records)


def main():
    """Main import workflow."""
    db = Database()

    try:
        # Get Alphabet manager and MFT program
        manager = db.fetch_one("SELECT id FROM managers WHERE manager_name = ?", ("Alphabet",))
        if not manager:
            print("[ERROR] Alphabet manager not found")
            return

        program = db.fetch_one("SELECT id FROM programs WHERE program_name = ?", ("MFT",))
        if not program:
            print("[ERROR] MFT program not found")
            return

        program_id = program['id']
        print(f"[INFO] Using MFT program ID: {program_id}")
        print(f"[INFO] Fund Size: ${FUND_SIZE:,}")
        print(f"[INFO] Submission Date: {SUBMISSION_DATE}")

        # Import market data
        mft_count = import_mft_market_data(db, program_id)

        # Import benchmark data
        benchmark_count = import_benchmark_data(db, program_id)

        # Summary
        print("\n=== Import Summary ===")
        print(f"MFT Market Records: {mft_count}")
        print(f"Benchmark Records: {benchmark_count}")
        print(f"Total Records: {mft_count + benchmark_count}")
        print("[OK] Import completed successfully")

    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
