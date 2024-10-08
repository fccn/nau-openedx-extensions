"""
Real implementation of user id verifications service.
"""


def get_user_id_verifications(user_id, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Read the user's `ManualVerification` from the edx-platform.

    Args:
        user_id: The user id to read the Id Verifications.

    Returns:
        An enumeration of those Id Verifications
    """
    return []

def create_user_id_verification(user_id, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Create a new `ManualVerification` on the edx-platform.

    Args:
        user_id: The user id that this Id verification should be created.

    Returns:
        The object created
    """
    return None
