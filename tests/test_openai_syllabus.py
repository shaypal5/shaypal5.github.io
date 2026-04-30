import unittest
from unittest import mock

from automation.models import Course, Material
from automation.openai_syllabus import _render_compact_markdown, _response_output_text, rewrite_syllabus_markdown


def sample_course() -> Course:
    return Course(
        slug="deep-learning-25b",
        title="Deep Learning",
        subtitle="Course page for teaching materials, 25/26 (Semester B)",
        institution="Tel Aviv University",
        role="Instructor",
        academic_period="25/26",
        status="active",
        source_drive_folder_id="folder-1",
        source_drive_folder_name="Deep Learning 25/6B CF",
        summary="summary",
        visibility="public",
        course_family="deep-learning",
        section="B",
    )


def sample_material() -> Material:
    return Material(
        title="Course Syllabus",
        url="https://example.com/syllabus",
        kind="syllabus",
        source_file_id="file-1",
        source_mime_type="application/vnd.google-apps.document",
        published=True,
        sort_key="01-syllabus",
    )


class OpenAISyllabusTests(unittest.TestCase):
    def test_rewrite_syllabus_markdown_returns_none_without_api_key(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(rewrite_syllabus_markdown(sample_course(), sample_material(), "text"))

    def test_rewrite_syllabus_markdown_honors_env_and_response_variants(self) -> None:
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            "output_text": '{"paragraph":"Short summary.","lectures":[{"slot":"1","title":"Intro","focus":"Overview"}]}'
        }
        with mock.patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_SYLLABUS_MODEL": "",
                "OPENAI_BASE_URL": "https://example.com/custom/",
            },
            clear=True,
        ), mock.patch("automation.openai_syllabus.requests.post", return_value=response) as post:
            rendered = rewrite_syllabus_markdown(sample_course(), sample_material(), "raw text")
        self.assertIn("Short summary.", rendered)
        self.assertIn("Intro", rendered)
        self.assertEqual(post.call_args.args[0], "https://example.com/custom/responses")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "gpt-5.2")

        nested = mock.Mock(status_code=200)
        nested.json.return_value = {
            "output": [{"content": [{"text": '{"paragraph":"Nested.","lectures":[] }'}]}]
        }
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), \
            mock.patch("automation.openai_syllabus.requests.post", return_value=nested):
            self.assertEqual(rewrite_syllabus_markdown(sample_course(), sample_material(), "raw text"), "Nested.")

    def test_rewrite_syllabus_markdown_handles_failures(self) -> None:
        material = sample_material()
        course = sample_course()

        bad_status = mock.Mock(status_code=500)
        bad_status.json.return_value = {}
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), \
            mock.patch("automation.openai_syllabus.requests.post", return_value=bad_status):
            self.assertIsNone(rewrite_syllabus_markdown(course, material, "raw text"))

        no_text = mock.Mock(status_code=200)
        no_text.json.return_value = {"output": [{"content": [{}]}]}
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), \
            mock.patch("automation.openai_syllabus.requests.post", return_value=no_text):
            self.assertIsNone(rewrite_syllabus_markdown(course, material, "raw text"))

        invalid_json = mock.Mock(status_code=200)
        invalid_json.json.return_value = {"output_text": "not json"}
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), \
            mock.patch("automation.openai_syllabus.requests.post", return_value=invalid_json):
            self.assertIsNone(rewrite_syllabus_markdown(course, material, "raw text"))

        empty_structured = mock.Mock(status_code=200)
        empty_structured.json.return_value = {"output_text": '{"paragraph":"","lectures":[]}'}
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), \
            mock.patch("automation.openai_syllabus.requests.post", return_value=empty_structured):
            self.assertIsNone(rewrite_syllabus_markdown(course, material, "raw text"))

    def test_response_output_text_and_render_compact_markdown(self) -> None:
        self.assertEqual(_response_output_text({"output_text": "Direct"}), "Direct")
        self.assertEqual(
            _response_output_text({"output": [{"content": [{"text": "Nested"}]}]}),
            "Nested",
        )
        self.assertEqual(_response_output_text({"output": []}), "")

        rendered = _render_compact_markdown(
            "Paragraph",
            [
                {"slot": "", "title": "", "focus": ""},
                {"slot": "1", "title": "Intro", "focus": "Overview"},
            ],
        )
        self.assertIn("Paragraph", rendered)
        self.assertIn("Intro", rendered)
        self.assertEqual(rendered.count("<tr>"), 2)
