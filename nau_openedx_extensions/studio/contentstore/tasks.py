import base64
import os
import subprocess

from celery import shared_task
from celery.utils.log import get_task_logger
from cms.djangoapps.contentstore.storage import course_import_export_storage
from cms.djangoapps.contentstore.views.import_export import _latest_task_status
from common.djangoapps.util.file import course_filename_prefix_generator  # lint-amnesty, pylint: disable=import-error
from django.conf import settings
from django.contrib.auth import get_user_model
from lms.djangoapps.instructor_task.models import ReportStore  # lint-amnesty, pylint: disable=import-error
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.site_configuration.models import (  # lint-amnesty, pylint: disable=import-error
    SiteConfiguration,
)
from path import Path as path
from user_tasks.models import UserTaskArtifact, UserTaskStatus

log = get_task_logger(__name__)

User = get_user_model()


class MockRequest():
    def __init__(self, user):
        self.user = user


FILE_READ_CHUNK = 1024  # bytes


def upload_tar_gz_to_report_store(file, name, course_id, timestamp, config_name="GRADES_DOWNLOAD"):
    """
    Upload given file buffer as a tar.gz file using ReportStore.
    """
    report_store = ReportStore.from_config(config_name)

    report_name = "{course_prefix}_{name}_{timestamp_str}.tar.gz".format(
        course_prefix=course_filename_prefix_generator(course_id),
        name=name,
        timestamp_str=timestamp.strftime("%Y-%m-%d-%H%M")
    )

    report_store.store(course_id, report_name, file)
    return report_name


def upload_tar_gz(file_name, name, course_key, timestamp, config_name="GRADES_DOWNLOAD"):
    """
    Upload a tar.gz using aws cli or ReportStore.
    The ReportStore sometimes fails to upload some files, so we use aws cli as primary upload method.    """
    bucket = settings.GRADES_DOWNLOAD.get('BUCKET')
    if bucket:
        AWS_ACCESS_KEY_ID = settings.GRADES_DOWNLOAD.get(
            'STORAGE_KWARGS', {}).get('access_key') or settings.AWS_ACCESS_KEY_ID
        AWS_SECRET_ACCESS_KEY = settings.GRADES_DOWNLOAD.get(
            'STORAGE_KWARGS', {}).get('secret_key') or settings.AWS_SECRET_ACCESS_KEY
        AWS_S3_ENDPOINT_URL = settings.GRADES_DOWNLOAD.get(
            'STORAGE_KWARGS', {}).get('endpoint_url') or settings.AWS_S3_ENDPOINT_URL

        report_store = ReportStore.from_config(config_name)
        report_name = "{course_prefix}_{name}_{timestamp_str}.tar.gz".format(
            course_prefix=course_filename_prefix_generator(course_key),
            name=name,
            timestamp_str=timestamp.strftime("%Y-%m-%d-%H%M")
        )
        path = report_store.path_to(course_key, report_name, '')

        my_env = os.environ.copy()
        my_env["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
        my_env["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
        returncode = subprocess.call(['aws',
                                      f"--endpoint={AWS_S3_ENDPOINT_URL}",
                                      's3',
                                      'cp',
                                      str(file_name),
                                      f"s3://{bucket}/{path}"],
                                     env=my_env)
        if returncode != 0:
            raise Exception(f"Failed to upload file to S3. Return code: {returncode}")
    else:
        with open(file_name, mode="r", encoding="utf-8") as file:
            upload_tar_gz_to_report_store(file, name, course_key, timestamp, config_name)


@shared_task(bind=True)
def transfer_course_content(self, user_id, course_key_string, language):
    """
    Transfer the course backup from the user storage to the course storage.
    This task has the same arguments as the cms/djangoapps/contentstore/tasks.py export_olx task,
    so they can be started with the same Django management command (export_course).
    """
    user = User.objects.get(id=user_id)
    course_key = CourseKey.from_string(course_key_string)
    cms_root_url = SiteConfiguration.get_value_for_org(
        course_key.org, "CMS_ROOT_URL", settings.CMS_ROOT_URL
    )
    cms_export_download_url = (
        f"{cms_root_url}/export/{course_key_string}"
    )
    lms_root_url = SiteConfiguration.get_value_for_org(
        course_key.org, "LMS_ROOT_URL", settings.LMS_ROOT_URL
    )
    lms_instructor_data_download_url = (
        f"{lms_root_url}/courses/{course_key_string}/instructor#view-data_download"
    )
    task_status = _latest_task_status(MockRequest(user=user), course_key_string)
    if task_status and task_status.state == UserTaskStatus.SUCCEEDED:
        artifact = None
        try:
            artifact = UserTaskArtifact.objects.get(status=task_status, name='Output')

            data_root = path(settings.GITHUB_REPO_ROOT)
            subdir = base64.urlsafe_b64encode(repr(course_key_string).encode('utf-8')).decode('utf-8')
            course_dir = data_root / subdir
            temp_filepath = course_dir / "export.tar.gz"
            if not course_dir.isdir():
                os.mkdir(course_dir)

            with course_import_export_storage.open(artifact.file.name, 'rb') as source:
                with open(temp_filepath, 'wb') as destination:
                    def read_chunk():
                        """
                        Read and return a sequence of bytes from the source file.
                        """
                        return source.read(FILE_READ_CHUNK)

                    for chunk in iter(read_chunk, b''):
                        destination.write(chunk)
        finally:
            if artifact:
                artifact.file.close()

        log.info("Start downloading the file of the course: %s from: %s now uploading to: %s",
                 course_key_string, cms_export_download_url, lms_instructor_data_download_url)
        upload_tar_gz(temp_filepath, "export_course_content", course_key, artifact.created)

        log.info("Sent export to report store with success of the course: %s from: %s to: %s",
                 course_key_string, cms_export_download_url, lms_instructor_data_download_url)
        os.remove(temp_filepath)
        return course_key_string, True
    else:
        log.error("No export found for course %s", course_key_string)
        return course_key_string, False
