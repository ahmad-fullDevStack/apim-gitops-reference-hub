terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# Per-team Key Vault. RBAC mode (no access policies). The APIM service-MI is
# granted Secrets User (shared MI is a known gap on the built-in gateway -
# see docs/reference_architecture.md §6).

resource "azurerm_key_vault" "this" {
  name                          = var.kv_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  public_network_access_enabled = var.public_network_access
  soft_delete_retention_days    = 7
  purge_protection_enabled      = false # POC; production should be true
  tags                          = var.tags
}

resource "azurerm_role_assignment" "apim_mi_secrets_user" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.apim_principal_id
}
