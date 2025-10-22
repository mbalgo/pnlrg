"""
Window-based time series analysis system for P&L Report Generator.

This module provides a sophisticated windowing framework for analyzing trading returns
across different time periods and market conditions. It separates window definitions
(what/when to analyze) from window instances (materialized data), enabling lazy
evaluation of potentially thousands of analysis windows.

Key concepts:
- WindowDefinition: Lightweight specification of a time window and participants
- Window: Materialized data for a window definition with lazy loading
- Statistics: Computed performance metrics for a return series
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import date
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta


@dataclass
class WindowDefinition:
    """
    Lightweight specification of a time window and participants.

    Defines what to analyze (programs and benchmarks) and when (date range),
    but does not contain actual data. Can be serialized to JSON.

    Attributes:
        start_date: First date of the window (inclusive)
        end_date: Last date of the window (inclusive)
        program_ids: List of program IDs to include in analysis
        benchmark_ids: List of market IDs (where is_benchmark=1) to include
        name: Optional descriptive name for this window
        window_set: Optional name of the window set this belongs to
        index: Optional position within the window set
        borrowed_data_start_date: Start of borrowed/overlapped data (if applicable)
        borrowed_data_end_date: End of borrowed/overlapped data (if applicable)
    """
    start_date: date
    end_date: date
    program_ids: List[int]
    benchmark_ids: List[int]
    name: Optional[str] = None
    window_set: Optional[str] = None
    index: Optional[int] = None
    borrowed_data_start_date: Optional[date] = None
    borrowed_data_end_date: Optional[date] = None

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'program_ids': self.program_ids,
            'benchmark_ids': self.benchmark_ids,
            'name': self.name,
            'window_set': self.window_set,
            'index': self.index,
            'borrowed_data_start_date': self.borrowed_data_start_date.isoformat() if self.borrowed_data_start_date else None,
            'borrowed_data_end_date': self.borrowed_data_end_date.isoformat() if self.borrowed_data_end_date else None
        }

    @classmethod
    def from_dict(cls, d: dict):
        """Deserialize from dict."""
        return cls(
            start_date=date.fromisoformat(d['start_date']),
            end_date=date.fromisoformat(d['end_date']),
            program_ids=d['program_ids'],
            benchmark_ids=d['benchmark_ids'],
            name=d.get('name'),
            window_set=d.get('window_set'),
            index=d.get('index'),
            borrowed_data_start_date=date.fromisoformat(d['borrowed_data_start_date']) if d.get('borrowed_data_start_date') else None,
            borrowed_data_end_date=date.fromisoformat(d['borrowed_data_end_date']) if d.get('borrowed_data_end_date') else None
        )


@dataclass
class Statistics:
    """
    Statistical measures for a return series.

    Provides both compounded and simple (non-compounded) statistics:
    - Compounded: Start with $1000, compound all returns
    - Simple: Invest $1000 each period (withdraw profits/top-up losses each period)

    IMPORTANT: As of the daily-data refactor, std_dev is calculated from DAILY returns
    (industry standard), while mean/median/CAGR are calculated from monthly returns.

    Attributes:
        count: Number of monthly return observations
        mean: Average monthly return (as decimal)
        median: Median monthly return (as decimal)
        std_dev: Standard deviation of DAILY returns, annualized (industry standard)
        cumulative_return_compounded: Total compounded return
        cumulative_return_simple: Sum of all returns
        max_drawdown_compounded: Maximum % decline from peak (compounded NAV)
        max_drawdown_simple: Maximum decline in cumulative P&L
        cagr: Compound Annual Growth Rate (annualized return)
        daily_count: Number of daily observations used for std_dev calculation
        daily_std_dev_raw: Standard deviation of daily returns (not annualized)
    """
    count: int
    mean: float
    median: float
    std_dev: float
    cumulative_return_compounded: float
    cumulative_return_simple: float
    max_drawdown_compounded: float
    max_drawdown_simple: float
    cagr: float = 0.0
    daily_count: int = 0
    daily_std_dev_raw: float = 0.0


class Window:
    """
    Materialized window containing actual return data.

    Fetches data from database on-demand and caches it for the session.
    Validates that all requested programs and benchmarks have complete
    data coverage for the window period.

    Attributes:
        definition: The WindowDefinition this window materializes
        db: Database instance for fetching data
        data_is_complete: Whether all programs/benchmarks have complete data
    """

    def __init__(self, definition: WindowDefinition, db):
        """
        Initialize window with a definition and database connection.

        Args:
            definition: WindowDefinition specifying what to analyze
            db: Database instance
        """
        self.definition = definition
        self.db = db
        self._manager_data: Dict[int, pd.DataFrame] = {}
        self._benchmark_data: Dict[int, pd.DataFrame] = {}
        self._data_is_complete: Optional[bool] = None

    @property
    def data_is_complete(self) -> bool:
        """
        Check if all programs and benchmarks have complete data for this window.

        Complete data means:
        - Data starts on or before window start_date
        - Data ends on or after window end_date
        - No validation of gaps (assumes monthly data is continuous)

        Returns:
            True if all requested entities have complete coverage, False otherwise
        """
        if self._data_is_complete is None:
            self._data_is_complete = self._check_completeness()
        return self._data_is_complete

    def _check_completeness(self) -> bool:
        """
        Verify all requested programs and benchmarks have data covering
        [start_date, end_date] without gaps.
        """
        # Check programs
        for program_id in self.definition.program_ids:
            data = self.get_manager_data(program_id)
            if not self._has_complete_coverage(data):
                return False

        # Check benchmarks
        for benchmark_id in self.definition.benchmark_ids:
            data = self.get_benchmark_data(benchmark_id)
            if not self._has_complete_coverage(data):
                return False

        return True

    def _has_complete_coverage(self, df: pd.DataFrame) -> bool:
        """
        Check if DataFrame has data for entire window period.

        For monthly data, we compare year/month only (not day) since
        monthly data may be dated at different days of the month.

        Args:
            df: DataFrame with 'date' column

        Returns:
            True if data covers full window, False otherwise
        """
        if df is None or len(df) == 0:
            return False

        data_start = df['date'].min()
        data_end = df['date'].max()

        # Convert to year-month tuples for comparison
        data_start_ym = (data_start.year, data_start.month)
        data_end_ym = (data_end.year, data_end.month)
        win_start_ym = (self.definition.start_date.year, self.definition.start_date.month)
        win_end_ym = (self.definition.end_date.year, self.definition.end_date.month)

        # Must start in or before window start month
        if data_start_ym > win_start_ym:
            return False

        # Must end in or after window end month
        if data_end_ym < win_end_ym:
            return False

        return True

    def get_manager_data(self, program_id: int) -> pd.DataFrame:
        """
        Fetch returns for a program within this window.

        Queries database for monthly returns in [start_date, end_date] range.
        Results are cached for subsequent calls.

        Args:
            program_id: Program ID to fetch

        Returns:
            DataFrame with columns ['date', 'return']
        """
        if program_id not in self._manager_data:
            # Query database for returns in [start_date, end_date]
            results = self.db.fetch_all("""
                SELECT pr.date, pr.return
                FROM pnl_records pr
                JOIN programs p ON pr.program_id = p.id
                JOIN markets m ON pr.market_id = m.id
                WHERE pr.program_id = ?
                AND m.name = 'Rise'
                AND pr.resolution = 'monthly'
                AND pr.date >= ?
                AND pr.date <= ?
                ORDER BY pr.date
            """, (program_id, self.definition.start_date, self.definition.end_date))

            df = pd.DataFrame(results, columns=['date', 'return'])
            if len(df) > 0:
                df['date'] = pd.to_datetime(df['date'])
            self._manager_data[program_id] = df

        return self._manager_data[program_id]

    def get_benchmark_data(self, market_id: int) -> pd.DataFrame:
        """
        Fetch returns for a benchmark within this window.

        Queries database for monthly benchmark returns in [start_date, end_date] range.
        Results are cached for subsequent calls.

        Args:
            market_id: Market ID to fetch (must have is_benchmark=1)

        Returns:
            DataFrame with columns ['date', 'return']
        """
        if market_id not in self._benchmark_data:
            # Get the Benchmarks program ID
            benchmarks_program = self.db.fetch_one(
                "SELECT id FROM programs WHERE program_name = 'Benchmarks'"
            )

            if not benchmarks_program:
                # No benchmarks program exists
                self._benchmark_data[market_id] = pd.DataFrame(columns=['date', 'return'])
                return self._benchmark_data[market_id]

            # Query for benchmark returns
            results = self.db.fetch_all("""
                SELECT pr.date, pr.return
                FROM pnl_records pr
                JOIN markets m ON pr.market_id = m.id
                WHERE pr.program_id = ?
                AND pr.market_id = ?
                AND m.is_benchmark = 1
                AND pr.resolution = 'monthly'
                AND pr.date >= ?
                AND pr.date <= ?
                ORDER BY pr.date
            """, (benchmarks_program['id'], market_id,
                  self.definition.start_date, self.definition.end_date))

            df = pd.DataFrame(results, columns=['date', 'return'])
            if len(df) > 0:
                df['date'] = pd.to_datetime(df['date'])
            self._benchmark_data[market_id] = df

        return self._benchmark_data[market_id]

    def get_manager_daily_data(self, program_id: int) -> pd.DataFrame:
        """
        Fetch DAILY returns for a program within this window.

        Aggregates across all markets (SUM of daily returns).
        This is the new primary method for fetching data, as industry standard
        statistics (especially std dev) should be calculated from daily returns.

        Args:
            program_id: Program ID to fetch

        Returns:
            DataFrame with columns ['date', 'return'] containing daily returns
        """
        cache_key = f'daily_{program_id}'
        if not hasattr(self, '_daily_manager_data'):
            self._daily_manager_data = {}

        if cache_key not in self._daily_manager_data:
            # Query database for DAILY returns, aggregated across all markets
            results = self.db.fetch_all("""
                SELECT pr.date, SUM(pr.return) as total_return
                FROM pnl_records pr
                WHERE pr.program_id = ?
                AND pr.resolution = 'daily'
                AND pr.date >= ?
                AND pr.date <= ?
                GROUP BY pr.date
                ORDER BY pr.date
            """, (program_id, self.definition.start_date, self.definition.end_date))

            df = pd.DataFrame(results, columns=['date', 'return'])
            if len(df) > 0:
                df['date'] = pd.to_datetime(df['date'])
            self._daily_manager_data[cache_key] = df

        return self._daily_manager_data[cache_key]

    def get_benchmark_daily_data(self, market_id: int) -> pd.DataFrame:
        """
        Fetch DAILY returns for a benchmark within this window.

        Args:
            market_id: Market ID to fetch (must have is_benchmark=1)

        Returns:
            DataFrame with columns ['date', 'return'] containing daily returns
        """
        cache_key = f'daily_{market_id}'
        if not hasattr(self, '_daily_benchmark_data'):
            self._daily_benchmark_data = {}

        if cache_key not in self._daily_benchmark_data:
            # Get the Benchmarks program ID
            benchmarks_program = self.db.fetch_one(
                "SELECT id FROM programs WHERE program_name = 'Benchmarks'"
            )

            if not benchmarks_program:
                # No benchmarks program exists
                self._daily_benchmark_data[cache_key] = pd.DataFrame(columns=['date', 'return'])
                return self._daily_benchmark_data[cache_key]

            # Query for DAILY benchmark returns
            results = self.db.fetch_all("""
                SELECT pr.date, pr.return
                FROM pnl_records pr
                JOIN markets m ON pr.market_id = m.id
                WHERE pr.program_id = ?
                AND pr.market_id = ?
                AND m.is_benchmark = 1
                AND pr.resolution = 'daily'
                AND pr.date >= ?
                AND pr.date <= ?
                ORDER BY pr.date
            """, (benchmarks_program['id'], market_id,
                  self.definition.start_date, self.definition.end_date))

            df = pd.DataFrame(results, columns=['date', 'return'])
            if len(df) > 0:
                df['date'] = pd.to_datetime(df['date'])
            self._daily_benchmark_data[cache_key] = df

        return self._daily_benchmark_data[cache_key]


# =============================================================================
# Helper Functions for Daily/Monthly Aggregation
# =============================================================================

def aggregate_daily_to_monthly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate daily returns to monthly returns by compounding within each month.

    Args:
        daily_df: DataFrame with 'date' and 'return' columns (daily returns)

    Returns:
        DataFrame with monthly returns (one row per calendar month)
    """
    if daily_df is None or len(daily_df) == 0:
        return pd.DataFrame(columns=['date', 'return'])

    # Ensure date is datetime
    df = daily_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'])

    # Group by year-month and compound returns within each month
    df['year_month'] = df['date'].dt.to_period('M')

    monthly_returns = []
    for period, group in df.groupby('year_month'):
        # Compound daily returns to get monthly return
        monthly_return = (1 + group['return']).prod() - 1
        # Use last day of the month as the date
        month_end_date = group['date'].max()
        monthly_returns.append({
            'date': month_end_date,
            'return': monthly_return
        })

    return pd.DataFrame(monthly_returns)


