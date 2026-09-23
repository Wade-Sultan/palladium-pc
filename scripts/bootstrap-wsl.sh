#!/usr/bin/env bash
# One-time tool install for the local minikube loop on a WSL2 Ubuntu machine.
# Idempotent: every step checks what is already there and skips it. Re-run
# after bumping a pin below.
#
# What it installs, and why each one is needed:
#   minikube           the cluster            (scripts/minikube-cilium-up.sh)
#   cilium CLI         CNI + Gateway API      (scripts/minikube-cilium-up.sh)
#   tilt               the dev loop           (Tiltfile)
#   helm               KEDA install           (local worker autoscaling)
#   postgresql-client  psql/pg_restore/pg_dump (scripts/seed-local-db.sh,
#                                              scripts/dump-prod-db.sh)
#   socat              the gateway relay      (scripts/gateway-forward.sh has a
#                                              python fallback, socat is faster)
#   jq, make, unzip    used by test scripts
#   uv + Python 3.12   runs pytest on the host (backend/pyproject.toml caps
#                                              Python below 3.14; Ubuntu 26.04
#                                              ships 3.14)
#
# NOT installed here: docker (Docker Desktop's WSL integration provides it),
# kubectl (already present), gcloud (only needed for prod, lives on Windows),
# KEDA itself (a cluster component, not a tool. See minikube-cilium-up.sh).
#
# Needs sudo for apt and for /usr/local/bin. Run it as yourself, not as root,
# so uv and its Python land in your home directory.
set -euo pipefail

MINIKUBE_VERSION="${MINIKUBE_VERSION:-v1.39.0}"
TILT_VERSION="${TILT_VERSION:-0.37.7}"
CILIUM_CLI_VERSION="${CILIUM_CLI_VERSION:-v0.20.0}"
# Helm 4, matching the get_helm.sh installer already tracked at the repo root.
HELM_VERSION="${HELM_VERSION:-v4.2.4}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
# Ubuntu 26.04's own package. 18 dumps a 17 server and restores 17-format
# dumps fine; dump-prod-db.sh only refuses clients OLDER than the server.
PG_CLIENT_PKG="${PG_CLIENT_PKG:-postgresql-client-18}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [ "$(id -u)" -eq 0 ]; then
  echo "Run this as your own user, not root. Uv must install into your home." >&2
  exit 1
fi
if [ "$(uname -m)" != "x86_64" ]; then
  echo "Pinned downloads below are amd64 only; this is $(uname -m)." >&2
  exit 1
fi

step() { printf '\n==> %s\n' "$*"; }

# --- 1. apt packages ---------------------------------------------------------
step "apt: socat jq make unzip $PG_CLIENT_PKG"
sudo apt-get update -qq
sudo apt-get install -y -qq socat jq make unzip "$PG_CLIENT_PKG"

# --- 2. minikube -------------------------------------------------------------
step "minikube $MINIKUBE_VERSION"
if command -v minikube >/dev/null && minikube version --short 2>/dev/null | grep -qx "$MINIKUBE_VERSION"; then
  echo "already installed"
else
  curl -fsSL -o "$WORK/minikube" \
    "https://github.com/kubernetes/minikube/releases/download/${MINIKUBE_VERSION}/minikube-linux-amd64"
  sudo install -m 0755 "$WORK/minikube" /usr/local/bin/minikube
fi

# --- 3. tilt -----------------------------------------------------------------
step "tilt v$TILT_VERSION"
if command -v tilt >/dev/null && tilt version 2>/dev/null | grep -q "^v${TILT_VERSION},"; then
  echo "already installed"
else
  curl -fsSL -o "$WORK/tilt.tgz" \
    "https://github.com/tilt-dev/tilt/releases/download/v${TILT_VERSION}/tilt.${TILT_VERSION}.linux.x86_64.tar.gz"
  tar -xzf "$WORK/tilt.tgz" -C "$WORK" tilt
  sudo install -m 0755 "$WORK/tilt" /usr/local/bin/tilt
fi

# --- 4. cilium CLI -----------------------------------------------------------
step "cilium CLI $CILIUM_CLI_VERSION"
if command -v cilium >/dev/null && cilium version --client 2>/dev/null | grep -q "$CILIUM_CLI_VERSION"; then
  echo "already installed"
else
  base="https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VERSION}"
  curl -fsSL -o "$WORK/cilium-linux-amd64.tar.gz"           "$base/cilium-linux-amd64.tar.gz"
  curl -fsSL -o "$WORK/cilium-linux-amd64.tar.gz.sha256sum" "$base/cilium-linux-amd64.tar.gz.sha256sum"
  (cd "$WORK" && sha256sum --check --quiet cilium-linux-amd64.tar.gz.sha256sum)
  sudo tar -xzf "$WORK/cilium-linux-amd64.tar.gz" -C /usr/local/bin cilium
fi

# --- 5. helm -----------------------------------------------------------------
step "helm $HELM_VERSION"
if command -v helm >/dev/null && helm version --template '{{.Version}}' 2>/dev/null | grep -qx "$HELM_VERSION"; then
  echo "already installed"
else
  curl -fsSL -o "$WORK/helm.tgz"        "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz"
  curl -fsSL -o "$WORK/helm.tgz.sha256" "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz.sha256sum"
  # The checksum file names the tarball by its original filename.
  (cd "$WORK" && mv helm.tgz "helm-${HELM_VERSION}-linux-amd64.tar.gz" \
     && sha256sum --check --quiet helm.tgz.sha256)
  tar -xzf "$WORK/helm-${HELM_VERSION}-linux-amd64.tar.gz" -C "$WORK" linux-amd64/helm
  sudo install -m 0755 "$WORK/linux-amd64/helm" /usr/local/bin/helm
fi

# --- 6. uv + Python + backend venv ------------------------------------------
step "uv, Python $PYTHON_VERSION, backend venv"
if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv python install "$PYTHON_VERSION"
# The tracked .venv may be a husk from another machine (a directory with no
# interpreter in it). uv sync recreates it against the pinned interpreter.
(cd "$REPO_ROOT/backend" && uv sync --python "$PYTHON_VERSION")

# --- 7. docker group ---------------------------------------------------------
step "docker"
if ! getent group docker | grep -qw "$USER"; then
  sudo usermod -aG docker "$USER"
  echo "added $USER to the docker group"
fi
if ! id -nG | grep -qw docker; then
  echo "This shell does not have the docker group yet. From PowerShell run:"
  echo "    wsl --shutdown"
  echo "then reopen the terminal. Docker Desktop must have WSL integration on for this distro."
fi

# --- summary -----------------------------------------------------------------
step "installed"
printf '%-10s %s\n' minikube "$(minikube version --short)"
printf '%-10s %s\n' tilt     "$(tilt version)"
printf '%-10s %s\n' cilium   "$(cilium version --client | head -1)"
printf '%-10s %s\n' helm     "$(helm version --template '{{.Version}}')"
printf '%-10s %s\n' kubectl  "$(kubectl version --client 2>/dev/null | head -1)"
printf '%-10s %s\n' psql     "$(psql --version)"
printf '%-10s %s\n' uv       "$(uv --version)"
printf '%-10s %s\n' python   "$("$REPO_ROOT/backend/.venv/bin/python" --version)"
echo
echo "Next: ./scripts/minikube-cilium-up.sh   then   tilt up -f scripts/Tiltfile"
