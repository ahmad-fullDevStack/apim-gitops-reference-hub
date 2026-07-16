output "workspace_id" {
  value = azurerm_log_analytics_workspace.this.id
}

output "workspace_name" {
  value = azurerm_log_analytics_workspace.this.name
}

output "application_insights_id" {
  value       = azurerm_application_insights.this.id
  description = "App Insights resource ID. Wire as an APIM Logger for distributed tracing."
}

output "application_insights_connection_string" {
  value       = azurerm_application_insights.this.connection_string
  sensitive   = true
  description = "Use as the APIM logger 'credentials.connectionString' value."
}

output "action_group_id" {
  value       = length(azurerm_monitor_action_group.platform) > 0 ? azurerm_monitor_action_group.platform[0].id : null
  description = "Action group ID (null when no alert_email_receivers are configured)."
}
