"""
Utility script for querying markets and performance by sector.

Usage examples:
- List all markets in a sector
- Get PnL data aggregated by sector
- Calculate sector-level statistics
"""

from database import Database
from datetime import date


def list_markets_by_sector(db, grouping_name='mft_sector'):
    """List all markets grouped by sector."""
    print(f"\n=== Markets by Sector (grouping: '{grouping_name}') ===\n")

    results = db.fetch_all(
        """SELECT s.sector_name, m.id as market_id, m.name as market_name
           FROM sectors s
           LEFT JOIN market_sector_mapping msm ON s.id = msm.sector_id
           LEFT JOIN markets m ON msm.market_id = m.id
           WHERE s.grouping_name = ?
           ORDER BY s.sector_name, m.name""",
        (grouping_name,)
    )

    current_sector = None
    market_count = 0

    for row in results:
        if row['sector_name'] != current_sector:
            if current_sector is not None:
                print()  # Blank line between sectors
            current_sector = row['sector_name']
            print(f"{current_sector}:")

        if row['market_name']:
            print(f"  - {row['market_name']} (ID: {row['market_id']})")
            market_count += 1
        else:
            print(f"  (no markets)")

    print(f"\nTotal markets: {market_count}")


def get_sector_ids(db, grouping_name='mft_sector'):
    """Get mapping of sector names to IDs."""
    sectors = db.fetch_all(
        "SELECT id, sector_name FROM sectors WHERE grouping_name = ?",
        (grouping_name,)
    )
    return {s['sector_name']: s['id'] for s in sectors}


def get_markets_in_sector(db, sector_name, grouping_name='mft_sector'):
    """Get all market IDs in a specific sector."""
    markets = db.fetch_all(
        """SELECT m.id, m.name
           FROM markets m
           JOIN market_sector_mapping msm ON m.id = msm.market_id
           JOIN sectors s ON msm.sector_id = s.id
           WHERE s.grouping_name = ? AND s.sector_name = ?
           ORDER BY m.name""",
        (grouping_name, sector_name)
    )
    return [(m['id'], m['name']) for m in markets]


def aggregate_pnl_by_sector(db, program_id, start_date=None, end_date=None, grouping_name='mft_sector'):
    """Aggregate PnL data by sector for a given program and date range."""
    print(f"\n=== Sector Aggregation (program_id={program_id}, grouping='{grouping_name}') ===\n")

    # Build date filter
    date_filter = ""
    params = [program_id, grouping_name]

    if start_date:
        date_filter += " AND pr.date >= ?"
        params.append(start_date)
    if end_date:
        date_filter += " AND pr.date <= ?"
        params.append(end_date)

    # Query sector-level aggregates
    query = f"""
        SELECT
            s.sector_name,
            COUNT(DISTINCT pr.date) as trading_days,
            COUNT(DISTINCT m.id) as market_count,
            AVG(pr.return) as avg_daily_return,
            MIN(pr.return) as min_return,
            MAX(pr.return) as max_return,
            SUM(CASE WHEN pr.return > 0 THEN 1 ELSE 0 END) as positive_days
        FROM pnl_records pr
        JOIN markets m ON pr.market_id = m.id
        JOIN market_sector_mapping msm ON m.id = msm.market_id
        JOIN sectors s ON msm.sector_id = s.id
        WHERE pr.program_id = ?
          AND s.grouping_name = ?
          {date_filter}
        GROUP BY s.sector_name
        ORDER BY s.sector_name
    """

    results = db.fetch_all(query, tuple(params))

    print(f"{'Sector':<20} {'Markets':<8} {'Days':<6} {'Avg Return':<12} {'Min':<10} {'Max':<10} {'Win%':<8}")
    print("-" * 90)

    for row in results:
        win_pct = (row['positive_days'] / (row['trading_days'] * row['market_count'])) * 100 if row['trading_days'] > 0 else 0
        print(f"{row['sector_name']:<20} {row['market_count']:<8} {row['trading_days']:<6} "
              f"{row['avg_daily_return']*100:>10.4f}% {row['min_return']*100:>8.2f}% "
              f"{row['max_return']*100:>8.2f}% {win_pct:>6.1f}%")


def sector_performance_summary(db, program_id, grouping_name='mft_sector'):
    """Show high-level sector performance summary."""
    print(f"\n=== Sector Performance Summary (program_id={program_id}) ===\n")

    # Get date range
    date_range = db.fetch_one(
        "SELECT MIN(date) as start, MAX(date) as end FROM pnl_records WHERE program_id = ?",
        (program_id,)
    )

    print(f"Period: {date_range['start']} to {date_range['end']}")

    aggregate_pnl_by_sector(db, program_id, grouping_name=grouping_name)


def main():
    """Example usage."""
    db = Database()

    try:
        # List markets by MFT sector
        list_markets_by_sector(db, grouping_name='mft_sector')

        # Show empty CTA sectors
        print("\n" + "="*60)
        list_markets_by_sector(db, grouping_name='cta_sector')

        # Get MFT program ID
        program = db.fetch_one("SELECT id FROM programs WHERE program_name = ?", ("MFT",))
        if program:
            # Show sector performance
            print("\n" + "="*60)
            sector_performance_summary(db, program['id'], grouping_name='mft_sector')

            # Example: Get markets in Energy sector
            print("\n" + "="*60)
            energy_markets = get_markets_in_sector(db, 'Energy', grouping_name='mft_sector')
            print(f"\nEnergy sector markets:")
            for market_id, market_name in energy_markets:
                print(f"  - {market_name} (ID: {market_id})")

    finally:
        db.close()


if __name__ == "__main__":
    main()
