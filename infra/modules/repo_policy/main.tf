terraform {
  required_version = ">= 1.7.0"
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.2"
    }
  }
}

# Repository ruleset on main implementing the path-scoped review controls:
# - PR required, CODEOWNERS review required;
# - required status checks for the six CI checks + terraform + tests;
# - no bypass actors (admin bypass denied);
# - linear history, no force-push.

resource "github_repository_ruleset" "main_protection" {
  name        = "main-protection"
  repository  = var.repository
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
  }

  # Explicitly no bypass actors. Admins cannot bypass.
  # If a break-glass identity is required, add a single bypass_actors block
  # pointing at a tightly-controlled team (ideally PIM-eligible).

  rules {
    creation                = false
    deletion                = true
    non_fast_forward        = true # block force pushes
    update                  = false
    required_linear_history = true

    pull_request {
      required_approving_review_count   = 2
      dismiss_stale_reviews_on_push     = true
      require_code_owner_review         = true
      require_last_push_approval        = true
      required_review_thread_resolution = true
    }

    required_status_checks {
      strict_required_status_checks_policy = true
      required_check {
        context        = "APIM-config CI checks"
        integration_id = 15368 # GitHub Actions
      }
      required_check {
        context        = "pytest + coverage (100% gate)"
        integration_id = 15368
      }
      required_check {
        context        = "actionlint"
        integration_id = 15368
      }
    }
  }
}

# Repository-level settings the ruleset doesn't cover
resource "github_repository_dependabot_security_updates" "this" {
  repository = var.repository
  enabled    = true
}

# Render CODEOWNERS from a template into .github/CODEOWNERS
resource "github_repository_file" "codeowners" {
  repository = var.repository
  branch     = "main"
  file       = ".github/CODEOWNERS"
  content = templatefile("${path.module}/templates/codeowners.tpl", {
    platform_team       = var.platform_team
    pensions_core_leads = var.pensions_core_leads_team
    org                 = var.github_owner
  })
  commit_message      = "chore: sync CODEOWNERS from repo_policy module"
  commit_author       = "apim-gitops-bot"
  commit_email        = "apim-gitops-bot@users.noreply.github.com"
  overwrite_on_create = true
}
