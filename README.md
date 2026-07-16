# apim-gitops-reference

A reference implementation of the **Azure API Management + GitOps multi-team isolation pattern** described in [docs/reference_architecture.md](docs/reference_architecture.md).

This repository is a **POC scaffold for a customer demo**. It is opinionated, deliberately small, and structured so that an engineer can:

1. `terraform apply` against a throwaway Azure subscription and get a working APIM (Standard v2) instance with one workspace, two team Key Vaults, RBAC, and Log Analytics in ~25 minutes.
2. Push a sample API change through the GitHub PR → build-validation → environment-approval → APIOps-publisher pipeline.
3. Run **five canned negative scenarios** (cross-team write, foreign-KV reference, `<base/>` escape, naming violation, drift detection) and watch the controls block each one.
4. See how every GitHub-specific control maps to its Azure DevOps equivalent (`docs/azure_devops_parity.md`).

> The repository targets **GitHub** as the SCM/CI of record because it has first-class file-in-repo ownership (`CODEOWNERS`), OIDC federation, and repository rulesets that are simpler to demo than the Azure DevOps equivalents. The parity doc shows the exact ADO setting/feature that achieves each control if you standardise on ADO instead.

> **Adopting this in your own environment?** Start with the
> **[Customer implementation guide](docs/IMPLEMENTATION_GUIDE.md)** — a
> step-by-step "do this on your side" walkthrough, including the field-tested
> gotchas in [§8 Things to be mindful of](docs/IMPLEMENTATION_GUIDE.md#8-things-to-be-mindful-of-field-tested-gotchas).
> The same gotchas are summarised under [Things to be mindful of](#things-to-be-mindful-of) below.

---

## Repository layout

```
apim-gitops-reference/
├── README.md                      # you are here
├── docs/
│   ├── reference_architecture.md  # condensed pointer to the source doc
│   ├── azure_devops_parity.md     # GitHub <-> ADO mapping
│   ├── demo_runbook.md            # 5 scenarios, step-by-step
│   └── diagrams/                  # mermaid copies of the source diagrams
├── infra/                         # Terraform
│   ├── envs/poc/                  # root module
│   └── modules/
│       ├── apim/
│       ├── workspace/
│       ├── team_kv/
│       ├── identity/              # SPs, OIDC federated creds, RBAC
│       └── observability/
├── apim-config/                   # the GitOps source of truth for APIM
│   ├── service/                   # platform-owned global APIM config
│   └── workspaces/
│       └── pensions-core/
│           ├── workspace.json
│           ├── policy.xml
│           ├── shared/            # canonical/shared APIs (contoso-), domain-leads-owned
│           └── teams/             # signpost README only — team API slices live in
│                                  #   the per-team spoke repos apim-team-a / apim-team-b
├── backends/                      # stub Azure Function used by team-a sample API
│   └── stub_orders_api/
├── .github/
│   ├── CODEOWNERS
│   ├── dependabot.yml
│   ├── workflows/
│   │   ├── pr-validation.yml         # build validation (the 6 CI checks)
│   │   ├── publisher.yml             # APIOps publisher, env-gated
│   │   ├── extractor-drift.yml       # scheduled drift detection
│   │   ├── terraform-validate.yml    # tf fmt + validate + tflint + checkov + plan
│   │   └── tests.yml                 # pytest + actionlint + Terratest (optional)
│   └── scripts/                      # Python implementations of the 6 CI checks
├── scripts/                          # demo helpers (idempotent bootstrap, teardown)
├── tests/
│   ├── unit/                         # pytest for .github/scripts/
│   ├── fixtures/                     # synthetic PR diffs for the 5 scenarios
│   ├── terraform/                    # Terratest skeletons + plan snapshot tests
│   └── e2e/                          # opt-in end-to-end against a real sub
├── .editorconfig
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml                    # pytest, coverage, ruff config
└── LICENSE
```

---

> **Hub-and-spoke:** the team API code (`teams/team-a/`, `teams/team-b/`) has
> been moved out of this hub into per-team **spoke repos** (`apim-team-a`,
> `apim-team-b`). The hub is the **control plane**: guardrail scripts,
> `config/ci.json` (the team registry/allowlists the publish gate enforces),
> the shared/canonical APIs, workspace policy, per-team infrastructure, reusable
> publish workflows, and drift detection. Each spoke mirrors the exact
> `apim-config/workspaces/<domain>/teams/<team>/` path and calls the hub's
> reusable workflows. See
> **[docs/multi_repo_hub_and_spoke.md](docs/multi_repo_hub_and_spoke.md)**.

## How the controls in the reference doc map to this repo

| Reference doc § | Control | Where it lives here |
|---|---|---|
| §4.2 | Team-owned folders | Per-team **spoke repos** (`apim-team-a`, `apim-team-b`); the hub keeps only the `teams/` signpost + the `config/ci.json` registry — see [docs/multi_repo_hub_and_spoke.md](docs/multi_repo_hub_and_spoke.md) |
| §4.3 | Path-scoped required reviewers | `.github/CODEOWNERS` + ruleset in `infra/modules/repo_policy/` |
| §4.3 | Bypass lockdown + self-approval off | Ruleset `bypass_actors = []`, `require_code_owner_review = true`, `dismiss_stale_reviews_on_push = true` |
| §4.4 | Pipeline-only writes | OIDC-federated `sp-apiops-publisher`; humans hold APIM Reader only |
| §4.4 | Environment approval gate | `.github/workflows/publisher.yml` targets `environment: apim-prod` with required reviewers |
| §4.4 | Drift reconciliation | `.github/workflows/extractor-drift.yml` (cron) |
| §4.4 | Audit retention | Diagnostic settings on APIM + ADO/GitHub audit log forwarded to Log Analytics in `modules/observability/` |
| §4.5 | 6 CI checks (path scope, base/, KV URI, backend allowlist, naming, secret scan) | `.github/scripts/*.py` invoked from `pr-validation.yml`, marked as required status checks by the ruleset |
| §5.x | Per-team Key Vault, named values | `infra/modules/team_kv/` (hub-provisioned) + `teams/<team>/named-values/` in the team's spoke repo |
| §6 | Workspace-gateway MI gap | Documented in `docs/reference_architecture.md`; NOT provisioned (would require workspace gateway) |

---

## Quickstart

```powershell
# 0. Prereqs
#    - Azure CLI logged in to a throwaway POC subscription (az must be on PATH:
#      APIOps authenticates via DefaultAzureCredential -> AzureCliCredential)
#    - Terraform >= 1.7
#    - Python 3.11+ (runs the CI guardrail scripts and unit tests)
#    - A self-hosted GitHub runner labelled [self-hosted, linux, x64] OR switch
#      runs-on to ubuntu-latest — otherwise every workflow run queues forever
#    - A GITHUB_TOKEN/PAT with repo-admin rights (for the repo-policy ruleset terraform)
#    - APIOps v7.0.3 extractor/publisher binaries (the publisher/extractor workflows download them)

cd infra/envs/poc
terraform init
terraform plan -var subscription_id=<sub-id> -var location=westeurope -out tfplan
terraform apply tfplan
```

> ⚠️ **Cost callout** (global guardrails). The default POC apply provisions:
> - **API Management Standard v2** (`StandardV2_1`) — workspaces are supported
>   on the service's default gateway at a small fraction of Premium's cost.
>   Set `sku_name = "Premium_1"` only if you need **dedicated** workspace
>   gateways (`infra/modules/workspace_gateway/`, ~€2,500/month list, Premium-only).
>   Confirm Standard v2 is available in your target region first (`SkuNotAvailable`
>   otherwise).
> - **Application Insights + Log Analytics** — pay-as-you-go ingestion
>   (low single-digit € / day for a POC, but uncapped). The module sets
>   `retention_in_days = 30` to bound it.
> - **Two Key Vaults** + a handful of Entra groups (negligible).
> - Metric alerts on APIM Capacity and 5xx (free unless they fire).
>
> The example `terraform.tfvars` pins `auto-delete-after` and tags every resource
> so the platform team can vacuum forgotten POCs. APIM deletion takes ~45 min and
> Key Vault soft-delete retention is 7 days — `terraform destroy` promptly after a
> demo. Confirm the target subscription before running `apply`.

Then follow [docs/demo_runbook.md](docs/demo_runbook.md) for the five canned scenarios.

---

## Things to be mindful of

The pattern has been exercised end-to-end against a live Standard v2 APIM
(Terraform applies clean, APIOps v7 extracts/publishes, 148 unit tests pass, the
negative-scenario guardrails block what they should). The traps below are mostly
**environmental** — they make a correct repo *look* broken (or make a broken
setup *look* fine). The full walkthrough is in the
[Customer implementation guide](docs/IMPLEMENTATION_GUIDE.md); the short list:

1. **No runner = silent no-op CI.** All workflows target
   `runs-on: [self-hosted, linux, x64]`. With no runner registered, every run
   sits in `queued` forever — it looks "pending", not "failed", and nothing
   executes. Register a self-hosted runner (see `infra/runner/`) or change
   `runs-on` to `ubuntu-latest` (8 occurrences across the workflows).
2. **The ruleset is the actual control.** CODEOWNERS + CI checks are *advisory*
   until the `main` ruleset makes them required and un-bypassable. Verify
   `bypass_actors = []` (on Azure DevOps, admins hold bypass **by default** —
   you must explicitly deny it). Without a ruleset, `GET /branches/main/protection`
   is 404 and merges are ungated.
3. **APIOps v7 env var needs the `_PATH` suffix** —
   `API_MANAGEMENT_SERVICE_OUTPUT_FOLDER_PATH`, not `..._OUTPUT_FOLDER`. The
   no-suffix name is silently ignored and the binary crashes.
4. **Governance layout ≠ APIOps native layout.** Multi-word folders use spaces
   (`named values`, `version sets`), each API needs `apiInformation.json`, and
   the version-set info file is `versionSetInformation.json`.
   [scripts/apiops_adapter.py](scripts/apiops_adapter.py) bridges the two and is
   already wired into both workflows — reuse it; don't hand-craft.
5. **Workspaces are created by Terraform, not APIOps.** Apply infra before the
   first publish.
6. **SKU & region.** Default is `StandardV2_1` (supports workspaces, far cheaper
   than Premium). Premium is only needed for *dedicated* workspace gateways.
   Confirm Standard v2 region availability to avoid `SkuNotAvailable`.
7. **OIDC subject must match exactly** `repo:OWNER/REPO:environment:ENV`. A
   placeholder owner/repo fails the `azure/login` token exchange.
8. **`az` must be on `PATH`** for APIOps to authenticate (locally and on the runner).
9. **Local Terraform state** is the default — move to a remote backend before
   anything shared.
10. **Runtime secret isolation is a known platform gap.** On the **built-in**
    gateway, all workspaces share one service managed identity, so per-team
    *runtime* outbound secret isolation is **not** enforced — only prevented at
    PR time by the KV-URI guardrail. The future-state closer is a workspace
    gateway + workspace-scoped managed identity (Premium). Brief stakeholders on
    this; it is a platform constraint, not an SCM choice. See
    §6 (per-team identity on the built-in gateway) of
    [docs/reference_architecture.md](docs/reference_architecture.md).

---

## Testing & coverage

The testable surfaces of this scaffold are:

1. **Python CI scripts** (`.github/scripts/`) — pure functions, exhaustively unit-tested with synthetic diffs (`tests/unit/`, `tests/fixtures/`). Coverage target: **100%** measured by `pytest --cov`.
2. **Terraform modules** — covered by `terraform validate`, `tflint`, `checkov`, and snapshot tests of `terraform plan` output (`tests/terraform/plan_snapshots/`). Optional Terratest run against a real subscription (`tests/terraform/terratest/`).
3. **GitHub Actions workflows** — linted with `actionlint`.
4. **Five demo scenarios** — each has a corresponding pytest case that runs the relevant CI script against a fixture diff and asserts the expected pass/fail.

```powershell
# Python coverage
python -m pip install -e .[dev]
pytest --cov --cov-report=term-missing --cov-fail-under=100

# Terraform validation (no cloud calls)
cd infra/envs/poc
terraform init -backend=false
terraform validate
tflint --recursive
checkov -d .

# Workflow lint
actionlint

# Terratest (real cloud, opt-in)
cd tests/terraform/terratest
go test -v -timeout 60m
```

CI runs all of the above on every PR via `.github/workflows/tests.yml`.

---

## License

MIT. See [LICENSE](LICENSE).

---

## Source material

This repo operationalises the reference architecture summarised in
[docs/reference_architecture.md](docs/reference_architecture.md).
Any disagreement between this README and that document should be resolved in favour of the reference architecture.
