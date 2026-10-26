#!/usr/bin/env python3
"""Version discovery and runner checks using fake CLIs; never run a model."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import doctor
import whisper_runtime as runtime


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="whisper-versions-", dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = self.root / "ggml-small.bin"
        self.model.write_bytes(b"fixture")
        self.source = self.root / "input.wav"
        self.source.touch()

    def cli(self, name, version, status=0, stderr=False):
        path = self.root / name
        redirect = " >&2" if stderr else ""
        path.write_text('#!/bin/sh\n[ "$1" = "--version" ] || exit 99\n'
                        f'echo "whisper.cpp version: {version}"{redirect}\nexit {status}\n')
        path.chmod(0o755)
        return path

    def policy(self, cli):
        path = self.root / "policy.conf"
        path.write_text(f"version=1\nwhisper_cli={cli}\ndefault_model={self.model}\n"
                        f"allowed_root={self.root}\nallowed_model={self.model}\n")
        return path

    def test_minimum_is_accepted(self):
        self.assertEqual(runtime.select_runtime(str(self.cli("current", "1.9.5")))["selected"]["version"], "1.9.5")

    def test_newest_is_numeric_and_not_path_order(self):
        paths = [self.cli("old", "1.9.1"), self.cli("nine", "1.9.9"),
                 self.cli("ten", "1.10.0"), self.cli("patch", "1.9.10")]
        with patch.object(runtime, "installed_candidates", return_value=paths):
            self.assertEqual(runtime.select_runtime()["selected"]["version"], "1.10.0")

    def test_future_major_is_accepted(self):
        self.assertEqual(runtime.select_runtime(str(self.cli("future", "2.0.0")))["selected"]["version"], "2.0.0")

    def test_upgrade_is_rediscovered_each_call(self):
        paths = [self.cli("current", "1.9.5")]
        with patch.object(runtime, "installed_candidates", side_effect=lambda: list(paths)):
            self.assertEqual(runtime.select_runtime()["selected"]["version"], "1.9.5")
            paths.append(self.cli("upgrade", "1.9.6"))
            self.assertEqual(runtime.select_runtime()["selected"]["version"], "1.9.6")

    def test_old_unknown_prerelease_and_failed_probe_stop(self):
        for i, (version, status) in enumerate([("1.9.4", 0), ("unknown", 0),
                                             ("1.10.0-rc1", 0), ("1.10.0", 1)]):
            with self.subTest(version=version, status=status):
                self.assertIsNone(runtime.select_runtime(str(self.cli(f"bad{i}", version, status)))["selected"])

    def test_missing_cli_stops(self):
        self.assertIsNone(runtime.select_runtime(str(self.root / "absent"))["selected"])

    def test_empty_discovery_stops(self):
        with patch.object(runtime, "installed_candidates", return_value=[]):
            self.assertIsNone(runtime.select_runtime()["selected"])

    def test_stderr_banner_is_supported(self):
        self.assertTrue(runtime.select_runtime(str(self.cli("stderr", "1.9.5", stderr=True)))["selected"])

    def test_symlinks_are_deduplicated(self):
        cli = self.cli("current", "1.9.5")
        link = self.root / "link"
        link.symlink_to(cli)
        with patch.object(runtime, "installed_candidates", return_value=[cli, link]):
            self.assertEqual(len(runtime.select_runtime()["candidates"]), 1)

    def test_explicit_pin_is_not_bypassed(self):
        old = self.cli("old", "1.9.1")
        with patch.object(runtime, "installed_candidates", return_value=[self.cli("new", "1.10.0")]) as discover:
            self.assertIsNone(runtime.select_runtime(str(old))["selected"])
            discover.assert_not_called()

    def test_doctor_uses_auto_and_refuses_old_pin(self):
        cli = self.cli("new", "1.10.0")
        args = argparse.Namespace(policy=self.policy("auto"), model_dir=[self.root], preference="quality")
        with patch.object(runtime, "installed_candidates", return_value=[cli]):
            report = doctor.build_report(args)
        self.assertTrue(report["policy"]["valid"])
        self.assertEqual(report["dependencies"]["whisper-cli"]["version"], "1.10.0")
        args.policy = self.policy(self.cli("old", "1.9.4"))
        self.assertEqual(doctor.build_report(args)["status"], "setup_required")

    def test_both_runners_check_versions_before_dry_run(self):
        for version in ("1.9.4", "1.9.5", "1.10.0", "unknown"):
            cli = self.cli("runner-cli", version)
            for name in ("run_whisper_chunk.sh", "run_whisper_metal_default.sh"):
                with self.subTest(version=version, runner=name):
                    cmd = [str(SCRIPTS / name), "--input", str(self.source), "--output",
                           str(self.root / "result"), "--dry-run"]
                    env = os.environ.copy()
                    if name == "run_whisper_chunk.sh":
                        cmd += ["--model", str(self.model)]
                        env["WHISPER_CLI"] = str(cli)
                    else:
                        cmd += ["--test-policy", str(self.policy(cli))]
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
                    self.assertEqual(result.returncode, 0 if version in ("1.9.5", "1.10.0") else 2, result.stderr)
                    if result.returncode == 0:
                        self.assertIn(str(cli), result.stdout)
                        self.assertIn(version, result.stderr)
                    self.assertFalse((self.root / "result.txt").exists())

    def test_configurator_preserves_auto_and_validates_pin(self):
        cmd = [str(SCRIPTS / "configure_local_policy.sh"), "--default-model", str(self.model),
               "--allow-root", str(self.root), "--dry-run", "--whisper-cli"]
        result = subprocess.run(cmd + [str(self.cli("old", "1.9.1"))], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        # No output policy is written during configuration diagnostics.
        result = subprocess.run(cmd + [str(self.cli("new", "1.10.0"))], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("whisper_cli=" + str(self.root / "new"), result.stdout)
        self.cli("whisper-cli", "1.10.0")
        env = os.environ.copy()
        env["PATH"] = str(self.root) + os.pathsep + env.get("PATH", os.defpath)
        result = subprocess.run(cmd + ["auto"], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("whisper_cli=auto\n", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
