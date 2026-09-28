"""Test the pairing button without network access: python3 tests/test_pair.py."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PairButton(unittest.TestCase):
    def run_pair(self, proxy="", override="", service="http://127.0.0.1:4096"):
        with tempfile.TemporaryDirectory(prefix="opencode-pair-test-") as directory:
            home = Path(directory)
            binary = home / ".opencode/bin/opencode"
            binary.parent.mkdir(parents=True)
            binary.write_text('''#!/bin/bash
if [ "$*" = 'service status' ]; then
  printf '%s\\n' "$MOCK_SERVICE_URL"
else
  printf '%s\\n' "$@" > "$HOME/args"
fi
''')
            binary.chmod(0o755)
            variables = dict(
                ARG_WEB_APP_URL=base64.b64encode(override.encode()).decode(),
                ARG_WEB_SLUG="opencode-web", ARG_WEB_PORT="4096",
            )
            expression = f'base64encode(templatefile("scripts/pair.sh.tftpl", {json.dumps(variables)}))'
            rendered = subprocess.run(
                ["terraform", "console"], input=expression, cwd=ROOT,
                text=True, capture_output=True, check=True,
            )
            script = base64.b64decode(json.loads(rendered.stdout)).decode()
            env = dict(os.environ, HOME=directory, VSCODE_PROXY_URI=proxy, MOCK_SERVICE_URL=service)
            result = subprocess.run(["bash"], input=script, env=env, text=True, capture_output=True, timeout=10)
            args_file = home / "args"
            return result, args_file.read_text().splitlines() if args_file.exists() else []

    def test_derived_origins(self):
        for proxy, expected in [
            ("https://{{port}}--main--project--alice.apps.example.com", "https://opencode-web--main--project--alice.apps.example.com"),
            ("https://{{port}}--dev--project--alice-apps.example.com:8443/", "https://opencode-web--dev--project--alice-apps.example.com:8443"),
            ("http://{{port}}--main--project--alice.example.test:8080", "http://opencode-web--main--project--alice.example.test:8080"),
        ]:
            with self.subTest(proxy=proxy):
                result, args = self.run_pair(proxy=proxy)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(args, ["pair", "--url", expected])

    def test_override_takes_precedence(self):
        result, args = self.run_pair(proxy="invalid", override="https://custom.example.com/")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(args, ["pair", "--url", "https://custom.example.com"])

    def test_missing_placeholder(self):
        for proxy in ["", "https://unrelated.example.com"]:
            with self.subTest(proxy=proxy):
                result, args = self.run_pair(proxy=proxy)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("web_app_url", result.stderr)
                self.assertEqual(args, [])

    def test_rejects_non_origin_proxy(self):
        for proxy in ["https://example.com/{{port}}", "https://{{port}}.example.com/?a=b", "file://{{port}}.example.com", "https://user:password@{{port}}.example.com"]:
            with self.subTest(proxy=proxy):
                result, args = self.run_pair(proxy=proxy)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(args, [])

    def test_service_must_match_configured_port(self):
        for service in ["stopped", "http://127.0.0.1:49374"]:
            with self.subTest(service=service):
                result, args = self.run_pair(override="https://app.example.com", service=service)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not ready", result.stderr)
                self.assertEqual(args, [])


if __name__ == "__main__":
    unittest.main()
