# Coder OpenCode Module

Install and configure [OpenCode](https://opencode.ai) in a Coder workspace. The module adds two apps to the workspace UI:

- **OpenCode Web** opens OpenCode's browser interface through Coder's authenticated app proxy.
- **OpenCode TUI** opens an interactive terminal and runs `opencode --continue` in the configured project directory.

## Usage

Reference a tagged release to keep module updates predictable:

```tf
module "opencode" {
  source = "git::https://github.com/fdobrovolny/coder-opencode.git?ref=v1.1.0"

  agent_id = coder_agent.main.id
  workdir  = "/home/coder/project"
}
```

## Authentication

OpenCode can use credentials already present in the workspace. For non-interactive setup, pass the contents of `$HOME/.local/share/opencode/auth.json`:

```tf
module "opencode" {
  source = "git::https://github.com/fdobrovolny/coder-opencode.git?ref=v1.1.0"

  agent_id = coder_agent.main.id
  workdir  = "/home/coder/project"
  auth_json = var.opencode_auth_json
}
```

The module writes supplied authentication data with owner-only file permissions. Mark the template variable that provides it as sensitive.

## Configuration

Provide an OpenCode configuration as JSON when the workspace should be configured automatically:

```tf
module "opencode" {
  source = "git::https://github.com/fdobrovolny/coder-opencode.git?ref=v1.1.0"

  agent_id = coder_agent.main.id
  workdir  = "/home/coder/project"

  config_json = jsonencode({
    "$schema" = "https://opencode.ai/config.json"
    model     = "anthropic/claude-sonnet-4"
  })
}
```

The web server listens only on the workspace loopback interface and the Coder app is owner-only. Its default port is `4096`.

The module uses `opencode serve` so the headless workspace does not attempt to launch `xdg-open` when the server starts.

> [!IMPORTANT]
> OpenCode requires Coder's [wildcard access URL](https://coder.com/docs/admin/networking/wildcard-access-url). Its frontend uses root-relative asset, API, and WebSocket URLs, which are not compatible with Coder's path-based app proxy. The module therefore requires `subdomain = true`.

To install OpenCode with only the terminal app, disable the web app and server:

```tf
module "opencode" {
  source = "git::https://github.com/fdobrovolny/coder-opencode.git?ref=v1.1.0"

  agent_id   = coder_agent.main.id
  workdir    = "/home/coder/project"
  enable_web = false
}
```

## Install Pipeline

The module uses [`coder-utils`](https://registry.coder.com/modules/coder/coder-utils) to serialize pre-install, install, post-install, and web server startup scripts. Runtime scripts and logs are stored under `$HOME/.coder-modules/fdobrovolny/opencode/`.

The `scripts` output contains the ordered `coder exp sync` names, allowing downstream startup scripts to wait for OpenCode.

## Attribution

This project is derived from the [`coder-labs/opencode`](https://github.com/coder/registry/tree/main/registry/coder-labs/modules/opencode) module in the [Coder Registry](https://github.com/coder/registry). It has been modified for distribution as a standalone repository.

## License

Licensed under the [Apache License 2.0](LICENSE).

## References

- [OpenCode configuration](https://opencode.ai/docs/config/)
- [OpenCode web interface](https://opencode.ai/docs/web/)
- [Coder applications](https://coder.com/docs/admin/templates/extending-templates/web-apps)
