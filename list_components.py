"""
Component Discovery Tool

List all registered components with their metadata, optionally filtered by category
or manager/program combination.

Usage:
    python list_components.py
    python list_components.py --category charts
    python list_components.py --manager alphabet --program mft
"""

import argparse
from component_registry import get_registry
import register_components  # Import to trigger component registration


def format_benchmarks(benchmark_combinations):
    """Format benchmark combinations for display."""
    if not benchmark_combinations or benchmark_combinations == [[]]:
        return "No benchmarks"

    formatted = []
    for combo in benchmark_combinations:
        if not combo:
            formatted.append("(none)")
        else:
            formatted.append(", ".join(combo))

    return "; ".join(formatted)


def print_component(component, verbose=False):
    """Print component information."""
    print(f"\n[{component.category.upper()}] {component.name}")
    print(f"  ID: {component.id}")
    print(f"  Description: {component.description}")
    print(f"  Version: {component.version}")

    if component.benchmark_support:
        print(f"  Benchmarks: {format_benchmarks(component.benchmark_combinations)}")
    else:
        print(f"  Benchmarks: Not supported")

    if component.variants:
        print(f"  Variants: {', '.join(component.variants)}")

    if verbose and component.parameters:
        print(f"  Parameters: {component.parameters}")


def main():
    parser = argparse.ArgumentParser(
        description='List available components in the registry'
    )
    parser.add_argument(
        '--category',
        choices=['charts', 'tables', 'text', 'all'],
        default='all',
        help='Filter by component category'
    )
    parser.add_argument(
        '--manager',
        help='Filter by manager name (requires --program)'
    )
    parser.add_argument(
        '--program',
        help='Filter by program name (requires --manager)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed information'
    )

    args = parser.parse_args()

    # Validate arguments
    if (args.manager and not args.program) or (args.program and not args.manager):
        print("Error: --manager and --program must be used together")
        return 1

    # Get registry
    registry = get_registry()

    # Get components to display
    if args.category == 'all':
        components = registry.list_all()
        category_name = "All Components"
    elif args.category == 'charts':
        components = registry.list_charts()
        category_name = "Chart Components"
    elif args.category == 'tables':
        components = registry.list_tables()
        category_name = "Table Components"
    elif args.category == 'text':
        components = registry.list_text_blocks()
        category_name = "Text Components"

    # Print header
    print("=" * 70)
    print(f"COMPONENT REGISTRY: {category_name}")
    print("=" * 70)

    if args.manager and args.program:
        print(f"Showing components for: {args.manager} - {args.program}")
        print()

    if not components:
        print("\nNo components found.")
        return 0

    print(f"\nTotal Components: {len(components)}")

    # Group by category if showing all
    if args.category == 'all':
        charts = [c for c in components if c.category == 'chart']
        tables = [c for c in components if c.category == 'table']
        texts = [c for c in components if c.category == 'text']

        if charts:
            print(f"\n{'='*70}")
            print(f"CHARTS ({len(charts)})")
            print('='*70)
            for component in sorted(charts, key=lambda x: x.name):
                print_component(component, args.verbose)

        if tables:
            print(f"\n{'='*70}")
            print(f"TABLES ({len(tables)})")
            print('='*70)
            for component in sorted(tables, key=lambda x: x.name):
                print_component(component, args.verbose)

        if texts:
            print(f"\n{'='*70}")
            print(f"TEXT BLOCKS ({len(texts)})")
            print('='*70)
            for component in sorted(texts, key=lambda x: x.name):
                print_component(component, args.verbose)
    else:
        # Show single category
        for component in sorted(components, key=lambda x: x.name):
            print_component(component, args.verbose)

    print()
    return 0


if __name__ == '__main__':
    exit(main())
