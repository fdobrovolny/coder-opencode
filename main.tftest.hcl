# Derived from Coder Registry's coder-labs/opencode module and modified for this repository.

mock_provider "coder" {}

run "defaults_are_correct" {
  command = plan

  variables {
    agent_id = "test-agent"
    workdir  = "/home/coder/project"
  }

  assert {
    condition     = var.install_opencode
    error_message = "OpenCode installation should be enabled by default."
  }

  assert {
    condition     = !var.update_on_start
    error_message = "Automatic updates should be disabled by default."
  }

  assert {
    condition     = var.opencode_version == "latest"
    error_message = "The default OpenCode version should be latest."
  }

  assert {
    condition     = var.web_port == 4096
    error_message = "The default web port should be 4096."
  }

  assert {
    condition     = coder_app.web[0].display_name == "OpenCode Web"
    error_message = "The default web app display name should be OpenCode Web."
  }

  assert {
    condition     = coder_app.web[0].url == "http://localhost:4096"
    error_message = "The web app should use the default OpenCode port."
  }

  assert {
    condition     = coder_app.web[0].share == "owner"
    error_message = "The web app should only be shared with the workspace owner."
  }

  assert {
    condition     = coder_app.web[0].subdomain
    error_message = "The web app should use a subdomain because OpenCode does not support path-prefixed URLs."
  }

  assert {
    condition     = coder_app.web[0].open_in == "tab"
    error_message = "The web app should open in a new browser tab."
  }

  assert {
    condition     = coder_app.pair[0].display_name == "OpenCode Pair" && coder_app.pair[0].agent_id == "test-agent" && coder_app.pair[0].open_in == "slim-window"
    error_message = "The pairing button should open a workspace terminal."
  }

  assert {
    condition     = strcontains(coder_app.pair[0].command, "VSCODE_PROXY_URI") && strcontains(coder_app.pair[0].command, "APP_SLUG='opencode-web'")
    error_message = "Pairing should derive the URL for the web app slug at runtime."
  }

  assert {
    condition     = coder_app.tui.display_name == "OpenCode TUI"
    error_message = "The default terminal app display name should be OpenCode TUI."
  }

  assert {
    condition     = coder_app.tui.open_in == "slim-window"
    error_message = "The terminal app should open in a slim window."
  }

  assert {
    condition     = strcontains(coder_app.tui.command, "opencode --continue")
    error_message = "The terminal app should continue the latest OpenCode session."
  }

  assert {
    condition     = strcontains(local.start_script, "opencode service start") && !strcontains(local.start_script, "nohup")
    error_message = "OpenCode should manage its background service and credentials."
  }

  assert {
    condition     = strcontains(local.start_script, "GET /api/info") && !strcontains(local.start_script, "$${SERVER_URL}/global/health")
    error_message = "Readiness should check the authenticated v2 API."
  }

  assert {
    condition     = strcontains(coder_app.tui.command, "--server http://127.0.0.1:4096") && strcontains(coder_app.tui.command, "opencode service get password")
    error_message = "The terminal should authenticate to the workspace web service."
  }

  assert {
    condition     = strcontains(local.start_script, "$${HOME}/.opencode/bin:$${PATH}")
    error_message = "The rendered start script should contain runtime shell variables."
  }

  assert {
    condition     = !strcontains(local.start_script, "$$")
    error_message = "The rendered start script should not contain doubled dollar signs."
  }
}

run "custom_app_configuration" {
  command = plan

  variables {
    agent_id              = "test-agent"
    workdir               = "/home/coder/project/"
    web_port              = 8080
    web_app_display_name  = "OpenCode Browser"
    tui_app_display_name  = "OpenCode Terminal"
    pair_app_display_name = "Connect Browser"
    web_app_url           = "https://opencode.example.com"
    subdomain             = true
    order                 = 10
    group                 = "AI Tools"
    icon                  = "/custom/opencode.svg"
  }

  assert {
    condition     = local.workdir == "/home/coder/project"
    error_message = "The workdir should have its trailing slash removed."
  }

  assert {
    condition     = coder_app.web[0].url == "http://localhost:8080"
    error_message = "The web app should use the configured port."
  }

  assert {
    condition     = strcontains(coder_app.tui.command, "--server http://127.0.0.1:8080") && strcontains(local.start_script, "ARG_WEB_PORT='8080'")
    error_message = "The terminal and service should use the configured port."
  }

  assert {
    condition     = coder_app.web[0].display_name == "OpenCode Browser" && coder_app.tui.display_name == "OpenCode Terminal"
    error_message = "Both app display names should be configurable."
  }

  assert {
    condition     = coder_app.web[0].subdomain && coder_app.web[0].order == 10 && coder_app.web[0].group == "AI Tools"
    error_message = "The web app should use the configured UI options."
  }

  assert {
    condition     = coder_app.pair[0].display_name == "Connect Browser" && coder_app.pair[0].group == "AI Tools" && coder_app.pair[0].order == 10 && coder_app.pair[0].icon == "/custom/opencode.svg"
    error_message = "The pairing app should respect the configured UI options."
  }

  assert {
    condition     = strcontains(coder_app.pair[0].command, base64encode("https://opencode.example.com")) && strcontains(coder_app.pair[0].command, "http://127.0.0.1:8080")
    error_message = "Pairing should respect the public URL override and configured server port."
  }

  assert {
    condition     = coder_app.tui.order == 10 && coder_app.tui.group == "AI Tools" && coder_app.tui.icon == "/custom/opencode.svg"
    error_message = "The terminal app should use the configured UI options."
  }
}

