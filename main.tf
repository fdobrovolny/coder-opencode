# Derived from Coder Registry's coder-labs/opencode module and modified for this repository.

terraform {
  required_version = ">= 1.0"

  required_providers {
    coder = {
      source  = "coder/coder"
      version = ">= 2.13"
    }
  }
}

variable "agent_id" {
  description = "The ID of a Coder agent."
  type        = string
}

variable "order" {
  description = "The order determines the position of the apps in the Coder UI. The lowest order is shown first and apps with equal order are sorted by name."
  type        = number
  default     = null
}

variable "group" {
  description = "The name of the Coder app group that both OpenCode apps belong to."
  type        = string
  default     = null
}

variable "icon" {
  description = "The icon to use for the OpenCode apps and scripts."
  type        = string
  default     = "/icon/opencode.svg"
}

variable "workdir" {
  description = "The project directory in which OpenCode runs. It is created during installation if it does not exist."
  type        = string

  validation {
    condition     = trimspace(var.workdir) != ""
    error_message = "workdir must not be empty."
  }
}

variable "web_app_display_name" {
  description = "Display name for the OpenCode web app."
  type        = string
  default     = "OpenCode Web"
}

variable "tui_app_display_name" {
  description = "Display name for the OpenCode terminal app."
  type        = string
  default     = "OpenCode TUI"
}

variable "web_port" {
  description = "Port on which the OpenCode web server listens."
  type        = number
  default     = 4096

  validation {
    condition     = var.web_port >= 1 && var.web_port <= 65535
    error_message = "web_port must be between 1 and 65535."
  }
}

variable "subdomain" {
  description = "Whether the OpenCode web app uses a subdomain instead of a path."
  type        = bool
  default     = false
}

variable "pre_install_script" {
  description = "Custom script to run before installing OpenCode."
  type        = string
  default     = null
}

variable "post_install_script" {
  description = "Custom script to run after installing OpenCode."
  type        = string
  default     = null
}

variable "install_opencode" {
  description = "Whether to install OpenCode."
  type        = bool
  default     = true
}

variable "opencode_version" {
  description = "The version of OpenCode to install."
  type        = string
  default     = "latest"
}

variable "auth_json" {
  description = "Contents of OpenCode auth.json for non-interactive authentication."
  type        = string
  default     = ""
  sensitive   = true
}

variable "config_json" {
  description = "OpenCode JSON configuration. See https://opencode.ai/docs/config/."
  type        = string
  default     = ""
}

locals {
  workdir = var.workdir == "/" ? "/" : trimsuffix(var.workdir, "/")
  install_script = templatefile("${path.module}/scripts/install.sh.tftpl", {
    ARG_INSTALL_OPENCODE = tostring(var.install_opencode)
    ARG_OPENCODE_VERSION = var.opencode_version
    ARG_WORKDIR          = base64encode(local.workdir)
    ARG_AUTH_JSON        = base64encode(var.auth_json)
    ARG_OPENCODE_CONFIG  = base64encode(var.config_json)
  })
  start_script = templatefile("${path.module}/scripts/start.sh.tftpl", {
    ARG_WORKDIR  = base64encode(local.workdir)
    ARG_WEB_PORT = tostring(var.web_port)
  })
}

module "coder_utils" {
  source  = "registry.coder.com/coder/coder-utils/coder"
  version = "0.0.1"

  agent_id            = var.agent_id
  module_directory    = "$HOME/.coder-modules/fdobrovolny/opencode"
  display_name_prefix = "OpenCode"
  icon                = var.icon
  pre_install_script  = var.pre_install_script
  install_script      = local.install_script
  post_install_script = var.post_install_script
  start_script        = local.start_script
}

resource "coder_app" "web" {
  agent_id     = var.agent_id
  slug         = "opencode-web"
  display_name = var.web_app_display_name
  url          = "http://localhost:${var.web_port}"
  icon         = var.icon
  subdomain    = var.subdomain
  share        = "owner"
  order        = var.order
  group        = var.group

  healthcheck {
    url       = "http://localhost:${var.web_port}"
    interval  = 3
    threshold = 20
  }
}

resource "coder_app" "tui" {
  agent_id     = var.agent_id
  slug         = "opencode-tui"
  display_name = var.tui_app_display_name
  command      = <<-EOT
    #!/bin/bash
    set -e
    export PATH="$HOME/.opencode/bin:$PATH"
    cd "$(echo -n '${base64encode(local.workdir)}' | base64 -d)"
    exec opencode --continue
  EOT
  icon         = var.icon
  order        = var.order
  group        = var.group
  open_in      = "slim-window"
}

output "scripts" {
  description = "Ordered list of coder exp sync names produced by this module, in run order."
  value       = module.coder_utils.scripts
}
