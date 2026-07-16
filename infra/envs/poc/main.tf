terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.11"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.2"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "azuread" {}

provider "azapi" {
  subscription_id = var.subscription_id
}

# GitHub provider authenticates via the GITHUB_TOKEN env var (a fine-grained
# PAT or installation token with admin rights on the target repo).
provider "github" {
  owner = var.github_owner
}

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
  numeric = true
}

locals {
  prefix = "${var.name_prefix}-${random_string.suffix.result}"
  tags = merge(var.tags, {
    project             = "apim-gitops-reference"
    environment         = var.environment
    managed_by          = "terraform"
    owner               = var.owner
    "auto-delete-after" = var.auto_delete_after
  })
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.prefix}"
  location = var.location
  tags     = local.tags
}

module "observability" {
  source                = "../../modules/observability"
  workspace_name        = "log-${local.prefix}"
  resource_group_name   = azurerm_resource_group.this.name
  location              = azurerm_resource_group.this.location
  apim_id               = module.apim.id
  retention_days        = 30
  alert_email_receivers = var.alert_email_receivers
  tags                  = local.tags
}

module "apim" {
  source                                 = "../../modules/apim"
  apim_name                              = "apim-${local.prefix}"
  resource_group_name                    = azurerm_resource_group.this.name
  location                               = azurerm_resource_group.this.location
  publisher_email                        = var.publisher_email
  publisher_name                         = var.publisher_name
  sku_name                               = var.sku_name
  application_insights_id                = module.observability.application_insights_id
  application_insights_connection_string = module.observability.application_insights_connection_string
  base_policy_definition_id              = var.base_policy_definition_id
  tags                                   = local.tags
}

# One workspace per domain. The CI freeze_workspace.py check enforces the
# inverse: any workspace folder added to apim-config/workspaces/ must also be
# listed in config/ci.json `domains`, which is the same source the user wires
# into this map via tfvars.
module "workspace" {
  source                 = "../../modules/workspace"
  for_each               = var.domains
  apim_id                = module.apim.id
  workspace_name         = each.key
  workspace_display_name = each.value.display_name
  workspace_description  = "Domain workspace (${each.value.tier}, active=${each.value.active})"
}

module "kv_team_a" {
  source              = "../../modules/team_kv"
  kv_name             = "kv-${local.prefix}-team-a"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  apim_principal_id   = module.apim.identity_principal_id
  tags                = local.tags
}

module "kv_team_b" {
  source              = "../../modules/team_kv"
  kv_name             = "kv-${local.prefix}-team-b"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  apim_principal_id   = module.apim.identity_principal_id
  tags                = local.tags
}

module "identity" {
  source       = "../../modules/identity"
  name_prefix  = local.prefix
  apim_id      = module.apim.id
  github_owner = var.github_owner
  github_repo  = var.github_repo

  # Per-team Entra groups + service-scope Reader floor. Workspace contributor
  # / reader bindings only attach when the team has a real workspace_id.
  # PDF §"RBAC and Access Control".
  team_groups = {
    "team-a" = {
      workspace_id = module.workspace["pensions-core"].id
    }
    "team-b" = {
      workspace_id = module.workspace["pensions-core"].id
    }
    "pensions-core-leads" = {
      workspace_id = module.workspace["pensions-core"].id
    }
  }
}

module "repo_policy" {
  source                   = "../../modules/repo_policy"
  count                    = var.manage_github_repo ? 1 : 0
  repository               = var.github_repo
  github_owner             = var.github_owner
  platform_team            = var.platform_team
  pensions_core_leads_team = var.pensions_core_leads_team
}
