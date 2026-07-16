variable "name_prefix" {
  type        = string
  description = "Short prefix included in SP display names (e.g. 'apim-poc')"
}

variable "apim_id" {
  type        = string
  description = "Resource ID of the APIM service the SPs will be granted on"
}

variable "github_owner" {
  type        = string
  description = "GitHub org/user that owns the repo (e.g. 'contoso')"
}

variable "github_repo" {
  type        = string
  description = "Repository name (e.g. 'apim-gitops-reference-hub')"
}

variable "spoke_repos" {
  type = map(object({
    repo        = string
    environment = optional(string, "apim-prod")
    subject     = optional(string)
  }))
  default     = {}
  description = <<-EOT
    Map of team key -> spoke repo that runs the hub reusable team-publish.yml.
    For each entry the module adds a federated identity credential on the
    publisher app so that spoke's workflow can log in via OIDC:

      - repo        : spoke repository name under github_owner (e.g. 'apim-team-a')
      - environment : deployment environment gating the publish (default apim-prod)
      - subject     : optional explicit OIDC subject. Leave unset to use the
                      default repo:<owner>/<repo>:environment:<env>. Set it when
                      federating on a stricter claim such as the reusable
                      workflow's job_workflow_ref.

    All spokes federate onto the single publisher SP; see main.tf for why per-team
    SPs buy no isolation while teams share a workspace.
  EOT
}

variable "team_groups" {
  type = map(object({
    workspace_id     = optional(string)
    assign_workspace = optional(bool, true)
  }))
  default     = {}
  description = <<-EOT
    Map of team key -> object. For each entry the module provisions:
      - an Entra security group <prefix>-<team>-contributor
      - an Entra security group <prefix>-<team>-reader
      - a service-scope "API Management Service Reader Role" floor for both
      - workspace-scope Contributor / Reader assignments when assign_workspace
        is true (the default)

    assign_workspace is a statically-known toggle so the workspace role
    assignments' for_each does not depend on workspace_id, which is only known
    after apply when wired from the workspace module. Set it false for teams
    that have no workspace yet.

    The PDF §"RBAC and Access Control" specifies this exact pattern
    (per-workspace groups + service-scope read floor).
  EOT
}
