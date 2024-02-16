"""
Script that checks the course versions from MongoDB and MySQL.

To manually develop the script you can edit it on the fly and execute it.
docker cp courses_version_check_mongo_mysql.py \
    openedx_lms:/openedx/venv/lib/python3.8/site-packages/nau_openedx_extensions/\
        management/commands/courses_version_check_mongo_mysql.py && \
    docker exec -i openedx_lms python manage.py lms courses_version_check_mongo_mysql
"""

from common.djangoapps.split_modulestore_django.models import (  # lint-amnesty, pylint: disable=import-error
    SplitModulestoreCourseIndex,
)
from django.conf import settings
from django.core.management.base import BaseCommand
from xmodule.mongo_utils import connect_to_mongodb  # lint-amnesty, pylint: disable=import-error


class Command(BaseCommand):
    """
    Script that checks the course versions from MongoDB and MySQL.
    """

    help = "Checks the course versions from MongoDB and MySQL"

    def log_msg(self, msg):
        self.stdout.write(str(msg))
        self.stdout.flush()

    @staticmethod
    def organize_courses(mysql, mongo):
        """
        Function to check which courses are in mysql, mongo and both
        """
        mysql_courses = {course["course_id"] for course in mysql}
        mongo_courses = {course["course_id"] for course in mongo}

        # Courses that are only in mysql
        only_mysql = [
            course
            for course in mysql
            if course["course_id"] in mysql_courses - mongo_courses
        ]
        # Courses that are only in mysql
        only_mongo = [
            course
            for course in mongo
            if course["course_id"] in mongo_courses - mysql_courses
        ]
        # Courses that are in both databases
        both = [
            course["course_id"]
            for course in mysql + mongo
            if course["course_id"] in mysql_courses & mongo_courses
        ]

        return only_mysql, only_mongo, both

    @staticmethod
    def find_different_versions(mysql, mongo, id_list, mode):
        """
        Function to find courses that have different versions
        """

        different_versions = []
        mysql_courses = [course for course in mysql if course["course_id"] in id_list]
        mongo_courses = [course for course in mongo if course["course_id"] in id_list]

        for mysql_course in mysql_courses:
            for mongo_course in mongo_courses:
                if (
                    mysql_course["course_id"] == mongo_course["course_id"]
                    and mysql_course[mode] != mongo_course[mode]
                ):
                    different_versions.append(
                        {
                            "course_id": mysql_course["course_id"],
                            "mongo_id": mongo_course[mode],
                            "mongo_last_update": mongo_course["last_update"],
                            "mysql_id": mysql_course[mode],
                            "mysql_last_update": mysql_course["last_update"],
                        }
                    )

        return different_versions

    def handle(self, *args, **options):
        """
        Execute the command
        """
        # Configurations needed to connect to mongo
        tz_aware = None
        db = settings.CONTENTSTORE["DOC_STORE_CONFIG"].get("db")
        host = settings.CONTENTSTORE["DOC_STORE_CONFIG"].get("host")
        port = settings.CONTENTSTORE["DOC_STORE_CONFIG"].get("port")
        user = settings.CONTENTSTORE["DOC_STORE_CONFIG"].get("user")
        password = settings.CONTENTSTORE["DOC_STORE_CONFIG"].get("password")

        kwargs = {
            "replicaSet": settings.CONTENTSTORE["DOC_STORE_CONFIG"].get("replicaSet"),
            "connectTimeoutMS": 2000,
            "socketTimeoutMS": 3000,
            "ssl": settings.CONTENTSTORE["DOC_STORE_CONFIG"].get("ssl"),
        }

        database = connect_to_mongodb(
            db,
            host,
            port=port,
            tz_aware=tz_aware,
            user=user,
            password=password,
            **kwargs
        )

        active_versions = database["modulestore.active_versions"]

        mongo_query = {}

        # Take out all active versions
        mongo_courses = list(active_versions.find(mongo_query))

        mongo_publish = []
        mongo_draft = []

        # Keep only the information we need
        for course in mongo_courses:
            mongo_publish.append(
                {
                    "publish_id": str(course.get("versions").get("published-branch")),
                    "course_id": "course-v1:"
                    + course.get("org")
                    + "+"
                    + course.get("course")
                    + "+"
                    + course.get("run"),
                    "last_update": course.get("last_update"),
                }
            )
            mongo_draft.append(
                {
                    "draft_id": str(course.get("versions").get("draft-branch")),
                    "course_id": "course-v1:"
                    + course.get("org")
                    + "+"
                    + course.get("course")
                    + "+"
                    + course.get("run"),
                    "last_update": course.get("last_update"),
                }
            )

        # Take out all active versions
        mysql_courses = SplitModulestoreCourseIndex.objects.all()

        mysql_courses = list(
            SplitModulestoreCourseIndex.objects.values(
                "course_id",
                "draft_version",
                "published_version",
                "library_version",
                "last_update",
            )
        )

        mysql_publish = []
        mysql_draft = []

        # Keep only the information we need
        for course in mysql_courses:
            mysql_publish.append(
                {
                    "publish_id": course["published_version"],
                    "course_id": str(course["course_id"]),
                    "last_update": course["last_update"],
                }
            )
            mysql_draft.append(
                {
                    "draft_id": course["draft_version"],
                    "course_id": str(course["course_id"]),
                    "last_update": course["last_update"],
                }
            )

        publish_only_mysql, publish_only_mongo, publish_both = self.organize_courses(
            mysql_publish, mongo_publish
        )

        self.log_msg("=" * 100)
        self.log_msg("Publish version only in mysql")
        self.log_msg("=" * 100)
        self.log_msg(publish_only_mysql)
        self.log_msg("=" * 100)
        self.log_msg("Draft version only in mongo")
        self.log_msg("=" * 100)
        self.log_msg(publish_only_mongo)

        draft_only_mysql, draft_only_mongo, draft_both = self.organize_courses(
            mysql_draft, mongo_draft
        )

        self.log_msg("=" * 100)
        self.log_msg("Draft version only in mysql")
        self.log_msg("=" * 100)
        self.log_msg(draft_only_mysql)
        self.log_msg("=" * 100)
        self.log_msg("Draft version only in mongo")
        self.log_msg("=" * 100)
        self.log_msg(draft_only_mongo)

        different_publish_versions = self.find_different_versions(
            mysql_publish, mongo_publish, publish_both, "publish_id"
        )

        self.log_msg("=" * 100)
        self.log_msg("Different publish version")
        self.log_msg("=" * 100)
        self.log_msg(different_publish_versions)

        different_draft_versions = self.find_different_versions(
            mysql_draft, mongo_draft, draft_both, "draft_id"
        )

        self.log_msg("=" * 100)
        self.log_msg("Different draft version")
        self.log_msg("=" * 100)
        self.log_msg(different_draft_versions)
