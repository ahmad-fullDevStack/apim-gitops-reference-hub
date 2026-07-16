terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azapi = {
      source  = "azure/azapi"
      version = "~> 1.15"
    }
  }
}

# Workspace gateway. AzAPI used because azurerm has no first-class resource yet.
# API surface: Microsoft.ApiManagement/service/workspaces/{ws}/gateways/{gw}@2024-05-01
resource "azapi_resource" "gateway" {
  type      = "Microsoft.ApiManagement/service/gateways@2024-05-01"
  parent_id = var.apim_id
  name      = var.gateway_name

  body = jsonencode({
    properties = {
      description = var.description
      locationData = {
        name = var.region
      }
    }
  })

  schema_validation_enabled = false
}

# Binding: associate the gateway with the workspace. Required so APIM routes
# requests for APIs in that workspace through the dedicated capacity unit.
# Note: PDF §"Identified Gaps and Mitigations" - workspace gateway MI binding
# is not yet GA; this module provisions the gateway only. Secret access still
# flows through the service-level system MI until the gap is addressed.
resource "azapi_resource" "workspace_binding" {
  count     = var.workspace_id == null ? 0 : 1
  type      = "Microsoft.ApiManagement/service/workspaces/gateways@2024-05-01"
  parent_id = var.workspace_id
  name      = var.gateway_name

  body = jsonencode({
    properties = {
      gatewayId = azapi_resource.gateway.id
    }
  })

  schema_validation_enabled = false
}
