"""
Brochures package for automated report generation.

This package contains modules for managing brochure templates, instances,
and generating PDF reports from database-stored configurations.
"""

from . import generator
from . import templates
from . import renderer

__all__ = ['generator', 'templates', 'renderer']
