"""Serializers for Data Extractor API requests and responses."""
# pylint: disable=abstract-method
import logging
from datetime import datetime

from rest_framework import serializers

from nau_openedx_extensions.edxapp_wrapper.certificates import GeneratedCertificate
from nau_openedx_extensions.edxapp_wrapper.student import CourseEnrollment
from nau_openedx_extensions.partner_integration.exception import (
    PartnerIntegrationInvalidDataProvidedException,
    PartnerIntegrationNoDataProvidedException,
)

logger = logging.getLogger(__name__)


class CompleteCertificateDataSerializer(serializers.ModelSerializer):
    """Serializer to flatten certificate, user, and course enrollment data."""
    certificate_date = serializers.DateTimeField(source='created_date', read_only=True)
    certificate_url = serializers.CharField(source='download_url', read_only=True)
    user_nif = serializers.CharField(source='user.nau_nif', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    course_id = serializers.CharField(read_only=True)
    course_name = serializers.CharField(source='course_display_name', read_only=True)
    enrollment_date = serializers.DateTimeField(read_only=True)
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        """Returns the full name of the user, or username if full name is not available."""
        user = obj.user
        full_name = user.get_full_name().strip()
        return full_name or user.username

    class Meta:
        model = GeneratedCertificate
        fields = [
            "certificate_date",
            "certificate_url",
            "user_nif",
            "user_email",
            "username",
            "name",
            "course_id",
            "course_name",
            "enrollment_date"
        ]


class DataExtractorRequestSerializer(serializers.Serializer):
    """Data extractor request serializer with validation."""
    start_date = serializers.CharField(required=False)
    end_date = serializers.CharField(required=False)
    courses = serializers.ListField(child=serializers.CharField(), required=False)
    nifs = serializers.ListField(child=serializers.CharField(), required=False)
    emails = serializers.ListField(child=serializers.EmailField(), required=False)
    usernames = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        """Validates the request data."""
        start = attrs.get("start_date")
        end = attrs.get("end_date")

        self._validate_dates(start, end)

        nifs = attrs.get("nifs", [])
        emails = attrs.get("emails", [])
        usernames = attrs.get("usernames", [])
        query_security_scope = self.context.get("query_security_scope", {})

        if not nifs and not emails and not usernames:
            if not query_security_scope:
                raise PartnerIntegrationNoDataProvidedException()

        return attrs

    def _validate_dates(self, start_date: datetime, end_date: datetime):
        """Validates if the provided dates are correct."""
        if not start_date and not end_date:
            return

        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)

            if start > end:
                raise PartnerIntegrationInvalidDataProvidedException("Start date must not be greater than end date.")

            if (end - start).days > 365:
                raise PartnerIntegrationInvalidDataProvidedException("Date range cannot exceed one year.")
        except PartnerIntegrationInvalidDataProvidedException as e:
            logger.error("DataExtractorRequestSerializer: Invalid date range provided.", exc_info=e)
            raise e
        except Exception as e:
            logger.error("DataExtractorRequestSerializer: Invalid date format provided.", exc_info=e)
            raise PartnerIntegrationInvalidDataProvidedException("Invalid date format. Use ISO 8601 format.") from e


class EnrollUserRequestSerializer(serializers.Serializer):
    """Serializer for enroll user request with validation."""
    course = serializers.CharField(required=False)
    nif = serializers.CharField(required=False)
    email = serializers.CharField(required=False)
    username = serializers.CharField(required=False)

    def validate(self, attrs):
        """Validates the request data."""
        course = attrs.get("course")
        nif = attrs.get("nif")
        email = attrs.get("email")
        username = attrs.get("username")
        query_security_scope = self.context.get("query_security_scope", {})

        if not query_security_scope:
            raise PartnerIntegrationNoDataProvidedException("No security scope configured to enroll users.")

        if not course:
            raise PartnerIntegrationNoDataProvidedException("Course ID must be provided to enroll users.")

        if not nif and not email and not username:
            raise PartnerIntegrationNoDataProvidedException(
                "At least one of NIF, email, or username must be provided to enroll users."
            )

        return attrs


