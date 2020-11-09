#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

import os
import re

from setuptools import setup


def load_requirements(*requirements_paths):
    """
    Load all requirements from the specified requirements files.
    Returns a list of requirement strings.
    """
    requirements = set()
    for path in requirements_paths:
        requirements.update(
            line.split('#')[0].strip() for line in open(path).readlines()
            if is_requirement(line)
        )
    return list(requirements)


def is_requirement(line):
    """
    Return True if the requirement line is a package requirement;
    that is, it is not blank, a comment, or editable.
    """
    # Remove whitespace at the start/end of the line
    line = line.strip()

    # Skip blank lines, comments, and editable installs
    return not (
        line == '' or
        line.startswith('-r') or
        line.startswith('#') or
        line.startswith('-e') or
        line.startswith('git+') or
        line.startswith('-c')
    )


def get_version(*file_paths):
    """Retrieves the version from the main app __init__.py"""
    filename = os.path.join(os.path.dirname(__file__), *file_paths)
    version_file = open(filename).read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError('Unable to find version string.')


version = get_version("nau_openedx_extensions", "__init__.py")


setup(
    name="nau-openedx-extensions",
    version=version,
    author="eduNEXT",
    author_email="contact@edunext.co",
    url="https://gitlab.fccn.pt/nau/nau-openedx-extensions",
    description="NAU openedX extensions",
    long_description="",
    install_requires=load_requirements('requirements/base.in'),
    scripts=[],
    license="AGPL 3.0",
    platforms=["any"],
    zip_safe=False,
    packages=[
        'nau_openedx_extensions',
    ],
    include_package_data=True,
    entry_points={
        "lms.djangoapp": [
            "nau_openedx_extensions = nau_openedx_extensions.apps:NauOpenEdxConfig",
        ],
        "openedx.course_tab": [
            "nau = nau_openedx_extensions.message_gateway.views.tab:NauMessageGatewayTab",
            ],
    }
)
