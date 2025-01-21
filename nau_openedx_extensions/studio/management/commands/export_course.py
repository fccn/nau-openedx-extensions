"""
This command has 2 execution modes, one for exporting course content and another for transferring course content.
It dispatch celery tasks that or export to a tar.gz file or transfer course content and upload it to the course 'GRADES_DOWNLOAD' storage.

Warn: this django command will dispatch multiple celery tasks, making the CMS celery workers having many pending tasks.
Please check the CMS_URL/heartbeat?extended to monitor its progress.

Export a specific course:
  python manage.py cms export_course --task export --username <my_username> <course_id>

Export multiple courses:
  python manage.py cms export_course --task export --username <my_username> <course_id_1>,<course_id_2>,<course_id_3>

Export all courses:
  python manage.py cms export_course --task export --username <my_username>

Transfer all courses:
  python manage.py cms export_course --task transfer --username <my_username> 

Transfer a specific course:
  python manage.py cms export_course --task transfer --username <my_username> <course_id_1>,<course_id_2>,<course_id_3>
"""
from time import sleep

from cms.djangoapps.contentstore.tasks import export_olx  # lint-amnesty, pylint: disable=import-error
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from xmodule.modulestore.django import modulestore

from nau_openedx_extensions.studio.contentstore.tasks import \
    transfer_course_content  # lint-amnesty, pylint: disable=import-error

User = get_user_model()

def get_task_name(task_name):
    """
    Generate the task givent its name.
    """
    if task_name == 'export':
        # The upstream export course content task
        return export_olx
    elif task_name == 'transfer':
        # The custom transfer course content task
        return transfer_course_content
    else:
        raise "Task not supported"

class Command(BaseCommand):
    """
    This command has 2 execution modes, one for exporting course content and another for transferring course content.
    It dispatch celery tasks that or export to a tar.gz file or transfer course content and upload it to the course 'GRADES_DOWNLOAD' storage.
    """

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, help="The username of the user to export the course content")
        parser.add_argument("--task", default='export', nargs='?', choices=['export', 'transfer'], help="Task to execute: export or transfer")
        parser.add_argument("--index", type=int, default=0, help="Start index of the course ids to begin exporting")
        parser.add_argument("course_ids", nargs="*", metavar="course_id", default=None, help="Course ids to export or if omitted, all courses will be exported")

    def log_msg(self, msg):
        self.stdout.write(msg)
        self.stdout.flush()

    def handle(self, *args, **options):
        """
        Execute the command
        """
        course_ids = options.get("course_ids", None)
        if not course_ids:
            module_store = modulestore()
            courses = module_store.get_courses()
            course_ids = [str(x.id) for x in courses]

        username = options.get("username", None)
        user = User.objects.get(username=username)
        user_id = user.id

        start_index = options.get("index")
        course_ids.sort()
        courses_count = len(course_ids)

        task_name = options.get("task")
        task_func = get_task_name(options.get("task"))

        course_celery_task_dict = {}
        for index in range(start_index, courses_count):
            course_id = course_ids[index]
            self.log_msg(f"Enqueue task {task_name} - {index+1} of {courses_count} - {course_id}")
            task = task_func.delay(user_id, course_id, "en")
            course_celery_task_dict[course_id] = task

        self.log_msg("Wait for tasks to finish...")

        failed_courses = []
        successfull_courses = []
        for course_id, celery_task in course_celery_task_dict.items():
            while not celery_task.ready():
                self.log_msg(f"Waiting for task {celery_task} to complete...")
                sleep(5)
            self.log_msg(f"Task {celery_task} for course {course_id} has finished with {'success' if celery_task.successful() else 'failure'}")
            if task.successful():
                successfull_courses.append(course_id)
            else:
                failed_courses.append(course_id)
        
        self.log_msg(f"Tasks completed, successful count: {len(successfull_courses)}, failed, {len(failed_courses)}")
