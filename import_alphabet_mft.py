"""
Import script for Alphabet manager's MFT program.

This script:
1. Creates the Alphabet manager in the database
2. Creates the MFT program linked to Alphabet
3. Creates sector markets (Energy, Base Metals, Bonds, FX, Equity Indices)
4. Imports daily PnL data from CSV and converts to percentage returns
5. Stores data in pnl_records table with daily resolution

Data Source: C:\\Users\\matth\\alphabet_backtest\\20251020_sectors_only.csv
Fund Size: $10,000,000
Starting NAV: 1000
"""

import csv
from datetime import datetime
from database import Database


def parse_date(date_str):
    """Parse date string in D/M/YYYY or DD/MM/YYYY format."""
    return datetime.strptime(date_str, '%d/%m/%Y').date()


def parse_pnl(pnl_str):
    """Parse PnL string with commas (e.g., '21,496' or '-13,064') to float."""
    if not pnl_str or pnl_str.strip() == '':
        return 0.0
    # Remove commas and convert to float
    return float(pnl_str.replace(',', ''))


def convert_pnl_to_return(pnl, fund_size):
    """
    Convert absolute USD PnL to percentage return as decimal.

    Args:
        pnl: Daily PnL in USD
        fund_size: Total fund size in USD

    Returns:
        Decimal return where 0.01 = 1%
    """
    return pnl / fund_size


