output "id" {
  value = azurerm_api_management.this.id
}

output "name" {
  value = azurerm_api_management.this.name
}

output "identity_principal_id" {
  description = "Principal ID of the APIM service-level managed identity (shared MI on built-in gateway)"
  value       = azurerm_api_management.this.identity[0].principal_id
}

output "gateway_url" {
  value = azurerm_api_management.this.gateway_url
}
