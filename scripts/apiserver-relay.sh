#!/usr/bin/env bash
# A fixed host port for the minikube API server: 127.0.0.1:${RELAY_PORT}
# (18443 by default) -> minikube:8443 on minikube's docker network.
#
# Why: the docker driver publishes the API server on an ephemeral host port
# (127.0.0.1::8443), and Docker hands out a new one whenever the node container
# starts, so it moves on every `minikube stop`/`start` as well as every rebuild.
# Anything holding a copy of the kubeconfig outside WSL (a Docker Sandbox
# reaching the host through host.docker.internal, say) breaks each time, and a
# sandbox network policy has to approve every new port.
#
# How: a socat container joined to the `minikube` network, so it reaches the
# node by container name on the API server's real port, which never changes.
# It is published through Docker Desktop like minikube's own port, so it is
# reachable from the Windows host.
#
# NO RESTART POLICY, deliberately. The minikube node takes a static address on
# the `minikube` network (192.168.49.2), but only when it starts; the relay gets
# whatever address is free. With `--restart unless-stopped`, Docker Desktop
# restarted the relay on its own before minikube, the relay took the node's
# address, and `minikube start` then failed with "failed to set up container
# networking: Address already in use". So the relay must only ever start after
# the node: minikube-resume.sh and minikube-cilium-up.sh run `up` once the
# cluster is running. After a Docker restart it stays exited until then, and an
# exited container holds no address.
#
# The certificate does not name host.docker.internal, so a client using this
# port needs `tls-server-name: localhost` in its kubeconfig cluster entry.
#
# minikube-cilium-up.sh runs `down` before `minikube delete` (a container still
# attached to the `minikube` network stops minikube from deleting it) and `up`
# after; minikube-resume.sh runs `up`. Run either by hand at any time.
#
#   scripts/apiserver-relay.sh [up|down|status]
set -euo pipefail

RELAY_PORT="${RELAY_PORT:-18443}"
RELAY_IMAGE="${RELAY_IMAGE:-alpine/socat:1.8.0.3}"
NAME="palladium-apiserver-relay"

case "${1:-up}" in
  up)
    if ! docker network inspect minikube >/dev/null 2>&1; then
      echo "docker network 'minikube' not found: start the cluster first." >&2
      exit 1
    fi
    # Recreate rather than reuse, so a changed RELAY_PORT or image always applies.
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    # No --restart: see the header.
    docker run -d --name "$NAME" \
      --network minikube \
      -p "127.0.0.1:${RELAY_PORT}:8443" \
      "$RELAY_IMAGE" \
      TCP-LISTEN:8443,fork,reuseaddr TCP:minikube:8443 >/dev/null
    echo "apiserver relay: 127.0.0.1:${RELAY_PORT} -> minikube:8443"
    ;;
  down)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    echo "apiserver relay removed"
    ;;
  status)
    docker ps -a --filter "name=^${NAME}$" --format '{{.Names}}  {{.Status}}  {{.Ports}}'
    ;;
  *)
    echo "usage: $0 [up|down|status]" >&2
    exit 1
    ;;
esac
