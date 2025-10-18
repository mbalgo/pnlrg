"""
Database module for PnL Report Generator.
Handles SQLite database initialization and connection management.
"""

import sqlite3
from pathlib import Path
from typing import Optional


class Database:
    """Database manager for PnL Report Generator."""

    def __init__(self, db_path: str = "pnlrg.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file. Defaults to 'pnlrg.db'
        """
        self.db_path = Path(db_path)
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """
        Establish connection to database.

        Returns:
            SQLite connection object
        """
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
        return self.connection

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def initialize_schema(self):
        """
        Initialize database schema from schema.sql file.
        Creates all tables, indexes, and constraints if they don't exist.
        """
        schema_path = Path(__file__).parent / "schema.sql"

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        conn = self.connect()
        cursor = conn.cursor()

        # Execute schema (SQLite supports multiple statements)
        cursor.executescript(schema_sql)
        conn.commit()

        print(f"Database initialized successfully at: {self.db_path.absolute()}")

    def execute(self, query: str, params: tuple = ()):
        """
        Execute a single query.

        Args:
            query: SQL query string
            params: Query parameters (for parameterized queries)

        Returns:
            Cursor object with results
        """
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def execute_many(self, query: str, params_list: list):
        """
        Execute same query with multiple parameter sets.

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            Cursor object
        """
        conn = self.connect()
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()
        return cursor

    def fetch_all(self, query: str, params: tuple = ()) -> list:
        """
        Fetch all rows from a query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of Row objects
        """
        cursor = self.execute(query, params)
        return cursor.fetchall()

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """
        Fetch single row from a query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Row object or None
        """
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_database(db_path: str = "pnlrg.db"):
    """
    Create and initialize a new database.

    Args:
        db_path: Path for the database file

    Returns:
        Database instance
    """
    db = Database(db_path)
    db.initialize_schema()
    return db


if __name__ == "__main__":
    # Example usage: initialize database
    db = create_database()
    print("Database created and initialized successfully!")
    db.close()
