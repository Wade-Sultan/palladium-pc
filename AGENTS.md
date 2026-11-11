# AGENTS.md

Guidance for any coding agent working in this repository. `CLAUDE.md` holds the full detail
(commands, local cluster, how a chat turn runs, deployment). Read it before you change anything
non-trivial. This file is the short list of rules that must hold no matter which tool you are.

## Palladium: rules agents must not break

- **Compatibility is enforced by SQL pre-filtering.** The LLM never sees an incompatible
  candidate. Do not move a compatibility check into a prompt or into post-hoc filtering of model
  output.
- **Alembic in `backend/` (the builder) is the only migration authority.** `commerce/` (Go) only
  consumes the schema, and `admin/prisma/schema.prisma` is a mapped view of it. A schema change
  means an Alembic revision first, then the Prisma models.
- **Amazon-derived data never enters the ML pipeline.** Not as training data, not as DSPy
  examples, not as embeddings, not as recommender input.
- **builder and commerce never call each other.** The frontend orchestrates both.

  **One exception: builder batch jobs may ask commerce to send email.** The only such calls are
  `POST /internal/v1/price-alerts` (from the pricing ETL, `app/services/pricing_etl/alerts.py`)
  and `POST /internal/v1/listing-failure-digest` (from `app/jobs/listing_failure_digest.py`), both
  through `backend/app/services/commerce_client.py`. Why the exception exists:
  - There is no frontend in the loop. Both run as CronJobs with no user session, so nothing can
    orchestrate them.
  - Commerce owns transactional email: `RESEND_API_KEY` and the templates live only there. The
    alternative is copying that credential into the builder image, which breaks the
    narrowest-scope secrets rule below.
  - A price alert has to fire where the price is written. The ETL is the only writer of
    `street_price_cents`, so it is the only place that sees a real drop instead of inferring one.

  The exception is narrow: calls go one way only (builder to commerce, never the reverse), only to
  commerce's `/internal/*` email routes behind `COMMERCE_INTERNAL_KEY`, only from batch jobs (never
  from a chat turn or request path), and only with a user id, never an email address (commerce
  reads `users.email` itself). Anything else needs an ADR (see below).
- **`amazon_listings.affiliate_tag` stays empty until Associates approval.**
- **Imports quarantine bad rows; they never drop them.**
- **Prod secrets live in Secret Manager as `<name>-prod`, scoped to the narrowest service.** See
  `deploy/overlays/prod/patches/secrets-scoped.yaml` for the per-service split, and add every new
  builder-image workload there.

## Before changing architecture

Search Falconer for the relevant decision first. Falconer access here is read-only: when a change
implies a new decision, end the session with a draft ADR for Wade to file, in this shape:

```markdown
# ADR: <title>

## Context
## Decision
## Alternatives
## Consequences
```

## Repo conventions that catch agents out

- **No em-dashes anywhere**: code, comments, docstrings, commit messages, docs, UI copy. Use a
  comma, colon, parentheses or a full stop instead, never `--` or an en-dash.
- The module-header docstrings in `backend/app/services/` explain why a design is the way it is.
  Read the header before changing a module and update it rather than deleting it.
- `print()` is banned in backend code (ruff `T201`) except in `app/seeds/*`.
- Lint gates: `uv run bash scripts/lint.sh` in `backend/`, `npx biome ci ./` and
  `npx tsc --noEmit` in `frontend/`. `npm run lint` in `frontend/` rewrites files.
- Never run a bare `minikube start`; `scripts/minikube-cilium-up.sh` is the only supported way to
  (re)create the local cluster. `scripts/minikube-resume.sh` restarts a cleanly stopped one.
- Never point Tilt or `kubectl` at anything but the `minikube` context.
