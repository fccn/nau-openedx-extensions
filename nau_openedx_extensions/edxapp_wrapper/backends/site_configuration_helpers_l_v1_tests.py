"""
Implementation used only for tests to get an Open edX site configuration.
"""


def get_value(val_name, default=None, **kwargs):  # pylint: disable=unused-argument
    """
    Return configuration value for the key specified as name argument.

    Args:
        val_name (str): Name of the key for which to return configuration value.
        default: default value tp return if key is not found in the configuration

    Returns:
        Configuration value for the given key.
    """
    return default
