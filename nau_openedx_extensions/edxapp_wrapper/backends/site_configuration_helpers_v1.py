"""
Real implementation on getting an Open edX site configuration.
"""
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers  # pylint: disable=import-error


def get_value(val_name, default=None, **kwargs):
    """
    Return configuration value for the key specified as name argument.

    Args:
        val_name (str): Name of the key for which to return configuration value.
        default: default value tp return if key is not found in the configuration

    Returns:
        Configuration value for the given key.
    """
    return configuration_helpers.get_value(val_name, default)
