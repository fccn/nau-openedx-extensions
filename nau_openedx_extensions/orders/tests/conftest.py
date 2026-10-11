"""
Fixtures for the orders app tests.
"""

import pytest


@pytest.fixture(autouse=True)
def no_webpack_loader(monkeypatch):
    """
    Render LMS page templates without webpack bundles, the same way edx-platform's own conftest does.
    """
    monkeypatch.setattr(
        "webpack_loader.templatetags.webpack_loader.render_bundle",
        lambda entry, extension=None, config="DEFAULT", attrs="": "",
    )
    monkeypatch.setattr(
        "webpack_loader.utils.get_as_tags",
        lambda entry, extension=None, config="DEFAULT", attrs="": [],
    )
    monkeypatch.setattr(
        "webpack_loader.utils.get_files",
        lambda entry, extension=None, config="DEFAULT", attrs="": [],
    )
