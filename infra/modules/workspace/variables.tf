variable "apim_id" {
  type = string
}

variable "workspace_name" {
  type    = string
  default = "pensions-core"
}

variable "workspace_display_name" {
  type    = string
  default = "Pensions Core"
}

variable "workspace_description" {
  type    = string
  default = "Shared domain workspace provisioned by apim-gitops-reference"
}
