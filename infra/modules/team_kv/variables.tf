variable "kv_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "apim_principal_id" {
  type        = string
  description = "Principal ID of the APIM service-level MI (granted Secrets User)"
}

variable "public_network_access" {
  type    = bool
  default = true # POC default; set false + add PE for production
}

variable "tags" {
  type    = map(string)
  default = {}
}
