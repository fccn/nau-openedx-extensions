"""
Tests for the certificate_export.html template rendering.

Verifies the HTML structure, data attributes, and content that the
JavaScript (certificate_export.js) relies on to function correctly.
"""

from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey


class CertificateExportTemplateTest(TestCase):
    """
    Test the rendered HTML output of the certificate_export.html template.

    Uses the real FilterCertificateExportTab.run_filter() to render the
    template with a realistic context, then parses the output with
    BeautifulSoup to verify the HTML structure.
    """

    PIPELINE_PATH = "nau_openedx_extensions.filters.pipeline"

    def setUp(self):
        """Set up a realistic rendering context."""
        self.course_key = CourseKey.from_string("course-v1:NAU+Demo+2025")
        self.course = MagicMock(id=self.course_key, display_name="Demo Course")

    def _render(self):
        """Render the template through FilterCertificateExportTab and return HTML."""
        from nau_openedx_extensions.filters.pipeline import FilterCertificateExportTab

        filter_instance = FilterCertificateExportTab(
            filter_type=MagicMock(), running_pipeline=MagicMock()
        )
        context = {"course": self.course, "sections": []}

        with patch(f"{self.PIPELINE_PATH}.reverse") as mock_reverse:
            mock_reverse.side_effect = lambda name, kwargs: f"/mock/{name}/{kwargs['course_id']}"
            result = filter_instance.run_filter(context, "instructor_dashboard.html")

        section = result["context"]["sections"][0]
        return section["fragment"].content

    def _soup(self):
        """Return a BeautifulSoup object of the rendered template."""
        return BeautifulSoup(self._render(), "html.parser")


    def test_csv_export_button_exists(self):
        """The CSV export button is rendered with the correct id."""
        soup = self._soup()
        button = soup.find("button", id="export-csv-certificates")
        self.assertIsNotNone(button)

    def test_zip_export_button_exists(self):
        """The ZIP export button is rendered with the correct id."""
        soup = self._soup()
        button = soup.find("button", id="export-zip-certificates")
        self.assertIsNotNone(button)

    def test_student_answers_button_exists(self):
        """The student answers report button is rendered with the correct id."""
        soup = self._soup()
        button = soup.find("button", id="generate-student-answers-report")
        self.assertIsNotNone(button)


    def test_csv_button_data_attributes(self):
        """The CSV button has data-endpoint, data-success, and data-failure."""
        soup = self._soup()
        button = soup.find("button", id="export-csv-certificates")

        self.assertTrue(button["data-endpoint"])
        self.assertTrue(button["data-success"])
        self.assertTrue(button["data-failure"])

    def test_zip_button_data_attributes(self):
        """The ZIP button has data-endpoint, data-success, and data-failure."""
        soup = self._soup()
        button = soup.find("button", id="export-zip-certificates")

        self.assertTrue(button["data-endpoint"])
        self.assertTrue(button["data-success"])
        self.assertTrue(button["data-failure"])

    def test_student_answers_button_data_attributes(self):
        """The student answers button has data-endpoint, data-success, and data-failure."""
        soup = self._soup()
        button = soup.find("button", id="generate-student-answers-report")

        self.assertTrue(button["data-endpoint"])
        self.assertTrue(button["data-success"])
        self.assertTrue(button["data-failure"])

    def test_endpoints_contain_course_id(self):
        """All button endpoints contain the course ID."""
        soup = self._soup()
        for button_id in ("export-csv-certificates", "export-zip-certificates", "generate-student-answers-report"):
            button = soup.find("button", id=button_id)
            self.assertIn(
                str(self.course_key),
                button["data-endpoint"],
                f"Button #{button_id} endpoint does not contain the course ID",
            )


    def test_problem_location_input_exists(self):
        """The problem-location input field is rendered."""
        soup = self._soup()
        input_field = soup.find("input", id="problem-location")
        self.assertIsNotNone(input_field)

    def test_problem_location_has_placeholder(self):
        """The input field has a placeholder with a block key example."""
        soup = self._soup()
        input_field = soup.find("input", id="problem-location")
        self.assertIn("block-v1:", input_field.get("placeholder", ""))


    def test_data_download_link_exists(self):
        """A link to the Data Download tab is rendered."""
        soup = self._soup()
        link = soup.find("a", href=lambda h: h and "data_download" in h)
        self.assertIsNotNone(link)

    def test_data_download_link_contains_course_id(self):
        """The data download link contains the course ID."""
        soup = self._soup()
        link = soup.find("a", href=lambda h: h and "data_download" in h)
        self.assertIn(str(self.course_key), link["href"])

    def test_error_msg_data_attribute(self):
        """The root container has a data-error-msg attribute."""
        soup = self._soup()
        container = soup.find("div", class_="certificate-export-section")
        self.assertIsNotNone(container)
        self.assertTrue(container.get("data-error-msg"))

    def test_certificate_export_heading(self):
        """An h3 heading for 'Certificate Export' is rendered."""
        soup = self._soup()
        headings = [h3.get_text() for h3 in soup.find_all("h3")]
        self.assertTrue(
            any("Certificate Export" in h for h in headings),
            f"Expected 'Certificate Export' heading, got: {headings}",
        )

    def test_student_answers_heading(self):
        """An h3 heading for 'Student Answers Values Report' is rendered."""
        soup = self._soup()
        headings = [h3.get_text() for h3 in soup.find_all("h3")]
        self.assertTrue(
            any("Student Answers" in h for h in headings),
            f"Expected 'Student Answers' heading, got: {headings}",
        )

    def test_status_containers_exist(self):
        """Error, success, info, and warning status divs are rendered."""
        soup = self._soup()
        for status_class in ("error", "success", "info", "warning"):
            div = soup.find("div", class_=f"message-status {status_class}")
            self.assertIsNotNone(
                div,
                f"Missing .message-status.{status_class} container",
            )
