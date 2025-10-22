# Component Library System

## Overview

The Component Library System provides a centralized registry for all charts, tables, and text blocks that can be included in brochures. It features smart caching, batch generation, and organized output structure.

## Implementation Date

2025-10-22

## Key Features

✅ **Component Discovery** - List all available components with metadata
✅ **Batch Generation** - Generate all components for a manager/program in one command
✅ **Smart Caching** - Only regenerate when data or code changes
✅ **Benchmark Combinations** - Support for single and multiple benchmarks
✅ **Organized Output** - Clean folder structure per manager/program
✅ **Manifest Tracking** - JSON metadata for each generation run

## Architecture

### Core Files

1. **component_registry.py** - Component registration system
2. **register_components.py** - Component definitions and registration
3. **generate_all_components.py** - Batch generation with caching
4. **list_components.py** - Component discovery tool

### Component Structure

```python
@dataclass
class ComponentDefinition:
    id: str                      # e.g., 'cumulative_windows_5yr_additive'
    name: str                    # Human-readable name
    category: str                # 'chart', 'table', or 'text'
    description: str             # Brief description
    function: Callable           # Generation function
    benchmark_support: bool      # Can include benchmarks?
    benchmark_combinations: List # [[],['sp500'],['sp500','areit']]
    version: str                 # For cache invalidation
    variants: List[str]          # Named variants (e.g., ['compounded','additive'])
```

## Usage

### List Available Components

```bash
# List all components
python list_components.py

# List only charts
python list_components.py --category charts

# List tables
python list_components.py --category tables
```

**Example Output:**
```
======================================================================
COMPONENT REGISTRY: All Components
======================================================================

Total Components: 5

======================================================================
CHARTS (4)
======================================================================

[CHART] Cumulative Windows Overlay (5-Year, Additive)
  ID: cumulative_windows_5yr_additive
  Description: 5-year non-overlapping windows with additive returns...
  Version: 1.0.0
  Benchmarks: (none); sp500; areit; sp500, areit
```

### Generate All Components

```bash
# Generate all components for Alphabet MFT
python generate_all_components.py --manager Alphabet --program MFT

# Generate only charts
python generate_all_components.py --manager Alphabet --program MFT --category charts

# Generate specific components
python generate_all_components.py --manager Alphabet --program MFT --components cumulative_windows_5yr_additive

# Force regeneration (ignore cache)
python generate_all_components.py --manager Alphabet --program MFT --force
```

**Example Output:**
```
======================================================================
GENERATING COMPONENTS: Alphabet - MFT
======================================================================
Manager: Alphabet (ID: 3)
Program: MFT (ID: 11)
Data Range: 2006-01-03 to 2025-10-17
Output Directory: export\alphabet\mft
Force Regeneration: False

Components to process: 1

[CHART] Cumulative Windows Overlay (5-Year, Additive)
  Generating: alphabet_mft_cumulative_windows_5yr_additive.pdf... [OK]
  Generating: alphabet_mft_cumulative_windows_5yr_additive_sp500.pdf... [OK]
  Generating: alphabet_mft_cumulative_windows_5yr_additive_areit.pdf... [OK]
  Cached: alphabet_mft_cumulative_windows_5yr_additive_areit_sp500.pdf

======================================================================
GENERATION SUMMARY
======================================================================
Generated: 3
Cached:    1
Failed:    0
Total:     4
```

## Output Structure

```
export/
├── alphabet/
│   └── mft/
│       ├── alphabet_mft_cumulative_windows_5yr_additive.pdf
│       ├── alphabet_mft_cumulative_windows_5yr_additive_sp500.pdf
│       ├── alphabet_mft_cumulative_windows_5yr_additive_areit.pdf
│       ├── alphabet_mft_cumulative_windows_5yr_additive_areit_sp500.pdf
│       └── manifest.json
├── rise_capital/
│   ├── cta_50m_30/
│   └── cta_100m_30/
```

## Naming Convention

**Format:** `{manager}_{program}_{component_id}_{variant}_{benchmarks}.pdf`

**Examples:**
- `alphabet_mft_equity_curve_full_history.pdf` (no benchmark)
- `alphabet_mft_equity_curve_full_history_sp500.pdf` (with SP500)
- `alphabet_mft_equity_curve_full_history_areit_sp500.pdf` (multiple benchmarks)
- `alphabet_mft_cumulative_windows_5yr_compounded.pdf`

**Benchmark Sorting:** Benchmarks are sorted alphabetically for consistent naming

## Manifest Structure

Each output folder contains a `manifest.json` file:

