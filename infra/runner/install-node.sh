#!/usr/bin/env bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

# Node.js 20 LTS (provides npm; required by the raven-actions/actionlint composite action)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y --no-install-recommends nodejs
node --version
npm --version

# shellcheck and pyflakes are optional actionlint extras
sudo apt-get install -y --no-install-recommends shellcheck python3-pyflakes
shellcheck --version | head -n 2 || true

echo "NODE_INSTALL_COMPLETE"
