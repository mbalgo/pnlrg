"""
Component Registry System for PnL Report Generator.

This module provides a central registry for all chart, table, and text components
that can be included in brochures. Components are cataloged with metadata and
can be batch-generated for any manager/program combination.

Key Features:
- Component discovery and listing
- Benchmark combination support (single/multiple)
- Smart caching with manifest tracking
- Extensible registration system
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable, Any
from datetime import date, datetime
import hashlib
import json
from pathlib import Path


@dataclass
class ComponentDefinition:
    """
    Definition of a component that can be generated for a manager/program.

    Attributes:
        id: Unique component identifier (e.g., 'equity_curve', 'cumulative_windows_5yr')
        name: Human-readable name
        category: Component category ('chart', 'table', 'text')
        description: Brief description of what this component shows
        function: Callable that generates the component
        benchmark_support: Whether this component can include benchmarks
        benchmark_combinations: List of benchmark combinations to generate
        parameters: Additional parameters required by the generation function
        version: Component version (for cache invalidation)
        variants: Named variants of this component (e.g., {'compounded', 'additive'})
    """
    id: str
    name: str
    category: str
    description: str
    function: Callable
    benchmark_support: bool = False
    benchmark_combinations: List[List[str]] = field(default_factory=lambda: [[]])
    parameters: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    variants: List[str] = field(default_factory=list)

    def get_output_path(
        self,
        base_dir: Path,
        manager_slug: str,
        program_slug: str,
        variant: Optional[str] = None,
        benchmarks: Optional[List[str]] = None
    ) -> Path:
        """
        Generate standardized output path for this component (includes category subfolder).

        Args:
            base_dir: Base directory (e.g., Path('export/alphabet/mft'))
            manager_slug: Manager name slug (e.g., 'alphabet', 'rise_capital')
            program_slug: Program name slug (e.g., 'mft', 'cta_100m_30')
            variant: Optional variant name (e.g., 'compounded', 'additive')
            benchmarks: Optional list of benchmark names (e.g., ['sp500'], ['sp500', 'btop50'])

        Returns:
            Full path: e.g., Path('export/alphabet/mft/charts/alphabet_mft_equity_curve_sp500.pdf')
        """
        # Category subfolder
        category_folder = f"{self.category}s" if self.category != 'text' else 'text'

        # Filename parts
        parts = [manager_slug, program_slug, self.id]

        if variant:
            parts.append(variant)

        if benchmarks:
            # Sort benchmarks for consistent naming
            benchmark_str = '_'.join(sorted(benchmarks))
            parts.append(benchmark_str)

        filename = '_'.join(parts) + '.pdf'

        # Full path with category subfolder
        return base_dir / category_folder / filename

    def get_output_filename(
        self,
        manager_slug: str,
        program_slug: str,
        variant: Optional[str] = None,
        benchmarks: Optional[List[str]] = None
    ) -> str:
        """
        Generate standardized output filename for this component.

        Note: For full path with category subfolder, use get_output_path() instead.

        Args:
            manager_slug: Manager name slug (e.g., 'alphabet', 'rise_capital')
            program_slug: Program name slug (e.g., 'mft', 'cta_100m_30')
            variant: Optional variant name (e.g., 'compounded', 'additive')
            benchmarks: Optional list of benchmark names (e.g., ['sp500'], ['sp500', 'btop50'])

        Returns:
            Filename: e.g., 'alphabet_mft_equity_curve_sp500.pdf'
        """
        parts = [manager_slug, program_slug, self.id]

        if variant:
            parts.append(variant)

        if benchmarks:
            # Sort benchmarks for consistent naming
            benchmark_str = '_'.join(sorted(benchmarks))
            parts.append(benchmark_str)

        filename = '_'.join(parts) + '.pdf'
        return filename


class ComponentRegistry:
    """
    Central registry for all available components.

    Components are registered once during module initialization and can be
    queried for batch generation or discovery.
    """

    def __init__(self):
        self._components: Dict[str, ComponentDefinition] = {}

    def register(self, component: ComponentDefinition):
        """
        Register a component in the registry.

        Args:
            component: ComponentDefinition to register

        Raises:
            ValueError: If component ID already registered
        """
        if component.id in self._components:
            raise ValueError(f"Component '{component.id}' already registered")

        self._components[component.id] = component

    def get(self, component_id: str) -> Optional[ComponentDefinition]:
        """Get a component by ID."""
        return self._components.get(component_id)

    def list_all(self) -> List[ComponentDefinition]:
        """List all registered components."""
        return list(self._components.values())

    def list_by_category(self, category: str) -> List[ComponentDefinition]:
        """List components by category (chart/table/text)."""
        return [c for c in self._components.values() if c.category == category]

    def list_charts(self) -> List[ComponentDefinition]:
        """List all chart components."""
        return self.list_by_category('chart')

    def list_tables(self) -> List[ComponentDefinition]:
        """List all table components."""
        return self.list_by_category('table')

    def list_text_blocks(self) -> List[ComponentDefinition]:
        """List all text block components."""
        return self.list_by_category('text')


# Global registry instance
_registry = ComponentRegistry()


def get_registry() -> ComponentRegistry:
    """Get the global component registry instance."""
    return _registry


def register_component(
    id: str,
    name: str,
    category: str,
    description: str,
    function: Callable,
    **kwargs
) -> ComponentDefinition:
    """
    Convenience function to register a component.

    Args:
        id: Component ID
        name: Component name
        category: Component category
        description: Component description
        function: Generation function
        **kwargs: Additional ComponentDefinition fields

    Returns:
        The registered ComponentDefinition

    Example:
        >>> register_component(
        ...     id='equity_curve',
        ...     name='Equity Curve Chart',
        ...     category='chart',
        ...     description='Full history NAV curve',
        ...     function=generate_equity_curve,
        ...     benchmark_support=True,
        ...     benchmark_combinations=[[], ['sp500'], ['sp500', 'btop50']]
        ... )
    """
    component = ComponentDefinition(
        id=id,
        name=name,
        category=category,
        description=description,
        function=function,
        **kwargs
    )
    _registry.register(component)
    return component


def slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.

    Args:
        text: Text to slugify (e.g., "Rise Capital", "CTA_100M_30")

    Returns:
        Slug: e.g., "rise_capital", "cta_100m_30"
    """
    # Convert to lowercase
    slug = text.lower()

    # Replace spaces and special characters with underscores
    slug = slug.replace(' ', '_')
    slug = slug.replace('-', '_')

    # Remove any characters that aren't alphanumeric or underscore
    slug = ''.join(c for c in slug if c.isalnum() or c == '_')

    # Collapse multiple underscores
    while '__' in slug:
        slug = slug.replace('__', '_')

    # Strip leading/trailing underscores
    slug = slug.strip('_')

    return slug