```json
{
  "generated_date": "2025-10-22T12:13:19.938339",
  "manager": "alphabet",
  "program": "mft",
  "data_range": {
    "start_date": "2006-01-03",
    "end_date": "2025-10-17"
  },
  "components": {
    "alphabet_mft_cumulative_windows_5yr_additive_sp500.pdf": {
      "component_id": "cumulative_windows_5yr_additive",
      "variant": null,
      "benchmarks": ["sp500"],
      "generated_date": "2025-10-22T12:13:27.848148",
      "data_hash": "c886d13e6c304dafd30495b60f399f86",
      "code_version": "1.0.0"
    }
  }
}
```

## Caching Logic

A component is regenerated if:
1. PDF file doesn't exist
2. Component not in manifest
3. Data hash changed (new data added)
4. Code version changed (component updated)
5. `--force` flag used

Otherwise, the cached version is used.

**Data Hash Calculation:**
```python
# Based on:
- Record count in date range
- Latest submission date
- Latest data date
```

## Registered Components

### Charts (4)

1. **cumulative_windows_5yr_additive** ✅ Implemented
   - 5-year non-overlapping windows with additive returns
   - Uses borrow_mode for complete earliest window
   - Supports 4 benchmark combinations

2. **cumulative_windows_5yr_compounded** ⏳ To be implemented
   - Same as additive but with compounded returns

3. **equity_curve_full_history** ⏳ To be implemented
   - Full NAV history from inception
   - Supports 6 benchmark combinations

4. **monthly_performance** ⏳ To be implemented
   - Monthly bar chart

### Tables (1)

1. **performance_summary_table** ⏳ To be implemented
   - Returns, volatility, Sharpe for different periods

## Adding New Components

### 1. Create Generation Function

```python
def generate_my_chart(db, program_id, output_path, benchmarks=None, variant=None, **kwargs):
    """
    Generate my custom chart.

    Args:
        db: Database instance
        program_id: Program ID
        output_path: Where to save PDF
        benchmarks: List of benchmark names (e.g., ['sp500'])
        variant: Optional variant name
        **kwargs: Additional parameters

    Returns:
        Plotly Figure object
    """
    # Your chart generation code here
    # ...

    fig.write_image(output_path, format='pdf')
    return fig
```

### 2. Register Component

In `register_components.py`:

```python
register_component(
    id='my_chart',
    name='My Custom Chart',
    category='chart',
    description='Description of what this shows',
    function=generate_my_chart,
    benchmark_support=True,
    benchmark_combinations=[
        [],              # No benchmark
        ['sp500'],       # SP500 only
        ['sp500', 'areit']  # Multiple
    ],
    version='1.0.0'
)
```

### 3. Test

```bash
# List to verify registration
python list_components.py

# Generate for testing
python generate_all_components.py --manager Alphabet --program MFT --components my_chart
```

## Integration with Brochure System

The component library works alongside the brochure system:

1. **Component Generation** (this system) - Creates individual PDFs
2. **Component Discovery** - Browse PDFs to decide what to include
3. **Brochure Assembly** (existing system) - Combines selected components into final brochure

**Workflow:**
```bash
# Step 1: Generate all components
python generate_all_components.py --manager Alphabet --program MFT

# Step 2: Browse export/alphabet/mft/ folder to review PDFs

# Step 3: Create brochure selecting desired components
# (Future: brochure system will reference component IDs)
```

## Best Practices

1. **Always use the registry** - Don't create standalone generation scripts
2. **Version components** - Increment version when changing logic
3. **Test caching** - Run twice to ensure caching works
4. **Document benchmarks** - List all supported combinations
5. **Handle errors gracefully** - Return meaningful error messages
6. **Follow naming convention** - Use slugified manager/program names

## Future Enhancements

Planned improvements:
1. **HTML previews** - Generate HTML versions for faster browsing
2. **Thumbnail generation** - PNG thumbnails for quick visual scanning
3. **Component dependencies** - Track which components depend on others
4. **Brochure templates** - Predefined component sets per manager type
5. **Version history** - Track component evolution over time
6. **Automated testing** - Validate all components generate successfully

## Files Modified

- ✅ [component_registry.py](component_registry.py) - Registry system
- ✅ [register_components.py](register_components.py) - Component definitions
- ✅ [generate_all_components.py](generate_all_components.py) - Batch generator
- ✅ [list_components.py](list_components.py) - Discovery tool
- ✅ [generate_alphabet_mft_cumulative_windows_additive.py](generate_alphabet_mft_cumulative_windows_additive.py) - Adapted for registry
- ✅ [COMPONENT_SYSTEM.md](COMPONENT_SYSTEM.md) - This documentation

## See Also

- [BORROW_MODE_IMPLEMENTATION.md](BORROW_MODE_IMPLEMENTATION.md) - Borrow mode for windows
- [CLAUDE.md](CLAUDE.md) - Main project documentation
- [schema_chart_config.sql](schema_chart_config.sql) - Chart configuration database
