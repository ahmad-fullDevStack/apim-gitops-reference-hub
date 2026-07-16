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
  }
}

data "azuread_client_config" "current" {}

# Publisher SP: sole writer to APIM in normal ops
resource "azuread_application" "publisher" {
  display_name = "sp-${var.name_prefix}-apiops-publisher"
  owners       = [data.azuread_client_config.current.object_id]
}

resource "azuread_service_principal" "publisher" {
  client_id = azuread_application.publisher.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

# Federated credential: scoped to a single environment in a single repo
resource "azuread_application_federated_identity_credential" "publisher" {
  application_id = azuread_application.publisher.id
  display_name   = "github-${var.github_owner}-${var.github_repo}-env-apim-prod"
  description    = "Federation for publisher.yml in apim-prod environment"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_owner}/${var.github_repo}:environment:apim-prod"
}

resource "azurerm_role_assignment" "publisher_apim_contributor" {
  scope                = var.apim_id
  role_definition_name = "API Management Service Contributor"
  principal_id         = azuread_service_principal.publisher.object_id
}

# -----------------------------------------------------------------------------
# Hub-and-spoke: per-team spoke-repo federation on the publisher app.
#
# Each team's spoke repo runs the HUB-owned reusable workflow team-publish.yml.
# The OIDC token is minted in the CALLER (spoke) context, so its `sub` claim is
# repo:<owner>/<spoke-repo>:environment:<env>. We add one federated credential
# per spoke repo so those workflows can log in as the publisher SP.
#
# Why one shared publisher SP (not one per team): team-a and team-b share the
# pensions-core workspace (folders, not separate workspaces), so a per-team SP
# scoped to that workspace would have identical rights and buy no isolation
# within a domain. The authoritative publish-time control is the hub gate +
# scoped `to-native --team` build, not SP separation. Runtime egress isolation
# is enforced by the KV / backend-host allowlists in config/ci.json (the shared
# gateway managed identity means those allowlists are load-bearing, not just
# defence in depth).
# -----------------------------------------------------------------------------
resource "azuread_application_federated_identity_credential" "publisher_spoke" {
  for_each       = var.spoke_repos
  application_id = azuread_application.publisher.id
  display_name   = "github-${var.github_owner}-${each.value.repo}-env-${each.value.environment}"
  description    = "Federation for team-publish.yml called from spoke repo ${each.value.repo}"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  # Default subject is the caller repo + environment. Override per spoke if you
  # federate on a stricter claim (e.g. job_workflow_ref of the hub reusable).
  subject = coalesce(
    each.value.subject,
    "repo:${var.github_owner}/${each.value.repo}:environment:${each.value.environment}",
  )
}

# Extractor SP: read-only, used by the scheduled drift workflow
resource "azuread_application" "extractor" {
  display_name = "sp-${var.name_prefix}-apiops-extractor"
  owners       = [data.azuread_client_config.current.object_id]
}

resource "azuread_service_principal" "extractor" {
  client_id = azuread_application.extractor.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

resource "azuread_application_federated_identity_credential" "extractor" {
  application_id = azuread_application.extractor.id
  display_name   = "github-${var.github_owner}-${var.github_repo}-workflow-extractor"
  description    = "Federation for extractor-drift.yml"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_owner}/${var.github_repo}:ref:refs/heads/main"
}

resource "azurerm_role_assignment" "extractor_apim_reader" {
  scope                = var.apim_id
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.extractor.object_id
}

# -----------------------------------------------------------------------------
# Team Entra groups + RBAC floor.
#
# Source: PDF §"RBAC and Access Control" calls out per-workspace contributor /
# reader groups, plus a "service-scope floor" that grants every team
# "API Management Service Reader" so they can see the service envelope without
# being able to mutate it. The publisher SP remains the sole writer in normal
# operations - these groups are for break-glass / dashboard access.
# -----------------------------------------------------------------------------
resource "azuread_group" "team_contributor" {
  for_each         = var.team_groups
  display_name     = "apim-${var.name_prefix}-${each.key}-contributor"
  security_enabled = true
  owners           = [data.azuread_client_config.current.object_id]
  description      = "Workspace contributor for ${each.key} (break-glass; GitOps publisher is the normal writer)"
}

resource "azuread_group" "team_reader" {
  for_each         = var.team_groups
  display_name     = "apim-${var.name_prefix}-${each.key}-reader"
  security_enabled = true
  owners           = [data.azuread_client_config.current.object_id]
  description      = "Read-only access to the ${each.key} workspace"
}

# Service-scope floor: every team reader/contributor sees the APIM envelope.
resource "azurerm_role_assignment" "team_service_reader_floor_contrib" {
  for_each             = var.team_groups
  scope                = var.apim_id
  role_definition_name = "API Management Service Reader Role"
  principal_id         = azuread_group.team_contributor[each.key].object_id
}

resource "azurerm_role_assignment" "team_service_reader_floor_reader" {
  for_each             = var.team_groups
  scope                = var.apim_id
  role_definition_name = "API Management Service Reader Role"
  principal_id         = azuread_group.team_reader[each.key].object_id
}

# Per-workspace assignments. The map values point to a workspace resource ID;
# unset entries mean the team has no workspace-scoped permissions yet.
resource "azurerm_role_assignment" "team_workspace_contributor" {
  for_each = {
    for k, v in var.team_groups : k => v.workspace_id
    if coalesce(v.assign_workspace, true)
  }
  scope                = each.value
  role_definition_name = "API Management Workspace Contributor"
  principal_id         = azuread_group.team_contributor[each.key].object_id
}

resource "azurerm_role_assignment" "team_workspace_reader" {
  for_each = {
    for k, v in var.team_groups : k => v.workspace_id
    if coalesce(v.assign_workspace, true)
  }
  scope                = each.value
  role_definition_name = "API Management Workspace Reader"
  principal_id         = azuread_group.team_reader[each.key].object_id
}
