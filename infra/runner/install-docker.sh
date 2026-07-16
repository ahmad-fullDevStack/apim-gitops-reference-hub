#!/usr/bin/env bash
# Installs Docker CE so workflows using container-based actions
# (azure/cli@v2, bridgecrewio/checkov-action@v12, etc.) work on the
# self-hosted runner. Idempotent.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

if ! command -v docker >/dev/null 2>&1; then
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  . /etc/os-release
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  sudo apt-get update -y
  sudo apt-get install -y --no-install-recommends \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# Make the runner user a member of the docker group so it can exec containers
# without sudo (required by azure/cli@v2 and other container actions).
sudo usermod -aG docker runner

sudo systemctl enable --now docker

# Restart runner agent so it inherits the new group membership.
cd /home/runner/actions-runner
sudo ./svc.sh stop || true
sleep 2
sudo ./svc.sh start

docker --version
sudo -iu runner docker version --format '{{.Client.Version}}'
echo "DOCKER_INSTALLED"