def annualize_daily_std(daily_std: float, trading_days_per_year: int = 252) -> float:
    """
    Annualize standard deviation of daily returns.

    Industry standard formula: daily_std × sqrt(trading_days_per_year)

    Args:
        daily_std: Standard deviation of daily returns (as decimal, e.g., 0.02 for 2%)
        trading_days_per_year: Number of trading days per year (default: 252)

    Returns:
        Annualized standard deviation
    """
    return daily_std * np.sqrt(trading_days_per_year)


def compute_statistics(window: Window, entity_id: int,
                       entity_type: str = 'manager') -> Statistics:
    """
    Compute statistics for a program or benchmark within a window.

    NEW APPROACH (post-refactor):
    - Fetches DAILY data first for std dev calculation (industry standard)
    - Aggregates daily to monthly for mean/median/CAGR calculations
    - Falls back to monthly-only data if daily data not available

    Calculates both compounded and simple (non-compounded) statistics:
    - Compounded: Simulates starting with $1000 and compounding returns
    - Simple: Simulates investing $1000 each period (no compounding)

    Args:
        window: The time window to analyze
        entity_id: Program ID (if entity_type='manager') or Market ID (if entity_type='benchmark')
        entity_type: Either 'manager' or 'benchmark'

    Returns:
        Statistics object with all computed metrics

    Example:
        >>> window = Window(window_def, db)
        >>> stats = compute_statistics(window, program_id=1, entity_type='manager')
        >>> print(f"CAGR: {stats.cagr:.2%}")
        >>> print(f"Std Dev (annualized from daily): {stats.std_dev:.2%}")
    """
    # Step 1: Try to get DAILY data first (preferred)
    if entity_type == 'manager':
        daily_df = window.get_manager_daily_data(entity_id)
    else:  # entity_type == 'benchmark'
        daily_df = window.get_benchmark_daily_data(entity_id)

    # Step 2: Check if we have daily data
    has_daily_data = daily_df is not None and len(daily_df) > 0

    if has_daily_data:
        # NEW PATH: Use daily data for std dev, aggregate to monthly for other stats
        daily_returns = daily_df['return'].values
        daily_count = len(daily_returns)

        # Calculate std dev from DAILY returns (industry standard)
        if daily_count > 1:
            daily_std_raw = float(daily_returns.std(ddof=1))
            daily_std_annualized = annualize_daily_std(daily_std_raw)
        else:
            daily_std_raw = float('nan')
            daily_std_annualized = float('nan')

        # Aggregate daily to monthly for other statistics
        monthly_df = aggregate_daily_to_monthly(daily_df)

        if len(monthly_df) == 0:
            # Edge case: no monthly data after aggregation
            return Statistics(
                count=0,
                mean=float('nan'),
                median=float('nan'),
                std_dev=daily_std_annualized,  # Use daily std dev
                cumulative_return_compounded=float('nan'),
                cumulative_return_simple=float('nan'),
                max_drawdown_compounded=float('nan'),
                max_drawdown_simple=float('nan'),
                daily_count=daily_count,
                daily_std_dev_raw=daily_std_raw
            )

        monthly_returns = monthly_df['return'].values
        monthly_count = len(monthly_returns)

    else:
        # FALLBACK PATH: Only monthly data available (legacy, e.g., Rise CTA)
        if entity_type == 'manager':
            monthly_df = window.get_manager_data(entity_id)
        else:
            monthly_df = window.get_benchmark_data(entity_id)

        if monthly_df is None or len(monthly_df) == 0:
            return Statistics(
                count=0,
                mean=float('nan'),
                median=float('nan'),
                std_dev=float('nan'),
                cumulative_return_compounded=float('nan'),
                cumulative_return_simple=float('nan'),
                max_drawdown_compounded=float('nan'),
                max_drawdown_simple=float('nan'),
                daily_count=0,
                daily_std_dev_raw=float('nan')
            )

        monthly_returns = monthly_df['return'].values
        monthly_count = len(monthly_returns)
        daily_count = 0
        daily_std_raw = float('nan')

        # Estimate: use monthly std dev as fallback (NOT industry standard)
        if monthly_count > 1:
            daily_std_annualized = float(monthly_returns.std(ddof=1))
        else:
            daily_std_annualized = float('nan')

    # Step 3: Calculate statistics from monthly returns
    mean = float(monthly_returns.mean()) if monthly_count > 0 else float('nan')
    median = float(np.median(monthly_returns)) if monthly_count > 0 else float('nan')

    # Cumulative returns
    cumulative_return_compounded = float((1 + pd.Series(monthly_returns)).prod() - 1) if monthly_count > 0 else float('nan')
    cumulative_return_simple = float(monthly_returns.sum()) if monthly_count > 0 else float('nan')

    # CAGR (Compound Annual Growth Rate)
    # Use actual date range for accurate annualization
    if monthly_count > 0 and not np.isnan(cumulative_return_compounded):
        # Calculate years from actual window dates
        days = (window.definition.end_date - window.definition.start_date).days
        years = days / 365.25
        cagr = float(((1 + cumulative_return_compounded) ** (1.0 / years)) - 1) if years > 0 else 0.0
    else:
        cagr = 0.0

    # Drawdowns: Use DAILY data if available for more accurate intra-month drawdowns
    # This captures drawdowns that occur during a month, not just month-end values
    if has_daily_data and daily_count > 0:
        # Calculate from daily returns (most accurate)
        max_dd_comp = _calculate_max_drawdown_compounded(daily_returns)
        max_dd_simple = _calculate_max_drawdown_simple(daily_returns)
    else:
        # Fallback: Use monthly returns (legacy path)
        max_dd_comp = _calculate_max_drawdown_compounded(monthly_returns) if monthly_count > 0 else float('nan')
        max_dd_simple = _calculate_max_drawdown_simple(monthly_returns) if monthly_count > 0 else float('nan')

    return Statistics(
        count=monthly_count,
        mean=mean,
        median=median,
        std_dev=daily_std_annualized,  # INDUSTRY STANDARD: from daily returns
        cumulative_return_compounded=cumulative_return_compounded,
        cumulative_return_simple=cumulative_return_simple,
        max_drawdown_compounded=max_dd_comp,
        max_drawdown_simple=max_dd_simple,
        cagr=cagr,
        daily_count=daily_count,
        daily_std_dev_raw=daily_std_raw
    )


