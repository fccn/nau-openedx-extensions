"""
Test cases for NIF validation
This module contains a set of unit tests for the NIF validation function.
This test suite checks the functionality of the NIF validation
function to ensure it correctly identifies valid and invalid NIFs.
The tests include various scenarios such as valid NIFs, invalid NIFs,
empty NIFs, and NIFs with spaces or special characters.
Each test case is designed to cover a specific aspect of the NIF
validation logic, ensuring comprehensive coverage of the function's
behavior.
"""
from django.test import TestCase

from nau_openedx_extensions.utils.nif import is_nif_valid


class TestNifValidation(TestCase):
    """
    Test cases for NIF validation
    """

    def test_valid_nif(self):
        """Test valid NIFs"""
        valid_nifs = [
            "123456789",  # Single person started with '1'
            "237427893",  # Single person started with '2'
            "369538927",  # Single person started with '3' starting being issued from 2019
            "574826033",  # Company started with '5'
            "688501877",  # Public company started with '6'
            "828407487",  # Individual entrepreneur started with '8'
            "969359268",  # Irregular legal person or provisional number started with '9'
        ]
        for nif in valid_nifs:
            with self.subTest(nif=nif):
                self.assertTrue(is_nif_valid(nif), f"NIF {nif} should be valid")

    def test_nif_too_short(self):
        """Test too short NIF"""
        self.assertFalse(is_nif_valid("12345678"), "NIF too short should be invalid")

    def test_nif_too_long(self):
        """Test too long NIF"""
        self.assertFalse(is_nif_valid("12345678"), "NIF too long should be invalid")

    def test_nif_non_numeric_characters(self):
        """Test with non-numeric characters NIF"""
        self.assertFalse(is_nif_valid("abcdefghij"), "NIF with non-numeric characters should be invalid")

    def test_nif_invalid_checksum(self):
        """Test invalid checksum NIF"""
        self.assertFalse(is_nif_valid("123456784"), "NIF with invalid checksum should be invalid")

    def test_empty_nif(self):
        """Test empty NIF"""
        self.assertFalse(is_nif_valid(""), "Empty NIF should be invalid")

    def test_nif_with_spaces(self):
        """Test NIF with spaces"""
        self.assertFalse(is_nif_valid(" 123456789 "), "NIF with spaces should be invalid")

    def test_nif_with_special_characters(self):
        """Test NIF with special characters"""
        self.assertFalse(is_nif_valid("123-456-789"), "NIF with special characters should be invalid")
