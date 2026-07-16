terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 1.15"
    }
  }
}

# APIM workspaces are provisioned via AzAPI because the azurerm provider does
# not yet have a first-class resource for them. The workspaces sub-resource was
# added in API version 2023-05-01-preview and is GA from 2024-05-01.
resource "azapi_resource" "workspace" {
  type      = "Microsoft.ApiManagement/service/workspaces@2024-05-01"
  parent_id = var.apim_id
  name      = var.workspace_name

  body = jsonencode({
    properties = {
      displayName = var.workspace_display_name
      description = var.workspace_description
    }
  })

  schema_validation_enabled = false
}
