"""
Clean up old Alphabet MFT sector-level data.

Deletes:
1. All pnl_records for MFT program
2. Temporary sector markets (Energy, Base Metals, Bonds, FX, Equity Indices)
"""

from database import Database

def cleanup_old_alphabet_data():
    """Delete old Alphabet MFT data and temporary markets."""
    db = Database()

    try:
        # Get MFT program ID
        program = db.fetch_one(
            "SELECT id FROM programs WHERE program_name = ?",
            ("MFT",)
        )

        if not program:
            print("[INFO] MFT program not found, nothing to clean up")
            return

        program_id = program['id']
        print(f"[INFO] Found MFT program with ID: {program_id}")

        # Count existing records
        count_result = db.fetch_one(
            "SELECT COUNT(*) as count FROM pnl_records WHERE program_id = ?",
            (program_id,)
        )
        record_count = count_result['count']
        print(f"[INFO] Found {record_count} pnl_records for MFT program")

        # Delete pnl_records
        if record_count > 0:
            response = input(f"Delete {record_count} pnl_records for MFT? (yes/no): ")
            if response.lower() == 'yes':
                db.execute(
                    "DELETE FROM pnl_records WHERE program_id = ?",
                    (program_id,)
                )
                print(f"[OK] Deleted {record_count} pnl_records")
            else:
                print("[INFO] Skipped pnl_records deletion")
                return

        # Delete temporary sector markets
        temp_markets = ["Energy", "Base Metals", "Bonds", "FX", "Equity Indices"]

        for market_name in temp_markets:
            market = db.fetch_one(
                "SELECT id FROM markets WHERE name = ?",
                (market_name,)
            )
            if market:
                # Check if any pnl_records reference this market
                pnl_count = db.fetch_one(
                    "SELECT COUNT(*) as count FROM pnl_records WHERE market_id = ?",
                    (market['id'],)
                )
                if pnl_count['count'] > 0:
                    print(f"[WARNING] Market '{market_name}' still has {pnl_count['count']} pnl_records, skipping deletion")
                else:
                    db.execute(
                        "DELETE FROM markets WHERE id = ?",
                        (market['id'],)
                    )
                    print(f"[OK] Deleted market: {market_name}")
            else:
                print(f"[INFO] Market not found: {market_name}")

        print("[OK] Cleanup completed")

    except Exception as e:
        print(f"[ERROR] Cleanup failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Cleaning up old Alphabet MFT data...")
    cleanup_old_alphabet_data()
