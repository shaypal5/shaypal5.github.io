import importlib.util
import io
import contextlib
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mint_google_refresh_token.py"


def load_mint_module():
    spec = importlib.util.spec_from_file_location("mint_google_refresh_token", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScriptTests(unittest.TestCase):
    def test_mint_google_refresh_token_missing_dependency(self) -> None:
        module = load_mint_module()
        buffer = io.StringIO()
        with mock.patch.object(module, "InstalledAppFlow", None), contextlib.redirect_stderr(buffer):
            self.assertEqual(module.main(), 1)
        self.assertIn("google-auth-oauthlib", buffer.getvalue())

    def test_mint_google_refresh_token_missing_env(self) -> None:
        module = load_mint_module()
        buffer = io.StringIO()
        with mock.patch.dict("os.environ", {}, clear=True), contextlib.redirect_stderr(buffer):
            self.assertEqual(module.main(), 1)
        self.assertIn("Missing required environment variable: GOOGLE_OAUTH_CLIENT_ID", buffer.getvalue())
