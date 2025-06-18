"""
Utility functions for the certificate export module.
"""

import re


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to be safe for all operating systems.

    Args:
        filename (str): The original filename

    Returns:
        str: A sanitized filename safe for all operating systems
    """
    # Remove any non-alphanumeric characters except ._- and spaces
    sanitized = re.sub(r"[^\w\s\.\-]", "", filename)
    # Replace spaces with underscores
    sanitized = sanitized.replace(" ", "_")
    # Ensure the filename ends with .pdf
    if not sanitized.endswith(".pdf"):
        sanitized += ".pdf"
    return sanitized
