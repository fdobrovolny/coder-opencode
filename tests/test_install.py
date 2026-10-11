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
    def run_case(self, *, update=False, install=True, requested="latest", current="2.0.18", latest="2.0.19", fail=False, metadata=None, metadata_fail=False, installer_fail=False):
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
            if not current:
                binary.unlink()
            curl = bin_dir / "curl"
            curl.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$HOME/downloads"
if [[ "$*" == *https://opencode.ai/update/* ]]; then
  echo 'curl: (22) The requested URL returned error: 500' >&2
  exit 22
fi
if [[ "$*" == *https://registry.npmjs.org/@opencode%2fcli/latest* ]]; then
  if [ "$MOCK_METADATA_FAIL" = true ]; then exit 22; fi
  printf '%s\\n' "$MOCK_METADATA"
  exit 0
fi
if [ "$MOCK_FAIL" = true ]; then exit 22; fi
cat <<'INSTALLER'
set -eu
printf '%s\\n' "$*" >> "$HOME/installer-args"
if [ "$MOCK_INSTALLER_FAIL" = true ]; then exit 1; fi
version=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = --version ]; then version="${2#v}"; shift; fi
  shift
done
if [ -z "$version" ]; then
  curl -fsSL https://opencode.ai/update/api/latest/cli/npm || exit 1
  version="$MOCK_LATEST"
fi
printf '%s' "$version" > "$HOME/version"
if [ ! -x "$HOME/.opencode/bin/opencode" ]; then
  cp "$HOME/mock-opencode" "$HOME/.opencode/bin/opencode"
fi
INSTALLER
''')
            curl.chmod(0o755)
            # Let the mock installer create a binary for a fresh installation.
            (home / "mock-opencode").write_text('''#!/bin/bash
case "$*" in
  --version) printf 'opencode v%s\\n' "$(cat "$HOME/version")" ;;
  'service --help') exit 0 ;;
  *) exit 1 ;;
esac
''')
            (home / "mock-opencode").chmod(0o755)
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
            env.update(
                HOME=directory, PATH=f"{bin_dir}:/usr/bin:/bin",
                MOCK_LATEST=latest, MOCK_FAIL=str(fail).lower(),
                MOCK_METADATA=metadata if metadata is not None else json.dumps({"version": latest}),
                MOCK_METADATA_FAIL=str(metadata_fail).lower(),
                MOCK_INSTALLER_FAIL=str(installer_fail).lower(),
            )
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
        self.assertIn("https://registry.npmjs.org/@opencode%2fcli/latest", downloads)
        self.assertNotIn("https://opencode.ai/update/", downloads)
        self.assertEqual(args, "--no-modify-path --version 2.0.19\n")

    def test_unchanged_latest_keeps_service(self):
        code, version, downloads, _, stops = self.run_case(update=True, latest="2.0.18")
        self.assertEqual((code, version, stops), (0, "2.0.18", ""))
        self.assertTrue(downloads)

    def test_install_disabled_wins(self):
        self.assertEqual(self.run_case(update=True, install=False), (0, "2.0.18", "", "", ""))

    def test_matching_pin_skips_update(self):
        self.assertEqual(self.run_case(update=True, requested="v2.0.18"), (0, "2.0.18", "", "", ""))

    def test_different_pin_is_honored(self):
        code, version, downloads, args, stops = self.run_case(update=True, requested="v2.0.17")
        self.assertEqual((code, version, stops), (0, "2.0.17", "stop\n"))
        self.assertEqual(args, "--no-modify-path --version 2.0.17\n")
        self.assertNotIn("registry.npmjs.org", downloads)

    def test_installer_failure_fails_without_stopping_service(self):
        code, version, downloads, _, stops = self.run_case(update=True, fail=True)
        self.assertNotEqual(code, 0)
        self.assertEqual((version, stops), ("2.0.18", ""))
        self.assertTrue(downloads)

    def test_latest_installs_without_update_api_on_fresh_workspace(self):
        code, version, downloads, args, stops = self.run_case(current="")
        self.assertEqual((code, version, stops), (0, "2.0.19", ""))
        self.assertEqual(args, "--no-modify-path --version 2.0.19\n")
        self.assertNotIn("https://opencode.ai/update/", downloads)

    def test_latest_upgrades_v1(self):
        code, version, _, _, stops = self.run_case(current="1.18.33")
        self.assertEqual((code, version, stops), (0, "2.0.19", "stop\n"))

    def test_metadata_failure_fails_before_installing(self):
        code, version, downloads, args, stops = self.run_case(update=True, metadata_fail=True)
        self.assertNotEqual(code, 0)
        self.assertEqual((version, args, stops), ("2.0.18", "", ""))
        self.assertNotIn("https://opencode.ai/v2/install", downloads)

    def test_invalid_metadata_fails_before_installing(self):
        for metadata in ('{}', '{"version":"1.2.3"}', '{"version":"2.0.19-beta.1"}', '{"version":"garbage"}'):
            with self.subTest(metadata=metadata):
                code, version, downloads, args, stops = self.run_case(update=True, metadata=metadata)
                self.assertNotEqual(code, 0)
                self.assertEqual((version, args, stops), ("2.0.18", "", ""))
                self.assertNotIn("https://opencode.ai/v2/install", downloads)

    def test_upstream_installer_failure_does_not_report_success(self):
        code, version, _, args, stops = self.run_case(update=True, installer_fail=True)
        self.assertNotEqual(code, 0)
        self.assertEqual((version, stops), ("2.0.18", ""))
        self.assertTrue(args)


if __name__ == "__main__":
    unittest.main()