run "custom_install_configuration" {
  command = plan

  variables {
    agent_id         = "test-agent"
    workdir          = "/workspace/project"
    install_opencode = false
    opencode_version = "2.0.18"
    auth_json        = jsonencode({ provider = { type = "api", key = "secret" } })
    config_json      = jsonencode({ model = "anthropic/claude-sonnet-4" })
  }

  assert {
    condition     = strcontains(nonsensitive(local.install_script), "ARG_INSTALL_OPENCODE='false'")
    error_message = "The install script should receive the disabled install setting."
  }

  assert {
    condition     = strcontains(nonsensitive(local.install_script), "ARG_OPENCODE_VERSION='2.0.18'")
    error_message = "The install script should receive the configured version."
  }

  assert {
    condition     = strcontains(nonsensitive(local.install_script), base64encode("/workspace/project"))
    error_message = "The install script should receive the encoded workdir."
  }

  assert {
    condition     = strcontains(nonsensitive(local.install_script), "https://opencode.ai/v2/install")
    error_message = "Installation must use the v2 installer, not the legacy v1 release channel."
  }

  assert {
    condition     = strcontains(nonsensitive(local.install_script), "CODER_SCRIPT_BIN_DIR") && strcontains(nonsensitive(local.install_script), "ln -sf")
    error_message = "The install script should expose OpenCode through Coder's terminal PATH."
  }
}

run "invalid_web_port" {
  command = plan

  variables {
    agent_id = "test-agent"
    workdir  = "/home/coder/project"
    web_port = 70000
  }

  expect_failures = [var.web_port]
}

run "empty_workdir" {
  command = plan

  variables {
    agent_id = "test-agent"
    workdir  = ""
  }

  expect_failures = [var.workdir]
}

run "path_based_proxy_is_rejected" {
  command = plan

  variables {
    agent_id  = "test-agent"
    workdir   = "/home/coder/project"
    subdomain = false
  }

  expect_failures = [var.subdomain]
}

run "web_can_be_disabled" {
  command = plan

  variables {
    agent_id   = "test-agent"
    workdir    = "/home/coder/project"
    enable_web = false
    subdomain  = false
  }

  assert {
    condition     = length(coder_app.web) == 0 && length(coder_app.pair) == 0
    error_message = "The web and pairing apps should not be created when web support is disabled."
  }

  assert {
    condition     = !strcontains(coder_app.tui.command, "--server") && !strcontains(coder_app.tui.command, "OPENCODE_PASSWORD")
    error_message = "Terminal-only mode should use native OpenCode service discovery."
  }

  assert {
    condition     = local.start_script == null
    error_message = "The start script should not be rendered when web support is disabled."
  }

  assert {
    condition     = length(module.coder_utils.scripts) == 1
    error_message = "Only the install script should run when web support is disabled."
  }
}

run "automatic_updates_can_be_enabled" {
  command = plan

  variables {
    agent_id        = "test-agent"
    workdir         = "/home/coder/project"
    update_on_start = true
  }

  assert {
    condition     = strcontains(nonsensitive(local.install_script), "ARG_UPDATE_ON_START='true'")
    error_message = "The install script should receive the automatic update setting."
  }
}

run "invalid_pairing_origin" {
  command = plan

  variables {
    agent_id    = "test-agent"
    workdir     = "/home/coder/project"
    web_app_url = "https://example.com/path"
  }

  expect_failures = [var.web_app_url]
}
