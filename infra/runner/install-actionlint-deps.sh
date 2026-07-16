#!/usr/bin/env bash
# Installs the runtime dependencies that raven-actions/actionlint@v2
# expects on PATH. Idempotent.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

sudo apt-get install -y --no-install-recommends pipx

# pipx installs into the invoking user's ~/.local/bin. We install as the
# 'runner' user (which executes workflow jobs), then symlink the resulting
# binary into /usr/local/bin so PATH lookups succeed for every shell.
sudo -iu runner bash -c 'pipx install --force pyflakes'
sudo ln -sf /home/runner/.local/bin/pyflakes /usr/local/bin/pyflakes

# Restart the runner agent so any cached PATH is refreshed.
cd /home/runner/actions-runner
sudo ./svc.sh stop || true
sleep 2
sudo ./svc.sh start

which pyflakes
pyflakes --version
echo "ACTIONLINT_DEPS_INSTALLED"
