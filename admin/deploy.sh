#!/usr/bin/env bash
# admin/deploy.sh — deploy Palladium admin to Compute Engine
set -euo pipefail

# ---- Config ----
INSTANCE="palladium-admin"
ZONE="us-central1-a"
PROJECT="${GCP_PROJECT:-palladium}"  # override with: GCP_PROJECT=foo ./deploy.sh
REMOTE_DIR="~/palladium/admin"
SERVICE="palladium-admin"
BRANCH="${BRANCH:-main}"

# ---- Colors ----
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'
log()  { echo -e "${G}==>${N} $*"; }
warn() { echo -e "${Y}!! ${N} $*"; }
die()  { echo -e "${R}xx ${N} $*" >&2; exit 1; }

# ---- Preflight ----
command -v gcloud >/dev/null || die "gcloud not installed"
gcloud config set project "$PROJECT" >/dev/null

# Make sure local main is clean and pushed — otherwise the VM pulls stale code
if [[ -n "$(git status --porcelain)" ]]; then
  warn "You have uncommitted changes. They will NOT be deployed."
  read -rp "Continue anyway? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || die "Aborted."
fi

LOCAL_SHA=$(git rev-parse "$BRANCH")
REMOTE_SHA=$(git ls-remote origin "$BRANCH" | awk '{print $1}')
if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
  die "Local $BRANCH ($LOCAL_SHA) doesn't match origin ($REMOTE_SHA). Push first."
fi

log "Deploying $BRANCH @ ${LOCAL_SHA:0:8} to $INSTANCE"

# ---- Remote build & restart ----
# Heredoc with 'EOF' (quoted) so $vars expand on the *remote* side, not locally.
gcloud compute ssh "$INSTANCE" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  --command="bash -s" <<'REMOTE'
set -euo pipefail

cd ~/palladium/admin

echo "==> Fetching latest code"
git fetch origin
git reset --hard origin/main

echo "==> Loading secrets"
export MIX_ENV=prod
export PHX_SERVER=true
DB_PASS=$(gcloud secrets versions access latest --secret=palladium-db-password)
export DATABASE_URL="ecto://palladium_app:${DB_PASS}@localhost:5432/palladium"
export SECRET_KEY_BASE=$(gcloud secrets versions access latest --secret=palladium-admin-secret-key)
export ADMIN_PASSWORD=$(gcloud secrets versions access latest --secret=palladium-admin-password)

echo "==> Building release"
mix deps.get --only prod
mix deps.compile
mix compile
mix assets.deploy
mix release --overwrite

echo "==> Running migrations"
_build/prod/rel/admin/bin/admin eval "Admin.Release.migrate"

echo "==> Restarting service"
sudo systemctl restart palladium-admin
sudo systemctl is-active palladium-admin
REMOTE

log "Deploy complete. Checking health..."
sleep 3
gcloud compute ssh "$INSTANCE" --zone="$ZONE" --tunnel-through-iap \
  --command="sudo systemctl status palladium-admin --no-pager | head -20"

log "Done ✓"