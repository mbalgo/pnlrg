"""
Import CTA backtest results from HTML files into database - Version 2.
This version extracts complete historical data and includes benchmarks.
"""

import os
import re
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from database import Database


def parse_fund_size_from_folder(folder_name):
    """Extract fund size from folder name like '100M_30' -> 100000000."""
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
    """
    try:
        return datetime.strptime(date_str.strip(), '%d/%m/%Y')
    except ValueError:
        pass
    return None


def find_complete_data_file(folder_path):
    """
    Find the HTML file containing complete historical data (usually "from 1973").

    Args:
        folder_path: Path to folder (e.g., 100M_30)

    Returns:
        Path to HTML file with most complete data, or None
    """
    main_html = os.path.join(folder_path, "Rise_Capital_Simulation.html")
    if not os.path.exists(main_html):
        return None

    with open(main_html, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the earliest "from XXXX" entry
    # Pattern: <a>from 1973</a> followed by function...load("html/FILENAME.html")
    # Need to handle newlines and whitespace
    pattern = r'from\s+(\d{4})\s*</a>.*?load\("html/(.*?\.html)"\)'
    matches = re.findall(pattern, content, re.DOTALL)

    if not matches:
        return None

    # Find the earliest year
    earliest_year = min(int(year) for year, _ in matches)

    # Find the file for the earliest year
    for year, filename in matches:
        if int(year) == earliest_year:
            html_path = os.path.join(folder_path, "html", filename)
            if os.path.exists(html_path):
                return html_path

    return None


def extract_all_data_from_html(html_file_path):
    """
    Extract complete equity curve data including benchmarks from an HTML file.

    Returns:
        dict with 'dates' and columns like '5@2/20 FedFunds', 'SP500', 'BTOP50', etc.
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

    # Extract header row
    thead = table.find('thead')
    if not thead:
        return None

    headers = []
    for th in thead.find_all('th'):
        headers.append(th.get_text(strip=True))

    # Initialize data structure
    data = {'dates': []}
    for header in headers[1:]:  # Skip 'Date' column
        data[header] = []

    # Extract data rows
    tbody = table.find('tbody')
    if not tbody:
        return None

    for tr in tbody.find_all('tr'):
        cells = tr.find_all(['th', 'td'])
        if len(cells) < 2:
            continue

        date_str = cells[0].get_text(strip=True)
        date = parse_date(date_str)
        if not date:
            continue

        data['dates'].append(date)

        # Extract all column values
        for i, header in enumerate(headers[1:], start=1):
            if i < len(cells):
                value_str = cells[i].get_text(strip=True)
                try:
                    value = float(value_str.replace(',', ''))
                    data[header].append(value)
                except ValueError:
                    data[header].append(None)
            else:
                data[header].append(None)

    return data


def calculate_monthly_returns(dates, values):
    """
    Calculate monthly percentage returns from equity curve.

    Returns:
        Tuple of (starting_date, starting_nav, returns_list)
        where returns_list contains tuples of (date, return_pct)
    """
    if not dates or len(dates) < 2:
        return None, None, []

    starting_date = dates[0]
    starting_nav = values[0]
    returns_list = []

    # Calculate percentage returns starting from the second point
    for i in range(1, len(dates)):
        if values[i] is not None and values[i-1] is not None and values[i-1] != 0:
            return_pct = (values[i] - values[i-1]) / values[i-1]
            returns_list.append((dates[i], return_pct))

    return starting_date, starting_nav, returns_list


