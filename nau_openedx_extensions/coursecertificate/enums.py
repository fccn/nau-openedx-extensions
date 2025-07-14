"""
Enums for the certificate engine
"""

from enum import Enum


class FieldType(Enum):
    """Available field types for certificate data extraction"""

    STANDARD = "standard"
    CONCATENATED = "concatenated"
    COMPUTED = "computed"
    SUBSTRING = "substring"


class Transformations(Enum):
    """Available transformations for field values"""

    MD5 = "md5"
    BASE64 = "base64"
