"""
Mock implementation on getting a student course enrollment allowed.
"""


def get_student_course_enrollment_allowed(user, course_id, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Return configuration value for the key specified as name argument.

    Args:
        val_name (str): Name of the key for which to return configuration value.
        default: default value tp return if key is not found in the configuration

    Returns:
        Configuration value for the given key.
    """
    return None