def import_folder_v2(db, folder_path, manager_name="Rise Capital Management", program_name="CTA"):
    """
    Import complete data from a folder.

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

    # Find the complete data file
    html_path = find_complete_data_file(folder_path)
    if not html_path:
        print(f"  Could not find complete data file")
        return 0

    print(f"  Using file: {os.path.basename(html_path)}")

    # Extract all data
    all_data = extract_all_data_from_html(html_path)
    if not all_data or not all_data['dates']:
        print(f"  No data extracted")
        return 0

    print(f"  Date range: {all_data['dates'][0].strftime('%Y-%m-%d')} to {all_data['dates'][-1].strftime('%Y-%m-%d')}")
    print(f"  Number of data points: {len(all_data['dates'])}")
    print(f"  Columns found: {', '.join([k for k in all_data.keys() if k != 'dates'])}")

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
        # Update fund size if needed
        db.execute("UPDATE programs SET fund_size = ? WHERE id = ?", (fund_size, program_id))

    total_records = 0
    starting_date = None
    starting_nav = None

    # Import data for each column
    for col_name, values in all_data.items():
        if col_name == 'dates' or not values:
            continue

        # Determine market name and type
        if 'FedFunds' in col_name or '5@2/20' in col_name or '@' in col_name:
            # This is the CTA fund data
            market_name = "Rise"
            asset_class = "CTA Fund"
        elif 'SP500' in col_name or 'S&P500' in col_name:
            market_name = "SP500"
            asset_class = "Equity Index"
        elif 'BTOP50' in col_name:
            market_name = "BTOP50"
            asset_class = "CTA Index"
        elif 'Warren' in col_name or 'Buffet' in col_name or 'Buffett' in col_name:
            market_name = "WarrenBuffet"
            asset_class = "Equity"
        elif 'Winton' in col_name:
            market_name = "Winton"
            asset_class = "CTA Fund"
        elif 'AREIT' in col_name:
            market_name = "AREIT"
            asset_class = "REIT Index"
        else:
            market_name = col_name
            asset_class = "Unknown"

        # Create or get market
        market = db.fetch_one("SELECT id FROM markets WHERE name = ?", (market_name,))
        if not market:
            cursor = db.execute(
                "INSERT INTO markets (name, asset_class, region, currency) VALUES (?, ?, ?, ?)",
                (market_name, asset_class, "Global", "USD")
            )
            market_id = cursor.lastrowid
        else:
            market_id = market['id']

        # Calculate percentage returns
        start_date, start_nav, returns_data = calculate_monthly_returns(all_data['dates'], values)

        # Insert return records (only for the CTA fund, not benchmarks)
        if market_name == "Rise":
            # Store starting metadata for this program
            if start_date and start_nav:
                starting_date = start_date
                starting_nav = start_nav

            records_inserted = 0
            for date, return_pct in returns_data:
                # Check if record already exists
                existing = db.fetch_one(
                    "SELECT id FROM pnl_records WHERE date = ? AND program_id = ? AND market_id = ? AND resolution = ?",
                    (date.strftime('%Y-%m-%d'), program_id, market_id, 'monthly')
                )

                if not existing:
                    db.execute(
                        "INSERT INTO pnl_records (date, market_id, program_id, return, resolution) VALUES (?, ?, ?, ?, ?)",
                        (date.strftime('%Y-%m-%d'), market_id, program_id, return_pct, 'monthly')
                    )
                    records_inserted += 1

            print(f"  Inserted {records_inserted} return records for {market_name}")
            total_records += records_inserted

    # Update program with starting metadata
    if starting_date and starting_nav:
        db.execute(
            "UPDATE programs SET starting_nav = ?, starting_date = ? WHERE id = ?",
            (starting_nav, starting_date.strftime('%Y-%m-%d'), program_id)
        )
        print(f"  Updated program with starting NAV: ${starting_nav:,.0f} on {starting_date.strftime('%Y-%m-%d')}")

    return total_records


def find_all_from_year_files(folder_path):
    """
    Find all 'from YYYY' HTML files by parsing the main HTML file.

    Returns:
        List of tuples (year, html_file_path)
    """
    main_html = os.path.join(folder_path, "Rise_Capital_Simulation.html")
    if not os.path.exists(main_html):
        return []

    with open(main_html, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all "from YYYY" entries with their corresponding HTML files
    pattern = r'from\s+(\d{4})\s*</a>.*?load\("html/(.*?\.html)"\)'
    matches = re.findall(pattern, content, re.DOTALL)

    files = []
    for year, filename in matches:
        html_path = os.path.join(folder_path, "html", filename)
        if os.path.exists(html_path):
            files.append((int(year), html_path))

    # Sort by year
    files.sort(key=lambda x: x[0])
    return files


def find_benchmark_data(folder_path, benchmark_name_pattern):
    """
    Find the earliest 'from YYYY' file that contains a specific benchmark.

    Args:
        folder_path: Path to folder (e.g., 100M_30)
        benchmark_name_pattern: Pattern to search for in column names

    Returns:
        Tuple of (html_path, all_data) or (None, None) if not found
    """
    from_year_files = find_all_from_year_files(folder_path)

    for year, html_path in from_year_files:
        all_data = extract_all_data_from_html(html_path)
        if not all_data:
            continue

        # Check if benchmark exists in this file
        for col_name in all_data.keys():
            if col_name == 'dates':
                continue
            if benchmark_name_pattern.lower() in col_name.lower():
                print(f"  Found {benchmark_name_pattern} in 'from {year}' file")
                return html_path, all_data

    return None, None


def import_benchmarks(db, base_dir):
    """
    Import benchmark data (SP500, BTOP50, AREIT, Leading Competitor).
    Scans through 'from YYYY' files to find when each benchmark starts.
    Imports from 100M_30 folder since benchmark data is identical across fund sizes.

    Args:
        db: Database instance
        base_dir: Base directory containing CTA simulation results

    Returns:
        Number of benchmark records imported
    """
    # Find 100M_30 folder
    folder_path = os.path.join(base_dir, "100M_30")
    if not os.path.exists(folder_path):
        print("Could not find 100M_30 folder for benchmark import")
        return 0

    print(f"\n{'='*60}")
    print("Importing Benchmark Data")
    print(f"{'='*60}\n")

    # Get Benchmarks program
    benchmarks_program = db.fetch_one("SELECT id FROM programs WHERE program_name = 'Benchmarks'")
    if not benchmarks_program:
        print("Error: Benchmarks program not found")
        return 0

    benchmarks_program_id = benchmarks_program['id']
    total_records = 0

    # Process each benchmark
    benchmark_definitions = [
        ('SP500', 'SP500', 'Equity Index'),
        ('BTOP50', 'BTOP50', 'CTA Index'),
        ('AREIT', 'AREIT', 'REIT Index'),
        ('Leading Competitor', 'Winton', 'CTA Fund')
    ]

    for market_name, col_pattern, asset_class in benchmark_definitions:
        print(f"\nSearching for {market_name}...")

        # Find the HTML file containing this benchmark
        html_path, all_data = find_benchmark_data(folder_path, col_pattern)

        if not html_path or not all_data:
            print(f"  Warning: Could not find data for {market_name}")
            continue

        # Find matching column in the data
        matching_col = None
        for col_name in all_data.keys():
            if col_name == 'dates':
                continue
            if col_pattern.lower() in col_name.lower():
                matching_col = col_name
                break

        if not matching_col:
            print(f"  Warning: Could not find column for {market_name}")
            continue

        values = all_data[matching_col]
        if not values:
            print(f"  Warning: No values found for {market_name}")
            continue

        # Create or get market
        market = db.fetch_one("SELECT id FROM markets WHERE name = ?", (market_name,))
        if not market:
            cursor = db.execute(
                "INSERT INTO markets (name, asset_class, region, currency, is_benchmark) VALUES (?, ?, ?, ?, ?)",
                (market_name, asset_class, "Global", "USD", 1)
            )
            market_id = cursor.lastrowid
        else:
            market_id = market['id']
            # Update to mark as benchmark
            db.execute("UPDATE markets SET is_benchmark = 1 WHERE id = ?", (market_id,))

        # Calculate percentage returns
        start_date, start_nav, returns_data = calculate_monthly_returns(all_data['dates'], values)

        if not returns_data:
            print(f"  Warning: No return data calculated for {market_name}")
            continue

        # Insert return records
        records_inserted = 0
        for date, return_pct in returns_data:
            # Check if record already exists
            existing = db.fetch_one(
                "SELECT id FROM pnl_records WHERE date = ? AND program_id = ? AND market_id = ? AND resolution = ?",
                (date.strftime('%Y-%m-%d'), benchmarks_program_id, market_id, 'monthly')
            )

            if not existing:
                db.execute(
                    "INSERT INTO pnl_records (date, market_id, program_id, return, resolution) VALUES (?, ?, ?, ?, ?)",
                    (date.strftime('%Y-%m-%d'), market_id, benchmarks_program_id, return_pct, 'monthly')
                )
                records_inserted += 1

        print(f"  {market_name:20} {records_inserted:4} records  ({start_date.strftime('%Y-%m-%d')} to {returns_data[-1][0].strftime('%Y-%m-%d')})")
        total_records += records_inserted

    return total_records


def import_all_30_market_folders_v2(base_dir, db):
    """Import all folders with 30 markets."""
    folders_to_process = []

    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and '_30' in item and not item.endswith('.zip'):
            folders_to_process.append(item_path)

    total_records = 0
    for folder_path in sorted(folders_to_process):
        records = import_folder_v2(db, folder_path)
        total_records += records

    return total_records


if __name__ == "__main__":
    cta_results_dir = r"D:\CTA\CTA_Simulation_Results"

    print("Initializing database...")
    db = Database("pnlrg.db")

    # Don't reinitialize schema if it already exists
    if not os.path.exists("pnlrg.db"):
        db.initialize_schema()
    else:
        db.connect()
        print("Using existing database")

    print(f"\nImporting Rise CTA data from {cta_results_dir}")
    total_records = import_all_30_market_folders_v2(cta_results_dir, db)

    # Import benchmark data
    benchmark_records = import_benchmarks(db, cta_results_dir)

    print(f"\n{'='*60}")
    print(f"Import complete!")
    print(f"  Rise CTA records:  {total_records}")
    print(f"  Benchmark records: {benchmark_records}")
    print(f"  Total records:     {total_records + benchmark_records}")
    print(f"{'='*60}")

    db.close()
