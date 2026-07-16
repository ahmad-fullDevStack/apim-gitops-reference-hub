variable "subscription_id" {
  type        = string
  description = "Throwaway POC subscription ID"
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "name_prefix" {
  type        = string
  default     = "apim-poc"
  description = "Prefix applied to all resource names (random suffix appended)"
}

variable "publisher_email" {
  type    = string
  default = "platform-poc@contoso.invalid"
}

variable "publisher_name" {
  type    = string
  default = "APIM POC Platform Team"
}

variable "sku_name" {
  type        = string
  default     = "StandardV2_1"
  description = "APIM SKU. StandardV2_1 (cheap, workspace-capable on the default gateway) is the POC default; use Premium_1 only if adding dedicated workspace gateways."
}

variable "github_owner" {
  type        = string
  description = "GitHub org/user owning the apim-gitops-reference-hub repository"
}

variable "github_repo" {
  type    = string
  default = "apim-gitops-reference-hub"
}

variable "manage_github_repo" {
  type        = bool
  default     = true
  description = "If false, skip provisioning the GitHub ruleset / CODEOWNERS (useful for plan-only runs)"
}

variable "platform_team" {
  type    = string
  default = "apim-platform"
}

variable "pensions_core_leads_team" {
  type    = string
  default = "pensions-core-leads"
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "environment" {
  type        = string
  default     = "poc"
  description = "Logical environment name. Stamped into the `environment` tag and into resource naming."

  validation {
    condition     = contains(["poc", "dev", "test", "prod"], var.environment)
    error_message = "environment must be poc/dev/test/prod."
  }
}

variable "owner" {
  type        = string
  default     = "platform-poc@contoso.invalid"
  description = "Tag applied to every Azure resource (global guardrails)."
}

variable "auto_delete_after" {
  type        = string
  default     = "2099-12-31"
  description = "ISO date stamped into the auto-delete-after tag. Override in tfvars for POC environments."
}

variable "domains" {
  type = map(object({
    display_name = string
    tier         = string
    active       = bool
  }))
  default = {
    "pensions-core" = {
      display_name = "Pensions Core"
      tier         = "gold"
      active       = true
    }
  }
  description = <<-EOT
    Map of domain workspaces to create. Each key becomes the workspace name
    (must match a folder under apim-config/workspaces/ and an entry in
    config/ci.json `domains`). Inactive workspaces are still provisioned so
    CODEOWNERS routing works, but they will not get a dedicated gateway and
    will be tagged `active=false`.
  EOT
}

variable "alert_email_receivers" {
  type        = list(string)
  default     = []
  description = "Emails subscribed to the platform action group (capacity / 5xx alerts)."
}

variable "base_policy_definition_id" {
  type        = string
  default     = null
  description = "Optional Azure Policy definition ID auditing <base/> inheritance."
}
