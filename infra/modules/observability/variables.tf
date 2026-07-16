variable "workspace_name" {
  type        = string
  description = "Name of the Log Analytics workspace"
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "retention_days" {
  type    = number
  default = 30
}

variable "apim_id" {
  type        = string
  description = "Resource ID of the APIM service to attach diagnostic settings to"
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "enable_capacity_alerts" {
  type        = bool
  default     = true
  description = "Provision metric alerts for APIM Capacity > 70% and gateway 5xx spikes"
}

variable "alert_email_receivers" {
  type        = list(string)
  default     = []
  description = "Email addresses subscribed to the platform action group. Empty disables the action group; alerts still fire but have no destination."
}
