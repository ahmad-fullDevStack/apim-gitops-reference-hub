# Customer implementation guide

How to take the principles in the reference architecture and stand
them up in **your own** Azure + GitHub (or Azure DevOps) environment using this
repository as the starting template.

> This guide is the practical "do this on your side" companion to the
> conceptual material. For the *why*, read
> [docs/reference_architecture.md](reference_architecture.md) and the source
> deck/PDF. For the *what maps to what*, read the tables in
> [README.md](../README.md#how-the-controls-in-the-reference-doc-map-to-this-repo)
> and [docs/azure_devops_parity.md](azure_devops_parity.md). This document is
> the *how*, plus the **gotchas we verified end-to-end** so you don't rediscover
> them the hard way.

> **Running one repo per team instead of a monorepo?** See
> [docs/multi_repo_hub_and_spoke.md](multi_repo_hub_and_spoke.md) for the
> hub-and-spoke model, the drift fan-out, and the per-team cutover runbook.

---

## 0. What you get and what you must supply

This repo is an opinionated reference, not a turn-key product. Adopting it means
**forking it and replacing the sample-specific values with yours**. Concretely:

| You keep (reuse as-is) | You replace (your values) |
|---|---|
| The `apim-config/` folder shape (`workspaces/<domain>/teams/<team>/`) | The domain/team names, the sample APIs, policies, named values |
| The 9 CI guardrail scripts in `.github/scripts/` | `config/ci.json` (your domains, teams, tiers, allowlists, naming prefixes) |
| The Terraform module structure in `infra/modules/` | `infra/envs/poc/terraform.tfvars` (your subscription, region, org, repo) |
| The workflow shapes in `.github/workflows/` | `runs-on:` targets, environment names, OIDC client/tenant IDs |
| `scripts/apiops_adapter.py` (governance ↔ APIOps layout bridge) | nothing — reuse verbatim |

Everything in this repo has been exercised end-to-end against a live Azure APIM
(Standard v2) instance: Terraform applies clean, APIOps v7 extracts and
publishes the config, the 148 unit tests pass, and the negative-scenario
guardrails block the changes they are supposed to block.

---

## 1. Prerequisites (versions we validated)

| Tool | Version we used | Notes |
|---|---|---|
| Azure CLI | 2.87.0 | `az login` to a throwaway subscription. **APIOps needs `az` on `PATH`** (it authenticates via `DefaultAzureCredential` → `AzureCliCredential`). |
| Terraform | 1.7+ (we ran 1.15.x) | State defaults to **local** — see §6. |
| Python | 3.11+ (we ran 3.12) | Runs the CI guardrail scripts and unit tests. |
| APIOps | **v7.0.3** | `extractor` + `publisher` binaries. Env-var contract changed in v7 — see §5. |
| GitHub CLI (`gh`) | optional | Convenient for PRs; everything also works via the REST API or the web UI. |
| A self-hosted runner **or** a one-line edit to use GitHub-hosted runners | — | **This is the #1 thing that silently breaks CI — see §4.** |

---

## 2. Fork and re-key the configuration

1. Fork/clone this repo into your org.
2. Edit [config/ci.json](../config/ci.json):
   - `domains[]` — your business-domain workspaces (the PDF recommends ~8–10).
   - `teams[]` — each team's `name`, folder, reviewer group, and naming `prefix`.
   - `valid_tiers`, `kv_allowlist`, `backend_allowlist` — your governance values.
3. Rename the folders under `apim-config/workspaces/` and
   `apim-config/workspaces/<domain>/teams/` to match. **The folder names, the
   `config/ci.json` entries, and the CODEOWNERS paths must agree** — the
   path-scope and freeze-workspace guardrails compare them.
4. Update [.github/CODEOWNERS](../.github/CODEOWNERS) so each team folder maps to
   the matching reviewer group.

> Run `python -m pytest -q` after re-keying. The unit tests will tell you
> immediately if the folder names, `ci.json`, and CODEOWNERS have drifted apart.

---

## 3. Provision the Azure infrastructure

```powershell
cd infra/envs/poc
cp terraform.tfvars.example terraform.tfvars
# edit: subscription_id, location, github_owner, github_repo, domains, sku_name
$env:ARM_SUBSCRIPTION_ID = "<your-sub-id>"
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

What this creates: APIM (Standard v2 by default) + one workspace per domain +
per-team Key Vaults + Log Analytics/App Insights + the publisher/extractor
service principals with GitHub-OIDC federated credentials + (optionally) the
GitHub repository ruleset. See [infra/README.md](../infra/README.md) for the
per-module breakdown.

**SKU note:** the default is `StandardV2_1`. Standard v2 supports workspaces on
the service's default gateway at a small fraction of Premium's cost. Only set
`sku_name = "Premium_1"` if you need **dedicated** workspace gateways
(`infra/modules/workspace_gateway/`), which are Premium-only. Confirm Standard
v2 is available in your target region first (`SkuNotAvailable` otherwise).

---

## 4. Wire up CI runners (do not skip)

Every workflow in `.github/workflows/` is pinned to **self-hosted** runners:

```yaml
runs-on: [self-hosted, linux, x64]
```

This is deliberate — regulated customers usually run CI on private runners
inside their network so the OIDC token exchange and APIM calls never leave it.
**But it means that on a fresh fork with no runner registered, every workflow
run sits in `queued` forever and nothing actually executes.** We hit exactly
this: CI looked "green-pending" but no job ever started.

Pick one:

- **Recommended for production:** register a self-hosted runner with the labels
  `self-hosted, linux, x64` (org- or repo-level). The Terraform in
  `infra/runner/` has helper scripts (`install-*.sh`) for provisioning one.
- **For a quick demo only:** change every `runs-on: [self-hosted, linux, x64]`
  to `runs-on: ubuntu-latest`. There are 8 occurrences across
  `tests.yml`, `pr-validation.yml`, `terraform-validate.yml`,
  `extractor-drift.yml`, and `publisher.yml` (3 jobs).

After this, push a trivial PR and confirm the checks actually **run** (not just
queue).

---

## 5. Wire up APIOps v7 (env-var + layout contract)

The publisher and extractor run the **real APIOps v7 binaries**. Two things
changed in v7 that will bite you if you copied v4/v5 examples from the web:

1. **The output-folder env var must end in `_PATH`:**
   ```text
   AZURE_SUBSCRIPTION_ID
   AZURE_RESOURCE_GROUP_NAME
   API_MANAGEMENT_SERVICE_NAME
   API_MANAGEMENT_SERVICE_OUTPUT_FOLDER_PATH   ← the _PATH suffix is REQUIRED
   ```
   The older name `API_MANAGEMENT_SERVICE_OUTPUT_FOLDER` (no suffix) is silently
   ignored and the binary crashes. The workflows in this repo already use the
   correct name.

2. **The on-disk layout APIOps expects is not the governance layout.** APIOps
   wants a flat `apis/`, `backends/`, `named values/`, `version sets/`, …
   (multi-word folders use **spaces**, e.g. `named values`), each API has an
   `apiInformation.json`, and the version-set info file is
   `versionSetInformation.json`. Our governance layout
   (`teams/<team>/...` + `shared/...`) is friendlier for humans and CODEOWNERS.
   [scripts/apiops_adapter.py](../scripts/apiops_adapter.py) translates between
   the two (`to-native` before publish, `to-governance` after extract) and is
   already wired into both workflows. Reuse it verbatim.

3. **Workspaces must already exist.** APIOps publishes resources *into* a
   workspace but does **not** create workspaces — Terraform does
   (`infra/modules/workspace`). Apply Terraform before the first publish.

---

## 6. Turn on the guardrails (the ruleset is the linchpin)

The team-isolation model is only as strong as the **branch protection / ruleset**
on `main`. The CODEOWNERS file and CI checks are *advisory* until a ruleset makes
them **required and un-bypassable**. `infra/modules/repo_policy/` provisions this
via Terraform (needs a `GITHUB_TOKEN`/PAT with repo-admin rights).

Verify, after applying, that on `main`:

- a PR is required, and **CODEOWNERS review is required**;
- the CI checks (path-scope, `<base/>`, KV-URI allowlist, backend allowlist,
  naming, secret-scan, tier, freeze-workspace, versioning) are **required status
  checks**;
- `bypass_actors = []` — **no one**, including org/Project admins, can bypass.
  On GitHub this is an explicit empty list; on Azure DevOps, admins hold bypass
  **by default** and you must explicitly deny it (see the parity doc);
- self-approval and stale-review dismissal are configured
  (`require_last_push_approval`, `dismiss_stale_reviews_on_push`).

> We verified on a fork that **without** a ruleset, `GET /branches/main/protection`
> returns 404 and merges are ungated — the isolation is purely advisory. Treat
> "ruleset applied + `bypass_actors` empty" as the single most important
> acceptance check.

Also update the **OIDC federated-credential subject** to your real values. The
subject must be exactly `repo:<OWNER>/<REPO>:environment:<ENV>` (e.g.
`environment:apim-prod`). A placeholder owner/repo will fail the token exchange
at `azure/login` time even though everything else looks correct.

State backend: the POC defaults to **local** Terraform state. Before any shared
or production environment, configure an Azure Storage backend (see
[infra/README.md](../infra/README.md#state)).

---

## 7. Verify the controls actually block (negative scenarios)

The whole point of the pattern is that the wrong change is *stopped*. Prove it.
Each scenario in [docs/demo_runbook.md](demo_runbook.md) is reproducible, and
every one is also asserted by a unit test against a fixture diff, so you can
validate the logic **without touching Azure**:

```powershell
python -m pytest -q          # 148 tests; guardrail logic + round-trips
```

You can also run a single guardrail against a hand-written changed-file list —
e.g. prove the one-PR-per-team rule rejects a cross-team change:

```powershell
"apim-config/workspaces/<domain>/teams/team-a/apis/x/apiInformation.json
apim-config/workspaces/<domain>/teams/team-b/apis/y/apiInformation.json" |
  python .github/scripts/path_scope.py --changed-files -
# exits 1: "PR touches multiple team folders (team-a, team-b)"
```

For the full live demo (real PRs, real APIM, drift auto-revert), follow the
runbook end-to-end once your runner and ruleset are in place.

---

## 8. Things to be mindful of (field-tested gotchas)

A consolidated checklist of the traps we hit or that will bite a customer. Most
are environmental, not code:

1. **No runner = silent no-op CI.** Workflows target self-hosted runners; with
   none registered, runs queue forever and look "pending", not "failed". Either
   register a runner or switch `runs-on` to `ubuntu-latest`. (§4)
2. **The ruleset is the control.** CODEOWNERS + CI without a ruleset is
   advisory. `bypass_actors` **must** be empty; on Azure DevOps you must
   explicitly deny admin bypass. (§6)
3. **APIOps v7 env var needs the `_PATH` suffix.** `..._OUTPUT_FOLDER_PATH`,
   not `..._OUTPUT_FOLDER`. The no-suffix name is ignored and the binary
   crashes. (§5)
4. **Governance layout ≠ APIOps native layout.** Multi-word folders use spaces
   (`named values`, `version sets`); each API needs `apiInformation.json`;
   version-set info file is `versionSetInformation.json`. Use the adapter; don't
   hand-craft. (§5)
5. **Workspaces are created by Terraform, not APIOps.** Apply infra before the
   first publish. (§5)
6. **SKU & region.** Standard v2 supports workspaces and is far cheaper than
   Premium; Premium is only needed for *dedicated* workspace gateways. Confirm
   Standard v2 region availability to avoid `SkuNotAvailable`. (§3)
7. **OIDC subject must match exactly** `repo:OWNER/REPO:environment:ENV`. A
   placeholder owner/repo fails the token exchange. (§6)
8. **`az` must be on `PATH`** for APIOps to authenticate locally (and on the
   runner). (§1)
9. **Local Terraform state** is the default — move to a remote backend before
   anything shared. (§6)
10. **Runtime secret isolation is a known platform gap.** On the **built-in**
    gateway, all workspaces share one service managed identity, so per-team
    *runtime* outbound secret isolation is **not** enforced — it is only
    prevented at PR time by the KV-URI guardrail. The future-state closer is a
    **workspace gateway + workspace-scoped managed identity** (Premium). This is
    a platform constraint, not an SCM choice — call it out to stakeholders. See
    §6 (per-team identity on the built-in gateway) of the reference architecture.
11. **Cost & teardown.** APIM deletion takes ~45 min; Key Vault soft-delete
    retention is 7 days. Tag `auto-delete-after` and `terraform destroy`
    promptly after a demo. (§3)

---

## 9. If you standardise on Azure DevOps instead of GitHub

Everything here maps to Azure DevOps. The Python guardrail scripts, the
Terraform, the Entra groups, and APIOps are all SCM-agnostic; only the
ownership/branch-policy/OIDC plumbing differs. The exact ADO setting for each
control — and the per-row porting watch-outs — are in
[docs/azure_devops_parity.md](azure_devops_parity.md). The most important one:
**Project Administrators hold policy-bypass by default on ADO**; you must
explicitly deny it, or the entire model is advisory.

---

## 10. Acceptance checklist

Use this as a go/no-go before showing or shipping:

- [ ] `config/ci.json`, `apim-config/` folders, and `.github/CODEOWNERS` agree (unit tests pass).
- [ ] `terraform apply` is clean against your subscription; APIM is `Succeeded`.
- [ ] A self-hosted runner is registered (or `runs-on` switched) and a test PR's checks actually **run**.
- [ ] Ruleset on `main` is applied; `bypass_actors = []`; the 9 checks are required.
- [ ] OIDC subject matches your `repo:OWNER/REPO:environment:ENV`; `azure/login` succeeds.
- [ ] APIOps publisher run is green; extractor drift workflow opens an auto-revert PR when you hand-edit APIM.
- [ ] At least scenarios 1–4 from the runbook are demonstrably **blocked**.
- [ ] Stakeholders are briefed on the runtime secret-isolation gap (gotcha #10).
- [ ] Remote Terraform state backend configured for any non-throwaway environment.
