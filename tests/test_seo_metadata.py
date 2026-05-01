import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


class SeoMetadataTests(unittest.TestCase):
    def test_config_exposes_stable_identity_metadata(self) -> None:
        config = yaml.safe_load((REPO_ROOT / "_config.yml").read_text(encoding="utf-8"))

        self.assertEqual(config["url"], "https://shaypalachy.com")
        self.assertEqual(config["social_image"], "/images/prof_200_200.png")
        self.assertEqual(config["author"]["url"], "https://shaypalachy.com/")
        self.assertEqual(config["author"]["job_title"], "Head of AI & Data")
        self.assertEqual(
            config["author"]["same_as"],
            [
                "https://github.com/shaypal5",
                "https://www.linkedin.com/in/shaypalachy/",
                "https://twitter.com/shaypal5",
            ],
        )

    def test_head_includes_shared_seo_metadata_partial(self) -> None:
        head = (REPO_ROOT / "_includes" / "head.html").read_text(encoding="utf-8")
        seo = (REPO_ROOT / "_includes" / "seo.html").read_text(encoding="utf-8")

        self.assertIn("{% include seo.html %}", head)
        self.assertIn('<link rel="canonical" href="{{ canonical_url }}" />', seo)
        self.assertIn('<meta property="og:description"', seo)
        self.assertIn('<meta name="twitter:card" content="summary" />', seo)
        self.assertIn('"@type": "Person"', seo)
        self.assertIn('"sameAs": [', seo)
        self.assertIn('page.description | default: page.subtitle | default: site.description', seo)


if __name__ == "__main__":
    unittest.main()
