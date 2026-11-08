"""Tests for build_tools_index.py.

Run:
  python3 -m unittest tools/test_build_tools_index.py
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("build_tools_index", HERE / "build_tools_index.py")
bti = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bti)
SC = bti.load_skillchange()


class CatalogTests(unittest.TestCase):
    def test_every_skill_folder_has_a_catalog_entry_and_back(self):
        self.assertEqual(bti.check_catalog(bti.repo_skills()), [])

    def test_missing_catalog_entry_is_reported(self):
        errors = bti.check_catalog(bti.repo_skills() + ["brand-new-skill"])
        self.assertTrue(any("brand-new-skill" in e for e in errors))


class PublicOutputTests(unittest.TestCase):
    def test_lists_every_skill_and_is_public_safe(self):
        text = bti.render_public(SC)
        for skill in bti.repo_skills():
            self.assertIn(f"[`{skill}`](skills/{skill}/)", text)
        self.assertEqual(bti.public_violations(text, bti.configured_service_refs()), [])

    def test_does_not_depend_on_this_machine(self):
        before = bti.render_public(SC)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(bti, "HOME", Path(tmp)):
            self.assertEqual(bti.render_public(SC), before)

    def test_violation_report_never_echoes_the_match(self):
        hits = bti.public_violations(
            "see /Users/someone/x and abcdefghijklmnopqrst here", {"abcdefghijklmnopqrst"}
        )
        self.assertTrue(hits)
        for h in hits:
            self.assertNotIn("someone", h)
            self.assertNotIn("abcdefghijklmnopqrst", h)


class TrackedSourceTests(unittest.TestCase):
    """The script and these tests are committed, so they must hold no private notes either."""

    def test_tracked_files_hold_no_private_notes(self):
        import re

        folder = re.compile(r"\b\d{2}_[A-Z]")
        machine = ("~/" + "Library", "~/" + ".local/bin")
        for name in ("build_tools_index.py", "test_build_tools_index.py"):
            text = (HERE / name).read_text(encoding="utf-8")
            self.assertIsNone(folder.search(text), name)
            for m in machine:
                self.assertNotIn(m, text, name)


class LocalOutputTests(unittest.TestCase):
    def test_reads_server_names_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude.json").write_text(
                '{"mcpServers": {"svc": {"type": "http", "url": "https://secretref.example",'
                ' "headers": {"k": "SECRETVALUE"}}}}'
            )
            with mock.patch.object(bti, "HOME", home):
                text = bti.render_local(SC)
        self.assertIn("`svc` (http)", text)
        self.assertNotIn("SECRETVALUE", text)
        self.assertNotIn("secretref", text)


if __name__ == "__main__":
    unittest.main()
