"""
Test fixtures and mock objects for coursecertificate tests.
"""

from faker import Faker
from opaque_keys.edx.keys import CourseKey

fake = Faker()


class Profile:
    """
    Mock profile object.
    """

    def __init__(self, name: str):
        self.name = name


class User:
    """
    Mock user object.
    """

    def __init__(self):
        self.id = fake.random_int(1, 10000)
        self.username = f"user_{fake.random_int(1, 10000)}"
        self.email = f"{self.username}@example.com"
        self.profile = Profile(f"{fake.first_name()} {fake.last_name()}")
        self.nauuserextendedmodel = NauUserExtended(self)

    def __repr__(self):
        return f"<User {self.username} ({self.email})>"


class CourseEnrollment:
    """
    Mock course enrollment object.
    """

    def __init__(self, user: User):
        self.user = user
        self.created = fake.date_time_this_decade()


class NauUserExtended:
    """
    Mock nau user extended model object.
    """

    def __init__(self, user: User):
        self.user = user
        self.nif = fake.numerify("########")
        self.cc_nif = fake.numerify("########")
        self.cc_nic = fake.numerify("###############")

    def __repr__(self):
        return f"<NauUser {self.user.username}>"


class Certificate:
    """
    Mock certificate object.
    """

    def __init__(self, user: User):
        self.id = fake.random_int(1, 10000)
        self.user = user
        self.course_id = CourseKey.from_string(f"course-v1:edX+Demo{fake.random_int(1, 100)}+Course")
        self.verify_uuid = fake.uuid4()
        self.grade = fake.pyfloat(left_digits=0, right_digits=2, min_value=0.0, max_value=1.0)
        self.key = fake.uuid4()
        self.status = "downloadable"
        self.mode = fake.random_element(elements=["honor", "verified", "professional"])
        self.name = f"{user.profile.name}"
        self.created_date = fake.date_time_this_decade()
        self.modified_date = fake.date_time_this_decade()

    def __repr__(self):
        return f"<Certificate {self.course_id} - {self.name} - {self.grade}>"
