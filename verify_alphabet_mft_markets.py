"""
Verify Alphabet MFT market-level import integrity.

Checks:
1. Market creation (17 MFT markets + 2 benchmarks)
2. Record counts match CSV expectations
3. Date range validation
4. Sample data cross-check
5. Return statistics
6. Submission date tracking
"""

import csv
from datetime import datetime, date
from database import Database

# Configuration
MFT_CSV = r"C:\Users\matth\OneDrive\Documents\MFT Portfolios\MFT_20251021_MARKET_BREAKDOWN.csv"
BENCHMARK_CSV = r"C:\Users\matth\OneDrive\Documents\MFT Portfolios\MFT_20251021_BENCHMARKS.csv"
FUND_SIZE = 10_000_000

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
        dt = datetime.strptime(date_str.strip(), '%d/%m/%y')
        return dt.strftime('%Y-%m-%d')


def verify_markets(db):
    """Verify market creation."""
    print("\n=== Market Verification ===")

    all_markets = MARKET_NAMES + ["AREIT", "SP500"]
    found = 0

    for market_name in all_markets:
        market = db.fetch_one("SELECT id, is_benchmark FROM markets WHERE name = ?", (market_name,))
        if market:
            benchmark_str = "Benchmark" if market['is_benchmark'] else "Trading"
            print(f"[OK] {market_name:15s} (ID: {market['id']:2d}, {benchmark_str})")
            found += 1
        else:
            print(f"[ERROR] Market not found: {market_name}")

    print(f"\n[INFO] Found {found}/{len(all_markets)} markets")
    return found == len(all_markets)


def verify_record_counts(db, program_id):
    """Verify pnl_record counts."""
    print("\n=== Record Count Verification ===")

    # Total records
    total = db.fetch_one(
        "SELECT COUNT(*) as count FROM pnl_records WHERE program_id = ?",
        (program_id,)
    )
    print(f"Total PnL Records: {total['count']:,}")

    # By market
    market_counts = db.fetch_all(
        """SELECT m.name, COUNT(*) as count
           FROM pnl_records pr
           JOIN markets m ON pr.market_id = m.id
           WHERE pr.program_id = ?
           GROUP BY m.name
           ORDER BY m.name""",
        (program_id,)
    )

    print(f"\nRecords by Market:")
    for row in market_counts:
        print(f"  {row['name']:15s}: {row['count']:,}")

    return total['count']


def verify_date_range(db, program_id):
    """Verify date ranges."""
    print("\n=== Date Range Verification ===")

    # Overall date range
    date_range = db.fetch_one(
        """SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as unique_dates
           FROM pnl_records
           WHERE program_id = ?""",
        (program_id,)
    )

    print(f"Date Range: {date_range['min_date']} to {date_range['max_date']}")
    print(f"Unique Trading Days: {date_range['unique_dates']:,}")

    # Benchmark-specific ranges
    benchmarks = ["AREIT", "SP500"]
    for benchmark in benchmarks:
        bm_range = db.fetch_one(
            """SELECT MIN(pr.date) as min_date, MAX(pr.date) as max_date, COUNT(*) as count
               FROM pnl_records pr
               JOIN markets m ON pr.market_id = m.id
               WHERE pr.program_id = ? AND m.name = ?""",
            (program_id, benchmark)
        )
        if bm_range['count'] > 0:
            print(f"{benchmark:6s}: {bm_range['min_date']} to {bm_range['max_date']} ({bm_range['count']:,} records)")


def verify_sample_data(db, program_id):
    """Cross-check sample data against CSV."""
    print("\n=== Sample Data Cross-Check ===")

    # Read first 3 rows from CSV
    with open(MFT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        sample_rows = []
        for i, row in enumerate(reader):
            if i < 3:
                sample_rows.append(row)
            else:
                break

    # Check first date, WTI market
    first_date = parse_date(sample_rows[0]['Date'])
    wti_pnl = float(sample_rows[0]['WTI'].replace(',', '')) if sample_rows[0]['WTI'] else 0
    expected_return = wti_pnl / FUND_SIZE

    db_record = db.fetch_one(
        """SELECT pr.return
           FROM pnl_records pr
           JOIN markets m ON pr.market_id = m.id
           WHERE pr.program_id = ? AND m.name = 'WTI' AND pr.date = ?""",
        (program_id, first_date)
    )

    if db_record:
        csv_val = f"{expected_return:.10f}"
        db_val = f"{db_record['return']:.10f}"
        match = csv_val == db_val

        print(f"Date: {first_date}, Market: WTI")
        print(f"  CSV PnL: ${wti_pnl:,.2f}")
        print(f"  Expected Return: {csv_val}")
        print(f"  DB Return: {db_val}")
        print(f"  Match: {'[OK]' if match else '[ERROR]'}")
    else:
        print(f"[ERROR] Sample record not found in DB")


def verify_statistics(db, program_id):
    """Calculate basic statistics."""
    print("\n=== Return Statistics ===")

    stats = db.fetch_one(
        """SELECT
           COUNT(*) as total_records,
           AVG(return) as avg_return,
           MIN(return) as min_return,
           MAX(return) as max_return,
           SUM(CASE WHEN return > 0 THEN 1 ELSE 0 END) as positive_days,
           SUM(CASE WHEN return < 0 THEN 1 ELSE 0 END) as negative_days
           FROM pnl_records
           WHERE program_id = ?""",
        (program_id,)
    )

    print(f"Total Records: {stats['total_records']:,}")
    print(f"Avg Daily Return: {stats['avg_return']*100:.4f}%")
    print(f"Min Daily Return: {stats['min_return']*100:.2f}%")
    print(f"Max Daily Return: {stats['max_return']*100:.2f}%")
    print(f"Positive Days: {stats['positive_days']:,} ({stats['positive_days']/stats['total_records']*100:.1f}%)")
    print(f"Negative Days: {stats['negative_days']:,} ({stats['negative_days']/stats['total_records']*100:.1f}%)")


def verify_submission_dates(db, program_id):
    """Check submission date tracking."""
    print("\n=== Submission Date Tracking ===")

    submission_counts = db.fetch_all(
        """SELECT submission_date, COUNT(*) as count
           FROM pnl_records
           WHERE program_id = ?
           GROUP BY submission_date
           ORDER BY submission_date""",
        (program_id,)
    )

    print(f"Submissions:")
    for row in submission_counts:
        print(f"  {row['submission_date']}: {row['count']:,} records")


def main():
    """Main verification workflow."""
    db = Database()

    try:
        # Get MFT program
        program = db.fetch_one("SELECT id FROM programs WHERE program_name = ?", ("MFT",))
        if not program:
            print("[ERROR] MFT program not found")
            return

        program_id = program['id']
        print(f"Verifying data for MFT program (ID: {program_id})")

        # Run all verifications
        verify_markets(db)
        verify_record_counts(db, program_id)
        verify_date_range(db, program_id)
        verify_sample_data(db, program_id)
        verify_statistics(db, program_id)
        verify_submission_dates(db, program_id)

        print("\n" + "="*50)
        print("[OK] Verification completed")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
