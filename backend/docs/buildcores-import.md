# BuildCores component import

The importer converts a clean [BuildCores OpenDB](https://github.com/buildcores/buildcores-open-db)
checkout into Palladium's existing discovery payloads. Preview is database-free.
Staging writes the admin `/discovery` queue; approval creates the actual typed
`pc_parts` rows and shared groups through the existing admin forms. No schema
migration, paid API, embeddings, or LLM extraction is needed for this import.

## Preview a snapshot

From the repository root:

```bash
git clone https://github.com/buildcores/buildcores-open-db.git /tmp/buildcores-open-db
git -C /tmp/buildcores-open-db rev-parse HEAD
# Optionally pin a previously reviewed commit:
# git -C /tmp/buildcores-open-db checkout <commit-sha>
cd backend
python3 -m app.jobs.buildcores_import \
  --source /tmp/buildcores-open-db \
  --report /tmp/buildcores-preview.json
```

Use Python 3.12 or 3.13. The preview only requires the standard library. The JSON
report contains the source commit, license attribution, category counts, converted
fields, per-field source evidence, validation failures, and malformed records.
Uncommitted source-data edits are refused so commit links describe the data read.
Keep the checkout fixed between preview and staging.

To preview remotely, run **Actions > Preview BuildCores import > Run workflow**.
Supply a BuildCores commit, tag, or branch. Download the `buildcores-preview`
artifact, which includes the exact resolved revision and upstream license notice.
The action has no database access and does not publish parts. It must be merged
onto the default branch before GitHub exposes its manual trigger.

## Stage and approve

For the local Tilt admin, run from the repository root:

```bash
./scripts/import-buildcores-local.sh /tmp/buildcores-open-db
# Or select categories:
./scripts/import-buildcores-local.sh /tmp/buildcores-open-db --category CPU --category RAM
```

This checks the minikube context, reads the existing local database credentials
without printing them, and stages into `palladium_local` on localhost:5433.
It writes `/tmp/buildcores-staged-local.json`. Review the imported queue at
<http://localhost:3001/discovery?source=buildcores>.

Use the backend environment (`uv sync`) and an explicitly chosen database. For
the local Tilt database forwarded to port 5433, supply its connection string:

```bash
export DB_TARGET=url
export POSTGRES_DB_URL='postgresql://USER:PASSWORD@127.0.0.1:5433/DATABASE'
uv run python -m app.jobs.buildcores_import \
  --source /tmp/buildcores-open-db \
  --category CPU --category RAM \
  --report /tmp/buildcores-staged.json \
  --stage
```

Replace the connection-string placeholders with your database values. The normal
backend settings still apply to staging. `DB_TARGET=url` prevents a configured
Cloud SQL connector from taking precedence. Omit `--category` to include all nine
component directories; repeat it to select a smaller import. Start with a category
at a time to keep the review queue manageable.

Open `http://localhost:3001/discovery` when Tilt is running. Check matched catalog
parts before approving: exact/model-number/fuzzy matches are suggestions, never
automatic merges. Mark existing parts as duplicates. Correct failed fields in
the approval form using source evidence. Missing required values need researched
specifications, not placeholders.

The admin queue uses server-side pagination (50 items per page) and filters for
source, category, validation result, and name/model-number search across the whole
pending queue. BuildCores review dialogs link to the pinned source record. The
approval gate recognizes the importer's commit, UUID and source-path provenance
instead of requiring a web-discovery manufacturer-confirmation field. Ordinary
web discoveries still require that confirmation. Unknown CPU integrated graphics
and motherboard Wi-Fi must be explicitly selected before their forms can submit.

Every part approved from this import, by hand or automatically, enters the
catalog inactive. Switch it on with the Active checkbox on its list page (CPUs,
GPUs, RAM and so on) once it has a price and you are happy with it. The review
dialog lists why an item was not auto-approved.

## Auto-approval

Add `--auto-approve` to a staging run to approve every item that passes all of
these rules; everything else stays in the queue for a person:

- it passed validation;
- it is not a GPU whose `memory_bus` is 0 or missing, and not a GPU above 75W
  whose power connectors are all 0 (OpenDB writes 0 for unfilled values);
- dedup found no possible existing match, and no part of that type has its name;
- RAM kits, drives, PSUs and GPUs join exactly one existing group (RAM group,
  storage group, PSU group, GPU chipset). No group is ever created
  automatically, and GPU chipset candidates always wait for a person.

A group fits when its identity fields are known and equal (RAM: DDR generation,
speed, capacity, module count, CAS latency, module type; storage: type, form
factor, interface, capacity; PSU: wattage, form factor, efficiency, modularity;
GPU: chip name and VRAM size) and none of its other stored fields contradicts a
value the source gives. The rules live in `app/services/buildcores/auto_review.py`.

Add `--dry-run` to see the result without keeping it: the run stages, approves,
writes the report, then rolls everything back. The report's `staging` block
counts auto-approvals per category and manual-review reasons.

```bash
./scripts/import-buildcores-local.sh /tmp/buildcores-open-db --auto-approve --dry-run
```

Approve GPU chipset candidates before their board variants, or select an existing
chipset with the same VRAM configuration in the variant approval form. The admin
forms create or reuse RAM, PSU, and storage groups. Imported parts have no prices
or benchmark scores; run the existing pricing, benchmark and embedding workflows
as appropriate after approval to make the new catalog useful for recommendations.

## Scope and mapping

| OpenDB directory | Discovery category | Important conversion |
| --- | --- | --- |
| CPU | cpu | Nested cores, clocks and memory; socket normalization; explicit iGPU evidence |
| GPU | gpu_chipset + gpu_variant | Chipset candidates separated by VRAM capacity/type; physical board dimensions retained |
| Motherboard | motherboard | Board sizes and DDR vocabulary; missing Wi-Fi stays unknown; Wi-Fi M.2 sockets excluded from drive count |
| RAM | ram_kit | Kit capacity distinct from module capacity; ECC/module type; SO-DIMM records fail review validation |
| Storage | storage_drive | SSD/HDD from `storage_type`, NVMe from `nvme`; explicit PCIe generations and SATA interfaces |
| PSU | psu | Efficiency, modularity, form factor and available connectors |
| PCCase | case | Supported board sizes and clearances; acrylic is not glass |
| CPUCooler | cpu_cooler | Socket list; air or supported AIO radiator size |
| CaseFan | fan | Size, pack quantity, PWM, airflow and noise |

Peripherals, laptops, prebuilts, operating systems and accessory categories are
excluded. Expansion cards and thermal compound have no equivalent subtype and
are also outside this first importer.

Clearance limits round down and component dimensions round up when Palladium's
integer columns cannot preserve fractional millimeters. Fractional values in
other integer columns fail validation. Unsupported enums, legacy interfaces,
420/480mm AIO types, and missing compatibility fields are reported rather than
coerced. Empty source arrays are treated as unknown, not proof of absent hardware.
Older parts may fail the existing catalog's plausibility ranges.

GPU board clocks do not become chipset clocks. Shared TDP is populated only when
every board in that VRAM group reports the same value; otherwise the chipset
candidate requires review. Board evidence remains in `_buildcores.chipset_evidence`
in provenance. This is a conversion check, not a guarantee of source accuracy.

No source prices, retailer listings, product images, inferred performance scores,
or guessed compatibility values are imported. Price and image licensing fields
are not filled with database-license assumptions.

## Repeated imports and audit

Staging IDs are deterministic from the OpenDB UUID and category. Pending records
refresh in place, including renames; approved/rejected/duplicate records remain
untouched even when upstream changes. `reference_only` is preserved. This is an
additive import workflow, not live synchronization of approved catalog data.
Source deletions never delete or deactivate Palladium parts.

Different source UUIDs with the same normalized pending name are skipped and
counted as `name_conflicts_skipped`, respecting the queue's existing unique index.
The report retains all converted source records for investigating those conflicts.
Malformed JSON or mismatched UUID filenames appear under `rejected`; unnamed
records remain in the report but cannot enter the queue. Inspect all skip counts.

Each staging invocation is atomic and uses a PostgreSQL transaction advisory lock.
A failed invocation rolls back its run and queue writes together. Successful runs
appear as hardware runs with `buildcores-v1:<source-sha>` and a no-LLM model label.
There is no automatic production schedule. Auto-approval only adds new,
inactive parts; it never changes an existing part or group.

Source URLs pin the upstream commit. Provenance records source IDs, content hashes,
converter version and attribution. Keep the source checkout and its `LICENSE.txt`
when archiving or redistributing the data. Reports and the public About page carry
the notice: Contains information from BuildCores OpenDB, available under the
[Open Data Commons Attribution License v1.0](https://opendatacommons.org/licenses/by/1-0/).

## Tests

```bash
uv run pytest tests/discovery/test_buildcores.py tests/discovery/test_validate.py
# Optional PostgreSQL test, owns and drops a unique schema in this database:
BUILDCORES_TEST_DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@HOST/DATABASE' \
  uv run pytest tests/discovery/test_buildcores_db.py
```

Backend CI runs the PostgreSQL tests against its disposable database. They verify
idempotency, renames, dedup matching, preservation of reviewed/reference records,
name collisions, atomic rollback, and that auto-approval creates inactive parts
in an existing group while a dry run leaves nothing behind.
