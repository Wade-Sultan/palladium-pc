# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Palladium ([palladiumtech.ai](https://palladiumtech.ai)) recommends complete PC builds from a
conversation. The user describes what they want to do with the machine; a structured pipeline picks
components in dependency order with hard compatibility enforcement and explains its reasoning.

Four deployables plus one shared Postgres:

| Dir | Stack | Role | Where it runs |
|---|---|---|---|
| `backend/` | FastAPI + SQLModel/SQLAlchemy, Python 3.12, uv | `builder` (HTTP API, HPA 2–4) **and** `worker` (Pub/Sub subscriber, KEDA 1–8): same image, different command | GKE Autopilot, `api.palladiumtech.ai` |
| `frontend/` | Next.js 16 App Router, React 19, Tailwind 4, assistant-ui | Public site and chat UI | **Vercel**, not GKE |
| `admin/` | Next.js 16 + Prisma | Internal catalog/CMS over the same Postgres | GKE, port-forward only |
| `commerce/` | Go 1.25 | Retail listings, affiliate links, account sync, price-alert email (Resend) | GKE, `commerce.palladiumtech.ai` |

Postgres is Cloud SQL (pgvector enabled); Valkey is Memorystore. Neither is in the cluster.

## Commands

### Backend (`cd backend`)

```bash
uv sync                                   # install (dev tools live in [dependency-groups])
uv run fastapi dev app/main.py            # API on :8000
uv run bash scripts/test.sh               # full suite + coverage report + htmlcov/
uv run pytest tests/test_turn_stream.py            # one file
uv run pytest tests/recommender/test_scoring.py -k dominance   # one test
uv run bash scripts/lint.sh               # THE lint gate: ruff check + ruff format --check
bash scripts/format.sh                    # ruff --fix + format
uv run mypy app                           # by hand only. See below
uv run alembic upgrade head               # migrations
uv run alembic revision --autogenerate -m "..."
```

`mypy` is deliberately **not** in `scripts/lint.sh`: `strict = true` is set but the codebase has
never satisfied it. Don't add it back to the gate; do run it when working on types.

CI enforces `coverage report --fail-under=45`: a ratchet just under today's number, not a target.

The test suite needs a Postgres. CI starts one with `docker compose up -d db` from the repo root and
runs `scripts/prestart.sh` before the tests.

### Frontend (`cd frontend`)

```bash
npm run dev          # :3000
npm run build
npm run lint         # biome check --write. REWRITES files
npx biome ci ./      # what CI runs: read-only, non-zero on any finding
npx tsc --noEmit     # CI type gate, uses tsconfig.json (includes tests)
```

Node version comes from `frontend/.nvmrc` (24).

`npm run generate-client` and `scripts/generate-client.sh` are template leftovers. There is no
`openapi-ts.config.ts` and no generated client. The frontend calls the API through hand-written
fetch wrappers in `frontend/src/lib/*.ts`, all keyed off `NEXT_PUBLIC_API_URL`.

`frontend/tests/*.spec.ts` (Playwright) are also template leftovers: they target `localhost:5173`
and an email/password auth flow the app no longer has (auth is Firebase). No CI job runs them.

### Admin (`cd admin`) and commerce (`cd commerce`)

```bash
npm test            # node --test over tests/*.test.ts     | go test ./...
npm run lint        # eslint                                | go build ./...
npm run db:generate # prisma generate
```

Both are gated by `.github/workflows/test-unit.yml`.

## Local development: minikube, not docker compose

The supported loop is a local Kubernetes cluster driven by Tilt. The frontend is **not** in the
cluster. It stays on the host.

```bash
./scripts/minikube-cilium-up.sh      # cold-boot the cluster (DESTRUCTIVE: deletes the profile)
tilt up -f scripts/Tiltfile          # backend, worker, commerce, admin, postgres, valkey, pubsub emulator
cd frontend && npm run dev           # host, :3000
```

Never run a bare `minikube start` to repair the cluster. It can wipe `/etc/kubernetes` and leave an
unrecoverable control plane. `minikube-cilium-up.sh` is the only supported way to (re)create it; its
header explains why.

