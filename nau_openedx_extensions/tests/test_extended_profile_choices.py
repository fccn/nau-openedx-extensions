"""
Tests for the NAU extended profile controlled lists.

These guard the part that is easy to break silently: a code that does not match
between the choice list and the legacy map leaves rows holding a value no form
will accept, and nothing raises at migration time.
"""

from nau_openedx_extensions.custom_registration_form.choices import (
    CAE4_CHOICES,
    EMPLOYMENT_SITUATION_CHOICES,
    EMPLOYMENT_SITUATION_LEGACY_MAP,
    LEGACY_PUBLIC_SERVICE_CONTRACT,
    NUTS_CHOICES,
)

ALL_LISTS = {
    "employment_situation": EMPLOYMENT_SITUATION_CHOICES,
    "nuts": NUTS_CHOICES,
    "cae4": CAE4_CHOICES,
}

# Matches max_length on the model fields.
MAX_CODE_LENGTH = 64


def test_codes_are_unique_within_each_list():
    for name, choices in ALL_LISTS.items():
        codes = [code for code, _label in choices]
        assert len(codes) == len(set(codes)), f"duplicate code in {name}"


def test_codes_fit_the_column():
    for name, choices in ALL_LISTS.items():
        for code, _label in choices:
            assert len(code) <= MAX_CODE_LENGTH, f"{name}: {code} is too long"


def test_every_choice_has_a_label():
    for name, choices in ALL_LISTS.items():
        for code, label in choices:
            assert label.strip(), f"{name}: {code} has an empty label"


def test_legacy_map_targets_are_real_choices():
    valid_codes = {code for code, _label in EMPLOYMENT_SITUATION_CHOICES}
    for old_value, new_value in EMPLOYMENT_SITUATION_LEGACY_MAP.items():
        assert new_value in valid_codes, f"{old_value} maps to unknown code {new_value}"


def test_legacy_map_covers_every_previous_option():
    previously_stored = {
        "Student",
        "Unemployed",
        "Public service contract",
        "Private institution contract",
        "Self employed entrepreneur",
        "Other",
    }
    assert set(EMPLOYMENT_SITUATION_LEGACY_MAP) == previously_stored


def test_public_service_contract_keeps_its_own_code():
    # It was split into ten Função Pública entries, so it must not be silently
    # collapsed into one of them.
    assert EMPLOYMENT_SITUATION_LEGACY_MAP["Public service contract"] == LEGACY_PUBLIC_SERVICE_CONTRACT
    assert LEGACY_PUBLIC_SERVICE_CONTRACT in {code for code, _label in EMPLOYMENT_SITUATION_CHOICES}
