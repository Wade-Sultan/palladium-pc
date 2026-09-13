#!/usr/bin/env bash
# Cold-boot the local cluster: Minikube with no bundled CNI and no kube-proxy,
# then Cilium as CNI with kube-proxy replacement and Gateway API enabled.
#
# THIS SCRIPT IS THE ONLY SUPPORTED WAY TO (RE)CREATE THE CLUSTER. Do not run a
# bare `minikube start` against an existing profile to "repair" it. Doing so can
# make minikube reconfigure the control plane: it stops the kubelet and tears
# down /etc/kubernetes — including the PKI — and then re-runs kubeadm. That
# re-run fails, because kubeadm is not on the node's PATH (it lives only in
# /var/lib/minikube/binaries/<version>/, and minikube normally invokes it with an
# explicit PATH= prefix). The surfaced error is a bare
#
#     env: 'kubeadm': No such file or directory
#
# and what it leaves behind is a half-reset cluster whose kubelet crash-loops on
# a missing /etc/kubernetes/bootstrap-kubelet.conf. There is no repairing that —
# the CA is gone — so the only way out is the full rebuild below. Start here
# instead and skip the detour.
#
# DESTRUCTIVE: deletes the existing minikube profile. The catalog comes back
# via seed-db on the next `tilt up` (scripts/seed-local-db.sh), so the only
# real loss is anything written to local Postgres since the last dump.
#
# Version pairing matters: the Gateway API CRD version must be the one this
# Cilium release passes conformance against — see
# https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/gateway-api/
set -euo pipefail

CILIUM_VERSION="${CILIUM_VERSION:-1.20.0}"
GATEWAY_API_VERSION="${GATEWAY_API_VERSION:-v1.6.1}"
# Must match the chart version production runs: scaler metadata fields do
# change across minor versions, so an unpinned install would eventually
# disagree with the ScaledObject manifests it is meant to act on.
KEDA_VERSION="${KEDA_VERSION:-2.20.2}"

command -v cilium >/dev/null || {
  echo "cilium CLI not found — https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/#install-the-cilium-cli" >&2
  exit 1
}
command -v helm >/dev/null || {
  echo "helm not found — needed for KEDA at the end of this script. See scripts/bootstrap-wsl.sh" >&2
  exit 1
}

# Retries one command. The API server below accepts connections before it is
# reliably serving, and a `kubectl apply` that catches it mid-settle fails with
# "unexpected EOF" — which under `set -e` kills the entire bring-up and costs a
# full cluster rebuild. Observed on a cold boot, on the second CRD.
retry() {
  local attempts="$1" delay="$2"; shift 2
  local n=1
  until "$@"; do
    if [ "$n" -ge "$attempts" ]; then
      echo "giving up after $n attempts: $*" >&2
      return 1
    fi
    echo "attempt $n failed; retrying in ${delay}s" >&2
    n=$((n + 1))
    sleep "$delay"
  done
}

# Tilt snapshots the kubeconfig at startup and never re-reads it, so a Tilt
# that outlives this script keeps talking to the deleted cluster's API server
# endpoint. The failure is deeply misleading: stale API discovery surfaces as
# `no matches for kind "HTTPRoute"`, and any local_resource running kubectl
# inherits the dead endpoint. Stop it first, restart it after.
if pgrep -x tilt >/dev/null; then
  echo "tilt is running — stop it first (Ctrl-C), then re-run this script and 'tilt up' after." >&2
  exit 1
fi

minikube delete

