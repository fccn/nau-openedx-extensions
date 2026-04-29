"""
Tests for Id Verification of studentes.
"""

from datetime import datetime
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from openedx_events.learning.data import CourseEnrollmentData, UserData
from openedx_events.learning.signals import COURSE_ENROLLMENT_CHANGED

from nau_openedx_extensions.verify_student.id_verification import (
    event_receiver_no_id_verify_for_enrollment_modes,
    event_receiver_no_id_verify_on_login,
)


class VerifyStudentTest(TestCase):
    """
    Tests for Id Verification patch.
    """

    @patch(
        "nau_openedx_extensions.verify_student.id_verification.get_user_id_verifications"
    )
    @patch(
        "nau_openedx_extensions.verify_student.id_verification.create_user_id_verification"
    )
    def test_verify_student_create_new_verification(
        self, create_user_id_verification_mock, get_user_id_verifications_mock
    ):
        """
        Test an enrollment mode that requires a ID Verification.
        """
        user_id = 10
        get_user_id_verifications_mock.return_value = []
        COURSE_ENROLLMENT_CHANGED.connect(event_receiver_no_id_verify_for_enrollment_modes)
        COURSE_ENROLLMENT_CHANGED.send_event(
            enrollment=CourseEnrollmentData(
                user=UserData(id=user_id, is_active=True, pii=None),
                mode="verified",
                course=None,
                is_active=None,
                creation_date=None,
            )
        )
        create_user_id_verification_mock.assert_called_once()
        self.assertEqual(create_user_id_verification_mock.call_args.args[0], user_id)
        create_user_id_verification_mock_kwargs = (
            create_user_id_verification_mock.call_args.kwargs
        )
        self.assertEqual(
            create_user_id_verification_mock_kwargs,
            {
                **create_user_id_verification_mock_kwargs,
                **{
                    "status": "approved",
                },
            },
        )
        self.assertEqual(
            create_user_id_verification_mock_kwargs,
            {
                **create_user_id_verification_mock_kwargs,
                **{
                    "reason": "Skip id verification from nau_openedx_extensions",
                },
            },
        )
        self.assertEqual(
            create_user_id_verification_mock.call_args.kwargs.get(
                "expiration_date"
            ).year,
            datetime.today().year + 100,
        )

    @patch(
        "nau_openedx_extensions.verify_student.id_verification.get_user_id_verifications"
    )
    @patch(
        "nau_openedx_extensions.verify_student.id_verification.create_user_id_verification"
    )
    def test_verify_student_enrollment_mode_not_need_id_verification_patch(
        self, create_user_id_verification_mock, get_user_id_verifications_mock
    ):
        """
        Test a case enrollment mode that doesn't requires a ID Verification.
        """
        user_id = 10
        get_user_id_verifications_mock.return_value = []
        COURSE_ENROLLMENT_CHANGED.connect(event_receiver_no_id_verify_for_enrollment_modes)
        COURSE_ENROLLMENT_CHANGED.send_event(
            enrollment=CourseEnrollmentData(
                user=UserData(id=user_id, is_active=True, pii=None),
                mode="honor",
                course=None,
                is_active=None,
                creation_date=None,
            )
        )
        create_user_id_verification_mock.assert_not_called()

    @patch(
        "nau_openedx_extensions.verify_student.id_verification.get_user_id_verifications"
    )
    @patch(
        "nau_openedx_extensions.verify_student.id_verification.create_user_id_verification"
    )
    @override_settings(NAU_NO_ID_VERIFY_FOR_ENROLLMENT_MODES="verified, somemode")
    def test_verify_student_change_enrollment_modes_require_id_verification(
        self, create_user_id_verification_mock, get_user_id_verifications_mock
    ):
        """
        Test that changing the setting `NAU_NO_ID_VERIFY_FOR_ENROLLMENT_MODES` to include a custom enrollment mode,
        and test with that new custom enrollment mode, it still creates an id verification.
        """
        user_id = 10
        get_user_id_verifications_mock.return_value = []
        COURSE_ENROLLMENT_CHANGED.connect(event_receiver_no_id_verify_for_enrollment_modes)
        COURSE_ENROLLMENT_CHANGED.send_event(
            enrollment=CourseEnrollmentData(
                user=UserData(id=user_id, is_active=True, pii=None),
                mode="somemode",
                course=None,
                is_active=None,
                creation_date=None,
            )
        )
        create_user_id_verification_mock.assert_called_once()
        self.assertEqual(create_user_id_verification_mock.call_args.args[0], user_id)
        create_user_id_verification_mock_kwargs = (
            create_user_id_verification_mock.call_args.kwargs
        )
        self.assertEqual(
            create_user_id_verification_mock_kwargs,
            {
                **create_user_id_verification_mock_kwargs,
                **{
                    "status": "approved",
                },
            },
        )
        self.assertEqual(
            create_user_id_verification_mock_kwargs,
            {
                **create_user_id_verification_mock_kwargs,
                **{
                    "reason": "Skip id verification from nau_openedx_extensions",
                },
            },
        )
        self.assertEqual(
            create_user_id_verification_mock.call_args.kwargs.get(
                "expiration_date"
            ).year,
            datetime.today().year + 100,
        )

    @patch(
        "nau_openedx_extensions.verify_student.id_verification.get_user_id_verifications"
    )
    @patch(
        "nau_openedx_extensions.verify_student.id_verification.create_user_id_verification"
    )
    def test_verify_student_with_existing_id_verification(
        self, create_user_id_verification_mock, get_user_id_verifications_mock
    ):
        """
        Test that if the user already has an id verification, it won't try to create a new one.
        """
        active_at_datetime_mock = Mock()
        active_at_datetime_mock.return_value = True

        user_id = 10
        get_user_id_verifications_mock.return_value = active_at_datetime_mock
        COURSE_ENROLLMENT_CHANGED.connect(event_receiver_no_id_verify_for_enrollment_modes)
        COURSE_ENROLLMENT_CHANGED.send_event(
            enrollment=CourseEnrollmentData(
                user=UserData(id=user_id, is_active=True, pii=None),
                mode="verify",
                course=None,
                is_active=None,
                creation_date=None,
            )
        )
        create_user_id_verification_mock.assert_not_called()


