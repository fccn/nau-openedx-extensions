"""
Unit tests for survey export tasks.
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from nau_openedx_extensions.survey_export.tasks import export_course_surveys_task

TASKS_MODULE_PATH = "nau_openedx_extensions.survey_export.tasks"


class ExportCourseSurveysTaskTest(TestCase):
    """Tests for the export_course_surveys_task function."""

    @patch(f"{TASKS_MODULE_PATH}.Command")
    def test_export_course_surveys_task_runs_command_for_the_course(self, mock_command_class: MagicMock):
        """Test that the task runs the export_course_surveys command for the given course only."""
        course_id = "course-v1:NAU+Demo+Demo"

        export_course_surveys_task(course_id)

        mock_command_class.assert_called_once_with()
        mock_command_class.return_value.handle.assert_called_once_with(course_ids=[course_id])
