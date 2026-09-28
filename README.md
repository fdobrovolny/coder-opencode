# Coder OpenCode Module

Install and configure [OpenCode v2](https://opencode.ai/v2/docs) in a Coder workspace. The module adds three apps to the workspace UI when web support is enabled:

- **OpenCode Web** opens OpenCode's browser interface through Coder's authenticated app proxy.
- **OpenCode Pair** opens a terminal that generates a fresh browser sign-in link using the automatically derived OpenCode Web URL.
- **OpenCode TUI** opens an interactive terminal and continues the latest session in the configured project directory, authenticated to the same server as the web app.

## Usage

Use this checkout as a local module while testing the v2 migration (adjust the path to its location). Once published, pin the Git source to a release containing these changes; the older `v1.2.1` tag does not contain them:

```tf
module "opencode" {
  source = "./modules/coder-opencode"

  agent_id = coder_agent.main.id
  workdir  = "/home/coder/project"
}
```

## Authentication

OpenCode can use credentials already present in the workspace. For initial migration into a fresh v2 database, pass the legacy contents of `$HOME/.local/share/opencode/auth.json`:

```tf
module "opencode" {
  source = "./modules/coder-opencode"

  agent_id = coder_agent.main.id
  workdir  = "/home/coder/project"
  auth_json = var.opencode_auth_json
}
```

V2 imports this legacy file only when initializing its database. Updating `auth_json` does not update credentials in an existing v2 database; use `opencode auth login` there. The module writes supplied authentication data with owner-only file permissions. Mark the template variable that provides it as sensitive.

The installation script links `opencode` into Coder's `CODER_SCRIPT_BIN_DIR`, making the CLI available on `PATH` in new Coder terminal sessions without modifying shell profile files.

## Configuration

Provide an OpenCode configuration as JSON when the workspace should be configured automatically:

```tf
module "opencode" {
  source = "./modules/coder-opencode"

  agent_id = coder_agent.main.id
  workdir  = "/home/coder/project"

  config_json = jsonencode({
    "$schema" = "https://opencode.ai/config.json"
    model     = "anthropic/claude-sonnet-4"
  })
}
```

The web server listens only on the workspace loopback interface and the Coder app is owner-only. Its default port is `4096`.

The module configures and starts OpenCode's managed background service (`opencode service start`, which runs `serve` internally). It checks the authenticated v2 API at `/api/info` and the browser shell before reporting readiness. Repeated startup preserves running sessions when the hostname and port have not changed. Service startup output is written to `$HOME/.coder-modules/fdobrovolny/opencode/logs/server.log`.

Run one module instance per workspace user: it manages that user's OpenCode service hostname and port. No central OpenCode server is needed. The service runs on loopback alongside the workspace files and tools. Coder's app health check uses the public sign-in shell at `/`; API readiness is checked separately during startup.

## Browser sign-in

V2 requires OpenCode authentication in addition to Coder authentication. The service generates and privately stores a persistent password; the TUI reads it at runtime, so it is not embedded in Terraform state or app commands.

1. Click **OpenCode Pair** in Coder.
2. Open the printed link in the same browser. It signs you in and opens the web UI.
3. Use **OpenCode Web** for subsequent visits. Reopen **OpenCode Pair** when you need a new sign-in link.

The button derives the public app origin from Coder's `VSCODE_PROXY_URI`, replacing `{{port}}` with the `opencode-web` app slug. This preserves the supplied scheme, wildcard domain, workspace, agent, owner, and any custom port. Coder [provides this environment variable to terminals](https://github.com/coder/coder/blob/main/agent/agent.go) using its [configured wildcard app hostname](https://github.com/coder/coder/blob/main/coderd/agentapi/manifest.go). No Coder API token or extra Terraform inputs are needed for the default setup.

For a custom public origin or a regional proxy different from the supplied origin, set `web_app_url` in the module:

```tf
web_app_url           = "https://YOUR-OPENCODE-APP-HOST"
pair_app_display_name = "OpenCode Pair" # Optional button label
```

Use the OpenCode app's origin, without a path, rather than the Coder dashboard URL or `localhost`. If the proxy environment variable is missing or invalid, the button explains how to set this override. The pairing button is omitted when `enable_web = false`.

Pairing links are single-use and expire after five minutes. Browser sessions last 30 days; changing the service password invalidates them. Links are generated only when the button is clicked and are not saved in Terraform state or as the Coder app URL. See [OpenCode v2 browser access](https://opencode.ai/v2/docs/cli/web).

You can also generate a link manually from a workspace terminal:

```sh
opencode pair --url https://YOUR-OPENCODE-APP-HOST
```

For a terminal connection outside the Coder TUI app, run inside the workspace:

```sh
export OPENCODE_PASSWORD="$(opencode service get password)"
opencode --server http://127.0.0.1:4096 --continue
```

Substitute your configured `web_port` if different. Ordinary `opencode --continue` also discovers this managed service automatically.

## Upgrading from v1

This module requires OpenCode v2. The module uses the [official v2 installer](https://opencode.ai/v2/docs). With `install_opencode = true`, existing v1 installations are upgraded, and an explicit `opencode_version` is installed when it differs from the installed version. `latest` preserves an existing v2 installation by default. With installation disabled, provide v2 yourself.

To update to the latest v2 release on every workspace start, enable `update_on_start`:

```tf
module "opencode" {
  source = "./modules/coder-opencode"

  agent_id         = coder_agent.main.id
  workdir          = "/home/coder/project"
  install_opencode = true
  opencode_version = "latest"
  update_on_start  = true
}
```

`update_on_start` defaults to `false`. It has no effect when installation is disabled or a specific version is pinned. When enabled with `latest`, startup runs the v2 installer each time and requires network access; an installer failure fails the install step. If the binary version changes, the old managed service is stopped so the startup script or next terminal client starts the new version. An unchanged version keeps its running service.

Stop any old standalone `opencode serve` or `opencode web` process before migrating a running workspace, or restart the workspace to clear it. The new managed service cannot take over a port occupied by an old process. Provider `auth_json` contains provider credentials; it is separate from the server password and browser pairing.

> [!IMPORTANT]
> OpenCode requires Coder's [wildcard access URL](https://coder.com/docs/admin/networking/wildcard-access-url). Its frontend uses root-relative asset, API, and WebSocket URLs, which are not compatible with Coder's path-based app proxy. The module therefore requires `subdomain = true`.

To install OpenCode with only the terminal app, disable the web app and automatic server startup:

```tf
module "opencode" {
  source = "./modules/coder-opencode"

  agent_id   = coder_agent.main.id
  workdir    = "/home/coder/project"
  enable_web = false
}
```

In terminal-only mode, the TUI uses OpenCode’s native service discovery and starts its background service on demand.

## Install Pipeline

The module uses [`coder-utils`](https://registry.coder.com/modules/coder/coder-utils) to serialize pre-install, install, post-install, and web server startup scripts. Runtime scripts and logs are stored under `$HOME/.coder-modules/fdobrovolny/opencode/`.

The `scripts` output contains the ordered `coder exp sync` names, allowing downstream startup scripts to wait for OpenCode.

## Validation

Run `terraform fmt -check -recursive`, `terraform validate`, `terraform test`, `python3 tests/test_install.py`, and `python3 tests/test_pair.py`. The installation policy and pairing URL tests use mocks and do not access the network. With OpenCode v2 installed, `python3 tests/smoke_v2.py` tests startup, API authentication, repeated startup, and browser pairing in a temporary home without using your provider credentials. Add `--install-version 2.0.18` to also download that version and test the upgrade from a simulated v1 installation.

## Attribution

This project is derived from the [`coder-labs/opencode`](https://github.com/coder/registry/tree/main/registry/coder-labs/modules/opencode) module in the [Coder Registry](https://github.com/coder/registry). It has been modified for distribution as a standalone repository.

## License

Licensed under the [Apache License 2.0](LICENSE).

## References

- [OpenCode configuration](https://opencode.ai/docs/config/)
- [OpenCode web interface](https://opencode.ai/v2/docs/cli/web)
- [Coder applications](https://coder.com/docs/admin/templates/extending-templates/web-apps)
