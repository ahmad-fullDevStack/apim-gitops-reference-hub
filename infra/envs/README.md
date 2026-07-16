# `envs/` — environment composition layer

Following an environment-separation strategy, the reference platform runs
under **Dev / Test / Prod** environments. To keep the IaC manageable and to
avoid drift between near-identical roots, **this repo uses one parameterised
Terraform root** (`envs/poc/`) plus one **tfvars file per environment**:

```
infra/envs/poc/
    main.tf                  # the composition (shared across envs)
    variables.tf             # environment-aware inputs
    outputs.tf
    terraform.tfvars.example # POC defaults
    dev.tfvars.example       # Dev environment
    test.tfvars.example      # Test environment
    prod.tfvars.example      # Prod environment
```

## Driving each environment

```pwsh
# Dev
terraform init -backend-config="key=apim-gitops-reference-hub.dev.tfstate"
terraform plan  -var-file=dev.tfvars -out=tfplan
terraform apply tfplan

# Test
terraform init -reconfigure -backend-config="key=apim-gitops-reference-hub.test.tfstate"
terraform plan  -var-file=test.tfvars -out=tfplan
terraform apply tfplan

# Prod
terraform init -reconfigure -backend-config="key=apim-gitops-reference-hub.prod.tfstate"
terraform plan  -var-file=prod.tfvars -out=tfplan
terraform apply tfplan
```

## Boundary enforcement

- Each env uses its own **Azure subscription** (`subscription_id` per tfvars)
  and its own **state backend container key** (above).
- The publisher SP has a separate federated credential per env subject
  (`...:environment:apim-dev`, `apim-test`, `apim-prod`). The GitHub
  Environments enforce reviewer approvals at the Prod gate.
- `manage_github_repo` is only `true` in the env that owns the GitHub
  policy (Prod by convention). The other envs must set it to `false` to
  avoid contention.
