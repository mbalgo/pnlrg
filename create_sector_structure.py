"""
Create sector structure for MFT and CTA strategies.

Creates two grouping schemes:
1. 'mft_sector' - Only sectors with markets (5 sectors, 17 markets mapped)
2. 'cta_sector' - All sectors including empty ones (9 sectors, 0 markets mapped)
"""

from database import Database

# Sector definitions
MFT_SECTORS = [
    "Energy",
    "Base Metal",
    "Fixed Income",
    "Foreign Exchange",
    "Equity Index"
]

CTA_SECTORS = [
    "Energy",
    "Base Metal",
    "Precious Metal",
    "Crop",
    "Soft",
    "Meat",
    "Fixed Income",
    "Foreign Exchange",
    "Equity Index"
]

# Market to sector mappings for MFT
MFT_MARKET_MAPPINGS = {
    "Energy": ["WTI", "ULSD Diesel", "Brent"],
    "Base Metal": ["Ali", "Copper", "Zinc"],
    "Fixed Income": ["10y bond", "T-Bond", "Gilts 10y", "KTB 10s"],
    "Foreign Exchange": ["USDKRW"],
    "Equity Index": ["ASX 200", "DAX", "CAC 40", "Kospi 200", "TX index", "WIG 20"]
}


def create_sectors(db, grouping_name, sector_names):
    """Create sector definitions for a grouping."""
    print(f"\n=== Creating '{grouping_name}' sectors ===")

    sector_ids = {}

    for sector_name in sector_names:
        # Check if already exists
        existing = db.fetch_one(
            "SELECT id FROM sectors WHERE grouping_name = ? AND sector_name = ?",
            (grouping_name, sector_name)
        )

        if existing:
            print(f"[INFO] Sector already exists: {grouping_name} / {sector_name} (ID: {existing['id']})")
            sector_ids[sector_name] = existing['id']
        else:
            cursor = db.execute(
                "INSERT INTO sectors (grouping_name, sector_name) VALUES (?, ?)",
                (grouping_name, sector_name)
            )
            sector_id = cursor.lastrowid
            sector_ids[sector_name] = sector_id
            print(f"[OK] Created sector: {grouping_name} / {sector_name} (ID: {sector_id})")

    return sector_ids


def create_market_mappings(db, grouping_name, mappings):
    """Create market-to-sector mappings."""
    print(f"\n=== Creating market mappings for '{grouping_name}' ===")

    # Get sector IDs for this grouping
    sectors = db.fetch_all(
        "SELECT id, sector_name FROM sectors WHERE grouping_name = ?",
        (grouping_name,)
    )
    sector_lookup = {s['sector_name']: s['id'] for s in sectors}

    total_mappings = 0

    for sector_name, market_names in mappings.items():
        sector_id = sector_lookup.get(sector_name)

        if not sector_id:
            print(f"[ERROR] Sector not found: {sector_name}")
            continue

        print(f"\nSector: {sector_name} (ID: {sector_id})")

        for market_name in market_names:
            # Get market ID
            market = db.fetch_one(
                "SELECT id FROM markets WHERE name = ?",
                (market_name,)
            )

            if not market:
                print(f"  [ERROR] Market not found: {market_name}")
                continue

            market_id = market['id']

            # Check if mapping already exists
            existing = db.fetch_one(
                "SELECT 1 FROM market_sector_mapping WHERE market_id = ? AND sector_id = ?",
                (market_id, sector_id)
            )

            if existing:
                print(f"  [INFO] Mapping already exists: {market_name}")
            else:
                db.execute(
                    "INSERT INTO market_sector_mapping (market_id, sector_id) VALUES (?, ?)",
                    (market_id, sector_id)
                )
                print(f"  [OK] Mapped: {market_name} (market_id={market_id})")
                total_mappings += 1

    print(f"\n[INFO] Created {total_mappings} new mappings")
    return total_mappings


def verify_structure(db):
    """Verify the created sector structure."""
    print("\n" + "="*60)
    print("=== Verification ===")
    print("="*60)

    # Count sectors by grouping
    groupings = db.fetch_all(
        """SELECT grouping_name, COUNT(*) as count
           FROM sectors
           GROUP BY grouping_name
           ORDER BY grouping_name"""
    )

    print("\nSectors by Grouping:")
    for row in groupings:
        print(f"  {row['grouping_name']}: {row['count']} sectors")

    # Show MFT sector details with market counts
    print("\n--- 'mft_sector' Details ---")
    mft_sectors = db.fetch_all(
        """SELECT s.sector_name, COUNT(msm.market_id) as market_count
           FROM sectors s
           LEFT JOIN market_sector_mapping msm ON s.id = msm.sector_id
           WHERE s.grouping_name = 'mft_sector'
           GROUP BY s.id, s.sector_name
           ORDER BY s.sector_name"""
    )

    for row in mft_sectors:
        print(f"  {row['sector_name']:20s}: {row['market_count']} markets")

    # Show CTA sector details (should all be 0 markets)
    print("\n--- 'cta_sector' Details ---")
    cta_sectors = db.fetch_all(
        """SELECT s.sector_name, COUNT(msm.market_id) as market_count
           FROM sectors s
           LEFT JOIN market_sector_mapping msm ON s.id = msm.sector_id
           WHERE s.grouping_name = 'cta_sector'
           GROUP BY s.id, s.sector_name
           ORDER BY s.sector_name"""
    )

    for row in cta_sectors:
        print(f"  {row['sector_name']:20s}: {row['market_count']} markets")

    # Show detailed market assignments for MFT
    print("\n--- MFT Market Assignments ---")
    assignments = db.fetch_all(
        """SELECT s.sector_name, m.name as market_name
           FROM market_sector_mapping msm
           JOIN sectors s ON msm.sector_id = s.id
           JOIN markets m ON msm.market_id = m.id
           WHERE s.grouping_name = 'mft_sector'
           ORDER BY s.sector_name, m.name"""
    )

    current_sector = None
    for row in assignments:
        if row['sector_name'] != current_sector:
            current_sector = row['sector_name']
            print(f"\n  {current_sector}:")
        print(f"    - {row['market_name']}")

    print("\n" + "="*60)


def main():
    """Main workflow."""
    db = Database()

    try:
        # Create MFT sectors
        mft_sector_ids = create_sectors(db, 'mft_sector', MFT_SECTORS)

        # Create CTA sectors
        cta_sector_ids = create_sectors(db, 'cta_sector', CTA_SECTORS)

        # Create MFT market mappings
        total_mappings = create_market_mappings(db, 'mft_sector', MFT_MARKET_MAPPINGS)

        # Verify
        verify_structure(db)

        print("\n[OK] Sector structure created successfully")

    except Exception as e:
        print(f"\n[ERROR] Failed to create sector structure: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
