"""
Functions for the certificate engine
"""

from django.db.models import Func


class ToBase64(Func):  # pylint: disable=abstract-method
    """Convert a value to base64"""

    function = "TO_BASE64"


class SubstringIndex(Func):  # pylint: disable=abstract-method
    """Extract a substring using a substring index"""

    function = "SUBSTRING_INDEX"
