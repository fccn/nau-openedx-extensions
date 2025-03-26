"""
Before executing this command run: export_course_content_async.py
Then run this command to transfer the exported course content from User Tasks to GRADES_DOWNLOAD storage.
Making the backup of the course more easily available to the teams.

Transfer a specific course:
  python manage.py cms transfer_export_course_content --username <my_username> <course_id>

Transfer multiple courses:
  python manage.py cms transfer_export_course_content --username <my_username> <course_id_1>,<course_id_2>,<course_id_3>

Transfer all courses:
  python manage.py cms transfer_export_course_content --username <my_username>

Transfer not archived courses:
  python manage.py cms transfer_export_course_content --username <my_username> --skip-archived
"""

import base64
import datetime
import os

import pytz
from cms.djangoapps.contentstore.storage import course_import_export_storage
from cms.djangoapps.contentstore.views.import_export import _latest_task_status
from common.djangoapps.util.file import course_filename_prefix_generator  # lint-amnesty, pylint: disable=import-error
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from lms.djangoapps.instructor_task.models import ReportStore  # lint-amnesty, pylint: disable=import-error
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.site_configuration.models import (  # lint-amnesty, pylint: disable=import-error
    SiteConfiguration,
)
from path import Path as path
from user_tasks.models import UserTaskArtifact, UserTaskStatus
from xmodule.modulestore.django import modulestore

from nau_openedx_extensions.utils.course import is_course_archived

User = get_user_model()


class MockRequest:
    def __init__(self, user):
        self.user = user


FILE_READ_CHUNK = 1024  # bytes


def upload_tar_gz_to_report_store(
    file, name, course_id, timestamp, config_name="GRADES_DOWNLOAD"
):
    """
    Upload given file buffer as a tar.gz file using ReportStore.
    """
    report_store = ReportStore.from_config(config_name)

    report_name = "{course_prefix}_{name}_{timestamp_str}.tar.gz".format(
        course_prefix=course_filename_prefix_generator(course_id),
        name=name,
        timestamp_str=timestamp.strftime("%Y-%m-%d-%H%M"),
    )

    report_store.store(course_id, report_name, file)
    return report_name


