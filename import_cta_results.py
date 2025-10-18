"""
Import CTA backtest results from HTML files into database.

This script parses HTML files from the CTA_Simulation_Results directory,
extracts equity curve data, calculates monthly P&L, and imports into the database.
"""

import os
import re
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from database import Database


def parse_fund_size_from_folder(folder_name):
    """
    Extract fund size from folder name like '100M_30' -> 100000000.

    Args:
        folder_name: Folder name like '100M_30', '1000M_30', etc.

    Returns:
        Fund size in dollars as float
    """
    match = re.match(r'(\d+)M_(\d+)', folder_name)
    if match:
        size_millions = float(match.group(1))
        num_markets = int(match.group(2))
        return size_millions * 1_000_000, num_markets
    return None, None


def parse_date(date_str):
    """
    Parse date string from HTML tables.
    Handles formats like: '2/01/1990', '31/01/1990'

    Args:
        date_str: Date string from HTML

    Returns:
        datetime object or None
    """
    # Try DD/MM/YYYY format
    try:
        return datetime.strptime(date_str.strip(), '%d/%m/%Y')
    except ValueError:
        pass

    # Try D/MM/YYYY format
    try:
        return datetime.strptime(date_str.strip(), '%d/%m/%Y')
    except ValueError:
        pass

    return None


