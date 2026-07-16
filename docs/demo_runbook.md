# Demo runbook — nine scenarios

Each scenario is a self-contained PR that exercises one of the controls described in the reference architecture. The repository's tests (`tests/unit/`) also assert each of these against the canned fixture diffs in `tests/fixtures/`, so the scenarios are reproducible without ever touching Azure.

> **Hub-and-spoke note.** The team API slices (`teams/team-a/**`, `teams/team-b/**`)
> now live in the per-team **spoke repos** (`apim-team-a`, `apim-team-b`), not in
> this hub. The spokes mirror the exact `apim-config/workspaces/pensions-core/teams/<team>/`
> path, so the team-slice scenarios below (**1–4**) run **from a spoke clone** with
> the commands unchanged — the spoke's PR calls the hub's reusable checks, which
> read `config/ci.json` from the hub and enforce the same guardrails. The
> control-plane / shared-domain scenarios (**5–9**) run in this hub. See
> [multi_repo_hub_and_spoke.md](multi_repo_hub_and_spoke.md).

| # | Scenario | What gets blocked | By which control |
|---|---|---|---|
| 1 | Team A engineer modifies `teams/team-b/**` | PR cannot complete | CODEOWNERS requires team-b approval + CI `path_scope.py` fails |
| 2 | Team A adds a named value pointing at `kv-team-b` | PR cannot complete | CI `kv_uri_allowlist.py` fails |
| 3 | Team A's policy omits `<base/>` in `<inbound>` | PR cannot complete | CI `base_inheritance.py` fails |
| 4 | Team A creates `teamb-orders-v2` (impersonation) | PR cannot complete | CI `naming_convention.py` fails |
| 5 | Someone edits APIM directly in the portal | Drift detected within 1 hour | `extractor-drift.yml` opens auto-revert PR |
| 6 | Someone adds `apim-config/workspaces/payments/` without listing `payments` in `config/ci.json:domains[]` | PR cannot complete | CI `freeze_workspace.py` fails |
| 7 | A workspace.json sets `"tier": "bronze"` and `"active": true` | PR cannot complete | CI `tier_check.py` fails |
| 8 | An OpenAPI spec sets `deprecated: true` without `info.x-deprecation-date` | PR cannot complete | CI `versioning.py` fails |
| 9 | Two teams ship the same backend URL | Reported, not blocked | `inventory.py` flags duplicates in the extractor artifact |

## Pre-demo setup

1. Apply Terraform to a throwaway POC subscription:

   ```powershell
   cd infra/envs/poc
   terraform init
   terraform apply -var subscription_id=<id> -var location=westeurope
   ```

2. Push the repo to GitHub. The repo-policy Terraform creates the ruleset, environments, and OIDC federated credentials.

3. Add yourself to the `team-a-reviewers` GitHub team. Add a second account to `team-b-reviewers`.

4. Wait for the first `publisher.yml` run to complete — it pushes the initial APIM config from `apim-config/` into the workspace.

## Scenario 1 — cross-team write

```powershell
git checkout -b demo/cross-team-write
# Edit team-b's API as team-a
sed -i 's/Orders/OrdersHacked/' apim-config/workspaces/pensions-core/teams/team-b/apis/teamb-claims-v1/specification.yaml
git commit -am "chore: cross-team edit demo"
git push -u origin demo/cross-team-write
gh pr create --title "Demo: cross-team write" --body "Expected to fail"
```

**Expected:** PR check `path-scope` fails. PR review shows `team-b-reviewers` is required and you cannot approve as a Team A member. Merge button stays disabled.

## Scenario 2 — foreign KV reference

```powershell
git checkout -b demo/foreign-kv
cat > apim-config/workspaces/pensions-core/teams/team-a/named-values/api-key.json <<'EOF'
{
  "displayName": "teama-api-key",
  "keyVault": {
    "secretIdentifier": "https://kv-pensions-core-team-b.vault.azure.net/secrets/api-key"
  }
}
EOF
git add . && git commit -m "chore: foreign kv ref demo"
git push -u origin demo/foreign-kv
gh pr create --title "Demo: foreign KV reference" --body "Expected to fail"
```

**Expected:** PR check `kv-uri-allowlist` fails with `Team team-a is not allowed to reference vault kv-pensions-core-team-b`.

## Scenario 3 — missing `<base/>`

```powershell
git checkout -b demo/missing-base
# Strip <base/> from the inbound section of team-a's policy
python - <<'PY'
import pathlib, re
p = pathlib.Path("apim-config/workspaces/pensions-core/teams/team-a/apis/teama-orders-v1/policy.xml")
p.write_text(re.sub(r"<base\s*/>", "", p.read_text(), count=1))
PY
git commit -am "chore: drop base/ demo"
git push -u origin demo/missing-base
gh pr create --title "Demo: missing base/" --body "Expected to fail"
```

