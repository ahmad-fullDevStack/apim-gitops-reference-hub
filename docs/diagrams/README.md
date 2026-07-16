# Repository diagrams

Mermaid diagrams that, together, give a complete visual representation of everything in this repo. Render in VS Code with the **Markdown Preview Mermaid Support** extension, on GitHub directly (`.mmd` is rendered in PR previews when embedded in Markdown), or in any Mermaid-aware viewer (`https://mermaid.live`).

| # | File | What it shows | When to look at it |
|---|---|---|---|
| 1 | [01_repo_topology.mmd](01_repo_topology.mmd) | Every top-level folder of the repo and what it contains. Highlights the per-tier workspaces and the shared/canonical layout under `pensions-core`. | Onboarding. Answers "where does X live?". |
| 2 | [02_gitops_pipeline.mmd](02_gitops_pipeline.mmd) | End-to-end flow: author → PR + CI → CODEOWNERS review → merge → Dev/Test/Prod publisher → APIM → drift reconciliation. | Understanding the full delivery loop. |
| 3 | [03_ci_checks.mmd](03_ci_checks.mmd) | The 9 pre-merge CI checks + 1 report-only inventory scan, how they share `_common.py` and are orchestrated by `run_all.py`. | Adding / modifying a CI check. |
| 4 | [04_terraform_modules.mmd](04_terraform_modules.mmd) | Terraform module dependency graph: what each module under `infra/modules/` provisions and how `envs/poc/` wires them. | Adding a Terraform module or changing the env composition. |
| 5 | [05_workspace_topology.mmd](05_workspace_topology.mmd) | The 8 domain workspaces (Gold / Silver / Bronze), the gateway capacity model, and the canonical-API + version-set layout inside `pensions-core/shared/`. | Discussing the workspace-consolidation strategy. |
| 6 | [06_identity_rbac.mmd](06_identity_rbac.mmd) | Service principals, OIDC federation, Entra security groups, the Service-Reader floor, and the documented runtime KV gap. | Auditing RBAC or wiring a new team. |
| 7 | [07_defence_in_depth.mmd](07_defence_in_depth.mmd) | For each threat / unsafe action, every layer that stops it (pre-commit → PR → CODEOWNERS → env gate → Azure RBAC → Azure Policy → monitoring). | Security review or compliance walkthrough. |

## Conventions used in the diagrams

- **Gold** workspaces are highlighted yellow, **Silver** grey, **Bronze** orange-brown.
- **Pipeline / SP** boxes are blue; **Azure resources** dark blue; **gates and approvals** yellow; **report-only / observability** green; **documented gaps** outlined red.
- Dotted edges mean "consumed by / observed by" (loose coupling). Solid edges mean an enforced control or a direct dependency.
- Names match the actual code (e.g. `path_scope` is `path_scope.py`, `team_kv` is `infra/modules/team_kv/`).

## Updating the diagrams

If a folder is renamed, a script is added, or a Terraform module changes shape, update the corresponding `.mmd`. There is no automated rendering step — the diagrams are reviewed visually in PR previews. Keep node labels short; APIM resource names belong in real code, not diagrams.