def extract_equity_curve_from_html(html_file_path):
    """
    Extract equity curve data from an HTML file.

    Args:
        html_file_path: Path to HTML file

    Returns:
        dict with keys: 'dates', 'program_values' (5@2/20 FedFunds),
        and benchmark values if available
    """
    with open(html_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')

    # Find the "Plot Data" section
    plot_data_header = soup.find('h2', string=re.compile('Plot Data'))
    if not plot_data_header:
        return None

    # Find the table after the "Plot Data" header
    table = plot_data_header.find_next('table')
    if not table:
        return None

    # Extract header row to find column indices
    thead = table.find('thead')
    if not thead:
        return None

    headers = []
    for th in thead.find_all('th'):
        headers.append(th.get_text(strip=True))

    # Find the column index for the program (typically "5@2/20 FedFunds (adj)")
    program_col_idx = None
    for idx, header in enumerate(headers):
        if 'FedFunds' in header or '5@2/20' in header:
            program_col_idx = idx
            break

    if program_col_idx is None:
        return None

    # Extract data rows
    tbody = table.find('tbody')
    if not tbody:
        return None

    dates = []
    values = []

    for tr in tbody.find_all('tr'):
        cells = tr.find_all(['th', 'td'])
        if len(cells) <= program_col_idx:
            continue

        date_str = cells[0].get_text(strip=True)
        value_str = cells[program_col_idx].get_text(strip=True)

        date = parse_date(date_str)
        if not date:
            continue

        # Parse value (remove commas)
        try:
            value = float(value_str.replace(',', ''))
        except ValueError:
            continue

        dates.append(date)
        values.append(value)

    return {
        'dates': dates,
        'values': values
    }


def calculate_monthly_pnl(dates, values):
    """
    Calculate monthly P&L from equity curve.

    Args:
        dates: List of datetime objects
        values: List of equity curve values

    Returns:
        List of tuples (date, pnl) for each month
    """
    if not dates or len(dates) < 2:
        return []

    pnl_data = []

    for i in range(1, len(dates)):
        pnl = values[i] - values[i-1]
        pnl_data.append((dates[i], pnl))

    return pnl_data


def import_folder(db, folder_path, manager_name="Rise Capital Management", program_name="CTA"):
    """
    Import data from a single folder (e.g., 100M_30).

    Args:
        db: Database instance
        folder_path: Path to folder containing HTML files
        manager_name: Name of the manager
        program_name: Name of the program

    Returns:
        Number of records imported
    """
    folder_name = os.path.basename(folder_path)
    fund_size, num_markets = parse_fund_size_from_folder(folder_name)

    if fund_size is None:
        print(f"Could not parse folder name: {folder_name}")
        return 0

    print(f"\nProcessing {folder_name}: ${fund_size:,.0f} with {num_markets} markets")

    # Create or get manager
    manager = db.fetch_one("SELECT id FROM managers WHERE manager_name = ?", (manager_name,))
    if not manager:
        cursor = db.execute("INSERT INTO managers (manager_name) VALUES (?)", (manager_name,))
        manager_id = cursor.lastrowid
    else:
        manager_id = manager['id']

    # Create or get program
    program_lookup = f"{program_name}_{folder_name}"
    program = db.fetch_one("SELECT id FROM programs WHERE program_name = ?", (program_lookup,))
    if not program:
        cursor = db.execute(
            "INSERT INTO programs (program_name, fund_size, manager_id) VALUES (?, ?, ?)",
            (program_lookup, fund_size, manager_id)
        )
        program_id = cursor.lastrowid
    else:
        program_id = program['id']

    # Find all HTML files in the html subdirectory
    html_dir = os.path.join(folder_path, 'html')
    if not os.path.exists(html_dir):
        print(f"No html directory found in {folder_path}")
        return 0

    # For now, let's just process one representative file
    # We can expand this to process all files later
    html_files = [f for f in os.listdir(html_dir) if f.endswith('.html')]

    if not html_files:
        print(f"No HTML files found in {html_dir}")
        return 0

    # Process the first file that has equity curve data
    for html_file in html_files:
        html_path = os.path.join(html_dir, html_file)
        equity_data = extract_equity_curve_from_html(html_path)

        if equity_data:
            print(f"Found equity curve data in {html_file}")
            print(f"  Date range: {equity_data['dates'][0]} to {equity_data['dates'][-1]}")
            print(f"  Number of data points: {len(equity_data['dates'])}")

            # Calculate monthly P&L
            pnl_data = calculate_monthly_pnl(equity_data['dates'], equity_data['values'])

            # For now, we'll insert aggregate P&L (no market breakdown yet)
            # Since we don't have per-market data, we'll create a single "aggregate" market
            market = db.fetch_one("SELECT id FROM markets WHERE name = ?", ("Aggregate",))
            if not market:
                cursor = db.execute(
                    "INSERT INTO markets (name, asset_class, region, currency) VALUES (?, ?, ?, ?)",
                    ("Aggregate", "Mixed", "Global", "USD")
                )
                market_id = cursor.lastrowid
            else:
                market_id = market['id']

            # Insert P&L records
            records_inserted = 0
            for date, pnl in pnl_data:
                # Check if record already exists
                existing = db.fetch_one(
                    "SELECT id FROM pnl_records WHERE date = ? AND program_id = ? AND market_id = ?",
                    (date.strftime('%Y-%m-%d'), program_id, market_id)
                )

                if not existing:
                    db.execute(
                        "INSERT INTO pnl_records (date, market_id, program_id, pnl) VALUES (?, ?, ?, ?)",
                        (date.strftime('%Y-%m-%d'), market_id, program_id, pnl)
                    )
                    records_inserted += 1

            print(f"  Inserted {records_inserted} P&L records")
            return records_inserted

    print(f"No equity curve data found in any HTML files")
    return 0


def import_all_30_market_folders(base_dir, db):
    """
    Import all folders with 30 markets from the base directory.

    Args:
        base_dir: Base directory containing simulation results
        db: Database instance

    Returns:
        Total number of records imported
    """
    folders_to_process = []

    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and '_30' in item and not item.endswith('.zip'):
            # Extract fund size to filter
            fund_size, _ = parse_fund_size_from_folder(item)
            if fund_size and fund_size >= 50_000_000:  # Only process 50M and above
                folders_to_process.append(item_path)

    total_records = 0
    for folder_path in sorted(folders_to_process):
        records = import_folder(db, folder_path)
        total_records += records

    return total_records


if __name__ == "__main__":
    # Path to CTA simulation results
    cta_results_dir = r"D:\CTA\CTA_Simulation_Results"

    # Initialize database
    print("Initializing database...")
    db = Database("pnlrg.db")
    db.initialize_schema()

    # Import data
    print(f"\nImporting data from {cta_results_dir}")
    total_records = import_all_30_market_folders(cta_results_dir, db)

    print(f"\n{'='*60}")
    print(f"Import complete! Total records inserted: {total_records}")
    print(f"{'='*60}")

    db.close()
