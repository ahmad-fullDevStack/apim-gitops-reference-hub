output "apim_name" {
  value = module.apim.name
}

output "apim_id" {
  value = module.apim.id
}

output "apim_gateway_url" {
  value = module.apim.gateway_url
}

output "apim_principal_id" {
  value = module.apim.identity_principal_id
}

output "workspace_id" {
  value = { for k, m in module.workspace : k => m.id }
}

output "kv_team_a_uri" {
  value = module.kv_team_a.uri
}

output "kv_team_b_uri" {
  value = module.kv_team_b.uri
}

output "publisher_client_id" {
  value       = module.identity.publisher_client_id
  description = "Wire as GitHub repo variable AZURE_PUBLISHER_CLIENT_ID"
}

output "extractor_client_id" {
  value       = module.identity.extractor_client_id
  description = "Wire as GitHub repo variable AZURE_EXTRACTOR_CLIENT_ID"
}

output "log_analytics_workspace_id" {
  value = module.observability.workspace_id
}

output "github_repo_variables_to_set" {
  description = "Convenience: the set of variables to add via 'gh variable set'"
  value = {
    AZURE_PUBLISHER_CLIENT_ID = module.identity.publisher_client_id
    AZURE_EXTRACTOR_CLIENT_ID = module.identity.extractor_client_id
    AZURE_TENANT_ID           = data.azurerm_client_config.current.tenant_id
    AZURE_SUBSCRIPTION_ID     = var.subscription_id
    APIM_NAME                 = module.apim.name
    APIM_RG                   = azurerm_resource_group.this.name
  }
}