def _calculate_max_drawdown_compounded(returns: np.ndarray) -> float:
    """
    Calculate maximum drawdown using compounded returns.

    Simulates starting with $1000 and compounding through all returns,
    then calculates the maximum percentage decline from any running peak.

    Args:
        returns: Array of returns as decimals (e.g., 0.03 for 3%)

    Returns:
        Maximum drawdown as a negative decimal (e.g., -0.25 for -25% drawdown)
    """
    if len(returns) == 0:
        return float('nan')

    # Start with 1000, compound through returns
    nav = 1000 * (1 + pd.Series(returns)).cumprod()

    # Calculate running maximum
    running_max = nav.expanding().max()

    # Drawdown at each point (as percentage of running max)
    drawdown = (nav - running_max) / running_max

    return float(drawdown.min())  # Most negative value


def _calculate_max_drawdown_simple(returns: np.ndarray) -> float:
    """
    Calculate maximum drawdown with $1000 invested each period.

    This represents a withdraw-all-profits / top-up-all-losses strategy
    where $1000 is invested at the start of each period.

    Args:
        returns: Array of returns as decimals

    Returns:
        Maximum drawdown in dollars (as negative value)
    """
    if len(returns) == 0:
        return float('nan')

    # Each period: invest 1000, get return
    period_pnls = 1000 * returns

    # Cumulative P&L
    cumulative_pnl = pd.Series(period_pnls).cumsum()

    # Running maximum
    running_max = cumulative_pnl.expanding().max()

    # Drawdown (in dollars)
    drawdown = cumulative_pnl - running_max

    return float(drawdown.min())  # Most negative value


