"""Email block backend abstraction."""

from lms.djangoapps.bulk_email.models import EMAIL_TARGETS, Target  # pylint: disable=import-error


def get_email_target():
    """Get email target."""
    return EMAIL_TARGETS

def get_target():
    """Get target."""
    return Target