Ports Tilt forwards: builder `:8000`, commerce `:8080`, admin `:3001`, Postgres `:5433`, Valkey
`:6379`. `scripts/gateway-forward.sh` relays `127.0.0.1:8081` → the Cilium Gateway (hosts
`api.palladium.local`, `commerce.palladium.local`); port 80 is unavailable under WSL2.

```bash
./scripts/mk-smoke.sh                  # end-to-end chat turn through the DISPATCHED path, no LLM spend
./scripts/mk-verify-locked-parts.sh    # locked-parts machinery against the real seeded catalog
./scripts/mk-verify-system-offer.sh    # system offers: fit, offer store, picks via a worker, commerce
./scripts/seed-local-db.sh [--force]   # restore .local-seed/palladium.dump, strip PII
./scripts/dump-prod-db.sh              # refresh that dump from Cloud SQL
./scripts/logs.sh [-H]                 # prod GKE logs (live kubectl, or -H for Cloud Logging history)
```

Things that will bite:

- **`allow_k8s_contexts('minikube')`** guards `scripts/Tiltfile`, and `mk-smoke.sh` refuses any other
  context. Keep it that way, without it a stray kubectl context deploys to prod.
- **Seed runs before migrate, never after.** `pg_restore --clean` drops `alembic_version`, so
  reversing the order silently pins local to production's schema at dump time.
- **Only `backend/app` is live-synced.** Editing anything else under `backend/` (tests, scripts,
  `pyproject.toml`, `uv.lock`) rebuilds the image and replaces the builder pod, killing any job
  running inside it.
- **Editing `deploy/overlays/local/patches/config-local.yaml` or `.env.local`** does not restart
  pods on its own; Tilt's `config-roll` resource does it, and it must run *after* the ConfigMap
  apply. A builder holding a stale empty `VALKEY_HOST` silently serves every turn inline while the
  cluster looks correct.
- **The pubsub emulator persists nothing.** If its pod restarts, re-trigger `pubsub-setup` by hand
  or the worker logs `NotFound` forever.
- `pricing-etl` and `discovery` CronJobs are deployed but manual-trigger locally: the pricing ETL
  burns SerpAPI quota.
- The complete-system catalog is not in the prod dump yet: after `seed-local-db.sh`, run
  `uv run python -m app.seeds.seed_systems` (idempotent, overwrites admin edits to those rows).
- After restarting the Pub/Sub emulator, restart the builder and worker too: their gRPC channels
  stay pinned to the dead emulator pod, so publishes vanish and turns hang with no error.
- The local seed currently has no games/benchmark rows and no embeddings, and `OPENAI_API_KEY` is
  unset locally, so game-spec lookups and pgvector search need seeding before they can be exercised.

`docker-compose.yml` / `docker-compose.dev.yml` / `DEV_SETUP.md` / `development.md` /
`backend/README.md` predate the minikube setup and come from the
[full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) this repo was
copier-generated from. Root `docker compose up -d db` is still used (by CI) for a throwaway
Postgres; the rest is stale.

## Architecture: how one chat turn runs

This is the part worth understanding before changing anything in `backend/app/services/`.

```
POST /api/v1/chat            app/api/routes/chat.py        (assistant-transport protocol)
  └─ publish to Pub/Sub  ──► app/worker.py  ──► run_turn   (app/services/turn_runner.py)
       (or inline fallback in the API process)                   │
                                                                 ├─ LangGraph  app/services/graph/
                                                                 └─ DSPy       app/services/recommender/
  events ──► Valkey Redis Stream  chat:evt:{turn_id}   (app/services/turn_stream.py)
  browser ◄── server-authoritative state ops           (app/services/transport.py)
```

**Dispatch degrades, it does not fail.** If Pub/Sub or Valkey is unconfigured, `/chat` runs the turn
inline in the API process. That fallback is the only path the pytest suite exercises, so `run_turn`
is deliberately one implementation shared by both callers and the fallback has to keep working. It
also means a test that only asserts "a build came back" proves nothing about dispatch,
`mk-smoke.sh` exists to assert a *worker* ran the turn, read from the Valkey claim key. The local
overlay runs 1 worker against the Pub/Sub emulator and a real Valkey, so the dispatched path *is*
exercisable locally.

