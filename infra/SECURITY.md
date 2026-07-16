# Security posture & Checkov skips

This document explains every Checkov rule that the POC infrastructure intentionally
suppresses, plus the Azure controls that mitigate the residual risk. **Every skip
listed here must be re-evaluated before this stack is promoted out of the POC
subscription.**

The two skips referenced in [`.github/workflows/terraform-validate.yml`](../.github/workflows/terraform-validate.yml)
are:

| Checkov ID | Title | Why skipped in this POC | Production-grade fix |
|---|---|---|---|
| `CKV_AZURE_71` | API Management services should use a virtual network | The POC instance is exposed via the default public endpoint so demo workshops can curl the gateway without VPN. A production deployment must use **External or Internal VNet integration** (`virtual_network_type = "External"` or `"Internal"`) and place the gateway behind Front Door / Application Gateway. | Set `virtual_network_type` and `virtual_network_configuration.subnet_id` on `azurerm_api_management`, peer the APIM subnet to the workload VNets that host the backends, and add Private DNS zones for the management/portal endpoints. |
| `CKV_AZURE_109` | Key Vault should have purge protection enabled | Purge protection cannot be disabled once enabled; for an ephemeral POC that gets `terraform destroy`d, that means the soft-deleted vault names linger for 90 days and the next `terraform apply` collides. | Set `purge_protection_enabled = true` and `soft_delete_retention_days = 90` on `azurerm_key_vault` in non-POC environments. Treat the soft-deleted vault namespace as a finite resource. |

## Controls that are **not** skipped

The following Checkov rules are enforced on every PR via `terraform-validate.yml`:

- `CKV_AZURE_5` — RBAC enabled on AKS clusters (we don't run AKS, but the rule is on by default and would catch a regression).
- `CKV_AZURE_31` — Key Vault uses RBAC authorisation (`enable_rbac_authorization = true`).
- `CKV_AZURE_32` — Key Vault firewall denies public access (set `network_acls.default_action = "Deny"`; **TODO** in this POC; tracked).
- `CKV_AZURE_42` — Diagnostic settings exist on the APIM service.
- `CKV_AZURE_77` — APIM admin email is set.
- `CKV2_AZURE_18` — Storage accounts under management are encrypted with customer-managed keys (n/a here, no storage accounts).

## Known POC weaknesses

These are documented gaps that **must** be closed before a production handover:

1. **No customer-managed encryption keys (CMK).** APIM and Key Vault both use Microsoft-managed keys. Add an Azure Key Vault HSM-backed key + grant the APIM MI `Key Vault Crypto Service Encryption User` and set `encryption.key_vault_key_id` on the APIM resource.
2. **No Private Endpoints.** Key Vaults are reachable from any Azure region. Add `azurerm_private_endpoint` resources + Private DNS zones in production.
3. **No Azure Policy assignment.** The PR-time CI checks are defence-in-depth; the **last line of defence is Azure Policy at the management-group scope**. Assign the built-in initiative *API Management Compliance* in the target subscription before going live.
4. **OIDC subject claims are environment-scoped, not repo+env+actor-scoped.** GitHub now supports `repo:{owner}/{repo}:environment:{env}` plus actor claims. The publisher should pin to a specific GitHub team's actor list once known.
5. **Repo ruleset has no required signed commits.** Add `required_signatures = true` once all platform-team contributors have GPG/SSH signing set up.

## Threat model summary

| Threat | Mitigation in this POC | Mitigation in production |
|---|---|---|
| Cross-team data exfiltration via shared APIM secrets | Team-scoped Key Vaults + `kv_uri_allowlist` CI check | + Private Endpoints, Azure Policy `kv-uri-allowlist` at MG scope |
| Backend pivot by abusing a foreign team's API definition | `path_scope` + `naming_convention` CI checks + path-scoped CODEOWNERS | + Network segmentation between APIM subnet and team workload subnets |
| Compromised SP exfiltrates Key Vault secrets | SP role limited to `Key Vault Secrets User` (read only) | + Conditional Access policy on the SP, IP allowlist on the GitHub-OIDC issuer |
| Force-push to main bypasses CI | Repository ruleset blocks force-push with no bypass actors, requires linear history | Same |
| Drift between APIM runtime and git | `extractor-drift.yml` cron + PR for diffs | Same, plus alerting if extractor lag > 1 hour |