class VerifyStudentOnLoginTest(TestCase):
    """
    Tests for the login-triggered ID Verification receiver.
    """

    @patch(
        "nau_openedx_extensions.verify_student.id_verification.get_user_id_verifications"
    )
    @patch(
        "nau_openedx_extensions.verify_student.id_verification.create_user_id_verification"
    )
    def test_login_creates_verification_when_none_exists(
        self, create_user_id_verification_mock, get_user_id_verifications_mock
    ):
        """
        Test that logging in creates an ID Verification when the user has none.
        """
        user = Mock()
        user.id = 42
        get_user_id_verifications_mock.return_value = []

        event_receiver_no_id_verify_on_login(sender=None, user=user, request=None)

        create_user_id_verification_mock.assert_called_once()
        self.assertEqual(create_user_id_verification_mock.call_args.args[0], user.id)
        call_kwargs = create_user_id_verification_mock.call_args.kwargs
        self.assertEqual(call_kwargs["status"], "approved")
        self.assertEqual(call_kwargs["reason"], "Skip id verification from nau_openedx_extensions")
        self.assertEqual(call_kwargs["expiration_date"].year, datetime.today().year + 100)

    @patch(
        "nau_openedx_extensions.verify_student.id_verification.get_user_id_verifications"
    )
    @patch(
        "nau_openedx_extensions.verify_student.id_verification.create_user_id_verification"
    )
    def test_login_does_not_create_verification_when_already_active(
        self, create_user_id_verification_mock, get_user_id_verifications_mock
    ):
        """
        Test that logging in does not create a duplicate ID Verification when one is already active.
        """
        user = Mock()
        user.id = 42
        existing_verification = Mock()
        existing_verification.active_at_datetime.return_value = True
        get_user_id_verifications_mock.return_value = [existing_verification]

        event_receiver_no_id_verify_on_login(sender=None, user=user, request=None)

        create_user_id_verification_mock.assert_not_called()

    @patch(
        "nau_openedx_extensions.verify_student.id_verification.get_user_id_verifications"
    )
    @patch(
        "nau_openedx_extensions.verify_student.id_verification.create_user_id_verification"
    )
    def test_login_does_not_propagate_exceptions(
        self, create_user_id_verification_mock, get_user_id_verifications_mock
    ):
        """
        Test that an error inside the login receiver doesn't break the login flow.
        """
        user = Mock()
        user.id = 42
        get_user_id_verifications_mock.return_value = []
        create_user_id_verification_mock.side_effect = Exception("DB error")

        # Should not raise
        event_receiver_no_id_verify_on_login(sender=None, user=user, request=None)
