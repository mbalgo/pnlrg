"""
Verification script for Alphabet MFT import.

This script performs detailed verification of the imported data:
1. Confirms manager and program exist
2. Verifies all markets were created
3. Checks data completeness and consistency
4. Compares CSV totals against database records
"""

import csv
from database import Database


def verify_alphabet_import():
    """Verify the Alphabet MFT import."""

    CSV_PATH = r"C:\Users\matth\alphabet_backtest\20251020_sectors_only.csv"
    MANAGER_NAME = "Alphabet"
    PROGRAM_NAME = "MFT"
    FUND_SIZE = 10_000_000

    SECTORS = ["Energy", "Base Metals", "Bonds", "FX", "Equity Indices"]

    db = Database()
    db.connect()

    try:
        print("Alphabet MFT Import Verification")
        print("=" * 60)

        # 1. Verify manager
        print("\n1. Manager Verification")
        manager = db.fetch_one(
            "SELECT id, manager_name FROM managers WHERE manager_name = ?",
            (MANAGER_NAME,)
        )
        if manager:
            print(f"   [OK] Manager '{MANAGER_NAME}' found (ID: {manager['id']})")
        else:
            print(f"   [ERROR] Manager '{MANAGER_NAME}' not found!")
            return

        # 2. Verify program
        print("\n2. Program Verification")
        program = db.fetch_one(
            """SELECT id, program_name, fund_size, starting_nav, starting_date, manager_id
               FROM programs WHERE program_name = ? AND manager_id = ?""",
            (PROGRAM_NAME, manager['id'])
        )
        if program:
            print(f"   [OK] Program '{PROGRAM_NAME}' found (ID: {program['id']})")
            print(f"        Fund Size: ${program['fund_size']:,.0f}")
            print(f"        Starting NAV: {program['starting_nav']}")
            print(f"        Starting Date: {program['starting_date']}")
        else:
            print(f"   [ERROR] Program '{PROGRAM_NAME}' not found!")
            return

        # 3. Verify markets
        print("\n3. Market Verification")
        market_ids = {}
        for sector in SECTORS:
            market = db.fetch_one(
                "SELECT id, name, asset_class, region, currency FROM markets WHERE name = ?",
                (sector,)
            )
            if market:
                market_ids[sector] = market['id']
                print(f"   [OK] Market '{sector}' found (ID: {market['id']})")
            else:
                print(f"   [ERROR] Market '{sector}' not found!")
                return

        # 4. Verify PnL records count
        print("\n4. PnL Records Verification")
        total_records = db.fetch_one(
            "SELECT COUNT(*) as cnt FROM pnl_records WHERE program_id = ?",
            (program['id'],)
        )['cnt']
        print(f"   Total records in database: {total_records:,}")

        # Per-market counts
        for sector in SECTORS:
            count = db.fetch_one(
                """SELECT COUNT(*) as cnt FROM pnl_records
                   WHERE market_id = ? AND program_id = ?""",
                (market_ids[sector], program['id'])
            )['cnt']
            print(f"   {sector:20s}: {count:5,} records")

        # 5. Date range verification
        print("\n5. Date Range Verification")
        date_info = db.fetch_one(
            """SELECT
                   MIN(date) as first_date,
                   MAX(date) as last_date,
                   COUNT(DISTINCT date) as unique_dates
               FROM pnl_records WHERE program_id = ?""",
            (program['id'],)
        )
        print(f"   First date: {date_info['first_date']}")
        print(f"   Last date:  {date_info['last_date']}")
        print(f"   Unique dates: {date_info['unique_dates']:,}")

        # 6. Cross-check with CSV
        print("\n6. CSV Cross-Check")
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            csv_rows = list(reader)

        print(f"   CSV rows: {len(csv_rows):,}")
        print(f"   Expected total records: {len(csv_rows) * len(SECTORS):,}")
        print(f"   Actual total records: {total_records:,}")

        if total_records == len(csv_rows) * len(SECTORS):
            print(f"   [OK] Record counts match!")
        else:
            print(f"   [WARNING] Record count mismatch!")

        # 7. Sample data verification (first 3 rows)
        print("\n7. Sample Data Verification (First 3 Rows)")

        for i in range(min(3, len(csv_rows))):
            csv_row = csv_rows[i]
            date_str = csv_row['Date']

            # Parse date (DD/MM/YYYY)
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%d/%m/%Y').date()
            db_date = date_obj.strftime('%Y-%m-%d')

            print(f"\n   Row {i+1}: {date_str} -> {db_date}")

            for sector in SECTORS:
                # Get CSV PnL
                csv_pnl_str = csv_row[sector]
                csv_pnl = float(csv_pnl_str.replace(',', '')) if csv_pnl_str.strip() else 0.0
                expected_return = csv_pnl / FUND_SIZE

                # Get DB return
                db_return = db.fetch_one(
                    """SELECT return FROM pnl_records
                       WHERE date = ? AND market_id = ? AND program_id = ?""",
                    (db_date, market_ids[sector], program['id'])
                )

                if db_return:
                    actual_return = db_return['return']
                    match = abs(actual_return - expected_return) < 1e-10
                    status = "[OK]" if match else "[MISMATCH]"
                    print(f"      {sector:20s}: CSV PnL={csv_pnl:>10,.0f} -> Expected={expected_return:.8f}, Actual={actual_return:.8f} {status}")
                else:
                    print(f"      {sector:20s}: [ERROR] No record found in database!")

        # 8. Return statistics
        print("\n8. Return Statistics")
        stats = db.fetch_one(
            """SELECT
                   MIN(return) as min_ret,
                   MAX(return) as max_ret,
                   AVG(return) as avg_ret,
                   SUM(CASE WHEN return > 0 THEN 1 ELSE 0 END) as positive_days,
                   SUM(CASE WHEN return < 0 THEN 1 ELSE 0 END) as negative_days,
                   SUM(CASE WHEN return = 0 THEN 1 ELSE 0 END) as zero_days
               FROM pnl_records WHERE program_id = ?""",
            (program['id'],)
        )

        print(f"   Min return:  {stats['min_ret']:>10.6f} ({stats['min_ret']*100:>7.4f}%)")
        print(f"   Max return:  {stats['max_ret']:>10.6f} ({stats['max_ret']*100:>7.4f}%)")
        print(f"   Avg return:  {stats['avg_ret']:>10.6f} ({stats['avg_ret']*100:>7.4f}%)")
        print(f"   Positive:    {stats['positive_days']:>10,} records")
        print(f"   Negative:    {stats['negative_days']:>10,} records")
        print(f"   Zero:        {stats['zero_days']:>10,} records")

        print("\n" + "=" * 60)
        print("[SUCCESS] Verification completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Verification failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    verify_alphabet_import()
