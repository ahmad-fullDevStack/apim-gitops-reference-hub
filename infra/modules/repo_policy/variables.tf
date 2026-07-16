variable "repository" {
  type        = string
  description = "Repository name (without owner)"
}

variable "github_owner" {
  type = string
}

variable "platform_team" {
  type        = string
  description = "GitHub team slug for the platform team (e.g. 'apim-platform')"
}

variable "pensions_core_leads_team" {
  type        = string
  description = "GitHub team slug for the pensions-core domain leads"
}
