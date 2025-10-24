"""
Generate all rolling CAGR charts for Alphabet MFT strategy.

This script generates all 9 window size variants × 3 benchmark combinations = 27 charts.
"""

from database import Database
from components.rolling_cagr_chart import generate_rolling_cagr_chart
from pathlib import Path
import time


def generate_all_rolling_cagr_charts():
    """Generate all rolling CAGR chart combinations for Alphabet MFT."""

    # Output directory
    output_dir = Path("export/alphabet/mft/charts")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("GENERATING ALL ROLLING CAGR CHARTS FOR ALPHABET MFT")
    print("=" * 80)
    print()

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

        print(f"Program: {program['manager_name']} {program['program_name']} (ID: {program['id']})")
        print(f"Output directory: {output_dir.absolute()}")
        print()

        # Define all window sizes
        window_configs = [
            (1, "1month"),
            (2, "2month"),
            (3, "3month"),
            (6, "6month"),
            (12, "1year"),
            (24, "2year"),
            (36, "3year"),
            (60, "5year"),
            (120, "10year"),
        ]

        # Define benchmark combinations
        benchmark_configs = [
            (None, ""),
            (['sp500'], "_sp500"),
            (['areit'], "_areit"),
        ]

        total_charts = len(window_configs) * len(benchmark_configs)
        current = 0
        successful = 0
        failed = 0
        start_time = time.time()

        # Generate all combinations
        for window_months, window_label in window_configs:
            for benchmarks, benchmark_suffix in benchmark_configs:
                current += 1

                # Build output filename
                filename = f"alphabet_mft_rolling_cagr_{window_label}{benchmark_suffix}.pdf"
                output_path = output_dir / filename

                # Display progress
                benchmark_desc = "no benchmark" if benchmarks is None else f"with {benchmarks[0].upper()}"
                print(f"[{current}/{total_charts}] Generating {window_label} rolling CAGR ({benchmark_desc})...")

                try:
                    generate_rolling_cagr_chart(
                        db=db,
                        program_id=program['id'],
                        output_path=str(output_path),
                        window_months=window_months,
                        benchmarks=benchmarks
                    )
                    successful += 1
                    print(f"    [SUCCESS] Saved to: {filename}")

                except Exception as e:
                    failed += 1
                    print(f"    [FAILED] Error: {e}")

                print()

        # Summary
        elapsed = time.time() - start_time
        print("=" * 80)
        print("GENERATION COMPLETE")
        print("=" * 80)
        print(f"Total charts: {total_charts}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Time elapsed: {elapsed:.1f} seconds")
        print(f"Average time per chart: {elapsed/total_charts:.2f} seconds")
        print()
        print(f"All charts saved to: {output_dir.absolute()}")
        print("=" * 80)


if __name__ == "__main__":
    generate_all_rolling_cagr_charts()
