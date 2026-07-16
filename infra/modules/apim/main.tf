terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

resource "azurerm_api_management" "this" {
  name                = var.apim_name
  resource_group_name = var.resource_group_name
  location            = var.location
  publisher_email     = var.publisher_email
  publisher_name      = var.publisher_name
  sku_name            = var.sku_name

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Azure Policy assignment that audits the "policies must inherit parent scope
# using <base/>" rule. This is a defence-in-depth layer behind the CI
# base_inheritance check - if someone bypasses GitOps and edits in the portal,
# Defender for Cloud / Policy still flags it.
#
# Built-in definition: "API Management policies should use only encrypted
# named values" is one example; for <base/> enforcement we use a custom
# definition referenced by var.base_policy_definition_id. When null we skip
# the assignment so the module remains usable in environments without the
# definition present.
#
# Source: PDF §"Centralized Policy Governance" - "Azure Policy can be used
# to enforce that all API and workspace policies inherit parent <base/>."
# -----------------------------------------------------------------------------
resource "azurerm_resource_policy_assignment" "base_inheritance" {
  count                = var.base_policy_definition_id == null ? 0 : 1
  name                 = "audit-apim-base-inheritance"
  resource_id          = azurerm_api_management.this.id
  policy_definition_id = var.base_policy_definition_id
  description          = "Audits that workspace/API/product policies <base/> back to the parent scope."
  display_name         = "APIM <base/> inheritance audit"

  parameters = jsonencode({
    effect = { value = var.base_policy_effect }
  })
}

# -----------------------------------------------------------------------------
# Application Insights logger. The service-level policy can <trace> to this
# logger via the logger-id 'app-insights-platform'. Created here so the
# logger lifecycle is co-located with the APIM service.
# -----------------------------------------------------------------------------
resource "azurerm_api_management_logger" "app_insights" {
  count               = var.enable_app_insights_logger ? 1 : 0
  name                = "app-insights-platform"
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  resource_id         = var.application_insights_id

  application_insights {
    connection_string = var.application_insights_connection_string
  }
}
