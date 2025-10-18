"""Check what columns are available in the HTML files."""

from import_cta_results_v2 import extract_all_data_from_html, find_complete_data_file
import os

folder = r'D:\CTA\CTA_Simulation_Results\100M_30'
html_path = find_complete_data_file(folder)

print(f"Reading: {os.path.basename(html_path)}\n")

data = extract_all_data_from_html(html_path)

print("Columns found:")
print("="*50)
for col in data.keys():
    if col != 'dates':
        print(f"  {col}")
