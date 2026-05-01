import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from automation.config import build_paths
from automation.link_check import (
    AllowlistRule,
    LinkCheckConfig,
    LinkHTMLParser,
    check_external_links,
    collect_rendered_external_link_result,
    collect_external_links,
    collect_rendered_external_links,
    collect_source_external_links,
    load_allowlist,
)


class DummyResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def close(self) -> None:
        pass


class LinkCheckTests(unittest.TestCase):
    def test_collect_external_links_from_public_content_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "teaching" / "materials").mkdir(parents=True)
            (root / "teaching").mkdir()
            (root / "_includes").mkdir()
            (root / "index.md").write_text("[Home](https://example.com/page).", encoding="utf-8")
            (root / "README.md").write_text("https://ignored.example", encoding="utf-8")
            (root / "_includes" / "about.md").write_text("https://include.example/about", encoding="utf-8")
            (root / "data" / "talks.yml").write_text(
                "markdown: '[Talk](https://talks.example/item){:target=\"_blank\"}'\n",
                encoding="utf-8",
            )
            (root / "data" / "teaching" / "courses.yml").write_text(
                "courses:\n- syllabus_url: https://docs.example/course\n",
                encoding="utf-8",
            )
            links = collect_source_external_links(build_paths(root))
        self.assertIn("https://example.com/page", links)
        self.assertIn("https://include.example/about", links)
        self.assertIn("https://talks.example/item", links)
        self.assertIn("https://docs.example/course", links)
        self.assertNotIn("https://ignored.example", links)

    def test_collect_external_links_defaults_to_rendered_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_root = root / "_site"
            site_root.mkdir()
            (root / "index.md").write_text("[Source](https://source.example/page)", encoding="utf-8")
            (site_root / "index.html").write_text(
                '<a href="https://rendered.example/page">Rendered</a>',
                encoding="utf-8",
            )
            paths = build_paths(root)
            links = collect_external_links(paths)
            rendered_links = collect_rendered_external_links(paths)
        self.assertIn("https://rendered.example/page", links)
        self.assertEqual(links, rendered_links)
        self.assertNotIn("https://source.example/page", links)

    def test_collect_rendered_external_links_ignores_absolute_site_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_root = root / "_site"
            site_root.mkdir()
            (root / "_config.yml").write_text(
                'url: "https://example.com"\n',
                encoding="utf-8",
            )
            (site_root / "index.html").write_text(
                '<link rel="canonical" href="https://example.com/">'
                '<a href="https://other.example/page">External</a>'
                '<a href="https://www.example.com/about.html">Author URL</a>',
                encoding="utf-8",
            )
            links = collect_rendered_external_links(build_paths(root))
        self.assertEqual(list(links), ["https://other.example/page", "https://www.example.com/about.html"])

    def test_collect_rendered_external_links_from_seo_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_root = root / "_site"
            site_root.mkdir()
            (root / "_config.yml").write_text(
                'url: "https://example.com"\n',
                encoding="utf-8",
            )
            (site_root / "index.html").write_text(
                '<meta property="og:url" content="https://example.com/">'
                '<meta property="og:image" content="https://cdn.example/og.png">'
                '<meta property="og:image:secure_url" content="https://secure.example/og.png">'
                '<meta name="twitter:image" content="https://cdn.example/twitter.png">'
                '<meta name="twitter:image:src" content="https://cdn.example/twitter-src.png">'
                '<meta name="description" content="https://ignored.example/description">',
                encoding="utf-8",
            )
            links = collect_rendered_external_links(build_paths(root))
        self.assertEqual(
            list(links),
            [
                "https://cdn.example/og.png",
                "https://cdn.example/twitter-src.png",
                "https://cdn.example/twitter.png",
                "https://secure.example/og.png",
            ],
        )

    def test_collect_rendered_external_links_from_json_ld_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_root = root / "_site"
            site_root.mkdir()
            (root / "_config.yml").write_text(
                'url: "https://example.com"\n',
                encoding="utf-8",
            )
            (site_root / "index.html").write_text(
                '<script type="application/ld+json">'
                "{"
                '"url": "https://www.example.com/author",'
                '"image": "https://example.com/internal-image.png",'
                '"sameAs": ["https://profile.example/user"],'
                '"nested": {"id": "https://nested.example/id"},'
                '"notUrl": "mailto:user@example.com"'
                "}"
                "</script>"
                '<script type="application/json">{"url": "https://ignored.example/script"}</script>'
                '<script type="application/ld+json">{"name": "Not a URL"}</script>',
                encoding="utf-8",
            )
            links = collect_rendered_external_links(build_paths(root))
        self.assertEqual(
            list(links),
            [
                "https://nested.example/id",
                "https://profile.example/user",
                "https://www.example.com/author",
            ],
        )

    def test_json_ld_parser_buffers_split_script_data(self) -> None:
        parser = LinkHTMLParser()
        parser.feed('<script type="application/ld+json">{"url": "https://split.')
        parser.feed('example/page", "sameAs": ["https://profile.example/user"]}')
        parser.feed("</script>")
        self.assertEqual(
            sorted(url for url, _ in parser.urls),
            ["https://profile.example/user", "https://split.example/page"],
        )

    def test_json_ld_parser_reports_malformed_script_start_line(self) -> None:
        parser = LinkHTMLParser()
        parser.feed(
            "<html>\n"
            "<body>\n"
            '<script type="application/ld+json">\n'
            '{"url": "https://broken.example/page",}\n'
            "</script>\n"
            "</body>\n"
            "</html>"
        )
        self.assertEqual(parser.urls, [])
        self.assertEqual(len(parser.json_ld_failures), 1)
        line, message = parser.json_ld_failures[0]
        self.assertEqual(line, 3)
        self.assertIn("malformed JSON-LD script could not be parsed", message)

    def test_collect_rendered_external_link_result_reports_malformed_json_ld(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_root = root / "_site"
            site_root.mkdir()
            (site_root / "index.html").write_text(
                "<html>\n"
                "<body>\n"
                '<script type="application/ld+json">\n'
                '{"url": "https://broken.example/page",}\n'
                "</script>\n"
                "</body>\n"
                "</html>",
                encoding="utf-8",
            )
            result = collect_rendered_external_link_result(build_paths(root))
        self.assertEqual(result.links, {})
        self.assertEqual(len(result.failures), 1)
        failure = result.failures[0]
        self.assertEqual(failure.path, site_root / "index.html")
        self.assertEqual(failure.line, 3)
        self.assertIn("malformed JSON-LD script could not be parsed", failure.message)

    def test_collect_rendered_external_link_result_reports_unterminated_json_ld(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_root = root / "_site"
            site_root.mkdir()
            (site_root / "index.html").write_text(
                "<html>\n"
                "<body>\n"
                '<script type="application/ld+json">\n'
                '{"url": "https://broken.example/page"}\n',
                encoding="utf-8",
            )
            result = collect_rendered_external_link_result(build_paths(root))
        self.assertEqual(result.links, {})
        self.assertEqual(len(result.failures), 1)
        failure = result.failures[0]
        self.assertEqual(failure.path, site_root / "index.html")
        self.assertEqual(failure.line, 3)
        self.assertEqual(failure.message, "unterminated JSON-LD script tag")

    def test_check_external_links_fails_malformed_rendered_json_ld(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site_root = root / "_site"
            site_root.mkdir()
            (site_root / "index.html").write_text(
                "<html>\n"
                "<body>\n"
                '<script type="application/ld+json">\n'
                '{"url": "https://broken.example/page",}\n'
                "</script>\n"
                "</body>\n"
                "</html>",
                encoding="utf-8",
            )
            session = mock.Mock()
            session.headers = {}
            session.close = mock.Mock()
            with mock.patch("automation.link_check.requests.Session", return_value=session):
                summary = check_external_links(
                    build_paths(root),
                    LinkCheckConfig(
                        allowlist_path=root / "missing.yml",
                        timeout_seconds=0.1,
                        retries=0,
                        max_workers=1,
                    ),
                )
        self.assertEqual(summary.checked, 0)
        self.assertEqual(len(summary.failures), 1)
        self.assertIn("_site/index.html:3: malformed JSON-LD script could not be parsed", summary.failures[0])
        session.head.assert_not_called()

    def test_check_external_links_reports_collection_failure_outside_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp, tempfile.TemporaryDirectory() as site_tmp:
            root = Path(repo_tmp)
            site_root = Path(site_tmp)
            (site_root / "index.html").write_text(
                '<script type="application/ld+json">{"url": "https://broken.example/page",}</script>',
                encoding="utf-8",
            )
            summary = check_external_links(
                build_paths(root),
                LinkCheckConfig(
                    allowlist_path=root / "missing.yml",
                    timeout_seconds=0.1,
                    retries=0,
                    max_workers=1,
                    site_root=site_root,
                ),
            )
        self.assertEqual(summary.checked, 0)
        self.assertEqual(len(summary.failures), 1)
        self.assertIn(f"{site_root / 'index.html'}:1: malformed JSON-LD script could not be parsed", summary.failures[0])

    def test_allowlist_rule_matching_and_loading(self) -> None:
        self.assertTrue(AllowlistRule("domain", "example.com", "reason").matches("https://www.example.com/a"))
        self.assertFalse(
            AllowlistRule("domain", "example.com", "reason", include_subdomains=False).matches(
                "https://www.example.com/a"
            )
        )
        self.assertTrue(AllowlistRule("prefix", "https://example.com/a", "reason").matches("https://example.com/a/b"))
        self.assertTrue(AllowlistRule("exact", "https://example.com/a", "reason").matches("https://example.com/a"))
        self.assertTrue(AllowlistRule("regex", r"example\.com/[0-9]+", "reason").matches("https://example.com/12"))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.yml"
            path.write_text(
                "allowlist:\n"
                "- match: domain\n"
                "  value: example.com\n"
                "  reason: External service blocks CI.\n",
                encoding="utf-8",
            )
            self.assertEqual(load_allowlist(path)[0].value, "example.com")

    def test_check_external_links_skips_allowlist_and_reports_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "teaching" / "materials").mkdir(parents=True)
            (root / "teaching").mkdir()
            (root / "index.md").write_text(
                "[OK](https://ok.example/page) [Broken](https://broken.example/missing) "
                "[Skipped](https://skip.example/page)",
                encoding="utf-8",
            )
            allowlist = root / "allow.yml"
            allowlist.write_text(
                "allowlist:\n"
                "- match: domain\n"
                "  value: skip.example\n"
                "  reason: Skipped in tests.\n",
                encoding="utf-8",
            )
            session = mock.Mock()
            session.head.side_effect = lambda url, **_: DummyResponse(404 if "broken" in url else 200)
            session.get.side_effect = lambda url, **_: DummyResponse(404 if "broken" in url else 200)
            session.headers = {}
            session.close = mock.Mock()
            with mock.patch("automation.link_check.requests.Session", return_value=session):
                summary = check_external_links(
                    build_paths(root),
                    LinkCheckConfig(
                        allowlist_path=allowlist,
                        timeout_seconds=0.1,
                        retries=0,
                        max_workers=1,
                        source="source",
                    ),
                )
        self.assertEqual(summary.checked, 2)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.skipped_by_rule, {"domain:skip.example": 1})
        self.assertEqual(len(summary.failures), 1)
        self.assertIn("https://broken.example/missing failed: HTTP 404", summary.failures[0])

    def test_check_external_links_falls_back_to_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "teaching" / "materials").mkdir(parents=True)
            (root / "teaching").mkdir()
            (root / "index.md").write_text("[OK](https://ok.example/page)", encoding="utf-8")
            session = mock.Mock()
            session.head.side_effect = requests.RequestException("head failed")
            session.get.return_value = DummyResponse(200)
            session.headers = {}
            session.close = mock.Mock()
            with mock.patch("automation.link_check.requests.Session", return_value=session):
                summary = check_external_links(
                    build_paths(root),
                    LinkCheckConfig(
                        allowlist_path=root / "missing.yml",
                        timeout_seconds=0.1,
                        retries=0,
                        max_workers=1,
                        source="source",
                    ),
                )
        self.assertEqual(summary.failures, [])
        session.get.assert_called_once()

    def test_check_external_links_retries_get_after_failed_head_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "teaching" / "materials").mkdir(parents=True)
            (root / "teaching").mkdir()
            (root / "index.md").write_text("[OK](https://ok.example/page)", encoding="utf-8")
            session = mock.Mock()
            session.head.return_value = DummyResponse(404)
            session.get.return_value = DummyResponse(200)
            session.headers = {}
            session.close = mock.Mock()
            with mock.patch("automation.link_check.requests.Session", return_value=session):
                summary = check_external_links(
                    build_paths(root),
                    LinkCheckConfig(
                        allowlist_path=root / "missing.yml",
                        timeout_seconds=0.1,
                        retries=0,
                        max_workers=1,
                        source="source",
                    ),
                )
        self.assertEqual(summary.failures, [])
        session.get.assert_called_once()
