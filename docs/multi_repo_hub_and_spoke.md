# Hub-and-spoke (multi-repo) model

How to run this reference as a **platform-owned hub** plus **one repo per team**,
instead of a single monorepo. The hub keeps the control plane (guardrail checks,
`config/ci.json`, shared/canonical APIs, workspace policy, drift detection); each
team gets a repo holding **only its slice** and publishes to its workspace
through hub-owned workflows.

Read the spoke-side story in
[team-repo-template/README.md](../team-repo-template/README.md). This document is
the **hub-side** view plus the **cutover runbook**.

---

## 1. What the hub owns vs what a spoke owns

| Concern | Hub (this repo) | Spoke (team repo) |
|---|---|---|
| Guardrail check logic (`.github/scripts/`) | Owns | Calls (can't edit) |
| `config/ci.json` (allowlists, prefixes, tiers) | Owns | PRs a change to the hub |
| Service policy, workspace policy, `workspace.json`, `shared/` | Owns | References only |
| The team's `teams/<team>/` slice | — | Owns |
| Publish workflow | Owns the reusable `team-publish.yml` | Thin caller pinned to a hub SHA |
| Drift detection (extractor Reader credential) | Owns | — |

The authoritative control is the **hub publish gate**, not anything a spoke can
edit. See the security-model table in the template README.

## 2. The pieces that make it work (already in this repo)

| File | Role |
|---|---|
| [.github/workflows/team-publish.yml](../.github/workflows/team-publish.yml) | **Authoritative** reusable: gate (central `ci.json`) + scoped `to-native --team` build + workspace-scoped OIDC publish, all in one un-skippable job. |
| [.github/workflows/reusable-checks.yml](../.github/workflows/reusable-checks.yml) | **Advisory** reusable: fast PR feedback for spokes. Not the control. |
| [scripts/apiops_adapter.py](../scripts/apiops_adapter.py) `--team` | Emits only one team's artifacts (skips shared + platform policy) so a publish can't touch another team in the shared workspace. |
| [.github/workflows/drift-fanout.yml](../.github/workflows/drift-fanout.yml) | Hub extracts the whole instance, routes native→governance, alarms on `_unassigned`, and opens a reconciliation PR **in each spoke**. |
| [scripts/drift_fanout.py](../scripts/drift_fanout.py) | Splits the routed extraction into a per-team matrix and raises the unassigned drift alarm. |
| [infra/modules/identity](../infra/modules/identity) `spoke_repos` | Adds a federated OIDC credential per spoke repo on the publisher SP. |

### Why scoped publish is safe in a shared workspace

`team-a` and `team-b` share the `pensions-core` workspace (they are folders, not
separate workspaces), so workspace-scoped RBAC cannot separate them. Two things
keep a team's publish from clobbering another team:

1. **Scoped build** — `apiops_adapter.py to-native --team team-a` emits only
   `teama-*` artifacts.
2. **Additive upsert** — APIOps publishes without `COMMIT_ID`, which (per the
   [APIOps Configuration wiki](https://github.com/Azure/apiops/wiki/Configuration))
   only upserts the artifacts present in the folder and never deletes resources
   absent from it. A `team-a` publish therefore cannot delete `team-b`'s APIs.

## 3. Drift fan-out

The hub holds the only extractor credential (Reader). `drift-fanout.yml` runs on
a schedule and:

1. Extracts the whole APIM instance (native layout).
2. Folds native → governance with `apiops_adapter.py to-governance`, which routes
   each resource into its owning team's folder by name prefix and quarantines
   unprefixed resources under `_unassigned/`.
3. **Alarm:** `drift_fanout.py unassigned` fails the job if anything landed in
   `_unassigned/` — that means APIM holds a resource matching no team prefix
   (out-of-band publish or naming violation) that no team folder can own.
4. **Fan-out:** for each team, it mints a short-lived GitHub App token scoped to
   that spoke, overlays the extracted slice, and opens a reconciliation PR in the
   spoke. The team decides: **merge** to adopt the live change as desired state,
   or **close** and re-run their publisher to restore the repo state.

The hub's existing [extractor-drift.yml](../.github/workflows/extractor-drift.yml)
still guards the hub-owned artifacts (service/workspace policy, `shared/`).

---

## 4. Cutover runbook (per team)

Move one team at a time. Do `team-a` first, confirm a full publish + drift cycle,
then repeat for `team-b`, then the other domains.

### 4.1 Prepare the spoke repo
1. Create the spoke repo `apim-<team>` under your org.
2. Copy [team-repo-template/](../team-repo-template/) into it and replace the
   placeholders (hub `owner/name`, `@REPLACE_WITH_HUB_COMMIT_SHA`, team + domain
   names, CODEOWNERS teams). See the template README checklist.
3. Copy the team's real slice from the hub
   (`apim-config/workspaces/<domain>/teams/<team>/`) into the same mirrored path
   in the spoke.

### 4.2 Provision identity
4. In `infra/envs/<env>`, add the team to `spoke_repos` on the identity module,
   e.g. `team-a = { repo = "apim-team-a" }`, and `terraform apply`. This adds the
   federated OIDC credential the spoke's `publisher.yml` needs. Keep the team's
   `team_groups` entry for workspace-scoped RBAC.
5. Set the spoke repo's secrets/vars (publisher client ID, tenant, subscription,
   `APIM_RG`, `APIM_NAME`) and configure the `apim-prod` environment.

### 4.3 Parity check (before you switch)
6. Freeze the team's slice in the hub (stop merging team changes there).
7. From the spoke, run `publisher.yml` against a **non-prod** environment first.
   Confirm the gate passes and the scoped build emits only that team's artifacts.
8. Diff the spoke publish result against the hub's last known-good for that team
   (or run the drift fan-out and confirm the spoke's reconciliation PR is empty).

### 4.4 Switch and retire
9. Point the team's day-to-day work at the spoke repo. Enable the spoke's
   `publisher.yml` on `apim-prod`.
10. Remove the team's slice from the hub (it now lives in the spoke). Keep
    `config/ci.json`, `shared/`, and workspace policy in the hub.
11. Confirm one clean drift-fanout cycle: no `_unassigned` alarm, empty
    reconciliation PR for the migrated team.

### 4.5 Rollback
If the spoke publish misbehaves, re-enable the hub slice and hub publisher for
that team (the slice is still in hub git history) and disable the spoke
`publisher.yml`. Because publishes are additive upserts, re-publishing the hub
slice restores the team's desired state without touching other teams.

---

## 5. Repo rulesets / branch protection

Apply these per repo. They are the enforcement floor that makes the pinned,
hub-owned workflows meaningful.

### Hub repo
- Require PRs to `main`; require the platform team as reviewers via
  [CODEOWNERS](../.github/CODEOWNERS) on `.github/`, `config/ci.json`, `service/`,
  `shared/`, and `infra/`.
- Require status checks: `tests`, `pr-validation`, `terraform-validate`.
- Restrict who can push/merge to the platform team; **do not** allow admins to
  bypass required checks.
- Protect the tags/SHAs that spokes pin to (don't force-push history spokes rely
  on).

### Spoke repo
- Require PRs to `main`; require the team's reviewers on their slice and the
  **platform team on `/.github/workflows/`** so the pin to the hub SHA can't be
  quietly changed (see the template CODEOWNERS).
- Require the advisory `pr-validation` check for fast feedback (optional but
  recommended).
- The real enforcement is the hub publish gate, which runs post-merge inside
  `team-publish.yml`; branch protection here mainly keeps `main` clean and stops
  the workflow pin from being edited without platform review.

### Azure DevOps variant
Enforcement moves to a required `extends` template at publish time plus denying
admin bypass (admins bypass by default on ADO). The pinned template is
lower-stakes here because the publish gate is authoritative — see
[docs/azure_devops_parity.md](azure_devops_parity.md).
