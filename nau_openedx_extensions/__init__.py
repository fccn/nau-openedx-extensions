# pylint: disable=django-not-configured
"""
Init for main nau openedx extensions app
"""

from __future__ import unicode_literals

import os
from pathlib import Path

__version__ = "0.3.0"

ROOT_DIRECTORY = Path(os.path.dirname(os.path.abspath(__file__)))
