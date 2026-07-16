variable "apim_id" {
  type        = string
  description = "Parent APIM service resource ID."
}

variable "gateway_name" {
  type        = string
  description = "Short gateway resource name (e.g. 'gw-pensions-core'). Must be unique within the service."

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$", var.gateway_name))
    error_message = "gateway_name must be lower-kebab, 3-40 chars."
  }
}

variable "workspace_id" {
  type        = string
  default     = null
  description = "Workspace resource ID this gateway is bound to. Null leaves the gateway unbound (rare)."
}

variable "region" {
  type        = string
  description = "Region where the gateway runs. Must match the parent APIM region for Premium v1."
}

variable "description" {
  type        = string
  default     = "Workspace gateway provisioned by apim-gitops-reference-hub"
  description = "Free-text description shown in the portal."
}
