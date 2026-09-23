#!/usr/bin/env bash
# Stage OpenDB into the same local database used by the Tilt admin panel.
# Credentials are read without printing them; production targets are not accepted.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$(kubectl config current-context)" != "minikube" ]; then
  echo "Select the minikube context before importing into the local admin." >&2
  exit 1
fi
if [ "$#" -lt 1 ]; then
  echo "Usage: $0 /path/to/buildcores-open-db [--category CPU ...] [--auto-approve] [--dry-run]" >&2
  exit 1
fi
if [ ! -x "$REPO_ROOT/backend/.venv/bin/python" ]; then
  echo "Run 'cd backend && uv sync' first." >&2
  exit 1
fi

"$REPO_ROOT/backend/.venv/bin/python" - "$REPO_ROOT" "$@" <<'PY'
import os
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values
import psycopg
from sqlalchemy.engine import URL

root = Path(sys.argv[1])
source = Path(sys.argv[2]).resolve()
extra = sys.argv[3:]
# Only category selection and the review switches can be forwarded, so a caller
# cannot override the source/report or redirect this command to another database.
switches = [a for a in extra if a in ('--auto-approve', '--dry-run')]
pairs = [a for a in extra if a not in switches]
if len(pairs) % 2 or any(pairs[i] != '--category' for i in range(0, len(pairs), 2)):
    raise SystemExit('Only --category NAME, --auto-approve and --dry-run are supported.')
password = dotenv_values(root / 'deploy/overlays/local/.env.local').get('POSTGRES_PASSWORD')
if not password:
    raise SystemExit('POSTGRES_PASSWORD is missing from deploy/overlays/local/.env.local')
url = URL.create('postgresql', username='palladium_app', password=password,
                 host='127.0.0.1', port=5433, database='palladium_local')
connection_string = url.render_as_string(hide_password=False)
with psycopg.connect(connection_string) as db:
    if db.execute('SELECT current_database()').fetchone()[0] != 'palladium_local':
        raise SystemExit('Refusing to import into a non-local database.')
environment = {**os.environ, 'DB_TARGET': 'url', 'POSTGRES_DB_URL': connection_string}
subprocess.run([sys.executable, '-m', 'app.jobs.buildcores_import', '--source', str(source),
                '--report', '/tmp/buildcores-staged-local.json', '--stage', *extra],
               cwd=root / 'backend', env=environment, check=True)
print('Review imported parts at http://localhost:3001/discovery?source=buildcores')
PY
