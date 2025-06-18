"""
Custom exceptions for the certificate export module.
"""


class CertificateExportError(Exception):
    """Base exception for all certificate export related errors."""


class CertificateDownloadError(CertificateExportError):
    """Raised when there is an error downloading certificates."""


class CertificateCompressionError(CertificateExportError):
    """Raised when there is an error compressing certificates."""
