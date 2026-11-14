#!/usr/bin/env bash
# Bring back a local cluster that was shut down cleanly with `minikube stop`,
# without rebuilding it. The everyday counterpart to minikube-cilium-up.sh.
#
# Why this exists: minikube-cilium-up.sh begins with `minikube delete`, so using
# it as the daily "turn the cluster on" step reinstalls Cilium, the Gateway API
# CRDs and KEDA every time, mints a new CA and client certs, moves the API
# server to a new host port, and throws away local Postgres. None of that is
# needed when the cluster was simply stopped: every addon, CRD, Helm release and
# the CoreDNS forward patch live in etcd and the node's volume, and the start
# flags (cni, kube-proxy skip, docker-opt dns) are stored in the profile.
#
# This script NEVER repairs anything. minikube-cilium-up.sh explains why: a
# `minikube start` against a profile that is not cleanly stopped can make
# minikube reconfigure the control plane, tear down /etc/kubernetes including
# the PKI, and leave a cluster that only a full rebuild recovers. So it starts
# the profile only from a clean Stopped state (or does nothing if it is already
# Running), then verifies the pieces the cold boot installs. Anything else, or
# any failed check, stops here and points at minikube-cilium-up.sh.
#
# Shut down with `minikube stop` (not by quitting Docker Desktop mid-run) so the
# next resume starts from a clean Stopped state.
#
# After a resume, the app pods were restarted by the kubelet in no particular
# order, not by Tilt in dependency order. The Pub/Sub emulator came back with
# no topics, and a builder that started before Valkey has latched Valkey off
# (see the Tiltfile). The closing message says what to do about that.
set -euo pipefail

command -v minikube >/dev/null || { echo "minikube not found" >&2; exit 1; }
command -v cilium >/dev/null || {
  echo "cilium CLI not found: https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/#install-the-cilium-cli" >&2
  exit 1
}

rebuild_hint() {
  echo "Not resuming. Rebuild instead: ./scripts/minikube-cilium-up.sh (DESTRUCTIVE, see its header)." >&2
  exit 1
}

# The docker driver needs a reachable daemon. Without one, `minikube status`
# reports the host as an error state, which would read as a broken profile.
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not reachable. Start Docker Desktop (with WSL integration for this distro) and re-run." >&2
  exit 1
fi

# Same reason as in minikube-cilium-up.sh: Tilt snapshots the kubeconfig at
# startup, and the API server's host port changes across a stop/start.
if pgrep -x tilt >/dev/null; then
  echo "tilt is running. Stop it first (Ctrl-C), then re-run this script and 'tilt up -f scripts/Tiltfile' after." >&2
  exit 1
fi

# `minikube status` exits non-zero for any state other than fully running, so
# the exit code is deliberately ignored and only the fields are read.
status="$(minikube status --format '{{.Host}} {{.Kubelet}} {{.APIServer}}' 2>/dev/null || true)"
echo "minikube status: ${status:-<none>}"

case "$status" in
  "Running Running Running")
    echo "Already running; verifying only."
    ;;
  "Stopped Stopped Stopped")
    # No flags: an existing profile starts from its stored config. Passing the
    # cold-boot flags here would only invite minikube to diff and reconfigure.
    minikube start
    ;;
  *)
    echo "Profile is missing or not cleanly stopped (Host Kubelet APIServer = '${status:-none}')." >&2
    rebuild_hint
    ;;
esac

if [ "$(kubectl config current-context)" != "minikube" ]; then
  echo "kubectl context is not minikube; refusing to run checks against anything else." >&2
  exit 1
fi

kubectl wait --for=condition=Ready node/minikube --timeout=180s || rebuild_hint
cilium status --wait --wait-duration 5m || rebuild_hint
kubectl wait --for=condition=Accepted=True gatewayclass/cilium --timeout=120s || {
  echo "GatewayClass not accepted: check: kubectl -n kube-system logs deploy/cilium-operator | grep -i gateway" >&2
  rebuild_hint
}
kubectl -n kube-system rollout status deployment/coredns --timeout=120s || rebuild_hint
kubectl wait --for=condition=available --timeout=300s -n keda deployment/keda-operator || rebuild_hint

# The API server's own host port moves on every node start. The relay gives
# clients outside WSL a fixed one. It has no restart policy (it would take the
# node's address if Docker started it first, see its header), so it is created
# here, after the node is up, on every resume.
"$(dirname "$0")/apiserver-relay.sh" up

cat <<'EOF'

Cluster resumed. Next:
  1. tilt up -f scripts/Tiltfile
  2. Once pubsub-setup has run in Tilt (it runs once on startup), restart the
     services that started out of order:
       kubectl rollout restart deploy/builder deploy/worker
EOF
