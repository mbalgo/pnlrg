"""
Generate Event Probability Analysis Charts for Alphabet MFT

This script generates event probability analysis charts showing the tail behavior
of the Alphabet MFT strategy compared to a normal distribution.

Creates two charts:
1. Short range (0-2 std dev): Standard view for typical events
2. Long range (0-8 std dev): Extended view revealing extreme tail events

Output:
- export/alphabet/mft/charts/alphabet_mft_event_probability_0_2.png
- export/alphabet/mft/charts/alphabet_mft_event_probability_0_8.png
"""

from database import Database
from pathlib import Path
from datetime import date
from windows import (
    WindowDefinition,
    Window,
    generate_x_values,
    compute_event_probability_analysis
)
from components.event_probability_chart import render_event_probability_chart_pair


def main():
    """Generate event probability analysis charts for Alphabet MFT."""

    # Connect to database
    with Database() as db:
        # Get Alphabet MFT program
        program = db.fetch_one("""
            SELECT p.id, p.program_name, p.fund_size, p.target_daily_std_dev, m.manager_name
            FROM programs p
            JOIN managers m ON p.manager_id = m.id
            WHERE p.program_name = 'MFT'
        """)

        if not program:
            print("ERROR: MFT program not found in database")
            return

        program_id = program['id']
        print(f"\nGenerating Event Probability Analysis for {program['manager_name']} {program['program_name']}")
        print(f"Fund Size: ${program['fund_size']:,.0f}")
        print(f"Target Daily Std Dev: {program['target_daily_std_dev']*100:.1f}%")

        # Get data range
        date_range = db.fetch_one("""
            SELECT MIN(date) as min_date, MAX(date) as max_date
            FROM pnl_records
            WHERE program_id = ? AND resolution = 'daily'
        """, (program_id,))

        if not date_range or not date_range['min_date']:
            print("ERROR: No daily data found for MFT program")
            return

        min_date = date.fromisoformat(date_range['min_date'])
        max_date = date.fromisoformat(date_range['max_date'])

        print(f"Data Range: {min_date} to {max_date}")
        print(f"Duration: {(max_date - min_date).days} days\n")

        # Create full-history window
        window_def = WindowDefinition(
            start_date=min_date,
            end_date=max_date,
            program_ids=[program_id],
            benchmark_ids=[],
            name="Full History"
        )
        window = Window(window_def, db)

        # Generate x values for both ranges
        print("Generating x values...")
        x_vals_short = generate_x_values(0, 2, 20)
        x_vals_long = generate_x_values(0, 8, 80)

        # Compute event probability analysis
        print("Computing event probability analysis (0-2 range)...")
        epa_short = compute_event_probability_analysis(window, program_id, x_vals_short, db)

        print("Computing event probability analysis (0-8 range)...")
        epa_long = compute_event_probability_analysis(window, program_id, x_vals_long, db)

        # Print summary statistics
        print(f"\nAnalysis Summary:")
        print(f"  Total Days: {epa_short.total_days:,}")
        print(f"  Gain Days: {epa_short.total_gain_days:,} ({100*epa_short.total_gain_days/epa_short.total_days:.1f}%)")
        print(f"  Loss Days: {epa_short.total_loss_days:,} ({100*epa_short.total_loss_days/epa_short.total_days:.1f}%)")
        print(f"  Realized Std Dev (annualized): {epa_short.realized_std_dev*100:.2f}%")
        if epa_short.used_target_std_dev:
            print(f"  Normalization: Using target std dev ({epa_short.target_std_dev*100:.1f}%)")
        else:
            print(f"  Normalization: Using realized std dev (no target set)")

        # Create output directory
        output_dir = Path('export/alphabet/mft/charts')
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate output paths
        output_path_short = output_dir / 'alphabet_mft_event_probability_0_2.png'
        output_path_long = output_dir / 'alphabet_mft_event_probability_0_8.png'

        # Configuration
        config = {
            'title': f'{program["manager_name"]} {program["program_name"]} - Event Probability Analysis',
            'figsize': (12, 8),
            'dpi': 300
        }

        # Render both charts
        print(f"\nGenerating charts...")
        render_event_probability_chart_pair(
            epa_short, epa_long, config,
            str(output_path_short), str(output_path_long)
        )

        print(f"\nCharts saved:")
        print(f"  Short range (0-2): {output_path_short}")
        print(f"  Long range (0-8): {output_path_long}")

        # Print detailed probability table
        print(f"\n{'='*80}")
        print(f"EVENT PROBABILITY TABLE (Full 0-8 range)")
        print(f"{'='*80}")
        print(f"{'X (std)':>8} | {'P[Gain>X]':>12} | {'P[Loss<-X]':>12} | {'P[Normal]':>12} | {'Gain Days':>10} | {'Loss Days':>10}")
        print(f"{'-'*80}")

        import numpy as np
        for threshold in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0]:
            idx = np.argmin(np.abs(np.array(epa_long.x_values) - threshold))
            actual_x = epa_long.x_values[idx]
            p_gain = epa_long.p_gains[idx]
            p_loss = epa_long.p_losses[idx]
            p_norm = epa_long.p_normal[idx]
            gain_days = p_gain * epa_long.total_days
            loss_days = p_loss * epa_long.total_days

            print(f"{actual_x:>8.2f} | {p_gain*100:>11.4f}% | {p_loss*100:>11.4f}% | {p_norm*100:>11.6f}% | {gain_days:>10.1f} | {loss_days:>10.1f}")

        print(f"{'='*80}")
        print(f"\nKey Insights:")
        # Find where gains exceed normal
        for threshold in [2.0, 3.0, 4.0]:
            idx = np.argmin(np.abs(np.array(epa_long.x_values) - threshold))
            ratio_gain = epa_long.p_gains[idx] / epa_long.p_normal[idx] if epa_long.p_normal[idx] > 0 else float('inf')
            ratio_loss = epa_long.p_losses[idx] / epa_long.p_normal[idx] if epa_long.p_normal[idx] > 0 else float('inf')
            print(f"  At {threshold} std dev: Gains are {ratio_gain:.1f}x normal, Losses are {ratio_loss:.1f}x normal")


if __name__ == "__main__":
    main()
