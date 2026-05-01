import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def render_site(destination: Path) -> None:
    if shutil.which("bundle") is None:
        raise unittest.SkipTest("Bundler is not available for rendered SEO metadata assertions.")
    try:
        subprocess.run(
            ["bundle", "exec", "jekyll", "build", "--destination", destination.as_posix()],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise unittest.SkipTest("Jekyll is not available for rendered SEO metadata assertions.") from exc
    except subprocess.CalledProcessError as exc:
        if "Could not find" in exc.stderr or "Could not locate Gemfile" in exc.stderr:
            raise unittest.SkipTest(f"Jekyll dependencies are not available: {exc.stderr}") from exc
        raise


def meta_content(html: str, selector: str) -> str:
    if selector.startswith("property="):
        pattern = rf'<meta\s+property="{re.escape(selector.removeprefix("property="))}"\s+content="([^"]*)"'
    else:
        pattern = rf'<meta\s+name="{re.escape(selector.removeprefix("name="))}"\s+content="([^"]*)"'
    match = re.search(pattern, html)
    if not match:
        raise AssertionError(f"Missing meta tag: {selector}")
    return match.group(1)


class SeoMetadataTests(unittest.TestCase):
    def test_config_exposes_stable_identity_metadata(self) -> None:
        config = yaml.safe_load((REPO_ROOT / "_config.yml").read_text(encoding="utf-8"))

        self.assertEqual(config["url"], "https://shaypalachy.com")
        self.assertEqual(config["social_image"], "/images/prof_200_200.png")
        self.assertEqual(config["author"]["url"], "https://shaypalachy.com/")
        self.assertEqual(config["author"]["job_title"], "Head of AI & Data")
        self.assertEqual(config["author"]["github"], "shaypal5")
        self.assertEqual(config["author"]["linkedin"], "shaypalachy")
        self.assertEqual(config["author"]["twitter"], "shaypal5")
        self.assertNotIn("same_as", config["author"])

    def test_rendered_metadata_uses_resolvable_canonicals_and_person_json_ld(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_root = Path(temp_dir)
            render_site(site_root)

            home = (site_root / "index.html").read_text(encoding="utf-8")
            blog = (site_root / "blog.html").read_text(encoding="utf-8")
            community = (site_root / "community.html").read_text(encoding="utf-8")

        self.assertIn('<link rel="canonical" href="https://shaypalachy.com/" />', home)
        self.assertEqual(meta_content(home, "property=og:url"), "https://shaypalachy.com/")

        self.assertIn('<link rel="canonical" href="https://shaypalachy.com/blog.html" />', blog)
        self.assertEqual(meta_content(blog, "property=og:url"), "https://shaypalachy.com/blog.html")
        blog_description = (
            "Selected writing by Shay Palachy-Affek on data science project practice, "
            "document embeddings, time series causality, and Python tooling."
        )
        self.assertEqual(meta_content(blog, "name=description"), blog_description)
        self.assertEqual(meta_content(blog, "property=og:description"), blog_description)
        self.assertEqual(meta_content(blog, "name=twitter:description"), blog_description)

        self.assertIn('<link rel="canonical" href="https://shaypalachy.com/community.html" />', community)
        self.assertEqual(meta_content(community, "property=og:url"), "https://shaypalachy.com/community.html")

        match = re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', home, re.S)
        self.assertIsNotNone(match)
        person = json.loads(match.group(1))
        self.assertEqual(person["@type"], "Person")
        self.assertEqual(person["url"], "https://shaypalachy.com/")
        self.assertEqual(person["image"], "https://shaypalachy.com/images/prof_200_200.png")
        self.assertEqual(
            person["sameAs"],
            [
                "https://github.com/shaypal5",
                "https://www.linkedin.com/in/shaypalachy/",
                "https://twitter.com/shaypal5",
            ],
        )


if __name__ == "__main__":
    unittest.main()
