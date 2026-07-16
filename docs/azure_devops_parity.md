# GitHub ↔ Azure DevOps parity

This repository uses GitHub because the controls map more cleanly onto demonstrable features (file-in-repo ownership, OIDC, repository rulesets). For organisations that standardise on **Azure DevOps**, every control below has a working ADO equivalent — with one important caveat per row called out under "watch-out".

## Control-by-control mapping

| Reference doc § | Control intent | GitHub feature used here | Azure DevOps equivalent | Watch-out when porting to ADO |
|---|---|---|---|---|
| §4.2 | One folder per team, no team-owned files outside its folder | Repo structure under `apim-config/workspaces/<ws>/teams/<team>/` | Same repo structure in an ADO Repo | None |
| §4.3 | Per-path required reviewer = team-owning group | `.github/CODEOWNERS` | "Automatically include reviewers" branch policy, **one per team-path, marked Required**, min 1 reviewer from named ADO security group | Path filters are glob-only, no per-file overrides. Keep one folder per team. |
| §4.3 | Policy lives as code, not as a manual setting | GitHub ruleset provisioned by Terraform `github_repository_ruleset` | Branch policies managed via `az repos policy ... create` / Bicep / REST in a **separate** `apim-platform-policies` repo | The policy config itself is **not** stored in `apim-config` — it's in repo settings. The platform repo holding the policy config must apply the same lockdown to itself. |
| §4.3 | No one may bypass the policy except a single break-glass identity | Ruleset `bypass_actors = []` (or a single PIM-eligible team) | Repo permissions: deny `Bypass policies when completing pull requests` and `Bypass policies when pushing` to all groups, including Project Administrators, except a single named PIM group | This is the single most important configuration item. Project admins hold bypass **by default** on ADO. Without an explicit deny, the rest of the model is advisory. |
| §4.3 | Requestor / recent pusher cannot self-approve | Ruleset `require_code_owner_review = true` + `require_last_push_approval = true` | Branch policy: "Requestors can't approve their own changes" + "Prohibit most recent pusher from approving" | Both are **off by default** in ADO. Turn both on. |
| §4.3 | Stale reviews dismissed on new push | Ruleset `dismiss_stale_reviews_on_push = true` | Branch policy: "Reset code reviewer votes when there are new changes" | Off by default in ADO. Turn on. |
| §4.3 | Reviewer groups are flat (not nested) | GitHub teams created flat by Terraform | Flat ADO security groups (mirrored from flat Entra groups) | Nested-group expansion for required reviewers has historically been delayed/partial in ADO. Use flat groups. |
| §4.4 | Pipeline is the only writer to APIM | `sp-apiops-publisher` SP holds `API Management Service Contributor`; humans hold Reader only | Same SP, same RBAC, but the SP is held in an **ADO Service Connection** | Service Connection → Security → **"Restrict permission to specific pipelines"** pointing at the publisher pipeline only. Otherwise any pipeline in the project can mint a token. |
| §4.4 | Production deploy requires a second independent approval | `environment: apim-prod` with required reviewers in `publisher.yml` | ADO Environment `apim-prod` with **Approvals and Checks** → pre-deployment approval | ADO Environments are real (don't confuse with "Stages"); the publisher pipeline must declare `environment: apim-prod` in its stage |
| §4.4 | No long-lived secrets in Git or CI | GitHub OIDC → Azure federated credentials (`azure/login@v2` with `client-id` + `tenant-id` only) | Workload Identity Federation in the ADO Service Connection (preview/GA as of 2025) | If ADO WIF isn't available in the customer's environment yet, fall back to a Key Vault-backed federated credential or to a managed identity hosted on a self-hosted agent — **never** a client secret committed anywhere |
| §4.4 | Drift reconciliation | `extractor-drift.yml` workflow on cron | ADO scheduled pipeline doing the same APIOps extractor + diff + auto-PR | None functional; YAML syntax differs |
| §4.4 | Audit retention beyond default | GitHub audit log streamed to Log Analytics (org-level, paid feature) | **ADO Auditing Streams** → Log Analytics. Default retention is **90 days** — forwarding is required for regulated workloads | Auditing Streams is part of ADO; enable it explicitly |
| §4.5 | 6 CI checks as required status checks | `pr-validation.yml` running `.github/scripts/*.py` + required-check ruleset | Same Python scripts wrapped in an **azure-pipelines.yml** registered as a **Build validation** branch policy, marked Required | Build validation policies are **also subject to bypass**. Same lockdown as the reviewer policy applies. |
| §6 | Per-team outbound MI on shared gateway | Not solvable on built-in gateway in either SCM | Same gap on either SCM. Workspace gateway + workspace MI is the long-term answer | This is a platform constraint, not an SCM choice |
| Reference: Workspace Consolidation | One workspace per business domain (~8-10); freeze on new workspaces | `.github/scripts/freeze_workspace.py` + `config/ci.json:domains[]` | Same Python script, same `ci.json`. Wire into the same ADO Build validation pipeline. | None functional. |
| Reference: Tiering (Gold/Silver/Bronze) | `tier` field enforced, bronze cannot be active | `.github/scripts/tier_check.py` | Same script in ADO. | None. |
| Reference: Versioning Policy | `info.version` required, `deprecated:true` requires `x-deprecation-date` | `.github/scripts/versioning.py` | Same script. | None. |
| Reference: Deduplication Strategy | Duplicate backend / policy detection (report-only) | `.github/scripts/inventory.py` run from `extractor-drift.yml`; artifact uploaded | Same script invoked from the ADO scheduled drift pipeline; publish as Pipeline artifact. | ADO artifact retention differs from GitHub; set explicitly. |
| Reference: Centralized Policy Governance | Azure Policy auditing `<base/>` inheritance at the APIM resource | `infra/modules/apim/main.tf` — `azurerm_resource_policy_assignment` | Identical Terraform; runs from either CI. | Policy definition GUID must exist in the target tenant. |
| Reference: Performance & Capacity | APIM Capacity + 5xx metric alerts | `infra/modules/observability/main.tf` — `azurerm_monitor_metric_alert` | Identical Terraform. | None. |
| Reference: RBAC and Access Control | Entra group per team + service-scope "API Management Service Reader Role" floor | `infra/modules/identity/main.tf` — `team_groups` for_each | Identical Terraform. Entra groups are SCM-agnostic. | None. |
| Reference: Environment Separation | Distinct Dev/Test/Prod with separate OIDC subjects | `.github/workflows/publisher.yml` 3 jobs + `apim-dev|test|prod` Environments | ADO Stages + Environments with pre-deployment approval. WIF subject per Service Connection. | Don't share one SP across envs. |

## Authentication setup, side by side

### GitHub OIDC (what this repo uses)

```hcl
resource "azuread_application_federated_identity_credential" "apiops_publisher" {
  application_id = azuread_application.apiops_publisher.id
  display_name   = "github-${var.github_owner}-${var.github_repo}-environment-apim-prod"
  description    = "Federation for ${var.github_repo} publisher.yml in apim-prod environment"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_owner}/${var.github_repo}:environment:apim-prod"
}
```

Then in the workflow:

```yaml
permissions:
  id-token: write
  contents: read
jobs:
  publish:
    environment: apim-prod
    steps:
      - uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      # ... apiops publisher steps ...
```

No secret. The federation token is scoped to a single workflow running against a single environment.

### Azure DevOps Workload Identity Federation (equivalent)

Create an ADO Service Connection of type **Azure Resource Manager**, authentication method **Workload Identity federation (automatic)**. ADO mints the federated credential on the Entra app on your behalf. The corresponding subject on the Entra app looks like:

```
sc://<ADO-org>/<ADO-project>/<service-connection-name>
```

Lock the Service Connection down:

- Service Connection → Security → **Restrict permission to specific pipelines** → add the publisher pipeline only.
- Service Connection → Security → deny `Use` to everyone else; grant `Use` to the publisher pipeline's service account.

Reference the connection from the pipeline:

```yaml
stages:
  - stage: Publish
    jobs:
      - deployment: PublishAPIM
        environment: apim-prod    # Environment must have pre-deployment approval configured
        strategy:
          runOnce:
            deploy:
              steps:
                - task: AzureCLI@2
                  inputs:
                    azureSubscription: 'sp-apiops-publisher'   # the locked-down Service Connection
                    scriptType: pscore
                    scriptLocation: scriptPath
                    scriptPath: scripts/apiops-publish.ps1
```

## CI script portability

The Python scripts under `.github/scripts/` (path scope, base/ check, KV URI allowlist, backend allowlist, naming, secret scan) are **plain Python** — they take a list of changed files via env or stdin and exit non-zero on failure. They are not GitHub-specific. The only platform-specific piece is the wrapper workflow that invokes them. The ADO equivalent is:

```yaml
steps:
  - checkout: self
    fetchDepth: 0
  - task: UsePythonVersion@0
    inputs: { versionSpec: '3.11' }
  - bash: |
      pip install -e .[dev]
      git diff --name-only origin/$(System.PullRequest.TargetBranch)...HEAD > /tmp/changed.txt
      python .github/scripts/path_scope.py --changed-files /tmp/changed.txt
      python .github/scripts/base_inheritance.py --changed-files /tmp/changed.txt
      python .github/scripts/kv_uri_allowlist.py --changed-files /tmp/changed.txt
      python .github/scripts/backend_allowlist.py --changed-files /tmp/changed.txt
      python .github/scripts/naming_convention.py --changed-files /tmp/changed.txt
      python .github/scripts/secret_scan.py --changed-files /tmp/changed.txt
    displayName: APIM-config CI checks
```

Register that pipeline as a **Build validation** branch policy on `main`, marked Required.

## Summary

Nothing in this reference repo is fundamentally GitHub-only. Every control — OIDC, file-in-repo ownership, environment gates, ruleset-as-code — has an Azure DevOps counterpart that is at least as expressive when the **three specific defaults are flipped** (bypass denied, self-approval off, recent-pusher approval off). Without those flips, ADO's controls are advisory and the model breaks.