def upload_tar_gz(
    file_name, name, course_key, timestamp, config_name="GRADES_DOWNLOAD"
):
    """
    Upload a tar.gz using aws cli or ReportStore.
    The ReportStore sometimes fails to upload some files, so we use aws cli as primary upload method.
    """
    bucket = settings.GRADES_DOWNLOAD.get("BUCKET")
    if bucket:
        AWS_ACCESS_KEY_ID = settings.GRADES_DOWNLOAD.get(
            "AWS_ACCESS_KEY_ID", settings.AWS_ACCESS_KEY_ID
        )
        AWS_SECRET_ACCESS_KEY = settings.GRADES_DOWNLOAD.get(
            "AWS_SECRET_ACCESS_KEY", settings.AWS_SECRET_ACCESS_KEY
        )
        AWS_S3_ENDPOINT_URL = settings.GRADES_DOWNLOAD.get("STORAGE_KWARGS", {}).get(
            "endpoint_url", settings.AWS_S3_ENDPOINT_URL
        )

        report_store = ReportStore.from_config(config_name)
        report_name = "{course_prefix}_{name}_{timestamp_str}.tar.gz".format(
            course_prefix=course_filename_prefix_generator(course_key),
            name=name,
            timestamp_str=timestamp.strftime("%Y-%m-%d-%H%M"),
        )
        path = report_store.path_to(course_key, report_name, "")

        import os
        import subprocess

        my_env = os.environ.copy()
        my_env["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
        my_env["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
        returncode = subprocess.call(
            [
                "aws",
                f"--endpoint={AWS_S3_ENDPOINT_URL}",
                "s3",
                "cp",
                file_name,
                f"s3://{bucket}/{path}",
            ],
            env=my_env,
        )
        if returncode != 0:
            raise Exception(f"Failed to upload file to S3. Return code: {returncode}")
    else:
        with open(file_name, mode="r", encoding="utf-8") as file:
            upload_tar_gz_to_report_store(
                file, name, course_key, timestamp, config_name
            )


def zip_a_file(inpath, outpath):
    import os
    import zipfile

    with zipfile.ZipFile(outpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(inpath, os.path.basename(inpath))


class Command(BaseCommand):
    """
    Export all course content to tar.gz and upload it to the course 'GRADES_DOWNLOAD' storage.
    """

    def add_arguments(self, parser):
        """
        Add arguments to the command
        """
        parser.add_argument(
            "--username",
            type=str,
            help="The username of the user to export the course content",
        )
        parser.add_argument(
            "--index",
            type=int,
            default=0,
            help="Start index of the course ids to begin exporting",
        )
        parser.add_argument(
            "--skip-archived",
            action="store_true",
            help="Skip archived courses",
        )
        parser.add_argument(
            "course_ids",
            nargs="*",
            metavar="course_id",
            default=None,
            help="Course ids to export or if omitted, all courses will be exported",
        )

    def log_msg(self, msg):
        """
        Log a message and flush it right away.
        """
        self.stdout.write(msg)
        self.stdout.flush()

    def handle(self, *args, **options):
        """
        Execute the command
        """
        now = datetime.datetime.now(pytz.UTC)

        course_ids = options.get("course_ids", None)
        if not course_ids:
            module_store = modulestore()
            courses = module_store.get_courses()
            course_ids = [str(x.id) for x in courses]

        username = options.get("username", None)
        user = User.objects.get(username=username)

        start_index = options.get("index", None)
        course_ids.sort()
        courses_count = len(course_ids)
        for index in range(start_index, courses_count):
            course_id = course_ids[index]

            # The `-` caracter of `--skip-archived` is converted to `_` underscore
            if options.get("skip_archived") and is_course_archived(course_id):
                self.log_msg(
                    f"Skipping {index+1} of {courses_count} - exporting {course_id} because it is archived"
                )
                continue

            self.log_msg(
                f"Processing {index+1} of {courses_count} - exporting {course_id}"
            )
            try:
                course_key = CourseKey.from_string(course_id)
                cms_root_url = SiteConfiguration.get_value_for_org(
                    course_key.org, "CMS_ROOT_URL", settings.CMS_ROOT_URL
                )
                cms_export_download_url = f"{cms_root_url}/export/{course_id}"
                lms_root_url = SiteConfiguration.get_value_for_org(
                    course_key.org, "LMS_ROOT_URL", settings.LMS_ROOT_URL
                )
                lms_instructor_data_download_url = (
                    f"{lms_root_url}/courses/{course_id}/instructor#view-data_download"
                )
                task_status = _latest_task_status(
                    MockRequest(user=user), str(course_key)
                )
                if task_status and task_status.state == UserTaskStatus.SUCCEEDED:
                    artifact = None
                    try:
                        artifact = UserTaskArtifact.objects.get(
                            status=task_status, name="Output"
                        )

                        data_root = path(settings.GITHUB_REPO_ROOT)
                        subdir = base64.urlsafe_b64encode(
                            repr(str(course_key)).encode("utf-8")
                        ).decode("utf-8")
                        course_dir = data_root / subdir
                        temp_filepath = course_dir / "export.tar.gz"
                        if not course_dir.isdir():
                            os.mkdir(course_dir)

                        with course_import_export_storage.open(
                            artifact.file.name, "rb"
                        ) as source:
                            with open(temp_filepath, "wb") as destination:

                                def read_chunk():
                                    """
                                    Read and return a sequence of bytes from the source file.
                                    """
                                    return source.read(FILE_READ_CHUNK)

                                for chunk in iter(read_chunk, b""):
                                    destination.write(chunk)
                    finally:
                        if artifact:
                            artifact.file.close()

                    self.log_msg(
                        f"Download file of the course: {course_id} from: {cms_export_download_url}"
                        f"now uploading to: {lms_instructor_data_download_url}"
                    )
                    upload_tar_gz(
                        temp_filepath,
                        "export_course_content",
                        course_key,
                        artifact.created,
                    )

                    self.log_msg(
                        f"Sent export to report store with success of the course: {course_id} from:"
                        f"{cms_export_download_url} to: {lms_instructor_data_download_url}"
                    )
                    os.remove(temp_filepath)
                else:
                    self.log_msg(
                        f"No export found for {course_id}, you can confirm the absent of the export"
                        f" file on: {cms_export_download_url}"
                    )

            except Exception as e:
                self.log_msg(f"Error exporting course {course_id}: {e}")
                # print stacktrace and continue
                import traceback

                self.log_msg(traceback.format_exc())
                continue