def import_alphabet_mft():
    """Main import function."""

    # Configuration
    MANAGER_NAME = "Alphabet"
    PROGRAM_NAME = "MFT"
    PROGRAM_NICE_NAME = "MFT"
    FUND_SIZE = 10_000_000
    STARTING_NAV = 1000
    CSV_PATH = r"C:\Users\matth\alphabet_backtest\20251020_sectors_only.csv"

    # Sector markets to create
    SECTORS = [
        "Energy",
        "Base Metals",
        "Bonds",
        "FX",
        "Equity Indices"
    ]

    db = Database()
    db.connect()

    try:
        print(f"Starting import for {MANAGER_NAME} - {PROGRAM_NAME}")
        print("=" * 60)

        # Step 1: Create or get manager
        print(f"\n1. Setting up manager: {MANAGER_NAME}")
        manager = db.fetch_one("SELECT id FROM managers WHERE manager_name = ?", (MANAGER_NAME,))

        if manager:
            manager_id = manager['id']
            print(f"   [OK] Manager already exists (ID: {manager_id})")
        else:
            cursor = db.execute("INSERT INTO managers (manager_name) VALUES (?)", (MANAGER_NAME,))
            manager_id = cursor.lastrowid
            print(f"   [OK] Created manager (ID: {manager_id})")

        # Step 2: Create program
        print(f"\n2. Setting up program: {PROGRAM_NAME}")
        program = db.fetch_one("SELECT id FROM programs WHERE program_name = ?", (PROGRAM_NAME,))

        if program:
            print(f"   [WARNING] Program '{PROGRAM_NAME}' already exists!")
            response = input("   Do you want to delete and recreate it? (yes/no): ")
            if response.lower() == 'yes':
                # Delete existing pnl_records first (due to foreign key constraint)
                program_id = program['id']
                db.execute("DELETE FROM pnl_records WHERE program_id = ?", (program_id,))
                db.execute("DELETE FROM programs WHERE id = ?", (program_id,))
                print(f"   [OK] Deleted existing program and its PnL records")
            else:
                print("   Aborting import.")
                return

        cursor = db.execute(
            """INSERT INTO programs
               (program_name, fund_size, starting_nav, manager_id)
               VALUES (?, ?, ?, ?)""",
            (PROGRAM_NAME, FUND_SIZE, STARTING_NAV, manager_id)
        )
        program_id = cursor.lastrowid
        print(f"   [OK] Created program (ID: {program_id})")
        print(f"     - Fund Size: ${FUND_SIZE:,}")
        print(f"     - Starting NAV: {STARTING_NAV}")

        # Step 3: Create sector markets
        print(f"\n3. Creating sector markets")
        market_ids = {}

        for sector in SECTORS:
            market = db.fetch_one("SELECT id FROM markets WHERE name = ?", (sector,))

            if market:
                market_ids[sector] = market['id']
                print(f"   [OK] Market '{sector}' already exists (ID: {market['id']})")
            else:
                cursor = db.execute(
                    """INSERT INTO markets
                       (name, asset_class, region, currency, is_benchmark)
                       VALUES (?, ?, ?, ?, ?)""",
                    (sector, 'future', 'US', 'USD', 0)
                )
                market_ids[sector] = cursor.lastrowid
                print(f"   [OK] Created market '{sector}' (ID: {market_ids[sector]})")

        # Step 4: Read and parse CSV
        print(f"\n4. Reading CSV file: {CSV_PATH}")

        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"   [OK] Loaded {len(rows)} rows from CSV")

        # Step 5: Convert and insert PnL records
        print(f"\n5. Converting PnL to returns and inserting records")

        pnl_records = []
        row_count = 0
        skipped_count = 0

        for row in rows:
            try:
                date = parse_date(row['Date'])

                # Process each sector
                for sector in SECTORS:
                    pnl = parse_pnl(row[sector])
                    return_pct = convert_pnl_to_return(pnl, FUND_SIZE)

                    pnl_records.append((
                        date.strftime('%Y-%m-%d'),
                        market_ids[sector],
                        program_id,
                        return_pct,
                        'daily'
                    ))

                row_count += 1

                if row_count % 100 == 0:
                    print(f"   Processing row {row_count}/{len(rows)}...", end='\r')

            except Exception as e:
                print(f"\n   [WARNING] Error processing row: {row}")
                print(f"     Error: {e}")
                skipped_count += 1
                continue

        print(f"\n   [OK] Processed {row_count} rows ({skipped_count} skipped)")

        # Bulk insert
        print(f"\n6. Bulk inserting {len(pnl_records)} PnL records...")

        db.execute_many(
            """INSERT INTO pnl_records
               (date, market_id, program_id, return, resolution)
               VALUES (?, ?, ?, ?, ?)""",
            pnl_records
        )
        print(f"   [OK] Inserted {len(pnl_records)} records")

        # Step 6: Update program starting_date
        first_date = min(row[0] for row in pnl_records)
        db.execute(
            "UPDATE programs SET starting_date = ? WHERE id = ?",
            (first_date, program_id)
        )
        print(f"\n7. Updated program starting_date: {first_date}")

        # Step 7: Verification and statistics
        print(f"\n8. Verification & Statistics")
        print("=" * 60)

        # Count records per market
        for sector in SECTORS:
            count = db.fetch_one(
                """SELECT COUNT(*) as cnt FROM pnl_records
                   WHERE market_id = ? AND program_id = ?""",
                (market_ids[sector], program_id)
            )['cnt']
            print(f"   {sector:20s}: {count:5d} records")

        # Date range
        date_range = db.fetch_one(
            """SELECT MIN(date) as min_date, MAX(date) as max_date
               FROM pnl_records WHERE program_id = ?""",
            (program_id,)
        )
        print(f"\n   Date Range: {date_range['min_date']} to {date_range['max_date']}")

        # Sample returns statistics
        stats = db.fetch_one(
            """SELECT
                   MIN(return) as min_ret,
                   MAX(return) as max_ret,
                   AVG(return) as avg_ret
               FROM pnl_records WHERE program_id = ?""",
            (program_id,)
        )
        print(f"\n   Return Statistics (as decimals, 0.01 = 1%):")
        print(f"     Min: {stats['min_ret']:.6f}")
        print(f"     Max: {stats['max_ret']:.6f}")
        print(f"     Avg: {stats['avg_ret']:.6f}")

        print("\n" + "=" * 60)
        print("[SUCCESS] Import completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Error during import: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_alphabet_mft()