**Expected:** PR check `base-inheritance` fails on `<inbound>` of `teama-orders-v1/policy.xml`.

## Scenario 4 — naming convention violation

```powershell
git checkout -b demo/naming
mkdir -p apim-config/workspaces/pensions-core/teams/team-a/apis/teamb-orders-v2
cp apim-config/workspaces/pensions-core/teams/team-a/apis/teama-orders-v1/specification.yaml \
   apim-config/workspaces/pensions-core/teams/team-a/apis/teamb-orders-v2/specification.yaml
git add . && git commit -m "chore: bad naming demo"
git push -u origin demo/naming
gh pr create --title "Demo: naming violation" --body "Expected to fail"
```

**Expected:** PR check `naming-convention` fails: `apis under teams/team-a/ must be prefixed with 'teama-'`.

## Scenario 5 — drift detection

1. In the Azure portal, open the APIM workspace and modify `teama-orders-v1` description to `"manually edited"`.
2. Run the extractor workflow on demand:
   ```powershell
   gh workflow run extractor-drift.yml
   ```
3. Wait ~2 min.

**Expected:** the extractor workflow opens an auto-revert PR titled `chore(drift): restore teama-orders-v1` containing the diff that re-applies the Git-known-good state.

## Scenario 6 — unsanctioned new workspace

```powershell
git checkout -b demo/freeze
mkdir -p apim-config/workspaces/payments
cat > apim-config/workspaces/payments/workspace.json <<'EOF'
{ "name": "payments", "displayName": "Payments", "tier": "gold", "active": true }
EOF
cat > apim-config/workspaces/payments/policy.xml <<'EOF'
<policies><inbound><base /></inbound><backend><base /></backend><outbound><base /></outbound><on-error><base /></on-error></policies>
EOF
git add . && git commit -m "chore: rogue workspace demo"
git push -u origin demo/freeze
gh pr create --title "Demo: unsanctioned workspace" --body "Expected to fail"
```

**Expected:** PR check `freeze-workspace` fails with `workspace 'payments' is not declared in config/ci.json:domains[]`. Adding the entry to `ci.json` (which is platform-owned via CODEOWNERS) unblocks it.

## Scenario 7 — bronze tier cannot be active

```powershell
git checkout -b demo/tier-bronze-active
python - <<'PY'
import json, pathlib
p = pathlib.Path("apim-config/workspaces/sandbox/workspace.json")
data = json.loads(p.read_text())
data["active"] = True
p.write_text(json.dumps(data, indent=2))
PY
git commit -am "chore: bronze+active demo"
git push -u origin demo/tier-bronze-active
gh pr create --title "Demo: bronze tier active" --body "Expected to fail"
```

**Expected:** PR check `tier-check` fails with `tier 'bronze' is not permitted with active=true (PDF: bronze has no SLA)`.

## Scenario 8 — deprecated API without deprecation date

```powershell
git checkout -b demo/versioning
python - <<'PY'
import pathlib, yaml
p = pathlib.Path("apim-config/workspaces/pensions-core/shared/apis/contoso-orders-canonical-v1/specification.yaml")
doc = yaml.safe_load(p.read_text())
doc["deprecated"] = True
p.write_text(yaml.safe_dump(doc, sort_keys=False))
PY
git commit -am "chore: deprecated-no-date demo"
git push -u origin demo/versioning
gh pr create --title "Demo: deprecated without date" --body "Expected to fail"
```

**Expected:** PR check `versioning` fails with `API is marked deprecated but info.x-deprecation-date is missing or not an ISO-8601 date`.

## Scenario 9 — duplicate backend (report-only)

```powershell
git checkout -b demo/dup-backend
mkdir -p apim-config/workspaces/pensions-core/teams/team-a/backends
cat > apim-config/workspaces/pensions-core/teams/team-a/backends/teama-canonical-dup.json <<'EOF'
{ "name": "teama-canonical-dup", "properties": { "url": "https://pensions-core-api.contoso.com/orders" } }
EOF
# Same URL is also configured on the canonical backend under shared/.
git commit -am "chore: dup backend demo"
gh pr create --title "Demo: duplicate backend (report-only)" --body "PR still passes; inventory.py flags this."
```

**Expected:** PR passes (inventory is not a pre-merge gate). The next scheduled `extractor-drift.yml` run uploads `inventory.json` showing both files under the same `duplicate_backend_urls` key.

## Teardown

```powershell
cd infra/envs/poc
terraform destroy -var subscription_id=<id> -var location=westeurope
```

Delete the demo branches and the demo PRs in the GitHub UI.
