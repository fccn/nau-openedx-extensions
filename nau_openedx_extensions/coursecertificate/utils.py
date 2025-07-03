"""
This module is used to read the config file and get the service config.
"""

import os
import yaml


def read_config(config_path):
    """
    Read the config file and return the config.

    Args:
        config_path (str): The path to the config file.

    Returns:
        dict: The config.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(current_dir, config_path), "r") as file:
        return yaml.safe_load(file)


def get_service_config(service_name):
    """
    Get the config for a given service.

    Args:
        service_name (str): The name of the service.

    Returns:
        dict: The config for the given service.
    """
    config = read_config("config.yml")
    return config[service_name]
