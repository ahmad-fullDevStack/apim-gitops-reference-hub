<#
.SYNOPSIS
  Provisions an Azure VM that runs the GitHub Actions self-hosted runner
  for <github-owner>/apim-gitops-reference-hub.

.DESCRIPTION
  See README.md in this directory for full design notes and cost estimate.
  Idempotent: rerunning will skip resources that already exist and re-push
  the runner install script via `az vm run-command invoke`.

  This script intentionally does NOT use `az vm create --custom-data` because
  the Windows az CLI has a long-standing base64 / quoting bug with that flag.
  We provision a bare VM and push the install via run-command instead.
#>

[CmdletBinding()]
param(
    [string]$ResourceGroup       = 'rg-apim-gitops-runner-poc',
    [string]$Location            = 'westeurope',
    [string]$VmSize              = 'Standard_D2s_v5',
    [string]$VmName              = 'vm-gha-runner-01',
    [string]$RunnerName          = 'gha-runner-01',
    [string]$RunnerLabels        = 'self-hosted,linux,x64,azure-poc',
    [string]$RunnerVersion       = '2.319.1',
    [string]$Repo                = '<github-owner>/apim-gitops-reference-hub',
    [string]$AutoShutdownTimeUtc = '1900',
    [string]$SshPubKeyPath       = (Join-Path $env:USERPROFILE '.ssh\id_rsa_apim_runner.pub')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==> Verifying gh CLI auth..." -ForegroundColor Cyan
gh auth status --hostname github.com 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'gh CLI not authenticated. Run: gh auth login' }

Write-Host "==> Verifying az CLI subscription..." -ForegroundColor Cyan
$ctx = az account show --output json | ConvertFrom-Json
Write-Host "    Subscription: $($ctx.name) ($($ctx.id))"
Write-Host "    Tenant      : $($ctx.tenantId)"

Write-Host "==> Ensuring resource group $ResourceGroup..." -ForegroundColor Cyan
az group create `
    --name $ResourceGroup `
    --location $Location `
    --tags purpose=github-actions-runner owner=<owner> environment=poc auto-delete-after=2026-09-08 repo=apim-gitops-reference-hub `
    --only-show-errors -o none

$repoUrl = "https://github.com/$Repo"

Write-Host "==> Ensuring NSG nsg-gha-runner (deny-all-inbound)..." -ForegroundColor Cyan
az network nsg create -g $ResourceGroup -n nsg-gha-runner -l $Location --only-show-errors -o none
az network nsg rule create -g $ResourceGroup --nsg-name nsg-gha-runner `
    -n deny-all-inbound --priority 4096 `
    --direction Inbound --access Deny --protocol '*' `
    --source-address-prefixes '*' --source-port-ranges '*' `
    --destination-address-prefixes '*' --destination-port-ranges '*' `
    --only-show-errors -o none 2>$null

$existing = az vm show -g $ResourceGroup -n $VmName --query id -o tsv 2>$null
if ($existing) {
    Write-Host "==> VM $VmName already exists. Skipping creation." -ForegroundColor Yellow
}
else {
    Write-Host "==> Creating VM $VmName ($VmSize) in $Location..." -ForegroundColor Cyan
    if (-not (Test-Path $SshPubKeyPath)) {
        throw "SSH public key not found at $SshPubKeyPath. Generate it with: ssh-keygen -t rsa -b 4096 -f `"$($SshPubKeyPath -replace '\.pub$','')`" -N '`"`"' -C 'apim-gitops-runner-poc'"
    }
    $sshPubKey = (Get-Content $SshPubKeyPath -Raw).Trim()
    az vm create `
        --resource-group $ResourceGroup `
        --name $VmName `
        --location $Location `
        --size $VmSize `
        --image Ubuntu2204 `
        --admin-username azureuser `
        --ssh-key-values $sshPubKey `
        --public-ip-sku Standard `
        --public-ip-address-allocation static `
        --nsg nsg-gha-runner `
        --os-disk-size-gb 30 `
        --storage-sku StandardSSD_LRS `
        --tags purpose=github-actions-runner owner=<owner> environment=poc auto-delete-after=2026-09-08 repo=apim-gitops-reference-hub `
        --only-show-errors -o table
    if ($LASTEXITCODE -ne 0) { throw 'az vm create failed.' }
}

Write-Host "==> Minting runner registration token..." -ForegroundColor Cyan
$tokenJson = gh api -X POST "repos/$Repo/actions/runners/registration-token" | ConvertFrom-Json
$token = $tokenJson.token
if (-not $token) { throw 'Failed to mint runner token.' }
Write-Host "    Token expires at: $($tokenJson.expires_at)"

$installScript = @"
#!/usr/bin/env bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

