"""
Batch Component Generation Script

Generates all registered components for a specific manager/program combination.
Features smart caching with manifest tracking to avoid unnecessary regeneration.

Usage:
    python generate_all_components.py --manager alphabet --program mft
    python generate_all_components.py --manager alphabet --program mft --force
    python generate_all_components.py --manager alphabet --program mft --category charts
    python generate_all_components.py --manager alphabet --program mft --components equity_curve,cumulative_windows_5yr
"""

import argparse
from pathlib import Path
from datetime import datetime
from database import Database
from component_registry import (
    get_registry,
    slugify,
    compute_data_hash,
    load_manifest,
    save_manifest,
    should_regenerate_component
)
import register_components  # Import to trigger component registration


def get_program_data_range(db, program_id: int) -> dict:
    """
    Get the date range for a program's data.

    Args:
        db: Database instance
        program_id: Program ID

    Returns:
        Dict with 'start_date' and 'end_date' strings
    """
    result = db.fetch_one("""
        SELECT
            MIN(date) as start_date,
            MAX(date) as end_date
        FROM pnl_records
        WHERE program_id = ?
    """, (program_id,))

    if not result or not result['start_date']:
        raise ValueError(f"No data found for program {program_id}")

    return {
        'start_date': result['start_date'],
        'end_date': result['end_date']
    }


def generate_component_file(
    db,
    component,
    manager_slug: str,
    program_slug: str,
    program_id: int,
    output_dir: Path,
    variant: str = None,
    benchmarks: list = None,
    **kwargs
) -> tuple:
    """
    Generate a single component file.

    Args:
        db: Database instance
        component: ComponentDefinition
        manager_slug: Manager slug
        program_slug: Program slug
        program_id: Program ID
        output_dir: Output directory path
        variant: Optional variant name
        benchmarks: Optional list of benchmark names
        **kwargs: Additional parameters for component function

    Returns:
        Tuple of (filename, success, message)
    """
    try:
        # Generate output path with category subfolder
        output_path = component.get_output_path(
            base_dir=output_dir,
            manager_slug=manager_slug,
            program_slug=program_slug,
            variant=variant,
            benchmarks=benchmarks
        )

        # Ensure category subfolder exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get just the filename for return value
        filename = output_path.name

        # Call component generation function
        # Each function should handle its own file saving
        result = component.function(
            db=db,
            program_id=program_id,
            output_path=str(output_path),
            benchmarks=benchmarks,
            variant=variant,
            **kwargs
        )

        return (filename, True, "Generated successfully")

    except Exception as e:
        return (filename if 'filename' in locals() else 'unknown', False, str(e))


