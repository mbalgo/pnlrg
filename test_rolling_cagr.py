"""
Test script for rolling CAGR chart generation.

This script tests the new rolling CAGR chart component with the Alphabet MFT program.
"""

from database import Database
from components.rolling_cagr_chart import generate_rolling_cagr_chart
from pathlib import Path


def test_rolling_cagr():
    """Test rolling CAGR chart generation with Alphabet MFT data."""

    # Create output directory
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    with Database() as db:
        # Get Alphabet MFT program ID
        program = db.fetch_one("""
            SELECT p.id, p.program_name, m.manager_name
            FROM programs p
            JOIN managers m ON p.manager_id = m.id
            WHERE m.manager_name = 'Alphabet' AND p.program_name = 'MFT'
        """)

        if not program:
            print("ERROR: Alphabet MFT program not found in database")
            return

        print(f"Found program: {program['manager_name']} {program['program_name']} (ID: {program['id']})")
        print()

        # Test 1: 1-year rolling CAGR (no benchmark)
        print("Test 1: 1-year rolling CAGR (no benchmark)")
        print("-" * 60)
        try:
            fig1 = generate_rolling_cagr_chart(
                db=db,
                program_id=program['id'],
                output_path=str(output_dir / "rolling_cagr_1year.pdf"),
                window_months=12,
                benchmarks=None
            )
            print("[PASS] Test 1: 1-year rolling CAGR generated successfully")
            print()
        except Exception as e:
            print(f"[FAIL] Test 1: {e}")
            print()

        # Test 2: 1-year rolling CAGR with SP500 benchmark
        print("Test 2: 1-year rolling CAGR with SP500 benchmark")
        print("-" * 60)
        try:
            fig2 = generate_rolling_cagr_chart(
                db=db,
                program_id=program['id'],
                output_path=str(output_dir / "rolling_cagr_1year_sp500.pdf"),
                window_months=12,
                benchmarks=['sp500']
            )
            print("[PASS] Test 2: 1-year rolling CAGR with SP500 generated successfully")
            print()
        except Exception as e:
            print(f"[FAIL] Test 2: {e}")
            print()

        # Test 3: 6-month rolling CAGR
        print("Test 3: 6-month rolling CAGR (no benchmark)")
        print("-" * 60)
        try:
            fig3 = generate_rolling_cagr_chart(
                db=db,
                program_id=program['id'],
                output_path=str(output_dir / "rolling_cagr_6month.pdf"),
                window_months=6,
                benchmarks=None
            )
            print("[PASS] Test 3: 6-month rolling CAGR generated successfully")
            print()
        except Exception as e:
            print(f"[FAIL] Test 3: {e}")
            print()

        # Test 4: 3-year rolling CAGR with AREIT benchmark
        print("Test 4: 3-year rolling CAGR with AREIT benchmark")
        print("-" * 60)
        try:
            fig4 = generate_rolling_cagr_chart(
                db=db,
                program_id=program['id'],
                output_path=str(output_dir / "rolling_cagr_3year_areit.pdf"),
                window_months=36,
                benchmarks=['areit']
            )
            print("[PASS] Test 4: 3-year rolling CAGR with AREIT generated successfully")
            print()
        except Exception as e:
            print(f"[FAIL] Test 4: {e}")
            print()

        print("=" * 60)
        print(f"All tests completed. Check the '{output_dir}' directory for output files.")
        print("=" * 60)


if __name__ == "__main__":
    test_rolling_cagr()