for i in {1..30}; do
  if ! sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; then break; fi
  sleep 5
done

sudo apt-get update -y
sudo apt-get install -y --no-install-recommends curl jq git unzip ca-certificates python3-pip python3-venv build-essential

if ! id runner >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash runner
  sudo usermod -aG sudo runner
  echo 'runner ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/runner >/dev/null
fi

sudo -u runner mkdir -p /home/runner/actions-runner
cd /home/runner/actions-runner
if [ ! -f ./config.sh ]; then
  sudo -u runner curl -fsSL -o actions-runner.tar.gz "https://github.com/actions/runner/releases/download/v$RunnerVersion/actions-runner-linux-x64-$RunnerVersion.tar.gz"
  sudo -u runner tar xzf actions-runner.tar.gz
  sudo -u runner rm actions-runner.tar.gz
fi

sudo ./bin/installdependencies.sh || true

sudo ./svc.sh stop 2>/dev/null || true
sudo ./svc.sh uninstall 2>/dev/null || true
sudo -u runner ./config.sh remove --token '$token' 2>/dev/null || true
sudo -u runner ./config.sh --unattended --url '$repoUrl' --token '$token' --name '$RunnerName' --labels '$RunnerLabels' --work _work --replace
sudo ./svc.sh install runner
sudo ./svc.sh start
sleep 3
sudo ./svc.sh status

if ! command -v terraform >/dev/null 2>&1; then
  curl -fsSL -o /tmp/tf.zip https://releases.hashicorp.com/terraform/1.9.5/terraform_1.9.5_linux_amd64.zip
  sudo unzip -o /tmp/tf.zip -d /usr/local/bin/
  rm /tmp/tf.zip
  sudo chmod +x /usr/local/bin/terraform
fi
terraform version

echo RUNNER_INSTALL_COMPLETE
"@

$scriptFile = Join-Path $here 'install-runner.generated.sh'
[IO.File]::WriteAllText($scriptFile, ($installScript -replace "`r`n", "`n"), [Text.UTF8Encoding]::new($false))

Write-Host "==> Pushing install script via az vm run-command invoke (takes ~3-5 min)..." -ForegroundColor Cyan
$logFile = Join-Path $here 'run-command.log'
az vm run-command invoke `
    -g $ResourceGroup -n $VmName `
    --command-id RunShellScript `
    --scripts "@$scriptFile" `
    --only-show-errors `
    -o json | Out-File -FilePath $logFile -Encoding UTF8
if ($LASTEXITCODE -ne 0) {
    Write-Warning "run-command invoke failed; see $logFile"
    exit 1
}
Write-Host "    Output saved to $logFile"

if ($AutoShutdownTimeUtc) {
    Write-Host "==> Configuring auto-shutdown at $AutoShutdownTimeUtc UTC..." -ForegroundColor Cyan
    $vmId = az vm show -g $ResourceGroup -n $VmName --query id -o tsv
    $shutdownObj = [ordered]@{
        status               = 'Enabled'
        taskType             = 'ComputeVmShutdownTask'
        dailyRecurrence      = @{ time = $AutoShutdownTimeUtc }
        timeZoneId           = 'UTC'
        targetResourceId     = $vmId
        notificationSettings = @{ status = 'Disabled'; timeInMinutes = 30 }
    }
    $propsFile = Join-Path $here 'shutdown-properties.generated.json'
    ($shutdownObj | ConvertTo-Json -Depth 5) | Out-File -FilePath $propsFile -Encoding UTF8
    az resource create `
        --resource-group $ResourceGroup `
        --resource-type 'Microsoft.DevTestLab/schedules' `
        --name "shutdown-computevm-$VmName" `
        --location $Location `
        --properties "@$propsFile" `
        --only-show-errors -o none
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Auto-shutdown configuration failed.' }
}

Write-Host ""
Write-Host "==> Verifying runner registration with GitHub..." -ForegroundColor Cyan
$deadline = (Get-Date).AddMinutes(3)
$ok = $false
while ((Get-Date) -lt $deadline) {
    $runner = gh api "repos/$Repo/actions/runners" --jq ".runners[] | select(.name == `"$RunnerName`")" 2>$null
    if ($runner) {
        Write-Host "==> Runner registered:" -ForegroundColor Green
        $runner | Out-Host
        $ok = $true
        break
    }
    Start-Sleep -Seconds 15
    Write-Host "    ...still waiting" -ForegroundColor DarkGray
}

if (-not $ok) {
    Write-Warning "Runner did not appear within 3 min. Investigate with:"
    Write-Warning "/e  az vm run-command invoke -g $ResourceGroup -n $VmName --command-id RunShellScript --scripts 'sudo journalctl -u actions.runner.* --no-pager -n 80'"
    exit 1
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
