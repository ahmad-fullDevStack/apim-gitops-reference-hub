#!/usr/bin/env bash
# Health-check for the self-hosted runner VM. Designed to survive
# az vm run-command's line handling: no nested bash -lc strings, no
# inner loops with shell variables.
set -uo pipefail

echo "=== runner identity ==="
id runner

echo
echo "=== systemd unit ==="
systemctl is-active 'actions.runner.<github-owner>-apim-gitops-reference.gha-runner-01.service' || true
systemctl is-enabled 'actions.runner.<github-owner>-apim-gitops-reference.gha-runner-01.service' || true

echo
echo "=== toolchain (via runner login shell) ==="
sudo -iu runner -- node --version    2>&1 | sed 's/^/  node       /' || true
sudo -iu runner -- npm  --version    2>&1 | sed 's/^/  npm        /' || true
sudo -iu runner -- shellcheck --version 2>&1 | head -n2 | sed 's/^/  shellcheck /' || true
sudo -iu runner -- pyflakes --version 2>&1 | sed 's/^/  pyflakes   /' || true
sudo -iu runner -- docker --version  2>&1 | sed 's/^/  docker     /' || true
sudo -iu runner -- terraform version 2>&1 | head -n1 | sed 's/^/  terraform  /' || true
sudo -iu runner -- git --version     2>&1 | sed 's/^/  git        /' || true
sudo -iu runner -- jq  --version     2>&1 | sed 's/^/  jq         /' || true
sudo -iu runner -- python3 --version 2>&1 | sed 's/^/  python3    /' || true
sudo -iu runner -- pipx --version    2>&1 | sed 's/^/  pipx       /' || true

echo
echo "=== docker daemon reachable as runner ==="
sudo -iu runner -- docker ps
sudo -iu runner -- docker run --rm hello-world 2>&1 | tail -n 6

echo
echo "=== disk ==="
df -h / | tail -n 1

echo
echo "=== last 10 lines of runner journal ==="
journalctl -u 'actions.runner.*' --no-pager -n 10 2>/dev/null || true

echo
echo "CHECK_OK"
