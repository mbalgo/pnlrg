"""
Event Probability Analysis Chart Component

Generates charts showing the probability of extreme events (large gains/losses)
compared to a normal distribution. Visualizes "fat tails" in return distributions.

Features:
- Log-scale Y-axis to reveal tail behavior
- Three curves: actual gains (blue squares), actual losses (red circles), normal distribution (black line)
- X-axis: normalized returns (daily P&L / target std dev)
- Shows heavy-tailed nature of trading returns
- Supports both target and realized std dev normalization
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from typing import Dict, Optional
from windows import EventProbabilityData


def render_event_probability_chart(
    epa_data: EventProbabilityData,
    config: Dict,
    output_path: str
) -> None:
    """
    Render event probability analysis chart to a file.

    Args:
        epa_data: EventProbabilityData object with computed probabilities
        config: Configuration dict with chart settings:
            - title: Chart title (required)
            - subtitle: Optional subtitle showing normalization method
            - figsize: Tuple (width, height) in inches (default: (10, 7))
            - dpi: Resolution in dots per inch (default: 300)
            - y_min: Minimum Y-axis value (default: 0.00001 = 10^-5)
            - y_max: Maximum Y-axis value (default: 1.0)
            - show_grid: Whether to show grid (default: True)
            - show_legend: Whether to show legend (default: True)
        output_path: Path to save the chart (e.g., 'output.png')

    Example:
        >>> config = {
        ...     'title': 'Event Probability Analysis - Alphabet MFT',
        ...     'subtitle': 'X-axis: Daily P&L / Target Std Dev (1%)',
        ...     'figsize': (12, 8),
        ...     'dpi': 300
        ... }
        >>> render_event_probability_chart(epa_data, config, 'chart.png')
    """
    # Extract configuration
    title = config.get('title', 'Event Probability Analysis')
    subtitle = config.get('subtitle')
    figsize = config.get('figsize', (10, 7))
    dpi = config.get('dpi', 300)
    y_min = config.get('y_min', 0.00001)
    y_max = config.get('y_max', 1.0)
    show_grid = config.get('show_grid', True)
    show_legend = config.get('show_legend', True)

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Plot normal distribution (black line, plotted first so it appears behind)
    ax.plot(
        epa_data.x_values,
        epa_data.p_normal,
        color='black',
        linestyle='-',
        linewidth=2.5,
        label='P[X>x] for Normal Distribution',
        zorder=1
    )

    # Plot actual gains (blue line)
    ax.plot(
        epa_data.x_values,
        epa_data.p_gains,
        color='blue',
        linestyle='-',
        linewidth=1.5,
        label='P[X>x] (gains)',
        zorder=3
    )

    # Plot actual losses (red line)
    ax.plot(
        epa_data.x_values,
        epa_data.p_losses,
        color='red',
        linestyle='-',
        linewidth=1.5,
        label='P[X<-x] (losses)',
        zorder=2
    )

    # Set log scale on Y-axis
    ax.set_yscale('log')

    # Set axis limits
    ax.set_xlim(min(epa_data.x_values), max(epa_data.x_values))
    ax.set_ylim(y_min, y_max)

    # Set axis labels
    ax.set_xlabel(
        'Amount lost or gained overnight divided by\nthe Target Standard Deviation of Daily Returns',
        fontsize=11,
        fontweight='bold'
    )
    ax.set_ylabel(
        'Probability of observing a gain or loss\ngreater than the abscissa value',
        fontsize=11,
        fontweight='bold'
    )

    # Add title (without subtitle showing std dev)
    if subtitle:
        full_title = f"{title}\n{subtitle}"
    else:
        full_title = title

    ax.set_title(full_title, fontsize=14, fontweight='bold', pad=20)

    # Add grid
    if show_grid:
        ax.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.3, zorder=0)

    # Add legend
    if show_legend:
        ax.legend(loc='upper right', fontsize=10, framealpha=0.9)

    # Format Y-axis tick labels
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f'{y:.5g}'))

    # Add data info text box (bottom right)
    info_text = (
        f"Total Days: {epa_data.total_days:,}\n"
        f"Gain Days: {epa_data.total_gain_days:,} ({100*epa_data.total_gain_days/epa_data.total_days:.1f}%)\n"
        f"Loss Days: {epa_data.total_loss_days:,} ({100*epa_data.total_loss_days/epa_data.total_days:.1f}%)\n"
        f"Fund Size: ${epa_data.fund_size:,.0f}"
    )
    ax.text(
        0.98, 0.02,
        info_text,
        transform=ax.transAxes,
        fontsize=8,
        verticalalignment='bottom',
        horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3)
    )

    # Tight layout
    plt.tight_layout()

    # Save figure (format determined by file extension)
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', format='pdf')
    plt.close()

    print(f"Event probability chart saved to: {output_path}")


def render_event_probability_chart_pair(
    epa_data_short: EventProbabilityData,
    epa_data_long: EventProbabilityData,
    config: Dict,
    output_path_short: str,
    output_path_long: str
) -> None:
    """
    Render both short-range (0-2) and long-range (0-8) charts.

    This is a convenience function to generate both standard views of the
    event probability analysis.

    Args:
        epa_data_short: EventProbabilityData for 0-2 range
        epa_data_long: EventProbabilityData for 0-8 range
        config: Base configuration dict (will be customized for each chart)
        output_path_short: Path for 0-2 range chart
        output_path_long: Path for 0-8 range chart

    Example:
        >>> # Generate both views
        >>> x_vals_short = generate_x_values(0, 2, 20)
        >>> x_vals_long = generate_x_values(0, 8, 80)
        >>> epa_short = compute_event_probability_analysis(window, program_id, x_vals_short, db)
        >>> epa_long = compute_event_probability_analysis(window, program_id, x_vals_long, db)
        >>> config = {'title': 'Event Probability - Alphabet MFT'}
        >>> render_event_probability_chart_pair(
        ...     epa_short, epa_long, config,
        ...     'event_prob_0_2.png', 'event_prob_0_8.png'
        ... )
    """
    # Render short-range chart
    config_short = config.copy()
    config_short['title'] = config.get('title', 'Event Probability Analysis') + ' (0-2 Std Dev)'
    render_event_probability_chart(epa_data_short, config_short, output_path_short)

    # Render long-range chart
    config_long = config.copy()
    config_long['title'] = config.get('title', 'Event Probability Analysis') + ' (0-8 Std Dev)'
    config_long['y_min'] = 0.0000001  # Lower minimum for long-range view
    render_event_probability_chart(epa_data_long, config_long, output_path_long)
