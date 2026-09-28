"""Test installation policy without network access: python3 tests/test_install.py."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallPolicy(unittest.TestCase):
    def run_case(self, *, update=False, install=True, requested="latest", current="2.0.18", latest="2.0.19", fail=False):
        with tempfile.TemporaryDirectory(prefix="opencode-install-test-") as directory:
            home = Path(directory)
            bin_dir = home / ".opencode/bin"
            bin_dir.mkdir(parents=True)
            (home / "version").write_text(current)
            binary = bin_dir / "opencode"
            binary.write_text('''#!/bin/bash
case "$*" in
  --version) printf 'opencode v%s\\n' "$(cat "$HOME/version")" ;;
  'service --help') exit 0 ;;
  'service stop') echo stop >> "$HOME/stops" ;;
  *) exit 1 ;;
esac
''')
            binary.chmod(0o755)
            curl = bin_dir / "curl"
            curl.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$HOME/downloads"
if [ "$MOCK_FAIL" = true ]; then exit 22; fi
cat <<'INSTALLER'
set -eu
printf '%s\\n' "$*" >> "$HOME/installer-args"
version="$MOCK_LATEST"
while [ "$#" -gt 0 ]; do
  if [ "$1" = --version ]; then version="${2#v}"; shift; fi
  shift
done
printf '%s' "$version" > "$HOME/version"
INSTALLER
''')
            curl.chmod(0o755)
            variables = dict(
                ARG_INSTALL_OPENCODE=str(install).lower(),
                ARG_UPDATE_ON_START=str(update).lower(), ARG_OPENCODE_VERSION=requested,
                ARG_WORKDIR=base64.b64encode(str(home / "project").encode()).decode(),
                ARG_AUTH_JSON="", ARG_OPENCODE_CONFIG="",
            )
            expression = f'base64encode(templatefile("scripts/install.sh.tftpl", {json.dumps(variables)}))'
            rendered = subprocess.run(
                ["terraform", "console"], input=expression, cwd=ROOT,
                text=True, capture_output=True, check=True,
            )
            script = base64.b64decode(json.loads(rendered.stdout)).decode()
            env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENCODE_", "CODER_"))}
            env.update(HOME=directory, MOCK_LATEST=latest, MOCK_FAIL=str(fail).lower())
            result = subprocess.run(["bash"], input=script, text=True, capture_output=True, env=env, timeout=10)
            def read(name):
                path = home / name
                return path.read_text() if path.exists() else ""
            return result.returncode, read("version"), read("downloads"), read("installer-args"), read("stops")

    def test_default_preserves_v2(self):
        self.assertEqual(self.run_case(), (0, "2.0.18", "", "", ""))

    def test_update_latest(self):
        code, version, downloads, args, stops = self.run_case(update=True)
        self.assertEqual((code, version, stops), (0, "2.0.19", "stop\n"))
        self.assertIn("https://opencode.ai/v2/install", downloads)
        self.assertEqual(args, "--no-modify-path\n")

    def test_unchanged_latest_keeps_service(self):
        code, version, downloads, _, stops = self.run_case(update=True, latest="2.0.18")
        self.assertEqual((code, version, stops), (0, "2.0.18", ""))
        self.assertTrue(downloads)

    def test_install_disabled_wins(self):
        self.assertEqual(self.run_case(update=True, install=False), (0, "2.0.18", "", "", ""))

    def test_matching_pin_skips_update(self):
        self.assertEqual(self.run_case(update=True, requested="v2.0.18"), (0, "2.0.18", "", "", ""))

    def test_different_pin_is_honored(self):
        code, version, _, args, stops = self.run_case(update=True, requested="2.0.17")
        self.assertEqual((code, version, stops), (0, "2.0.17", "stop\n"))
        self.assertEqual(args, "--no-modify-path --version 2.0.17\n")

    def test_installer_failure_fails_without_stopping_service(self):
        code, version, downloads, _, stops = self.run_case(update=True, fail=True)
        self.assertNotEqual(code, 0)
        self.assertEqual((version, stops), ("2.0.18", ""))
        self.assertTrue(downloads)


if __name__ == "__main__":
    unittest.main()
