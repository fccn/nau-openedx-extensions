"""
Tests for the FilterCertificateExportTab pipeline step.
"""

from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.filters.pipeline import BLOCK_CATEGORY, FilterCertificateExportTab

PIPELINE_PATH = "nau_openedx_extensions.filters.pipeline"


class FilterCertificateExportTabTest(TestCase):
    """
    Test the FilterCertificateExportTab pipeline step that adds the NAU custom
    reports tab to the instructor dashboard.
    """

    patch_reverse = patch(f"{PIPELINE_PATH}.reverse")
    patch_render = patch(f"{PIPELINE_PATH}.render_to_string")
    patch_fragment = patch(f"{PIPELINE_PATH}.Fragment")

    def setUp(self):
        """Set up test fixtures."""
        self.filter = FilterCertificateExportTab(
            filter_type=Mock(), running_pipeline=Mock()
        )
        self.course_id_str = "course-v1:NAU+Demo+DemoCourse"
        self.course_key = CourseKey.from_string(self.course_id_str)
        self.course = MagicMock(id=self.course_key, display_name="Test Course")
        self.context = {
            "course": self.course,
            "sections": [],
        }
        self.template_name = "instructor_dashboard.html"

    @patch_fragment
    @patch_render
    @patch_reverse
    def test_run_filter_adds_context_keys(
        self,
        mock_reverse: Mock,
        mock_render: Mock,
        mock_fragment: Mock,
    ):
        """Test that run_filter populates the context with all expected keys."""
        mock_reverse.side_effect = lambda name, kwargs: f"/mocked/{name}/{kwargs['course_id']}"
        mock_render.return_value = "<html>rendered</html>"

        with patch.object(self.filter, "resource_string", return_value="/* css or js */"):
            result = self.filter.run_filter(self.context, self.template_name)

        ctx = result["context"]


        self.assertIn("certificate_export_url", ctx)
        self.assertIn("certificate_export_pdf_url", ctx)
        self.assertIn("student_answers_values_report_url", ctx)
        self.assertIn("data_download_url", ctx)
        self.assertEqual(
            ctx["data_download_url"],
            f"/courses/{self.course_key}/instructor#view-data_download",
        )


        for key in (
            "csv_success", "csv_failure",
            "zip_success", "zip_failure",
            "student_answers_success", "student_answers_failure",
            "error_msg", "report_description", "data_download_text",
        ):
            self.assertIn(key, ctx, f"Missing context key: {key}")

    @patch_fragment
    @patch_render
    @patch_reverse
    def test_run_filter_appends_section_to_context(
        self,
        mock_reverse: Mock,
        mock_render: Mock,
        mock_fragment: Mock,
    ):
        """Test that a section dict is appended to context['sections']."""
        mock_reverse.side_effect = lambda name, kwargs: f"/mocked/{name}/{kwargs['course_id']}"
        mock_render.return_value = "<html>rendered</html>"

        with patch.object(self.filter, "resource_string", return_value="/* css or js */"):
            result = self.filter.run_filter(self.context, self.template_name)

        sections = result["context"]["sections"]
        self.assertEqual(len(sections), 1)

        section = sections[0]
        self.assertEqual(section["section_key"], BLOCK_CATEGORY)
        self.assertEqual(section["course_id"], str(self.course_key))
        self.assertEqual(section["template_path_prefix"], "/instructor_dashboard/")
        self.assertIn("section_display_name", section)

    @patch_fragment
    @patch_render
    @patch_reverse
    def test_run_filter_section_contains_fragment(
        self,
        mock_reverse: Mock,
        mock_render: Mock,
        mock_fragment: Mock,
    ):
        """Test the appended section contains a Fragment with HTML, CSS, and JS."""
        mock_reverse.side_effect = lambda name, kwargs: f"/mocked/{name}/{kwargs['course_id']}"
        mock_render.return_value = "<html>rendered</html>"
        mock_frag_instance = MagicMock()
        mock_fragment.return_value = mock_frag_instance

        with patch.object(self.filter, "resource_string", return_value="/* resource */") as mock_res:
            result = self.filter.run_filter(self.context, self.template_name)

        mock_fragment.assert_called_once_with("<html>rendered</html>")

        mock_frag_instance.add_css.assert_called_once_with("/* resource */")
        mock_frag_instance.add_javascript.assert_called_once_with("/* resource */")

        section = result["context"]["sections"][0]
        self.assertEqual(section["fragment"], mock_frag_instance)

    @patch_fragment
    @patch_render
    @patch_reverse
    def test_run_filter_returns_context(
        self,
        mock_reverse: Mock,
        mock_render: Mock,
        mock_fragment: Mock,
    ):
        """Test that run_filter returns {'context': context}."""
        mock_reverse.side_effect = lambda name, kwargs: f"/mocked/{name}/{kwargs['course_id']}"
        mock_render.return_value = "<html>rendered</html>"

        with patch.object(self.filter, "resource_string", return_value="/* res */"):
            result = self.filter.run_filter(self.context, self.template_name)

        self.assertIn("context", result)
        self.assertIs(result["context"], self.context)

    @patch_fragment
    @patch_render
    @patch_reverse
    def test_run_filter_uses_correct_template(
        self,
        mock_reverse: Mock,
        mock_render: Mock,
        mock_fragment: Mock,
    ):
        """Test that render_to_string is called with the correct template name."""
        mock_reverse.side_effect = lambda name, kwargs: f"/mocked/{name}/{kwargs['course_id']}"
        mock_render.return_value = "<html>rendered</html>"

        with patch.object(self.filter, "resource_string", return_value="/* res */"):
            self.filter.run_filter(self.context, self.template_name)

        mock_render.assert_called_once()
        args, _kwargs = mock_render.call_args
        self.assertEqual(args[0], "certificate_export/certificate_export.html")

    @patch_fragment
    @patch_render
    @patch_reverse
    def test_run_filter_calls_reverse_with_correct_url_names(
        self,
        mock_reverse: Mock,
        mock_render: Mock,
        mock_fragment: Mock,
    ):
        """Test that reverse is called for all three URL endpoints."""
        mock_reverse.side_effect = lambda name, kwargs: f"/mocked/{name}/{kwargs['course_id']}"
        mock_render.return_value = "<html>rendered</html>"

        with patch.object(self.filter, "resource_string", return_value="/* res */"):
            self.filter.run_filter(self.context, self.template_name)

        expected_url_names = [
            "nau-openedx-extensions:nau_export_certificates_csv",
            "nau-openedx-extensions:nau_export_certificates_pdf",
            "nau-openedx-extensions:nau_student_answers_values_report",
        ]
        self.assertEqual(mock_reverse.call_count, len(expected_url_names))
        for url_name in expected_url_names:
            mock_reverse.assert_any_call(url_name, kwargs={"course_id": self.course_key})

    @patch(f"{PIPELINE_PATH}.resources")
    def test_resource_string_reads_and_decodes(self, mock_resources: Mock):
        """Test that resource_string reads a file from the package and decodes to UTF-8."""
        mock_file = MagicMock()
        mock_file.read_bytes.return_value = b"body { color: red; }"
        mock_resources.files.return_value.joinpath.return_value = mock_file

        result = self.filter.resource_string("static/nau_openedx_extensions/css/certificate_export.css")

        mock_resources.files.assert_called_once_with("nau_openedx_extensions")
        mock_resources.files.return_value.joinpath.assert_called_once_with(
            "static/nau_openedx_extensions/css/certificate_export.css"
        )
        self.assertEqual(result, "body { color: red; }")

    @patch_fragment
    @patch_render
    @patch_reverse
    def test_run_filter_preserves_existing_sections(
        self,
        mock_reverse: Mock,
        mock_render: Mock,
        mock_fragment: Mock,
    ):
        """Test that run_filter does not remove existing sections."""
        existing_section = {"section_key": "existing", "section_display_name": "Existing"}
        self.context["sections"] = [existing_section]

        mock_reverse.side_effect = lambda name, kwargs: f"/mocked/{name}/{kwargs['course_id']}"
        mock_render.return_value = "<html>rendered</html>"

        with patch.object(self.filter, "resource_string", return_value="/* res */"):
            result = self.filter.run_filter(self.context, self.template_name)

        sections = result["context"]["sections"]
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0], existing_section)
        self.assertEqual(sections[1]["section_key"], BLOCK_CATEGORY)