class CompleteEnrollmentDataSerializer(serializers.ModelSerializer):
    """Serializer to flatten course enrollment, user, and course data."""
    user_nif = serializers.CharField(source='user.nau_nif', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    user_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)
    enrollment_date = serializers.DateTimeField(source="created", read_only=True)
    active_enrollment = serializers.BooleanField(source="is_active", read_only=True)
    course_id = serializers.CharField(source="course.id", read_only=True)
    course_name = serializers.CharField(source='course.display_name', read_only=True)
    course_org = serializers.CharField(source="course.org", read_only=True)
    course_start = serializers.CharField(source="course.start", read_only=True)
    course_end = serializers.CharField(source="course.end", read_only=True)
    course_enrollment_start = serializers.CharField(source="course.enrollment_start", read_only=True)
    course_enrollment_end = serializers.CharField(source="course.enrollment_end", read_only=True)

    def get_user_name(self, obj):
        """Returns the full name of the user, or username if full name is not available."""
        user = obj.user
        full_name = user.get_full_name().strip()
        return full_name or user.username

    class Meta:
        model = CourseEnrollment
        fields = [
            "user_nif",
            "username",
            "user_name",
            "user_email",
            "course_id",
            "course_name",
            "enrollment_date",
            "active_enrollment",
            "course_org",
            "course_start",
            "course_end",
            "course_enrollment_start",
            "course_enrollment_end",
        ]


class CourseGradeSerializer(serializers.Serializer):
    """Course grade serializer for data extractor responses."""
    percent = serializers.FloatField(required=False)
    letter_grade = serializers.CharField(required=False, allow_blank=True)
    passed = serializers.BooleanField(required=False)


class ProblemScoreSerializer(serializers.Serializer):
    """Serializer for individual problem scores within a subsection."""
    location = serializers.CharField()
    earned = serializers.FloatField()
    possible = serializers.FloatField()


class ReadSubsectionGradeSerializer(serializers.Serializer):
    """Serializer for subsection grades within a chapter."""
    location = serializers.CharField()
    display_name = serializers.CharField()
    format = serializers.CharField()
    earned = serializers.FloatField(source="graded_total.earned")
    possible = serializers.FloatField(source="graded_total.possible")
    percent_graded = serializers.FloatField()
    problem_scores = serializers.SerializerMethodField()

    def get_problem_scores(self, obj):
        """Gets the list of problem scores for the subsection."""
        return [
            {
                "location": str(locator),
                "earned": score.earned,
                "possible": score.possible,
            }
            for locator, score in obj.problem_scores.items()
        ]


class ChapterGradeSerializer(serializers.Serializer):
    """
    Serializer for chapter grades within a course to be used
    in data extractor responses.
    """
    display_name = serializers.CharField()
    url_name = serializers.CharField()
    sections = ReadSubsectionGradeSerializer(many=True)


class CompletionSummarySerializer(serializers.Serializer):
    """Serializer for completion summary data in data extractor responses."""
    complete_count = serializers.IntegerField()
    incomplete_count = serializers.IntegerField()
    locked_count = serializers.IntegerField()


class GradingPolicySerializer(serializers.Serializer):
    """Serializer for grading policy data in data extractor responses."""
    grader = serializers.JSONField(source="GRADER")
    grade_cutoffs = serializers.JSONField(source="GRADE_CUTOFFS")


class CourseProgressSerializer(serializers.Serializer):
    """Serializer for course progress data in data extractor responses."""
    username = serializers.CharField()
    user_has_passing_grade = serializers.BooleanField()
    completion_summary = CompletionSummarySerializer()
    course_grade = CourseGradeSerializer()
    grading_policy = GradingPolicySerializer()
    section_scores = ChapterGradeSerializer(many=True)
