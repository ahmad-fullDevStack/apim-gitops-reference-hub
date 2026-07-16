variable "apim_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "publisher_email" {
  type = string
}

variable "publisher_name" {
  type = string
}

variable "sku_name" {
  type        = string
  default     = "StandardV2_1"
  description = <<-EOT
    APIM SKU in "<tier>_<capacity>" form. Workspaces are supported on
    Standard v2 (StandardV2_1) and Premium (Premium_1). Standard v2 runs
    workspaces on the service's default managed gateway and is far cheaper,
    which is the right default for the POC. Premium_1 is required only if you
    add dedicated workspace gateways (modules/workspace_gateway).
  EOT

  validation {
    condition     = can(regex("^(StandardV2|Premium)_[0-9]+$", var.sku_name))
    error_message = "sku_name must be a workspace-capable SKU: StandardV2_<n> or Premium_<n>."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "base_policy_definition_id" {
  type        = string
  default     = null
  description = "Resource ID of the Azure Policy definition that audits <base/> inheritance. When null the assignment is skipped."
}

variable "base_policy_effect" {
  type        = string
  default     = "Audit"
  description = "Effect applied to the <base/> inheritance policy. Start in Audit; promote to Deny once teams are clean."

  validation {
    condition     = contains(["Audit", "Deny", "Disabled"], var.base_policy_effect)
    error_message = "base_policy_effect must be one of Audit, Deny, Disabled."
  }
}

variable "application_insights_id" {
  type        = string
  default     = null
  description = "App Insights resource ID. Used by the APIM logger when enabled."
}

variable "enable_app_insights_logger" {
  type        = bool
  default     = true
  description = <<-EOT
    Whether to create the App Insights APIM logger. This is a statically-known
    toggle so the logger's count does not depend on application_insights_id,
    which is only known after apply when wired from the observability module.
    Set false in environments that do not provision App Insights.
  EOT
}

variable "application_insights_connection_string" {
  type        = string
  default     = null
  sensitive   = true
  description = "App Insights connection string used by the APIM logger."
}
