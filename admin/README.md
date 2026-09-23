# Admin

Internal catalog and CMS for Palladium: a Next.js App Router app talking to the
same Cloud SQL Postgres as the backend, through Prisma.

Resource pages live one per directory under `src/app/`: parts (`cpus`, `gpus`,
`motherboards`, `ram`, `storage`, `psus`, `cases`, `cpu-coolers`, `fans` and
their grouping tables), plus `games`, `ai-models`, `software`,
`reference-builds`, `guide-videos`, `blog`, `discovery`, `listing-failures`,
`users` and `analytics`.

## Running it

```bash
npm install
npm run db:generate     # prisma generate: required before the first dev run
npm run dev             # :3000
```

Locally the app runs in the minikube cluster rather than on the host; `tilt up
-f scripts/Tiltfile` brings it up and forwards it to <http://localhost:3001>.
See `scripts/Tiltfile` and the repo root's `CLAUDE.md`.

```bash
npm test                # node --test over tests/*.test.ts
npm run lint            # eslint
npm run db:studio       # prisma studio
```

`npm test` and the repo's lint gate both run in `.github/workflows/test-unit.yml`.

## Schema

**Alembic owns the database schema**, not Prisma. `prisma/schema.prisma` is a
mapped view of the tables `backend/app/alembic/` creates (`@map` onto their
snake_case columns), so a schema change is an Alembic revision first and a
Prisma model update second. `npm run db:push` writes directly to whatever
`DATABASE_URL` points at. It is not part of any normal workflow here.

## Configuration

| Variable | What it is for |
|---|---|
| `DATABASE_URL` | Postgres, read by Prisma |
| `BACKEND_API_URL` | the builder API, for discovery review actions |
| `DISCOVERY_API_KEY` | shared secret for those calls |
| `BLOG_MEDIA_BUCKET` / `BLOG_MEDIA_BASE_URL` | GCS bucket behind `/api/blog/upload` |
| `PARTS_MEDIA_BUCKET` / `PARTS_MEDIA_BASE_URL` | GCS bucket behind `/api/parts/upload` |

Both buckets are created out of band, not by the deploy pipeline: uniform
bucket-level access, `roles/storage.objectAdmin` for the `palladium-admin` GSA
the admin KSA impersonates, and `roles/storage.objectViewer` for `allUsers`
(they hold nothing but images already embedded in public pages). The names must
match `deploy/base/admin/configmap.yaml`. Until the parts bucket exists,
`/api/parts/upload` falls back to the blog bucket under a `parts/` prefix.

Part images must be uploaded with their credit, source URL and licence filled
in. Case photos are sourced by hand from manufacturer press kits, and that
attribution is the basis for using the imagery: every rendered image shows its
credit line linked back to the source, so a blank credit is a bug, not a
cosmetic gap.

## Deployment

Built and deployed to GKE by the repo-wide Cloud Build pipeline
(`deploy/cloudbuild.yaml`); manifests in `deploy/base/admin/`. Nothing routes to
it publicly: reach production with:

```bash
kubectl -n palladium port-forward svc/admin 3000:80
```
