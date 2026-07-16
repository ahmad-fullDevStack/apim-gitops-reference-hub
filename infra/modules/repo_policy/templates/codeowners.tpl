# CODEOWNERS for ${org}
# Rendered by the repo_policy Terraform module. Do not hand-edit.
#
# Reference: docs/reference_architecture.md (path-scoped required reviewers)
#
# Routing rule (workspace-consolidation strategy):
#   - Workspace shell (workspace.json + policy.xml + shared/) requires the
#     domain leads team to approve. Domain leads enforce the canonical
#     backend + version-set decisions for that domain.
#   - Team API slices live in per-team spoke repos (hub-and-spoke model), not in
#     the hub. Only the teams/ signpost README remains here, owned by the leads.
#   - All cross-cutting paths (.github/, infra/, config/, scripts/, tests/)
#     are platform-owned.

# Platform team owns everything by default
*                                                                       @${org}/${platform_team}

# ----------------------------------------------------------------------------
# Apim-config governance
# ----------------------------------------------------------------------------
/apim-config/service/                                                   @${org}/${platform_team}

# Pensions Core (gold, active)
/apim-config/workspaces/pensions-core/workspace.json                    @${org}/${pensions_core_leads} @${org}/${platform_team}
/apim-config/workspaces/pensions-core/policy.xml                        @${org}/${pensions_core_leads} @${org}/${platform_team}
/apim-config/workspaces/pensions-core/shared/                           @${org}/${pensions_core_leads}
# Team API slices live in their own spoke repos (apim-team-a, apim-team-b).
# Only the teams/ signpost README remains in the hub, owned by the domain leads.
/apim-config/workspaces/pensions-core/teams/                            @${org}/${pensions_core_leads} @${org}/${platform_team}

# Investments (gold, inactive at POC time - still gated by leads)
/apim-config/workspaces/investments/                                    @${org}/${platform_team}

# Customer Identity (gold, inactive)
/apim-config/workspaces/customer-identity/                              @${org}/${platform_team}

# Integrations (silver, inactive)
/apim-config/workspaces/integrations/                                   @${org}/${platform_team}

# Data & Reporting (silver, inactive)
/apim-config/workspaces/data-reporting/                                 @${org}/${platform_team}

# Shared Services (silver, inactive)
/apim-config/workspaces/shared-services/                                @${org}/${platform_team}

# External Partners (silver, inactive) - extra-tight gate
/apim-config/workspaces/external-partners/                              @${org}/${platform_team}

# Sandbox (bronze, inactive) - even more relaxed once activated; for now
# platform-owned so nobody mistakes it for a production tier.
/apim-config/workspaces/sandbox/                                        @${org}/${platform_team}

# ----------------------------------------------------------------------------
# CI scripts, workflows, infra, config: platform-only
# ----------------------------------------------------------------------------
/.github/                                                               @${org}/${platform_team}
/infra/                                                                 @${org}/${platform_team}
/config/                                                                @${org}/${platform_team}
/scripts/                                                               @${org}/${platform_team}

# Tests
/tests/                                                                 @${org}/${platform_team}
