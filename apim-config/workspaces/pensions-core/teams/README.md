# `teams/` — team API slices live in per-team spoke repos

This folder is intentionally (almost) empty in the hub.

Under the **hub-and-spoke model** (see
[docs/multi_repo_hub_and_spoke.md](../../../../docs/multi_repo_hub_and_spoke.md)),
each team owns its API slice in its **own repository**, not here in the hub. The
hub keeps only the **control plane** (guardrail scripts, `config/ci.json`
allowlists, workspace policy, the shared/canonical APIs under
[`../shared/`](../shared/), reusable publish workflows, and drift detection).

## Where the team code lives

| Team | Prefix | Spoke repo | Mirrored slice path (inside the spoke) |
|---|---|---|---|
| team-a | `teama` | `apim-team-a` | `apim-config/workspaces/pensions-core/teams/team-a/` |
| team-b | `teamb` | `apim-team-b` | `apim-config/workspaces/pensions-core/teams/team-b/` |

Each spoke mirrors this exact path so the hub-owned guardrail scripts and the
`config/ci.json` team registry apply unchanged when the spoke's PR/publish runs
against the hub's central config.

## What still lives in the hub for these teams

- **`config/ci.json` → `teams[]`** — the authoritative registry (prefix, allowed
  Key Vaults, allowed backend hosts). The hub publish gate enforces these against
  every spoke publish; this is the security boundary and must stay in the hub.
- **`../shared/`** — the domain's canonical/shared APIs (prefix `contoso`), owned by
  the pensions-core leads, not by an individual team.
- **Per-team infrastructure** — `infra/` provisions each team's Key Vault, Entra
  groups, workspace-scoped RBAC, and the federated OIDC credential the spoke's
  publisher uses.

## Adding a new team

Follow the cutover runbook in
[docs/multi_repo_hub_and_spoke.md](../../../../docs/multi_repo_hub_and_spoke.md)
and register the team in [`config/ci.json`](../../../../config/ci.json).
