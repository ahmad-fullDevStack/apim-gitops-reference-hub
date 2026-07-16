# Reference architecture (condensed)

> **Scope.** This file is a one-page summary of the multi-team APIM isolation
> pattern this repository operationalises:
> 1. The intra-workspace team isolation pattern.
> 2. The wider workspace-consolidation / governance / dedup / tier strategy
>    (~8-10 domain workspaces, gold/silver/bronze tiers, Dev/Test/Prod).

## Problem

A platform team owns a shared Azure API Management instance. Multiple delivery teams need to publish APIs into the same APIM service. The teams must not be able to read each other's secrets, change each other's APIs, or write to each other's resources — but APIM's built-in workspace roles only express isolation at the **workspace** scope, not at the API / named-value / backend scope.

## Layer responsibility

APIM is the **abstraction and governance layer for APIs**. It is not a general-purpose IAM system, a secrets broker, or an application runtime. Several controls that look like APIM concerns are actually solved one layer up or one layer down:

| Concern | Owner | Why |
|---|---|---|
| Per-team write isolation on sub-workspace objects | **GitHub (or Azure DevOps)** | APIM has no per-resource RBAC matching at the role level for the built-in roles; CODEOWNERS / path-scoped required reviewers do |
| Per-tenant data authorization, per-tenant context | **Backend application** | The application knows its own tenancy model; APIM cannot enforce app-level row/object security |
| Per-team outbound secret isolation at runtime | **Workspace gateway + workspace MI** (future state) | Today's built-in gateway has a single service-MI shared across all workspaces — see the per-team identity on the built-in gateway section below |

## The pattern

1. **Teams hold APIM `Workspace Reader` only.** Never `Workspace Contributor`. The APIOps pipeline service principal is the **sole writer** in normal operations.
2. **Per-team folders under `apim-config/workspaces/<workspace>/teams/<team>/`.** No team-owned files outside that folder. *(In this reference implementation those per-team folders live in per-team **spoke repos** — `apim-team-a`, `apim-team-b` — that mirror the same path and call the hub's reusable checks; the pattern is identical. See [multi_repo_hub_and_spoke.md](multi_repo_hub_and_spoke.md).)*
3. **`CODEOWNERS` enforces folder ownership.** On a PR that touches `teams/team-b/**`, the `team-b-reviewers` team must approve. On Azure DevOps, the equivalent is a path-scoped "Automatically include reviewers" branch policy marked Required.
4. **Repository ruleset on `main`:**
   - require PR, require CODEOWNERS review, dismiss stale reviews on push;
   - require status checks: path-scope, `<base/>` inheritance, KV URI allowlist, backend allowlist, naming, secret scan;
   - `bypass_actors = []` (no role can bypass);
   - require linear history; block force pushes.
5. **Environment approval as a second independent gate.** Production deploys go through a GitHub Environment (`apim-prod`) with required reviewers; even a successfully-merged PR pauses for explicit approval before APIOps publishes.
6. **OIDC federation, no long-lived secrets.** The publisher SP authenticates to Azure via GitHub OIDC; no client secret lives in the repo or in GitHub Actions secrets.
7. **Drift reconciliation.** A scheduled extractor workflow compares APIM state against `apim-config/` and opens an auto-revert PR (and alerts) on any divergence.
8. **Audit forwarding.** APIM diagnostic settings + GitHub audit log are forwarded to Log Analytics for long-term retention.

## What this pattern does and does not enforce

| Action | Stopped where |
|---|---|
| Team A merges a change under `teams/team-b/**` | PR review (CODEOWNERS for team-b refuses) + CI path-scope check (`scripts/path_scope.py`) |
| Team A's policy references `kv-team-b` URI | CI named-value check (`scripts/kv_uri_allowlist.py`) |
| Team A's API publishes to a non-allowlisted backend | CI backend allowlist check |
| Team A names a resource `teamb-orders` to impersonate | CI naming check |
| Team A puts a literal secret in a named value | CI secret scan |
| Team A omits `<base/>` to bypass platform policy | CI `<base/>` check |
| Team A writes directly to APIM via portal/CLI | Azure RBAC — they only hold Reader |
| Team A reads `kv-team-b` directly | Azure RBAC — they have no role on that vault |
| Team A's runtime APIM policy reads from `kv-team-b` (shared service MI has access) | **Not blocked at runtime today.** Only prevented at PR time. This is the gap that workspace-gateway MI eventually closes. |

## Source diagrams

See [diagrams/](diagrams/).

## Wider scope this repo also operationalises

Beyond intra-workspace team isolation, the following controls live in this repo:

| Area | Control | Where it lives |
|---|---|---|
| Workspace consolidation strategy | One workspace per **business domain** (~8–10 total), provisioned via `for_each` over `var.domains` | [infra/envs/poc/main.tf](../infra/envs/poc/main.tf), [infra/envs/poc/terraform.tfvars.example](../infra/envs/poc/terraform.tfvars.example) |
| Tiering (Gold/Silver/Bronze) | `tier` field in `workspace.json`; CI rejects unknown tiers and Bronze-with-`active=true` | [.github/scripts/tier_check.py](../.github/scripts/tier_check.py), [config/ci.json](../config/ci.json) `valid_tiers` |
| Add-workspace freeze | Workspaces can only be added if listed in `config/ci.json:domains[]` | [.github/scripts/freeze_workspace.py](../.github/scripts/freeze_workspace.py) |
| Versioning policy | Spec must declare `info.version`; `deprecated:true` requires `x-deprecation-date` | [.github/scripts/versioning.py](../.github/scripts/versioning.py), [versioning_policy.md](versioning_policy.md) |
| Deduplication strategy | Canonical APIs + version sets under `pensions-core/shared/` | [apim-config/workspaces/pensions-core/shared/](../apim-config/workspaces/pensions-core/shared/) |
| Deduplication strategy (discovery) | Inventory scan reports duplicate backend URLs + near-duplicate policies | [.github/scripts/inventory.py](../.github/scripts/inventory.py), uploaded as workflow artifact by extractor-drift.yml |
| Centralized policy governance | Service-level `<cors>`, CSP, HSTS, X-Content-Type-Options, JWT scaffold, Application Insights logger | [apim-config/service/policy.xml](../apim-config/service/policy.xml), [infra/modules/apim/main.tf](../infra/modules/apim/main.tf) |
| Centralized policy governance | Azure Policy assignment auditing `<base/>` inheritance (Audit→Deny once teams are clean) | [infra/modules/apim/main.tf](../infra/modules/apim/main.tf) — `azurerm_resource_policy_assignment` |
| Performance & capacity | App Insights + Capacity / 5xx metric alerts | [infra/modules/observability/main.tf](../infra/modules/observability/main.tf) |
| Identified gaps and mitigations | Workspace gateway skeleton (with documented MI gap) | [infra/modules/workspace_gateway/](../infra/modules/workspace_gateway/) |
| RBAC and access control | Entra group per team (contributor + reader), service-scope "API Management Service Reader" floor | [infra/modules/identity/main.tf](../infra/modules/identity/main.tf) — `team_groups` |
| Environment separation | Dev / Test / Prod via per-env tfvars; OIDC subject per env (`environment:apim-dev|test|prod`) | [infra/envs/poc/{dev,test,prod}.tfvars.example](../infra/envs/poc/), [.github/workflows/publisher.yml](../.github/workflows/publisher.yml) |