**Why a Redis Stream and not pub/sub for events.** The browser attaches after `POST /chat` returns.
A stream is a durable log, so a reader can replay from `0`. That is what makes both the initial
attach and a mid-build reconnect work. The last entry is always `{"type": "end"}`, written only
after persistence commits.

**Server-authoritative state.** `transport.py` owns the whole conversation state including the
user's own message; the client renders what it is told. `usage`, `reference_estimate` and
`checkpoint` are internal events and must never reach a browser.

**End-of-turn ordering** in `turn_runner.py` is load-bearing: pipeline finishes → buffer written →
Postgres commit confirmed → buffer evicted → terminal stream entry. Step 5 last, so a client cannot
disconnect before its turn is durable.

### The graph (`app/services/graph/`)

```
START ─┬─ collect → route ─┬─ (incomplete) → ask ─────────────→ finalize → END
       │                   └─ (complete) → assess ─┬─ (fits) → offer → finalize
       │                                           └─ build ─┬─ present → finalize
       │                                                     └─ (paused) → finalize
       ├─ discuss ──────────────────────────────────────────────→ finalize
       └─ system_choice ─┬─ (custom) → build
                         └─ (taken / expired) ───────────────────→ finalize
```

**Complete systems** (`app/services/systems/`): `assess` may offer a ready-made machine (DGX Spark,
Mac Studio, Strix Halo) instead of building. The decision is rules over catalog data in `fit.py`,
never a model. What each family is good for, its OS and backend are columns on `system_families`
(`suited_for`), curated in admin, because they change with the market; keep product facts out of
code. An offer ends the turn like the case picker, saved in `paused_build`'s stores with
`kind="system_offer"`, and the click returns as a `select-system` command that enters at
`system_choice`.

`build` is **one** node wrapping the whole component pipeline. The DSPy steps have their own
sequencing, budget allocation and telemetry, and nothing branches between them. Checkpointing is a
hand-written `BaseCheckpointSaver` on Valkey (`graph/checkpoint.py`); `langgraph-checkpoint-redis`
is deliberately not a dependency because Memorystore for Valkey ships no Redis modules.

### The recommender (`app/services/recommender/`)

`dspy_pipeline.py` runs eleven DSPy modules in strict dependency order, each decision passed to the
next as a hard constraint:

```
ExtractProfile → DDR → CPU → Cooler → Motherboard → RAM → Storage → GPU → PSU → Case → Fans
```

- `_allocate_budget()` derives independent **soft** per-slot ceilings; they need not sum to the total.
- Each step emits one stable progress message before its DB query and nothing else while its module
  runs, so the UI does not flicker. Modules run via `dspy.asyncify`, not `streamify`, so a failing
  step raises its real exception rather than an anyio `TaskGroup` wrapper.
- `RECOMMEND_THINK_STEPS` (local only) names the DSPy calls allowed to use a reasoning model's
  native thinking; every other call is sent `reasoning_effort=none`. Unset, nothing changes.
- **Locked parts** (`locked_parts.py`): a part the user named short-circuits its Decide step
  entirely. Refused only as `unresolved`, `unaffordable` or `overspec` (plus `insufficient`).
- **Paused builds** (`paused_build.py`): the case step stops the turn rather than holding a worker
  open while a human picks. State is written to Valkey (read path) *and* Postgres (durable), each
  claimed atomically, so a double-click cannot produce two builds. The pick arrives as its own turn
  and resumes the pipeline outside the graph (`resume_build` in `chat_pipeline.py`).
- **Prompt artifacts** (`artifacts.py`): `DSPY_ARTIFACT_URI` pins an immutable optimized DSPy release
  in GCS, verified by schema hash. If a pinned release fails to load, the process must *not* fall
  back to baseline prompts.

LLM calls go through OpenRouter (`app/services/llm/`) so every call returns uniform token/cost
figures, billed to the conversation. `RECOMMEND_MODEL` overrides the Decide* model.

