"""
Test script for detailed fees Excel component.

This tests that the component can be called via the registry.
"""

from database import Database
from component_registry import get_registry
from datetime import date
import os
import register_components  # Force registration

def test_detailed_fees_component():
    """Test the detailed fees Excel component."""

    with Database() as db:
        # Get Alpha Bet MFT program
        program = db.fetch_one("""
            SELECT p.id
            FROM programs p
            JOIN managers m ON p.manager_id = m.id
            WHERE m.manager_name = 'Alpha Bet' AND p.program_name = 'MFT'
        """)

        if not program:
            print("Error: Alpha Bet MFT program not found")
            return

        # Get Alpha Bet Standard scenario
        scenario = db.fetch_one("""
            SELECT id FROM fee_scenarios WHERE scenario_name = 'Alpha Bet Standard'
        """)

        if not scenario:
            print("Error: Alpha Bet Standard scenario not found")
            return

        # Get the component from registry
        registry = get_registry()
        component_def = registry.get('detailed_fees_excel')

        if not component_def:
            print("Error: detailed_fees_excel component not found in registry")
            return

        print(f"Found component: {component_def.name}")
        print(f"Description: {component_def.description}")
        print(f"Category: {component_def.category}")
        print(f"Version: {component_def.version}")
        print()

        # Test output path
        output_path = 'test_output/alpha_bet_mft_detailed_fees_test.xlsx'

        # Create directory if needed
        os.makedirs('test_output', exist_ok=True)

        # Call the component function
        print(f"Generating detailed fees Excel to: {output_path}")
        result = component_def.function(
            db=db,
            program_id=program['id'],
            scenario_id=scenario['id'],
            output_path=output_path,
            fund_size=10_000_000,
            start_date=date(2006, 1, 3),
            end_date=date(2025, 10, 17)
        )

        print(f"\n[SUCCESS] Component test completed!")
        print(f"Output file: {result}")

        # Verify file exists
        if os.path.exists(result):
            file_size = os.path.getsize(result)
            print(f"File size: {file_size:,} bytes")
        else:
            print("[WARNING] Output file not found")

if __name__ == "__main__":
    test_detailed_fees_component()
