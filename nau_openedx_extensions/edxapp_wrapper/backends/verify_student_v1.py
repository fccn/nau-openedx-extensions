"""
Real implementation of user id verifications service.
"""
from django.contrib.auth import get_user_model
from lms.djangoapps.verify_student.models import ManualVerification  # pylint: disable=import-error


def get_user_id_verifications(user_id, *args, **kwargs):
    """
    Read the user's `ManualVerification` from the edx-platform.

    Args:
        user: The user id to read the Id Verifications.

    Returns:
        An enumeration of those Id Verifications
    """
    user = get_user_model().objects.get(id=user_id)
    return ManualVerification.objects.filter(user=user).order_by('-created_at')


def create_user_id_verification(user_id, *args, **kwargs):
    """
    Create a new `ManualVerification` on the edx-platform.

    Args:
        user: The user id that this Id verification should be created.

    Returns:
        The object created
    """
    user = get_user_model().objects.get(id=user_id)
    ManualVerification(user=user, name=user.profile.name, *args, **kwargs).save()