# --container-runtime=docker is REQUIRED, not a preference, and it is a pin
# against a default that already moved once. minikube v1.39.0 changed the
# default runtime to containerd as a documented breaking change, and minikube
# rejects --cni=false on every runtime except docker ("The \"containerd\"
# container runtime requires CNI"), so a cold boot on 1.39+ dies at this
# command without it.
#
# Docker rather than containerd — in theory. On minikube v1.39.0 + this
# --kubernetes-version, --container-runtime=docker is NOT actually honored:
# `kubectl get nodes -o wide` shows containerd regardless, with no error or
# warning from minikube. Left in place in case a future minikube build starts
# honoring it again, but nothing here currently depends on it: the Tiltfile
# builds on the HOST's docker daemon and loads into the node with `minikube
# image load` (see the Tiltfile), rather than building inside the node's own
# daemon — the docker-vs-containerd distinction below (the --docker-opt DNS
# fix, the build verification that follows) predates that and is now dead
# weight for the Tilt build path specifically, but harmless to leave: it's a
# no-op DNS setting on a daemon nothing builds in anymore.
#
# --cni=false / --network-plugin=cni: hand pod networking entirely to Cilium.
# skip-phases=addon/kube-proxy: no kube-proxy at all — Cilium's eBPF
# kube-proxy replacement handles Services, same as GKE Dataplane V2.
#
# --docker-opt dns: image builds run in bridge containers on the node's Docker
# daemon, which inherit the node's nameserver. Under WSL2 that is the host's
# mirrored-networking resolver, reachable from the node itself but NOT from a
# nested bridge container — so `uv sync` dies with "dns error: failed to lookup
# address information: Try again" on a different package every run. Public
# resolvers are reachable from the build netns; stored in the profile, so this
# survives `minikube stop && minikube start`.
minikube start --driver=docker --cpus=4 --memory=12g \
  --kubernetes-version=v1.33.0 \
  --addons=metrics-server \
  --container-runtime=docker \
  --network-plugin=cni --cni=false \
  --extra-config=kubeadm.skip-phases=addon/kube-proxy \
  --docker-opt dns=8.8.8.8 --docker-opt dns=1.1.1.1

# Verify the above actually took, rather than trusting the flag: a silent
# regression here surfaces much later as a confusing mid-build failure.
if ! (eval "$(minikube docker-env)" && \
      docker run --rm busybox timeout 8 nslookup files.pythonhosted.org >/dev/null 2>&1); then
  echo "build-container DNS still broken — falling back to node resolv.conf" >&2
  docker exec minikube sh -c \
    'printf "nameserver 8.8.8.8\nnameserver 1.1.1.1\noptions ndots:0\n" > /etc/resolv.conf'
fi

# Gateway API CRDs must exist BEFORE the operator starts, or Cilium disables
# its Gateway controller and the GatewayClass sits at "Waiting for controller".
retry 20 3 kubectl get --raw /readyz >/dev/null
for crd in gatewayclasses gateways httproutes referencegrants grpcroutes backendtlspolicies; do
  retry 5 3 kubectl apply -f "https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/${GATEWAY_API_VERSION}/config/crd/standard/gateway.networking.k8s.io_${crd}.yaml"
done
# TLSRoute ships in the experimental channel but is on Cilium's *required*
# list — without it the operator logs "Required GatewayAPI resources are not
# found" and the whole controller stays off.
retry 5 3 kubectl apply -f "https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/${GATEWAY_API_VERSION}/config/crd/experimental/gateway.networking.k8s.io_tlsroutes.yaml"

# With kube-proxy skipped there is no ClusterIP path to the API server yet, so
# Cilium is pointed at it directly. On the docker driver the API server
# listens on the node IP at 8443.
cilium install --version "${CILIUM_VERSION}" \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost="$(minikube ip)" \
  --set k8sServicePort=8443 \
  --set gatewayAPI.enabled=true \
  --set hubble.relay.enabled=true \
  --set hubble.ui.enabled=true

cilium status --wait

# The GatewayClass existing is not enough — it is created regardless, and sits
# at Accepted=Unknown "Waiting for controller" whenever a required CRD is
# missing. Assert the condition that actually matters, so a broken controller
# fails here instead of as a mystery 404 later.
if ! kubectl wait --for=condition=Accepted=True gatewayclass/cilium --timeout=120s; then
  echo "GatewayClass not accepted — check: kubectl -n kube-system logs deploy/cilium-operator | grep -i gateway" >&2
  exit 1
fi

# KEDA, which is what scales the worker Deployment. Installed here rather than
# left as a separate manual step because this script BEGINS with `minikube
# delete` — so without it every cluster rebuild silently comes back with no
# autoscaler, and a ScaledObject applied to a cluster that has no KEDA is
# admitted and then quietly ignored. The failure is invisible until someone
# wonders why the worker never scales.
#
# `upgrade --install` rather than `install` so re-running this against a
# surviving cluster is not an error.
helm repo add kedacore https://kedacore.github.io/charts >/dev/null
helm repo update kedacore >/dev/null
helm upgrade --install keda kedacore/keda \
  --namespace keda --create-namespace \
  --version "${KEDA_VERSION}" --wait --timeout 5m

# The operator restarts itself exactly once on a fresh install: it generates
# its webhook certs, writes them to a Secret, then exits 0 so the new certs are
# loaded. Waiting on the Deployment rather than the pod rides that out.
kubectl wait --for=condition=available --timeout=300s -n keda deployment/keda-operator

echo "Cluster ready. Next: tilt up"
