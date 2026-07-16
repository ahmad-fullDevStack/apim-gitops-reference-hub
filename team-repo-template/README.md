# Team spoke repo template

This folder is a **copy-me starting point** for a single team's own repository in
the hub-and-spoke (multi-repo) model. Each team gets its own repo containing
**only its slice** of the APIM config; the hub
([apim-gitops-reference](../)) stays the platform-owned control plane that owns
the guardrail checks, `config/ci.json`, the shared/canonical APIs, and drift
detection.

This template is the **wiring scaffold** — the two caller workflows and the
`CODEOWNERS` that bind a spoke to the hub — plus a **placeholder sample slice**
that shows the strict folder layout every API/backend/named-value must follow.
The sample uses obviously-fake names (`example-domain` / `example-team` /
`exampleteam-*`) so it can't be mistaken for a real team's live slice: delete it
and copy your team's real slice from the hub (see the checklist below).

## What's in here

```
team-repo-template/
├── apim-config/workspaces/example-domain/teams/example-team/   # PLACEHOLDER slice — shows the required layout
│   ├── apis/exampleteam-orders-v1/
│   │   ├── apiInformation.json    # displayName, path, protocols, subscriptionRequired, type
│   │   ├── policy.xml             # API-level policy; must <base /> in every section
│   │   └── specification.yaml     # OpenAPI 3.0.x
│   ├── backends/exampleteam-orders.json          # host must be on the team's allowed_backend_hosts
│   └── named-values/exampleteam-orders-api-key.json   # Key Vault reference
└── .github/
    ├── CODEOWNERS                    # team owns its slice; platform owns the workflow wiring
    └── workflows/
        ├── pr-validation.yml         # ADVISORY caller -> hub reusable-checks.yml
        └── publisher.yml             # AUTHORITATIVE caller -> hub team-publish.yml (gate + scoped publish)
```

The workflows are wired for `team-a` / `pensions-core` as concrete placeholders;
rename them to your team and domain when you adopt (see the checklist).

### Why the slice path is mirrored (not flattened)

Keep your slice at the **exact same relative path** it has in the hub
(`apim-config/workspaces/<domain>/teams/<team>/...`). This means the hub's checks,
the `apiops_adapter.py`, and `config/ci.json`'s `team.folder` values all keep
working with **zero logic changes** — the spoke repo just holds a sparse copy of
the same tree. The strict layout is:

- `apis/<api-name>/` — one folder per API, each with `apiInformation.json`,
  `policy.xml`, and `specification.yaml`.
- `backends/<backend-name>.json` — one file per backend.
- `named-values/<name>.json` — one file per named value (Key Vault references).

## The security model (read this)

| Workflow | Role | Can the team weaken it? |
|---|---|---|
| `pr-validation.yml` -> `reusable-checks.yml` | **Advisory** fast PR feedback | Yes — and it doesn't matter |
| `publisher.yml` -> `team-publish.yml` | **Authoritative** gate + scoped publish | No — it's hub-owned and atomic |

The authoritative gate lives **inside** the hub's `team-publish.yml`, in the same
job as the publish, so a team cannot insert steps between "check" and "publish"
or skip the check. Two isolation layers back it up:

1. The gate runs the hub's checks against the **central `config/ci.json`** (checked
   out from the hub, not this repo) — a team cannot widen its own Key Vault or
   backend allowlists.
2. The publish is **scoped to this team** (`apiops_adapter.py --team team-a`) and
   uses a **workspace-scoped OIDC credential**, so the blast radius is limited to
   this team's slice of the shared workspace.

## Adopting it — replace these placeholders

1. Copy this `.github/` scaffold into your new spoke repo.
2. **Delete the placeholder sample slice**
   (`apim-config/workspaces/example-domain/`) and copy your team's **real slice**
   from the hub (`apim-config/workspaces/<domain>/teams/<team>/`) into the **same
   mirrored path** in the spoke. Use the sample only as a layout reference.
3. `your-org/apim-gitops-reference` → your hub repo's `owner/name` (in both workflows).
4. `@REPLACE_WITH_HUB_COMMIT_SHA` → a **full commit SHA** of the hub repo. Pin to a
   SHA, not a branch/tag, so the guardrails can't be swapped out.
5. `team-a` → your team folder name; `pensions-core` → your domain workspace.
6. `@team-a-reviewers` / `@platform-team` → your real GitHub teams in `CODEOWNERS`.
7. Configure repo **secrets** (`AZURE_PUBLISHER_CLIENT_ID`, `AZURE_TENANT_ID`,
   `AZURE_SUBSCRIPTION_ID`) and **vars** (`APIM_RG`, `APIM_NAME`) for your team's
   workspace-scoped publisher SP (provisioned by the hub's `infra/modules/identity`).

## Things you do NOT do here

- **You don't edit the checks or `config/ci.json`.** Those live in the hub. If you
  need a **new backend host or Key Vault**, open a PR against the hub's
  `config/ci.json` — that's a deliberate platform-approved gate, not daily work.
- **You don't own the shared/canonical APIs** (`shared/...`) or the workspace
  policy — those stay in the hub. Reference them; don't copy them.
