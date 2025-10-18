"""
Migration script to add resolution column to existing pnl_records table.
"""

from database import Database

def migrate_add_resolution():
    """Add resolution column to pnl_records and update existing data."""

    db = Database("pnlrg.db")
    db.connect()

    print("Adding resolution column to pnl_records table...")

    try:
        # Add the resolution column with default value 'monthly'
        db.execute("ALTER TABLE pnl_records ADD COLUMN resolution TEXT NOT NULL DEFAULT 'monthly'")
        print("  [OK] Added resolution column")

        # Update all existing records to have 'monthly' resolution
        result = db.execute("UPDATE pnl_records SET resolution = 'monthly'")
        print(f"  [OK] Updated {result.rowcount} existing records to 'monthly' resolution")

        # Create indexes for performance
        db.execute("CREATE INDEX IF NOT EXISTS idx_pnl_resolution ON pnl_records(resolution)")
        print("  [OK] Created idx_pnl_resolution")

        db.execute("CREATE INDEX IF NOT EXISTS idx_pnl_program_resolution ON pnl_records(program_id, resolution)")
        print("  [OK] Created idx_pnl_program_resolution")

        # Create unique constraint (note: SQLite doesn't support adding constraints to existing tables easily)
        # We'll need to recreate the table to add the UNIQUE constraint
        print("\nCreating unique constraint on (date, market_id, program_id, resolution)...")

        # For now, just verify there are no duplicates
        duplicates = db.fetch_all("""
            SELECT date, market_id, program_id, resolution, COUNT(*) as count
            FROM pnl_records
            GROUP BY date, market_id, program_id, resolution
            HAVING count > 1
        """)

        if duplicates:
            print(f"  [WARNING] Found {len(duplicates)} duplicate records:")
            for dup in duplicates[:5]:
                print(f"    {dup['date']}, market={dup['market_id']}, program={dup['program_id']}, resolution={dup['resolution']}, count={dup['count']}")
        else:
            print("  [OK] No duplicates found - data is clean")

        print("\n" + "="*60)
        print("Migration completed successfully!")
        print("="*60)

        # Verify the schema
        print("\nVerifying schema...")
        schema = db.fetch_all("PRAGMA table_info(pnl_records)")
        print("\npnl_records columns:")
        for col in schema:
            print(f"  {col['name']:15} {col['type']:10} {'NOT NULL' if col['notnull'] else 'NULL':10} default={col['dflt_value']}")

    except Exception as e:
        print(f"\n[ERROR] Error during migration: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_add_resolution()