# =============================================================================
# Window Generation Functions
# =============================================================================

def generate_window_definitions_non_overlapping_snapped(
    start_date: date,
    end_date: date,
    window_length_years: int,
    program_ids: List[int],
    benchmark_ids: List[int],
    window_set_name: Optional[str] = None
) -> List[WindowDefinition]:
    """
    Generate non-overlapping windows aligned to calendar years.

    Windows are "snapped" to clean calendar boundaries. For example, 5-year
    windows will align to 1970, 1975, 1980, etc., regardless of when the
    data actually starts.

    Args:
        start_date: Earliest date to consider
        end_date: Latest date to consider
        window_length_years: Length of each window in years
        program_ids: Programs to include in analysis
        benchmark_ids: Benchmarks to include in analysis
        window_set_name: Optional name for this set of windows

    Returns:
        List of WindowDefinition objects

    Example:
        >>> # Generate 5-year calendar windows for 1973-2017 data
        >>> windows = generate_window_definitions_non_overlapping_snapped(
        ...     start_date=date(1973, 1, 1),
        ...     end_date=date(2017, 12, 31),
        ...     window_length_years=5,
        ...     program_ids=[1, 2],
        ...     benchmark_ids=[5, 6]
        ... )
        >>> # Returns: [1970-1975], [1975-1980], ..., [2015-2020]
    """
    # Snap to nearest multiple of window_length_years
    snap_year = (start_date.year // window_length_years) * window_length_years

    windows = []
    current_year = snap_year
    index = 0

    while True:
        win_start = date(current_year, 1, 1)
        win_end = date(current_year + window_length_years - 1, 12, 31)

        # Stop if window starts after our data range
        if win_start > end_date:
            break

        # Clip window to actual data range
        actual_start = max(win_start, start_date)
        actual_end = min(win_end, end_date)

        # Create window definition
        win_def = WindowDefinition(
            start_date=actual_start,
            end_date=actual_end,
            program_ids=program_ids.copy(),
            benchmark_ids=benchmark_ids.copy(),
            name=f"{current_year}-{current_year + window_length_years - 1}",
            window_set=window_set_name,
            index=index
        )
        windows.append(win_def)

        current_year += window_length_years
        index += 1

    return windows


def generate_window_definitions_non_overlapping_not_snapped(
    start_date: date,
    end_date: date,
    window_length_months: int,
    program_ids: List[int],
    benchmark_ids: List[int],
    window_set_name: Optional[str] = None
) -> List[WindowDefinition]:
    """
    Generate non-overlapping windows starting at first data date.

    Windows are NOT aligned to calendar boundaries - they start exactly
    at the start_date provided. This maximizes data utilization.

    Args:
        start_date: First date of first window
        end_date: Latest date to consider
        window_length_months: Length of each window in months
        program_ids: Programs to include
        benchmark_ids: Benchmarks to include
        window_set_name: Optional name for this set

    Returns:
        List of WindowDefinition objects

    Example:
        >>> # Generate 60-month windows starting from actual data start
        >>> windows = generate_window_definitions_non_overlapping_not_snapped(
        ...     start_date=date(1973, 6, 1),
        ...     end_date=date(2017, 5, 31),
        ...     window_length_months=60,
        ...     program_ids=[1],
        ...     benchmark_ids=[5]
        ... )
        >>> # Returns: [1973-06 to 1978-05], [1978-06 to 1983-05], ...
    """
    windows = []
    current_start = start_date
    index = 0

    while current_start < end_date:
        # Calculate end date (last day of the month before N months later)
        win_end = current_start + relativedelta(months=window_length_months) - relativedelta(days=1)

        # Clip to data range
        if win_end > end_date:
            win_end = end_date

        win_def = WindowDefinition(
            start_date=current_start,
            end_date=win_end,
            program_ids=program_ids.copy(),
            benchmark_ids=benchmark_ids.copy(),
            name=f"Period {index + 1} ({current_start.strftime('%Y-%m')} to {win_end.strftime('%Y-%m')})",
            window_set=window_set_name,
            index=index
        )
        windows.append(win_def)

        # Next window starts day after this one ends
        current_start = win_end + relativedelta(days=1)
        index += 1

    return windows


def generate_window_definitions_non_overlapping_reverse(
    earliest_date: date,
    latest_date: date,
    window_length_years: int,
    program_ids: List[int],
    benchmark_ids: List[int],
    window_set_name: Optional[str] = None,
    borrow_mode: bool = False
) -> List[WindowDefinition]:
    """
    Generate non-overlapping windows working backwards from the latest date.

    This ensures the most recent period is fully captured. The last window ends
    exactly at latest_date and spans a full window_length_years period. Then
    works backwards creating non-overlapping windows until earliest_date is reached.

    When borrow_mode=True, if the earliest window is incomplete (shorter than
    window_length_years), its end_date is extended forward to overlap with the
    next window, making it a complete window. The overlapping period is marked
    with borrowed_data_start_date and borrowed_data_end_date for visualization.

    Args:
        earliest_date: Earliest date in the dataset
        latest_date: Latest date in the dataset (end of most recent window)
        window_length_years: Length of each window in years
        program_ids: Programs to include in analysis
        benchmark_ids: Benchmarks to include in analysis
        window_set_name: Optional name for this set of windows
        borrow_mode: If True, extend incomplete earliest window by borrowing from next window

    Returns:
        List of WindowDefinition objects in chronological order (oldest first)

    Example (borrow_mode=False):
        >>> # Data from 2006-01-01 to 2020-12-31, 5-year windows
        >>> windows = generate_window_definitions_non_overlapping_reverse(
        ...     earliest_date=date(2006, 1, 1),
        ...     latest_date=date(2020, 12, 31),
        ...     window_length_years=5,
        ...     program_ids=[1],
        ...     benchmark_ids=[2]
        ... )
        >>> # Returns:
        >>> # Window 3: 2006-01-01 to 2009-12-31 (4 years, incomplete)
        >>> # Window 2: 2010-01-01 to 2014-12-31 (5 years)
        >>> # Window 1: 2015-01-01 to 2020-12-31 (5 years)

    Example (borrow_mode=True):
        >>> # Same data, but with borrow_mode=True
        >>> windows = generate_window_definitions_non_overlapping_reverse(
        ...     earliest_date=date(2006, 1, 1),
        ...     latest_date=date(2020, 12, 31),
        ...     window_length_years=5,
        ...     program_ids=[1],
        ...     benchmark_ids=[2],
        ...     borrow_mode=True
        ... )
        >>> # Returns:
        >>> # Window 3: 2006-01-01 to 2010-12-31 (5 years)
        >>> #   borrowed_data_start_date=2010-01-01
        >>> #   borrowed_data_end_date=2010-12-31
        >>> # Window 2: 2010-01-01 to 2014-12-31 (5 years)
        >>> # Window 1: 2015-01-01 to 2020-12-31 (5 years)
    """
    windows = []
    current_end = latest_date
    index = 0
    last_complete_window_start = None

    while True:
        # Calculate start date (exactly window_length_years before end)
        win_start = current_end - relativedelta(years=window_length_years)

        # If this window starts before our earliest data
        if win_start < earliest_date:
            # Save the start date of the last complete window we created
            last_complete_window_start = current_end
            break

        # Create window definition
        # Name shows the period ending date
        win_def = WindowDefinition(
            start_date=win_start,
            end_date=current_end,
            program_ids=program_ids.copy(),
            benchmark_ids=benchmark_ids.copy(),
            name=f"Period ending {current_end.strftime('%Y-%m-%d')}",
            window_set=window_set_name,
            index=index
        )
        windows.append(win_def)

        # Move to next window (ending the day before this one starts)
        current_end = win_start - relativedelta(days=1)
        index += 1

    # Check if there's still data before the last complete window
    # If so, create an incomplete window starting from earliest_date
    if last_complete_window_start is not None:
        potential_incomplete_end = last_complete_window_start - relativedelta(days=1)
        if potential_incomplete_end >= earliest_date:
            # There's data for an incomplete window
            win_def = WindowDefinition(
                start_date=earliest_date,
                end_date=potential_incomplete_end,
                program_ids=program_ids.copy(),
                benchmark_ids=benchmark_ids.copy(),
                name=f"Period ending {potential_incomplete_end.strftime('%Y-%m-%d')}",
                window_set=window_set_name,
                index=index
            )
            windows.append(win_def)

    # Reverse to return in chronological order (oldest first)
    windows.reverse()

    # Re-index after reversing
    for i, win in enumerate(windows):
        win.index = i

    # Handle borrow_mode: extend earliest window if incomplete
    if borrow_mode and len(windows) > 1:
        earliest_window = windows[0]

        # Check if earliest window is incomplete
        # (i.e., its start_date is later than what a full window would require)
        ideal_start = earliest_window.end_date - relativedelta(years=window_length_years)

        if earliest_window.start_date > ideal_start:
            # Window is incomplete - need to borrow data
            # Calculate how much we need to extend the end_date to make it complete
            actual_duration_days = (earliest_window.end_date - earliest_window.start_date).days
            target_duration_days = (earliest_window.end_date - ideal_start).days
            shortage_days = target_duration_days - actual_duration_days

            # Extend end_date forward to borrow from next window
            new_end_date = earliest_window.end_date + relativedelta(days=shortage_days)

            # The borrowed period is from the old end_date + 1 day to new end_date
            borrowed_start = earliest_window.end_date + relativedelta(days=1)
            borrowed_end = new_end_date

            # Update the window
            earliest_window.end_date = new_end_date
            earliest_window.borrowed_data_start_date = borrowed_start
            earliest_window.borrowed_data_end_date = borrowed_end

    return windows


def generate_window_definitions_overlapping(
    start_date: date,
    end_date: date,
    window_length_months: int,
    slide_months: int = 1,
    program_ids: List[int] = None,
    benchmark_ids: List[int] = None,
    window_set_name: Optional[str] = None
) -> List[WindowDefinition]:
    """
    Generate overlapping rolling windows.

    Creates windows that slide forward by a fixed interval (typically 1 month).
    This is useful for analyzing how metrics evolve over time.

    Args:
        start_date: First date of first window
        end_date: Latest date to consider
        window_length_months: Length of each window in months
        slide_months: How many months to slide forward for each window (default 1)
        program_ids: Programs to include (default empty list)
        benchmark_ids: Benchmarks to include (default empty list)
        window_set_name: Optional name for this set

    Returns:
        List of WindowDefinition objects

    Example:
        >>> # Generate 12-month rolling windows
        >>> windows = generate_window_definitions_overlapping(
        ...     start_date=date(1973, 6, 1),
        ...     end_date=date(2017, 5, 31),
        ...     window_length_months=12,
        ...     slide_months=1,
        ...     program_ids=[1],
        ...     benchmark_ids=[5]
        ... )
        >>> # Returns: [1973-06 to 1974-05], [1973-07 to 1974-06], ...
    """
    if program_ids is None:
        program_ids = []
    if benchmark_ids is None:
        benchmark_ids = []

    windows = []
    current_start = start_date
    index = 0

    while True:
        # Calculate end date
        win_end = current_start + relativedelta(months=window_length_months) - relativedelta(days=1)

        # Stop if window extends beyond data range
        if win_end > end_date:
            break

        win_def = WindowDefinition(
            start_date=current_start,
            end_date=win_end,
            program_ids=program_ids.copy(),
            benchmark_ids=benchmark_ids.copy(),
            name=f"Rolling {window_length_months}M ({current_start.strftime('%Y-%m')})",
            window_set=window_set_name,
            index=index
        )
        windows.append(win_def)

        # Slide forward
        current_start += relativedelta(months=slide_months)
        index += 1

    return windows


def generate_window_definitions_overlapping_reverse(
    end_date: date,
    earliest_date: date,
    window_length_months: int,
    slide_months: int = 1,
    program_ids: List[int] = None,
    benchmark_ids: List[int] = None,
    window_set_name: Optional[str] = None
) -> List[WindowDefinition]:
    """
    Generate trailing windows that all end at the same date.

    Windows slide backward in time, each ending at end_date. This answers
    questions like "What were the trailing 12-month returns as of today?"

    Args:
        end_date: End date for all windows (typically latest data date or "today")
        earliest_date: Don't create windows starting before this date
        window_length_months: Length of each window in months
        slide_months: How many months to slide backward for each window (default 1)
        program_ids: Programs to include (default empty list)
        benchmark_ids: Benchmarks to include (default empty list)
        window_set_name: Optional name for this set

    Returns:
        List of WindowDefinition objects, ordered with most recent first

    Example:
        >>> # Generate trailing 12-month windows as of 2017-05-31
        >>> windows = generate_window_definitions_overlapping_reverse(
        ...     end_date=date(2017, 5, 31),
        ...     earliest_date=date(1973, 6, 1),
        ...     window_length_months=12,
        ...     slide_months=1,
        ...     program_ids=[1],
        ...     benchmark_ids=[5]
        ... )
        >>> # Returns: [2016-06 to 2017-05], [2016-05 to 2017-04], ...
    """
    if program_ids is None:
        program_ids = []
    if benchmark_ids is None:
        benchmark_ids = []

    windows = []
    index = 0
    offset_months = 0

    while True:
        # Calculate window dates
        win_end = end_date - relativedelta(months=offset_months)
        win_start = win_end - relativedelta(months=window_length_months) + relativedelta(days=1)

        # Stop if window starts before earliest allowed date
        if win_start < earliest_date:
            break

        win_def = WindowDefinition(
            start_date=win_start,
            end_date=win_end,
            program_ids=program_ids.copy(),
            benchmark_ids=benchmark_ids.copy(),
            name=f"Trailing {window_length_months}M (as of {win_end.strftime('%Y-%m')})",
            window_set=window_set_name,
            index=index
        )
        windows.append(win_def)

        # Slide backward
        offset_months += slide_months
        index += 1

    # Reverse so most recent window is first
    return list(reversed(windows))


def generate_window_definitions_bespoke(
    windows_spec: List[Dict],
    program_ids: List[int],
    benchmark_ids: List[int],
    window_set_name: Optional[str] = None
) -> List[WindowDefinition]:
    """
    Generate custom window definitions from a specification.

    Allows creating hand-picked analysis periods for event-driven analysis
    (e.g., financial crises, specific market regimes).

    Args:
        windows_spec: List of dicts with 'name', 'start_date', 'end_date'
        program_ids: Programs to include
        benchmark_ids: Benchmarks to include
        window_set_name: Optional name for this set

    Returns:
        List of WindowDefinition objects

    Example:
        >>> windows_spec = [
        ...     {'name': '2008 Financial Crisis', 'start_date': '2007-06-01', 'end_date': '2009-03-31'},
        ...     {'name': 'COVID Crash', 'start_date': '2020-02-01', 'end_date': '2020-04-30'},
        ... ]
        >>> windows = generate_window_definitions_bespoke(
        ...     windows_spec=windows_spec,
        ...     program_ids=[1],
        ...     benchmark_ids=[5]
        ... )
    """
    windows = []

    for index, spec in enumerate(windows_spec):
        # Parse dates (accept either date objects or ISO strings)
        start = spec['start_date']
        if isinstance(start, str):
            start = date.fromisoformat(start)

        end = spec['end_date']
        if isinstance(end, str):
            end = date.fromisoformat(end)

        win_def = WindowDefinition(
            start_date=start,
            end_date=end,
            program_ids=program_ids.copy(),
            benchmark_ids=benchmark_ids.copy(),
            name=spec['name'],
            window_set=window_set_name,
            index=index
        )
        windows.append(win_def)

    return windows