def compute_data_hash(data_range: Dict[str, str], db, program_id: int) -> str:
    """
    Compute a hash of the underlying data for cache invalidation.

    Args:
        data_range: Dict with 'start_date' and 'end_date' strings
        db: Database instance
        program_id: Program ID

    Returns:
        Hash string (hex digest)
    """
    # Get record count and latest submission date
    result = db.fetch_one("""
        SELECT
            COUNT(*) as record_count,
            MAX(submission_date) as latest_submission,
            MAX(date) as latest_date
        FROM pnl_records
        WHERE program_id = ?
        AND date >= ?
        AND date <= ?
    """, (program_id, data_range['start_date'], data_range['end_date']))

    if not result:
        return hashlib.md5(b"no_data").hexdigest()

    # Create hash from key data characteristics
    hash_input = f"{result['record_count']}_{result['latest_submission']}_{result['latest_date']}"
    return hashlib.md5(hash_input.encode()).hexdigest()


def load_manifest(output_dir: Path) -> Dict:
    """
    Load manifest.json from output directory.

    Args:
        output_dir: Path to output directory

    Returns:
        Manifest dict, or empty dict if not found
    """
    manifest_path = output_dir / 'manifest.json'
    if not manifest_path.exists():
        return {}

    try:
        with open(manifest_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_manifest(output_dir: Path, manifest: Dict):
    """
    Save manifest.json to output directory.

    Args:
        output_dir: Path to output directory
        manifest: Manifest dict to save
    """
    manifest_path = output_dir / 'manifest.json'
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def should_regenerate_component(
    output_path: Path,
    manifest: Dict,
    component_id: str,
    current_data_hash: str,
    component_version: str,
    force: bool = False
) -> bool:
    """
    Determine if a component needs to be regenerated.

    Args:
        output_path: Path to component PDF
        manifest: Current manifest dict
        component_id: Component ID
        current_data_hash: Hash of current data
        component_version: Component version string
        force: If True, always regenerate

    Returns:
        True if component should be regenerated
    """
    # Force regeneration
    if force:
        return True

    # File doesn't exist
    if not output_path.exists():
        return True

    # Not in manifest
    filename = output_path.name
    if filename not in manifest.get('components', {}):
        return True

    component_info = manifest['components'][filename]

    # Data changed
    if component_info.get('data_hash') != current_data_hash:
        return True

    # Component version changed
    if component_info.get('code_version') != component_version:
        return True

    # No need to regenerate
    return False
