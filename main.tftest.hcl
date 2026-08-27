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
    condition     = var.opencode_version == "latest"
    error_message = "The default OpenCode version should be latest."
  }

  assert {
    condition     = var.web_port == 4096
    error_message = "The default web port should be 4096."
  }

  assert {
    condition     = coder_app.web.display_name == "OpenCode Web"
    error_message = "The default web app display name should be OpenCode Web."
  }

  assert {
    condition     = coder_app.web.url == "http://localhost:4096"
    error_message = "The web app should use the default OpenCode port."
  }

  assert {
    condition     = coder_app.web.share == "owner"
    error_message = "The web app should only be shared with the workspace owner."
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
    condition     = strcontains(local.start_script, "opencode web --hostname 127.0.0.1 --port")
    error_message = "The start script should launch the OpenCode web server on loopback."
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
    agent_id             = "test-agent"
    workdir              = "/home/coder/project/"
    web_port             = 8080
    web_app_display_name = "OpenCode Browser"
    tui_app_display_name = "OpenCode Terminal"
    subdomain            = true
    order                = 10
    group                = "AI Tools"
    icon                 = "/custom/opencode.svg"
  }

  assert {
    condition     = local.workdir == "/home/coder/project"
    error_message = "The workdir should have its trailing slash removed."
  }

  assert {
    condition     = coder_app.web.url == "http://localhost:8080"
    error_message = "The web app should use the configured port."
  }

  assert {
    condition     = coder_app.web.display_name == "OpenCode Browser" && coder_app.tui.display_name == "OpenCode Terminal"
    error_message = "Both app display names should be configurable."
  }

  assert {
    condition     = coder_app.web.subdomain && coder_app.web.order == 10 && coder_app.web.group == "AI Tools"
    error_message = "The web app should use the configured UI options."
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
    opencode_version = "1.2.3"
    auth_json        = jsonencode({ provider = { type = "api", key = "secret" } })
    config_json      = jsonencode({ model = "anthropic/claude-sonnet-4" })
  }

  assert {
    condition     = strcontains(nonsensitive(local.install_script), "ARG_INSTALL_OPENCODE='false'")
    error_message = "The install script should receive the disabled install setting."
  }

  assert {
    condition     = strcontains(nonsensitive(local.install_script), "ARG_OPENCODE_VERSION='1.2.3'")
    error_message = "The install script should receive the configured version."
  }

  assert {
    condition     = strcontains(nonsensitive(local.install_script), base64encode("/workspace/project"))
    error_message = "The install script should receive the encoded workdir."
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