def main():
    parser = argparse.ArgumentParser(
        description='Generate all components for a manager/program'
    )
    parser.add_argument(
        '--manager',
        required=True,
        help='Manager name (e.g., "Alphabet", "Rise Capital")'
    )
    parser.add_argument(
        '--program',
        required=True,
        help='Program name (e.g., "MFT", "CTA_100M_30")'
    )
    parser.add_argument(
        '--category',
        choices=['charts', 'tables', 'text', 'all'],
        default='all',
        help='Generate only specific category'
    )
    parser.add_argument(
        '--components',
        help='Comma-separated list of specific component IDs to generate'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration even if files are up-to-date'
    )
    parser.add_argument(
        '--output-dir',
        help='Custom output directory (default: export/{manager}/{program})'
    )

    args = parser.parse_args()

    # Initialize database
    db = Database()
    registry = get_registry()

    try:
        # Get manager and program from database
        manager = db.fetch_one(
            "SELECT id, manager_name FROM managers WHERE manager_name = ?",
            (args.manager,)
        )

        if not manager:
            print(f"Error: Manager '{args.manager}' not found in database")
            return 1

        program = db.fetch_one("""
            SELECT id, program_name
            FROM programs
            WHERE program_name = ?
            AND manager_id = ?
        """, (args.program, manager['id']))

        if not program:
            print(f"Error: Program '{args.program}' not found for manager '{args.manager}'")
            return 1

        program_id = program['id']
        manager_slug = slugify(manager['manager_name'])
        program_slug = slugify(program['program_name'])

        # Determine output directory
        if args.output_dir:
            output_dir = Path(args.output_dir)
        else:
            output_dir = Path('export') / manager_slug / program_slug

        output_dir.mkdir(parents=True, exist_ok=True)

        # Load existing manifest
        manifest = load_manifest(output_dir)

        # Get current data range and hash
        data_range = get_program_data_range(db, program_id)
        current_data_hash = compute_data_hash(data_range, db, program_id)

        print("=" * 70)
        print(f"GENERATING COMPONENTS: {manager['manager_name']} - {program['program_name']}")
        print("=" * 70)
        print(f"Manager: {manager['manager_name']} (ID: {manager['id']})")
        print(f"Program: {program['program_name']} (ID: {program_id})")
        print(f"Data Range: {data_range['start_date']} to {data_range['end_date']}")
        print(f"Output Directory: {output_dir}")
        print(f"Force Regeneration: {args.force}")
        print()

        # Determine which components to generate
        if args.components:
            # Specific components requested
            component_ids = [c.strip() for c in args.components.split(',')]
            components = [registry.get(cid) for cid in component_ids]
            components = [c for c in components if c is not None]

            if len(components) != len(component_ids):
                print(f"Warning: Some component IDs not found in registry")
        else:
            # All components (optionally filtered by category)
            if args.category == 'all':
                components = registry.list_all()
            elif args.category == 'charts':
                components = registry.list_charts()
            elif args.category == 'tables':
                components = registry.list_tables()
            elif args.category == 'text':
                components = registry.list_text_blocks()

        print(f"Components to process: {len(components)}")
        print()

        # Track statistics
        stats = {
            'generated': 0,
            'cached': 0,
            'failed': 0,
            'skipped': 0
        }

        # Update manifest metadata
        manifest['generated_date'] = datetime.now().isoformat()
        manifest['manager'] = manager_slug
        manifest['program'] = program_slug
        manifest['data_range'] = data_range

        if 'components' not in manifest:
            manifest['components'] = {}

        # Generate each component
        for component in components:
            print(f"[{component.category.upper()}] {component.name} ({component.id})")

            # Handle benchmark combinations
            if component.benchmark_support and component.benchmark_combinations:
                benchmark_combos = component.benchmark_combinations
            else:
                benchmark_combos = [[]]  # No benchmarks

            # Handle variants
            variants = component.variants if component.variants else [None]

            # Generate all combinations
            for variant in variants:
                for benchmarks in benchmark_combos:
                    # Get full output path with category subfolder
                    output_path = component.get_output_path(
                        base_dir=output_dir,
                        manager_slug=manager_slug,
                        program_slug=program_slug,
                        variant=variant,
                        benchmarks=benchmarks if benchmarks else None
                    )

                    filename = output_path.name

                    # Check if regeneration needed
                    if should_regenerate_component(
                        output_path,
                        manifest,
                        component.id,
                        current_data_hash,
                        component.version,
                        force=args.force
                    ):
                        # Generate
                        print(f"  Generating: {filename}... ", end='')
                        filename, success, message = generate_component_file(
                            db,
                            component,
                            manager_slug,
                            program_slug,
                            program_id,
                            output_dir,
                            variant=variant,
                            benchmarks=benchmarks if benchmarks else None
                        )

                        if success:
                            print("[OK]")
                            stats['generated'] += 1

                            # Update manifest
                            manifest['components'][filename] = {
                                'component_id': component.id,
                                'variant': variant,
                                'benchmarks': benchmarks,
                                'generated_date': datetime.now().isoformat(),
                                'data_hash': current_data_hash,
                                'code_version': component.version
                            }
                        else:
                            print(f"[FAILED] {message}")
                            stats['failed'] += 1
                    else:
                        # Use cached version
                        print(f"  Cached: {filename}")
                        stats['cached'] += 1

        # Save updated manifest
        save_manifest(output_dir, manifest)

        # Print summary
        print()
        print("=" * 70)
        print("GENERATION SUMMARY")
        print("=" * 70)
        print(f"Generated: {stats['generated']}")
        print(f"Cached:    {stats['cached']}")
        print(f"Failed:    {stats['failed']}")
        print(f"Skipped:   {stats['skipped']}")
        print(f"Total:     {stats['generated'] + stats['cached'] + stats['failed'] + stats['skipped']}")
        print()
        print(f"Output Directory: {output_dir}")
        print(f"Manifest Updated: {output_dir / 'manifest.json'}")

        return 0 if stats['failed'] == 0 else 1

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()


if __name__ == '__main__':
    exit(main())
