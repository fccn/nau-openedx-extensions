"""Facade` pattern implementation to extract data from the LMS database."""
# pylint: disable=import-error
import logging
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import OuterRef, Q, Subquery
from lms.djangoapps.course_blocks.api import get_course_blocks  # pylint: disable=unused-import
from lms.djangoapps.course_blocks.transformers import start_date
from lms.djangoapps.course_home_api.utils import get_course_or_403
from lms.djangoapps.courseware.courses import get_course_blocks_completion_summary
from lms.djangoapps.grades.api import CourseGradeFactory
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.block_structure.api import get_block_structure_manager
from openedx.core.djangoapps.content.block_structure.transformers import BlockStructureTransformers
from openedx.core.djangoapps.enrollments import api as enrollment_api
from openedx.features.content_type_gating.block_transformers import ContentTypeGateTransformer
from xmodule.modulestore.django import modulestore

from nau_openedx_extensions.edxapp_wrapper.certificates import GeneratedCertificate
from nau_openedx_extensions.edxapp_wrapper.content import CourseOverview
from nau_openedx_extensions.edxapp_wrapper.student import CourseEnrollment
from nau_openedx_extensions.edxapp_wrapper.util import use_read_replica_if_available
from nau_openedx_extensions.partner_integration.exception import (
    PartnerIntegrationCourseOwnerException,
    PartnerIntegrationDataConflictException,
    PartnerIntegrationInternalErrorException,
    PartnerIntegrationInvalidDataProvidedException,
)

logger = logging.getLogger(__name__)


