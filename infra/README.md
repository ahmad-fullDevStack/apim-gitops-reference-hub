# infra/

Terraform that provisions the POC: APIM (Standard v2 by default) + one workspace + two team Key Vaults + Log Analytics + the two service principals (publisher, extractor) with GitHub-OIDC federated credentials + the GitHub repository ruleset.

## Prerequisites

- Azure CLI logged in (`az login`) to a throwaway POC subscription.
- Terraform >= 1.7.
- `GITHUB_TOKEN` environment variable set to a token with admin rights on the target repository (a fine-grained PAT or a GitHub App installation token).
- The five GitHub teams referenced in `terraform.tfvars` already exist in the target org.

## Usage

```powershell
cd envs/poc
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars

terraform init
terraform plan -out tfplan
terraform apply tfplan
```

## What gets created

| Module | Resources |
|---|---|
| `modules/apim` | APIM (SKU from `var.sku_name`, default `StandardV2_1`) + system-assigned managed identity |
| `modules/workspace` | One APIM workspace `pensions-core` (via AzAPI — azurerm doesn't yet have a first-class resource) |
| `modules/team_kv` | Per-team Key Vault (RBAC mode) + role assignment granting APIM MI `Key Vault Secrets User` |
| `modules/identity` | `sp-...-apiops-publisher` (APIM Service Contributor) and `sp-...-apiops-extractor` (Reader) with GitHub-OIDC federated credentials |
| `modules/observability` | Log Analytics workspace + APIM diagnostic settings |
| `modules/repo_policy` | GitHub repository ruleset on `main`, CODEOWNERS file, Dependabot security updates |

## Cost

APIM is the dominant cost. The POC defaults to **Standard v2** (`StandardV2_1`),
which supports workspaces on the service's default managed gateway at a small
fraction of Premium's price. Set `sku_name = "Premium_1"` in `terraform.tfvars`
only if you need dedicated workspace gateways (`modules/workspace_gateway`),
which are Premium-only (~€2,500/month list). For a demo you can:

- run `terraform apply` only when you need to demonstrate live behaviour, and `terraform destroy` immediately after;
- confirm `StandardV2` is available in your target region first (it is not in every region) to avoid `SkuNotAvailable`.

Set the tag `auto-delete-after = "<date>"` in `terraform.tfvars` so the subscription's cleanup policy reaps it.

## Destructive operations

`terraform destroy` removes the APIM service (irreversible deletion takes ≅45 min) and the Key Vaults (soft-delete retention is 7 days). The destroy plan will be shown before apply. The publisher SP is **not** deleted automatically if you have manually granted it permissions elsewhere — inspect `terraform plan -destroy` first.

## State

This module defaults to **local state**. Before pointing at a real environment, configure an Azure Storage backend block in `envs/poc/main.tf` (or a separate `backend.tf`). See `global.instructions.md` for the workspace standard.