**Load-test mode**: a request carrying `X-Palladium-Load-Test` matching `LOAD_TEST_SECRET` is served
by in-process stub LMs (`app/core/loadtest.py`). The full pipeline runs against the real catalog
with no provider spend. An empty secret (the default) disables the header entirely. This is how
`mk-smoke.sh` and `deploy/loadtest/` (Locust) work.

### Batch jobs

CronJobs in `deploy/base/jobs/`, each `python -m app.jobs.<name>`: `discovery` (LLM-driven catalog
expansion: fetch, extract, dedup, evidence-check, validate, reconcile), `pricing_etl` (SerpAPI →
retail listings), `embeddings` (pgvector), `benchmarks`, `telemetry_drain`,
`listing_failure_digest`.

## Data and migrations

**Alembic is the only migration authority.** `deploy/base/jobs/migrate-job.yaml` runs
`alembic upgrade head` and every service waits on it. `admin/prisma/schema.prisma` is a *mapped view*
of that same schema (`@map` onto snake_case columns), not a source of truth. A schema change means
an Alembic revision first, then updating the Prisma models. Be careful with `npm run db:push` in
`admin/`: it writes to whatever `DATABASE_URL` points at.

`app/models/__init__.py` and `app/crud/__init__.py` re-export everything and carry a `F401` ignore.
Those imports are what register models with SQLAlchemy metadata. Drop one and
`alembic revision --autogenerate` quietly produces an empty migration instead of an error.

`app/core/config.py` builds `settings` at **import time** from `../.env` (repo root, gitignored).
`PROJECT_NAME`, `POSTGRES_SERVER`, `POSTGRES_USER`, `OPENROUTER_API_KEY` and `SERPAPI_KEY` have no
defaults, so anything that imports the app dies in pydantic validation without them (see the env
block in `.github/workflows/test-backend.yml`). Set `DB_TARGET=url` to point a one-off command at a
scratch database, since `env_ignore_empty=True` means a blank override is discarded rather than
applied.

## Deployment

One Cloud Build pipeline, `deploy/cloudbuild.yaml`, one trigger, on pushes to `main`. It deploys
builder, worker, commerce and admin to GKE Autopilot via `kustomize build deploy/overlays/prod`.
The frontend deploys separately on Vercel and is filtered out of the trigger by `--included-files`.
That filter is correctness, not an optimisation, since a frontend-only push would otherwise run a
migration Job and roll production. Any reference to `backend/cloudbuild.yaml`,
`commerce/cloudbuild.yaml` or `admin/cloudbuild.yaml` is stale.

Stages: three images build and push in parallel → `render` (kustomize + SHA substitution) →
`credentials` (cluster auth, Secret preflight) → `migrate` → `deploy` → `rollout`. **The migration
is a gate, not a step**: it runs as Job `migrate-$SHORT_SHA` and must complete before any Deployment
rolls. A migration that actually ran and raised does not auto-retry. The failure is deterministic.

Every build pushes an immutable `:$SHORT_SHA` alongside `:latest`; roll back by pinning a SHA, never
to `:latest`. If the bad deploy carried a migration, do **not** just roll pods back. Old code
against a migrated schema fails worse and less obviously.

Some operator runbooks (GCP console setup, Pub/Sub topology, tracing, RLS roles) are deliberately
gitignored, so they may exist in a working copy but are not part of a fresh clone. Don't cite them
by path from tracked files. `.gitignore` explains why: carry the fact itself instead, so a
checkout without them reads as complete.

## Conventions

- Run `uv run pre-commit install` once. Hooks: ruff, ruff-format, and `biome check` for `frontend/`.
- `print()` is banned in backend code by ruff `T201`; `app/seeds/*` is the only exception.
- The dense module-header docstrings across `backend/app/services/` record *why* a design is the way
  it is. Several of them exist because the obvious alternative failed silently in production. Read
  the header before changing a module, and keep the note updated rather than deleting it.
- **No em-dashes anywhere.** Not in code comments, docstrings, commit messages, documentation, or
  user-facing copy. This binds every agent working in this repo, not just one tool. Rewrite the
  sentence with a comma, a colon, parentheses, or a full stop rather than substituting `--` or an
  en-dash. Existing text predates the rule; fix it when you are already editing that line, not in a
  sweep of its own.
