"""What PyPI shows about the package: its version and where it points."""

import re
import unittest
from pathlib import Path

import postfinder

ROOT = Path(__file__).resolve().parent.parent


class Metadata(unittest.TestCase):
    def test_version_is_one_number(self):
        # pyproject.toml is what gets published, __version__ is what a caller
        # reads and what the User-Agent carries. They must not drift.
        pyproject = (ROOT / "pyproject.toml").read_text()
        declared = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
        self.assertEqual(declared, postfinder.__version__)
        self.assertEqual(declared, "0.1.1")

    def test_documentation_is_the_api_reference(self):
        # /en/docs/ never existed; the reference is at /api/.
        pyproject = (ROOT / "pyproject.toml").read_text()
        self.assertIn('Documentation = "https://postfinder.io/api/"', pyproject)
        self.assertNotIn("/en/docs/", pyproject + (ROOT / "README.md").read_text())

    def test_readme_links_the_website_beside_contact(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("(https://postfinder.io/en/contact/)", readme)
        self.assertIn("[postfinder.io](https://postfinder.io/)", readme)


if __name__ == "__main__":
    unittest.main()