class DataExtractorFacade:
    """
    DataExtractorFacade base class.
    The intention of this class is to provide common methods to be used by
    the different data extractor facades. Since the partner clients
    can only access data they are authorized to, the base security scope
    filtering logic is common to all data extractor facades.
    """

    def apply_base_security_scope(self, base_security_scope):
        """
        Applies the partner query security scope to filter courses. It comes from
        the partner configuration.

        The `base_security_scope` is a dictionary that defines the filtering logic to apply
        in the execution of the courses query. It garantees that the partners can only access
        data they are authorized to. It focus on filtering data at the course level, as courses
        are the main entity related to certificates. `org` is the base field to filter courses,
        it is required, but other fields are optional and can be used to refine the query.

        Example of a `base_security_scope`:
        {
            "org": "NAU",
            "end__gte": "2025-01-01"
        }
        """
        try:
            logger.info("Executing query by security scope.")
            course_query = use_read_replica_if_available(CourseOverview.objects.filter(**base_security_scope))

            return course_query
        except Exception as e:
            logger.error("Error applying base security scope.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e


class CertificateExportFacade(DataExtractorFacade):
    """
    `Facade` is a design pattern that provides a simplified interface to a complex subsystem.
    read more at:
    - https://refactoring.guru/design-patterns/facade
    - https://en.wikipedia.org/wiki/Facade_pattern

    `CertificateExportFacade` is an implmentation of the `Facade` pattern that applies the methods
    to extract certificate data from the LMS database, based on the client's query security scope
    or specific request parameters (nifs, emails).
    """

    def get_certificates(self, query_security_scope, start_dt, end_dt, courses, nifs, emails, usernames):
        """
        Fetches certificates based on the client's `query_security_scope` and request parameters.
        If no specific parameters are provided, it fetches certificates based on the `query_security_scope`.
        """
        logger.info("Fetching certificates using CertificateExportFacade.")
        try:
            base_security_scope = query_security_scope.get("base_security_scope")
            base_certificates_scope = query_security_scope.get("base_certificates_scope")
            courses_base_query = super().apply_base_security_scope(base_security_scope)
            certificates_base_query = self._apply_base_certificates_scope(base_certificates_scope, courses_base_query)
            certificates = self._execute_certificates_query(
                certificates_base_query, start_dt, end_dt, courses, nifs, emails, usernames)

            return certificates
        except Exception as e:
            logger.error("Error fetching certificates.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e

    def _apply_base_certificates_scope(self, base_certificates_scope, courses_base_query):
        """
        Applies the partner base certificates scope to filter certificates. It comes from
        the partner configuration.

        The `base_certificates_scope` is a dictionary that defines the filtering logic
        to apply in the execution of the certificates query. It allows base filtering at
        the certificate level, being unecessary to fetch all certificates related to the
        courses, and also being not necessary to provide data via payload to refine the query.

        Example of a `base_certificates_scope`:
        {
            "mode": "honor",
            "user__email__icontains": "example.com",
            "status__in": ["audit_passing", "honor_passing"],
            "created_date__gte": "2025-01-01",
        }
        """
        try:
            certificates_query = use_read_replica_if_available(
                GeneratedCertificate.objects.filter(
                    course_id__in=courses_base_query
                )
            )

            if base_certificates_scope:
                certificates_query = use_read_replica_if_available(
                    GeneratedCertificate.objects.filter(**base_certificates_scope)
                )

            logger.info("Assembled certificates base query by security scope.")
            return certificates_query
        except Exception as e:
            logger.error("Error applying base certificates scope.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e

    def apply_heavy_operations(self, certificate_ids):
        """
        Apply the heavy operations of the query
        """
        certificates_query = GeneratedCertificate.objects.filter(id__in=certificate_ids)
        certificates_query = certificates_query.select_related("user")
        certificates_query = certificates_query.distinct()
        certificates_query = self._annotate_course_data(certificates_query)
        certificates_query = self._annotate_enrollment_data(certificates_query)

        return certificates_query

    def _execute_certificates_query(self, certificates_base_query, start_dt, end_dt, courses, nifs, emails, usernames):
        """
        Returns a queryset of certificates filtered by specific request parameters (nifs, emails).
        """
        try:
            logger.info(f"Fetching certificates using specific parameters. NIFs: {nifs}, Emails: {emails}")
            certificates_query = certificates_base_query

            if courses:
                q = Q()
                for code in courses:
                    q |= Q(course_id__icontains=code)

                certificates_query = certificates_query.filter(q)

            if not start_dt or not end_dt:
                start = datetime.now()
                start_dt = datetime.combine(start, time.min) - timedelta(days=365)
                end_dt = start

            filters = Q()
            if emails:
                filters |= Q(user__email__in=emails)
            if usernames:
                filters |= Q(user__username__in=usernames)
            if nifs:
                filters |= Q(user__nauuserextendedmodel__nif__in=nifs)
                filters |= Q(user__nauuserextendedmodel__cc_nif__in=nifs)
            filters &= Q(created_date__range=(start_dt, end_dt))

            return use_read_replica_if_available(certificates_query.filter(filters).values_list("id", flat=True))
        except Exception as e:
            logger.error("Error executing certificates query.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e

    def _annotate_course_data(self, certificates_query):
        """Annotates the certificates queryset with course data."""
        try:
            course_qs = CourseOverview.objects.filter(id=OuterRef("course_id"))

            return certificates_query.annotate(
                course_org=Subquery(course_qs.values("org")[:1]),
                course_display_name=Subquery(course_qs.values("display_name")[:1]),
                course_start=Subquery(course_qs.values("start")[:1]),
                course_end=Subquery(course_qs.values("end")[:1]),
                course_enrollment_start=Subquery(course_qs.values("enrollment_start")[:1]),
                course_enrollment_end=Subquery(course_qs.values("enrollment_end")[:1]),
            )
        except Exception as e:
            logger.error("Error annotating course data.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e

    def _annotate_enrollment_data(self, certificates_query):
        """Annotates the certificates queryset with enrollment data."""
        try:
            course_enrollment_qs = CourseEnrollment.objects.filter(
                user=OuterRef("user"),
                course_id=OuterRef("course_id")
            )
            return certificates_query.annotate(enrollment_date=Subquery(course_enrollment_qs.values("created")[:1]))
        except Exception as e:
            logger.error("Error annotating enrollment data.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e


class EnrollmentFacade(DataExtractorFacade):
    """
    `Facade` is a design pattern that provides a simplified interface to a complex subsystem.
    read more at:
    - https://refactoring.guru/design-patterns/facade
    - https://en.wikipedia.org/wiki/Facade_pattern

    `EnrollmentFacade` is an implmentation of the `Facade` pattern that applies the methods
    to manage enrollments, based on the client's query security scope and specific request
    parameters (nifs, emails).
    """

    def get_enrollments(self, query_security_scope, start_dt, end_dt, courses, nifs, emails, usernames):
        """
        Fetches enrollments based on the client's `query_security_scope` and request parameters.
        If no specific parameters are provided, it fetches enrollments based on the `query_security_scope`.
        """
        logger.info("Fetching enrollments using EnrollmentFacade.")
        try:
            base_security_scope = query_security_scope.get("base_security_scope", {})
            base_enrollments_scope = query_security_scope.get("base_enrollments_scope", {})
            courses_base_query = super().apply_base_security_scope(base_security_scope)
            enrollments_base_query = self._apply_base_enrollments_scope(base_enrollments_scope, courses_base_query)
            enrollments = self._execute_enrollments_query(
                enrollments_base_query, start_dt, end_dt, courses, nifs, emails, usernames)

            return enrollments
        except Exception as e:
            logger.error("Error fetching enrollments.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e

    def enroll_user(self, query_security_scope, course_id, nif, email, username):
        """
        Enrolls a user in a course using his NIF or email provided.
        It implements the enrollment logic using the Open edX enrollment API.

        Returns:
            list: The course CourseEnrollment object for the enrolled user.
        """
        logger.info("EnrollmentFacade: Start user enrollment")
        User = get_user_model()
        try:
            base_security_scope = query_security_scope.get("base_security_scope", {})
            courses_base_query = super().apply_base_security_scope(base_security_scope)
            course = courses_base_query.get(id=course_id)

            user = None
            if email:
                user = use_read_replica_if_available(User.objects.filter(email=email)).get()
            elif nif and not user:
                filters = (
                    Q(nauuserextendedmodel__nif=nif) |
                    Q(nauuserextendedmodel__cc_nif=nif)
                )
                user = use_read_replica_if_available(User.objects.filter(filters)).get()
            elif username and not user:
                user = use_read_replica_if_available(User.objects.filter(username=username)).get()

            if CourseEnrollment.objects.filter(course=course, user=user).exists():
                raise PartnerIntegrationDataConflictException("The user is already enrolled in this course.")

            # It implements the enrollment process from Open edX enrollment API, but
            # the return is not the CourseEnrollment object, so we need to fetch it
            # after enrollment to maintain consistency of the returned data from our
            # enrollment API. Doing it this way, we garantee that all enrollment logic
            # from Open edX is executed properly, and the data returned is consistent
            # with the rest of the system when it comes to CourseEnrollment objects,
            # that is, all enrollment endpoints return the same serializer structure.
            enrollment = enrollment_api.add_enrollment(user.username, str(course.id))
            if enrollment:
                enrollment_register = use_read_replica_if_available(
                    CourseEnrollment.objects.filter(
                        course=course,
                        user=user
                    )
                ).select_related("user", "course").first()
                return enrollment_register

            logger.error(
                "EnrollmentFacade: Enrollment could not be completed, "
                "the method enrollment_api.add_enrollment returned None."
                "The course_id: %s, user_id: %s", str(course.id), str(user.id)
            )
            raise PartnerIntegrationInternalErrorException(
                "Enrollment could not be completed due to an internal error. "
                "Please verify the request parameters."
            )
        except CourseOverview.DoesNotExist as e:
            logger.error(
                (
                    "EnrollmentFacade: Attempt to enroll in a non-existing course,"
                    "or this partner can't access to this course."
                ), exc_info=e)
            raise PartnerIntegrationInvalidDataProvidedException(
                "The specified course ID does not exist or is not accessible by the partner.",
            ) from e
        except PartnerIntegrationDataConflictException as e:
            logger.error("EnrollmentFacade: Attempt to enroll an already enrolled user.", exc_info=e)
            raise e
        except User.DoesNotExist as e:
            logger.error("EnrollmentFacade: Attempt to enroll a non-existing user.", exc_info=e)
            raise PartnerIntegrationInvalidDataProvidedException("The specified user does not exist.") from e
        except PartnerIntegrationCourseOwnerException as e:
            logger.error("EnrollmentFacade: Attempt to enroll in a course not owned by the partner.", exec_info=e)
            raise e
        except PartnerIntegrationInternalErrorException as e:
            raise e
        except Exception as e:
            logger.error("EnrollmentFacade: Internal error during enrollment.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e

    def _apply_base_enrollments_scope(self, base_enrollments_scope, courses_base_query):
        """
        Applies the partner base enrollments scope to filter enrollments. It comes from
        the partner configuration.

        The `base_enrollments_scope` is a dictionary that defines the filtering logic
        to apply in the execution of the enrollments query. It allows base filtering at
        the enrollment level, being unecessary to fetch all enrollments related to the
        courses, and also being not necessary to provide data via payload to refine the query.

        Example of a `base_enrollments_scope`:
        {
            "mode": "honor",
            "created__gte": "2025-01-01",
            "is_active": True,
        }
        """
        try:
            enrollments_query = use_read_replica_if_available(
                CourseEnrollment.objects.filter(
                    course__id__in=courses_base_query
                )
            )

            if base_enrollments_scope:
                enrollments_query = use_read_replica_if_available(
                    CourseEnrollment.objects.filter(**base_enrollments_scope)
                )

            logger.info("Assembled enrollments base query by security scope.")
            return enrollments_query
        except Exception as e:
            logger.error("Error applying base enrollments scope.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e

    def apply_heavy_operations(self, enrollment_ids):
        """
        Apply the heavy operations of the query
        """
        enrollments_query = CourseEnrollment.objects.filter(id__in=enrollment_ids)
        enrollments_query = enrollments_query.select_related("user", "course")
        enrollments_query = enrollments_query.distinct()

        return enrollments_query

    def _execute_enrollments_query(self, enrollments_base_query, start_dt, end_dt, courses, nifs, emails, usernames):
        """
        Returns a queryset of enrollments filtered by specific request parameters (nifs, emails).
        """
        try:
            logger.info(f"Fetching enrollments using specific parameters. NIFs: {nifs}, Emails: {emails}")
            enrollments_query = enrollments_base_query

            if courses:
                q = Q()
                for code in courses:
                    q |= Q(course__id__icontains=code)

                enrollments_query = enrollments_query.filter(q)

            if not start_dt or not end_dt:
                start = datetime.now()
                start_dt = datetime.combine(start, time.min) - timedelta(days=365)
                end_dt = start

            filters = Q()
            if emails:
                filters |= Q(user__email__in=emails)
            if usernames:
                filters |= Q(user__username__in=usernames)
            if nifs:
                filters |= Q(user__nauuserextendedmodel__nif__in=nifs)
                filters |= Q(user__nauuserextendedmodel__cc_nif__in=nifs)
            filters &= Q(created__range=(start_dt, end_dt))

            return use_read_replica_if_available(enrollments_query.filter(filters).values_list("id", flat=True))
        except Exception as e:
            logger.error("Error executing enrollments query.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e


class StudentProgressExportFacade(DataExtractorFacade):
    """
    `Facade` is a design pattern that provides a simplified interface to a complex subsystem.
    read more at:
    - https://refactoring.guru/design-patterns/facade
    - https://en.wikipedia.org/wiki/Facade_pattern

    `StudentProgressExportFacade` is an implmentation of the `Facade` pattern that applies the methods
    to extract student progress data from the LMS database, based on the client's query security scope.
    """

    def _get_student_user(self, student_id, nif, email, username):
        """Gets the student User object"""
        try:
            User = get_user_model()

            if student_id:
                return User.objects.get(id=student_id)
            elif nif:
                return User.objects.get(nauuserextendedmodel__nif=student_id)
            elif username:
                return User.objects.get(nauuserextendedmodel__username=username)

            return User.objects.get(email=email)
        except Exception as e:
            logger.error("Error fetching student user.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e

    def get_student_progress(self, course, student_id, nif, email, username, query_security_scope):
        """
        Fetches student progress based on the client's `query_security_scope` and request parameters.
        """
        try:

            base_security_scope = query_security_scope.get("base_security_scope")
            courses_base_query = super().apply_base_security_scope(base_security_scope)
            course = courses_base_query.filter(id=course)
            if not course:
                raise PartnerIntegrationCourseOwnerException()

            course_key = CourseKey.from_string(course)
            student = self._get_student_user(student_id, nif, email, username)

            course = get_course_or_403(student, 'load', course_key, check_if_enrolled=False)
            collected_block_structure = get_block_structure_manager(course_key).get_collected()

            course_grade = CourseGradeFactory().read(student, collected_block_structure=collected_block_structure)
            course_grade.update(visible_grades_only=True)

            transformers = BlockStructureTransformers()
            transformers += [start_date.StartDateTransformer(), ContentTypeGateTransformer()]
            # usage_key = collected_block_structure.root_block_usage_key
            # course_blocks = get_course_blocks(
            #     student,
            #     usage_key,
            #     transformers=transformers,
            #     collected_block_structure=collected_block_structure,
            #     include_has_scheduled_content=True
            # )

            user_has_passing_grade = False
            if not student.is_anonymous:
                user_grade = course_grade.percent
                user_has_passing_grade = user_grade >= course.lowest_passing_grade

            block = modulestore().get_course(course_key)
            grading_policy = block.grading_policy

            student_progress = {
                'username': student.username,
                'user_has_passing_grade': user_has_passing_grade,
                'completion_summary': get_course_blocks_completion_summary(course_key, student),
                'course_grade': course_grade,
                'grading_policy': grading_policy,
                'section_scores': list(course_grade.chapter_grades.values()),
            }

            return student_progress
        except Exception as e:
            logger.error("Error fetching student progress.", exc_info=e)
            raise PartnerIntegrationInternalErrorException() from e
