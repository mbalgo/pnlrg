"""
Add submission_date column to pnl_records table.

This allows tracking when data was submitted/updated by managers.
Only creates new rows when actual return values change, not just submission dates.
"""

from database import Database
from datetime import date

def add_submission_date_column():
    """Add submission_date column to pnl_records with default value."""
    db = Database()

    try:
        # Check if column already exists
        result = db.fetch_one("PRAGMA table_info(pnl_records)")
        columns = db.fetch_all("PRAGMA table_info(pnl_records)")
        column_names = [col['name'] for col in columns]

        if 'submission_date' in column_names:
            print("[INFO] Column 'submission_date' already exists")
            return

        # Add the column with a default value of today's date
        today = date.today().strftime('%Y-%m-%d')
        db.execute(
            f"ALTER TABLE pnl_records ADD COLUMN submission_date TEXT NOT NULL DEFAULT '{today}'"
        )

        print(f"[OK] Added 'submission_date' column to pnl_records table")
        print(f"[INFO] Default value for existing records: {today}")

        # Verify the change
        columns = db.fetch_all("PRAGMA table_info(pnl_records)")
        for col in columns:
            if col['name'] == 'submission_date':
                print(f"[OK] Column verified: {col['name']} ({col['type']}, NOT NULL={col['notnull']}, DEFAULT={col['dflt_value']})")

    except Exception as e:
        print(f"[ERROR] Failed to add column: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Adding submission_date column to pnl_records table...")
    add_submission_date_column()
