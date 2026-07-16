output "publisher_client_id" {
  value       = azuread_application.publisher.client_id
  description = "Set as the GitHub repo variable AZURE_PUBLISHER_CLIENT_ID"
}

output "extractor_client_id" {
  value       = azuread_application.extractor.client_id
  description = "Set as the GitHub repo variable AZURE_EXTRACTOR_CLIENT_ID"
}

output "publisher_object_id" {
  value = azuread_service_principal.publisher.object_id
}

output "extractor_object_id" {
  value = azuread_service_principal.extractor.object_id
}

output "publisher_spoke_subjects" {
  value = {
    for k, c in azuread_application_federated_identity_credential.publisher_spoke :
    k => c.subject
  }
  description = "OIDC subject federated on the publisher SP per spoke repo."
}

output "team_contributor_group_ids" {
  value       = { for k, g in azuread_group.team_contributor : k => g.object_id }
  description = "Entra group object IDs per team (workspace contributor role)."
}

output "team_reader_group_ids" {
  value       = { for k, g in azuread_group.team_reader : k => g.object_id }
  description = "Entra group object IDs per team (read-only)."
}
