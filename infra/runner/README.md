# Self-hosted GitHub Actions runner (POC)

This subdirectory bootstraps a **single** Azure VM that runs the GitHub Actions
runner agent for `<github-owner>/apim-gitops-reference-hub`. It exists
because GitHub-hosted runners are disabled at the org/enterprise level for this
repo (see the failed runs on `main` for the explicit annotation).

> **POC only.** Not production-grade. There is no HA, no autoscaling, no
> ephemeral isolation. The runner is shared across all jobs in the repo. Do
> not point this at a repo that accepts PRs from untrusted forks — a malicious
> PR could exfiltrate any secret the runner has access to.

## What gets created

| Resource | Name | SKU / size | Approx cost (West Europe, 24/7) |
|---|---|---|---|
| Resource group | `rg-apim-gitops-runner-poc` | — | — |
| VNet + subnet | `vnet-gha-runner` / `snet-runner` | /24 | free |
| NSG | `nsg-gha-runner` | deny-all-inbound | free |
| Public IP | `pip-gha-runner` | Standard, static | ~$3/mo |
| NIC | `nic-gha-runner` | — | free |
| VM | `vm-gha-runner-01` | **Standard_D2s_v5** (2 vCPU, 8 GB) | ~$70/mo |
| OS disk | managed, Standard SSD 30 GB | — | ~$3/mo |
| Auto-shutdown | 19:00 UTC daily | — | free |

**Estimated total: ~$76/month** if left running 24/7. With the configured
auto-shutdown at 19:00 UTC and assuming a manual start at 09:00 UTC each
workday, the runtime drops to ~50h/wk → ~$22/mo.

> The original target was `Standard_B2s` (~$30/mo) but it returned
> `SkuNotAvailable` for this subscription in `westeurope`. Override with
> `-VmSize` when redeploying if you have capacity for B-series elsewhere.

All resources are tagged `purpose=github-actions-runner`,
`owner=<owner>`, `environment=poc`,
`auto-delete-after=2026-09-08`.

## Security posture

- **Inbound:** NSG denies everything. No SSH from the internet.
- **Outbound:** default Azure outbound (sufficient for `github.com`, package
  mirrors, Hashicorp releases). Will need a NAT Gateway once default
  outbound is deprecated.
- **Admin access:** via `az vm run-command invoke` only (Azure RBAC).
  An SSH key is generated but unreachable.
- **Runner registration token:** minted at deploy time, valid 1 hour, baked
  into cloud-init custom-data. Custom-data is stored encrypted at rest in
  Azure but is recoverable by anyone with `Microsoft.Compute/virtualMachines/read`
  on the VM. Treat it as a short-lived secret; it expires before it could be
  abused.

## Optional: install Node.js + shellcheck

The base install does not include Node.js. Some workflow actions (e.g.
`raven-actions/actionlint@v2`) shell out to `npm` and will fail with
`exit code 127` without it. Run [install-node.sh](install-node.sh) once
on the VM via run-command:

```powershell
az vm run-command invoke `
  -g rg-apim-gitops-runner-poc -n vm-gha-runner-01 `
  --command-id RunShellScript `
  --scripts "@infra/runner/install-node.sh" -o table
```

This installs Node.js 20 LTS (with `npm`), `shellcheck`, and `python3-pyflakes`.

### actionlint deps (pyflakes binary)

`raven-actions/actionlint@v2` calls a `pyflakes` **binary** (not the python
module). Ubuntu 22.04's `python3-pyflakes` apt package ships only the module,
so install the standalone CLI via pipx with
[install-actionlint-deps.sh](install-actionlint-deps.sh):

```powershell
az vm run-command invoke `
  -g rg-apim-gitops-runner-poc -n vm-gha-runner-01 `
  --command-id RunShellScript `
  --scripts "@infra/runner/install-actionlint-deps.sh" -o table
```

The script installs `pipx`, runs `pipx install pyflakes` as the `runner`
user, symlinks the result into `/usr/local/bin/pyflakes`, and restarts the
runner agent.

### Docker (for container-based actions)

`azure/cli@v2`, `bridgecrewio/checkov-action@v12`, and other Docker-based
GitHub Actions need a Docker daemon plus the `runner` user in the `docker`
group. Run [install-docker.sh](install-docker.sh) once:

```powershell
az vm run-command invoke `
  -g rg-apim-gitops-runner-poc -n vm-gha-runner-01 `
  --command-id RunShellScript `
  --scripts "@infra/runner/install-docker.sh" -o table
```

It adds the official Docker apt repo, installs `docker-ce`, enables the
`docker` service, adds `runner` to the `docker` group, and bounces the
runner agent so the new group membership takes effect.

## Deploy

```powershell
cd infra/runner
./deploy.ps1
```

This:

1. Ensures the resource group, NSG, and VM exist (creates if absent).
2. Mints a fresh runner registration token via `gh api` (1h TTL).
3. Builds an inline bash install script with the token baked in and pushes
   it to the VM via `az vm run-command invoke`. The script:
   - installs apt prerequisites (`curl`, `jq`, `git`, `unzip`, `python3-pip`, `build-essential`)
   - creates the `runner` user
   - downloads + unpacks `actions/runner v2.319.1`
   - registers with GitHub and installs the systemd service
   - installs Terraform 1.9.5 (matches the `terraform-validate` workflow)
4. Applies a 19:00 UTC daily auto-shutdown.
5. Polls `gh api .../actions/runners` until the runner shows as `online`.

> The script intentionally avoids `az vm create --custom-data` because the
> Windows az CLI has a long-standing base64 / quoting bug with that flag,
> and avoids `--generate-ssh-keys` because of a related bug in the SSH key
> validator. It generates and uses an explicit key at
> `~/.ssh/id_rsa_apim_runner.pub`.

Check install progress on the VM:

```bash
az vm run-command invoke \
  --resource-group rg-apim-gitops-runner-poc \
  --name vm-gha-runner-01 \
  --command-id RunShellScript \
  --scripts "sudo journalctl -u actions.runner.* --no-pager -n 50; sudo /home/runner/actions-runner/svc.sh status"
```

## Teardown

```powershell
az group delete --name rg-apim-gitops-runner-poc --yes --no-wait
```

Then deregister the orphaned runner record:

```bash
gh api repos/<github-owner>/apim-gitops-reference-hub/actions/runners \
  --jq '.runners[] | select(.name == "gha-runner-01") | .id' \
  | xargs -I {} gh api -X DELETE \
    repos/<github-owner>/apim-gitops-reference-hub/actions/runners/{}
```

## Workflow change required

All workflows in `.github/workflows/` are switched from
`runs-on: ubuntu-latest` to `runs-on: [self-hosted, linux, x64]`. If you ever
re-enable GitHub-hosted runners, revert that change.
