#!/usr/bin/env python3
"""Exercise the rendered scripts against an installed OpenCode v2 in an isolated home.

Run: python3 tests/smoke_v2.py
Requires terraform, opencode v2, curl, and bash. No provider credentials are used.
"""
import argparse
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import urllib.error
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--install-version", help="Also test upgrading a simulated v1 installation using the official v2 installer")
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
OPENCODE = shutil.which("opencode")
assert OPENCODE, "Install OpenCode v2 before running this smoke test"


def render(name, variables):
    if name == "install":
        variables.setdefault("ARG_UPDATE_ON_START", "false")
    expression = f'base64encode(templatefile("scripts/{name}.sh.tftpl", {json.dumps(variables)}))'
    result = subprocess.run(
        ["terraform", "console"], input=expression, text=True, capture_output=True,
        cwd=ROOT, check=True,
    )
    return base64.b64decode(json.loads(result.stdout)).decode()


with tempfile.TemporaryDirectory(prefix="coder-opencode-test-") as directory:
    home = Path(directory)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENCODE_", "XDG_"))}
    env.update(
        HOME=directory,
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_DATA_HOME=str(home / ".local/share"),
        XDG_STATE_HOME=str(home / ".local/state"),
        XDG_CACHE_HOME=str(home / ".cache"),
        OPENCODE_DISABLE_MODELS_FETCH="1",
        CODER_SCRIPT_BIN_DIR=str(home / "bin"),
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    project = home / "project with spaces"
    encoded = base64.b64encode(str(project).encode()).decode()

    def cli(*args):
        return subprocess.run(
            [OPENCODE, *args], env=env, text=True, capture_output=True,
            check=True, timeout=60,
        ).stdout.strip()

    def run_script(script):
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)
        subprocess.run(
            ["bash"], input=script, env=env, text=True, capture_output=True,
            check=True, timeout=90,
        )

    def info(password):
        token = base64.b64encode(f"opencode:{password}".encode()).decode()
        request = urllib.request.Request(url + "/api/info", headers={"Authorization": f"Basic {token}"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    try:
        if args.install_version:
            # Simulate an existing v1 binary, including its permissive --help behavior.
            binary = home / ".opencode/bin/opencode"
            binary.parent.mkdir(parents=True)
            binary.write_text('#!/bin/bash\nif [ "$1" = "--version" ]; then echo 1.18.33; fi\n')
            binary.chmod(0o755)
            disabled = render("install", dict(
                ARG_INSTALL_OPENCODE="false", ARG_OPENCODE_VERSION="latest",
                ARG_WORKDIR=encoded, ARG_AUTH_JSON="", ARG_OPENCODE_CONFIG="",
            ))
            rejected = subprocess.run(["bash"], input=disabled, env=env, text=True, capture_output=True, timeout=30)
            assert rejected.returncode != 0 and "requires OpenCode v2" in rejected.stderr
            OPENCODE = str(binary)
        run_script(render("install", dict(
            ARG_INSTALL_OPENCODE="true" if args.install_version else "false",
            ARG_OPENCODE_VERSION=args.install_version or "latest",
            ARG_WORKDIR=encoded, ARG_AUTH_JSON="", ARG_OPENCODE_CONFIG="",
        )))
        assert project.is_dir()
        assert (home / "bin/opencode").is_symlink()
        script = render("start", dict(ARG_WORKDIR=encoded, ARG_WEB_PORT=str(port)))
        run_script(script)
        password = cli("service", "get", "password")
        first = info(password)
        assert first["version"].startswith("2.")
        assert cli("service", "status") == url
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.status == 200
            assert "text/html" in response.headers["Content-Type"]
        try:
            urllib.request.urlopen(url + "/api/info", timeout=5)
            raise AssertionError("API accepted an unauthenticated request")
        except urllib.error.HTTPError as error:
            assert error.code == 401

        # Repeated Coder startup must keep the existing process and credential.
        run_script(script)
        assert cli("service", "get", "password") == password
        assert info(password)["pid"] == first["pid"]

        # Pairing supports the external Coder origin and stays on the same service.
        external = cli("pair", "--url", "https://opencode.example.test")
        assert "https://opencode.example.test/auth/connect/" in external
        pairing = cli("pair", "--url", url)
        link = re.search(r"http://[^\s]+/auth/connect/[^\s]+", pairing).group()
        browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with browser.open(urllib.request.Request(link, headers={"Accept": "text/html"}), timeout=5) as response:
            assert response.status == 200
        with browser.open(url + "/api/info", timeout=5) as response:
            assert json.load(response)["pid"] == first["pid"]
        try:
            urllib.request.urlopen(link, timeout=5)
            raise AssertionError("Pairing link was reusable")
        except urllib.error.HTTPError as error:
            assert error.code == 401
        print("PASS: v2 startup, authenticated API, web shell, idempotence, and browser pairing")
    finally:
        cli("service", "stop")
