# Local dev against Minikube. Frontend is NOT here — it keeps running on the
# host via `npm run dev` and talks to the cluster through the gateway hosts.
#
#   ./scripts/minikube-cilium-up.sh   # (re)creates the cluster: Cilium CNI,
#                                     # kube-proxy replacement, Gateway API
#   tilt up
#
# No `minikube tunnel` needed anymore — gateway-forward relays to the
# gateway Service's NodePort directly.

# Refuse to run against anything but the local cluster. Without this a stray
# kubectl context makes `tilt up` deploy to whatever it happens to be pointing
# at — including prod.
allow_k8s_contexts('minikube')

# docker_build below needs THIS shell's docker client pointed at minikube's
# inner daemon (see scripts/minikube-cilium-up.sh on why the driver is docker,
# not containerd). Skipping that step doesn't fail loudly here — Tilt just
# falls back to pushing the built image to Docker Hub under its bare name,
# which dies minutes later with a confusing "push access denied" from a
# repository that was never meant to exist. Catch the actual cause up front.
# Needed again every time after `minikube delete` / minikube-cilium-up.sh,
# since that's a fresh docker daemon each time.
if not os.environ.get('DOCKER_HOST'):
    fail('DOCKER_HOST is not set — this shell is not pointed at minikube\'s ' +
         'docker daemon. Run:\n\n    eval "$(minikube docker-env)"\n\n' +
         'in this terminal, then re-run tilt up.')

# The ADC secret can't come from secretGenerator: kustomize won't read files
# above the kustomization root without --load-restrictor LoadRestrictionsNone.
# Created here instead so a cold `minikube delete && tilt up` still works.
# commerce fails to *start* without it (firebase.NewApp runs before bind).
local_resource(
    'gcp-adc-secret',
    cmd='kubectl create secret generic gcp-adc ' +
        '--from-file=application_default_credentials.json=.gcloud/application_default_credentials.json ' +
        '--dry-run=client -o yaml | kubectl apply -f -',
    deps=['.gcloud/application_default_credentials.json'],
    labels=['setup'],
)

k8s_yaml(kustomize('deploy/overlays/local'))

# Rolls the pods whose configuration just changed.
#
# builder-config is a plain ConfigMap, not a generated one, so kustomize gives
# it no content-hash suffix and `kubectl apply` of a changed ConfigMap does not
# restart anything reading it. envFrom is resolved once, at pod start — so
# without this, editing config-local.yaml updates the ConfigMap in the cluster
# and every running pod keeps the old values, indefinitely.
#
# That failure is silent and it lies in the direction of a false pass: a builder
# holding a stale, empty VALKEY_HOST serves every turn on the inline path while
# the cluster looks correctly configured, so a test of the dispatched path
# quietly exercises the fallback instead.
local_resource(
    'config-roll',
    cmd='kubectl rollout restart deployment/builder deployment/worker && ' +
        'kubectl rollout status deployment/builder --timeout=180s',
    deps=[
        'deploy/overlays/local/patches/config-local.yaml',
        # The Secret has the same problem for the same reason: the
        # generator's name-suffix hash is disabled (see kustomization.yaml),
        # so a changed .env.local updates the Secret and rolls nothing.
        'deploy/overlays/local/.env.local',
    ],
    # MUST run after the ConfigMaps are applied, or it does the opposite of its
    # job: Tilt gives no ordering between a local_resource and a k8s apply, and
    # the roll losing that race restarts the pods onto the OLD ConfigMap moments
    # before the new one lands — the exact stale-config state this resource
    # exists to prevent, now with a cluster that looks correct because the
    # ConfigMap itself is right.
    #
    # 'uncategorized' is Tilt's catch-all resource, and it is where the
    # ConfigMaps and the Secret live because no workload claims them. Depending
    # on it is less explicit than grouping them under a name of their own — but
    # do NOT do that: reassigning those objects to a new k8s_resource makes Tilt
    # delete them from the cluster and report success without recreating them,
    # which takes every pod that reads them into CreateContainerConfigError.
    resource_deps=['uncategorized'],
    # Nothing to do on a cold start: the pods are about to be created with the
    # current ConfigMap anyway, and restarting them would only cost a rollout.
    auto_init=False,
    labels=['setup'],
)

docker_build(
    'palladium/builder',
    context='./backend',
    live_update=[
        # Paired with the local overlay's `fastapi dev` command, which reloads
        # on change. Syncing without that patch would copy files in and change
        # nothing.
        sync('./backend/app', '/app/app'),
        # A dependency change needs a real resync, not just a file copy.
        run('uv sync', trigger=['./backend/pyproject.toml', './backend/uv.lock']),
    ],
)
docker_build('palladium/commerce', context='./commerce')
docker_build('palladium/admin', context='./admin')

# Host-based routing entrypoint: 127.0.0.1:8081 → Cilium Gateway. The gateway
# Service is created by Cilium (not this Tiltfile) and is selector-less, so
# neither k8s_resource port_forwards nor `kubectl port-forward` can target it —
# the script relays to its NodePort instead. See the script header for the
# 8081-vs-80 WSL2 story.
local_resource(
    'gateway-forward',
    serve_cmd='./scripts/gateway-forward.sh',
    labels=['setup'],
)

k8s_resource('postgres', port_forwards='5433:5432', labels=['data'])

# Valkey and the Pub/Sub emulator: the two services that decide whether /chat
# dispatches a turn to a worker or runs it inline. The port-forward is for
# poking at keys from the host (any redis client speaks to Valkey).
k8s_resource('valkey', port_forwards='6379:6379', labels=['data'])
k8s_resource('pubsub-emulator', labels=['data'])

# Declares the topics and subscriptions into the emulator, which starts empty
# and persists nothing. MANUAL trigger mode with the default auto_init: it runs
# once on `tilt up`, then never again on its own. It uses the backend image (for
# google-cloud-pubsub only), so without this it would re-run on every single
# backend code change — pure noise, since the result is identical.
#
# Trigger it by hand if the emulator pod ever restarts: its topics die with it,
# and the worker starts logging NotFound on the subscription.
k8s_resource(
    'pubsub-setup',
    resource_deps=['pubsub-emulator'],
    trigger_mode=TRIGGER_MODE_MANUAL,
    labels=['data'],
)

# RESTORE FIRST, THEN MIGRATE. This order is not cosmetic and it must not be
# swapped back — it was the other way round, and that silently pinned local
# development to a schema OLDER than the code.
#
# seed-local-db.sh restores a production dump with `pg_restore --clean`, which
# drops and recreates every object it contains, including the alembic_version
# row. Running it after the migration therefore threw the migration away: the
# database ended up at whatever revision production was on when the dump was
# taken, alembic never ran again, and nothing anywhere reported a problem. The
# symptom is a column the ORM believes in and Postgres has never heard of,
# surfacing as a runtime error inside whichever feature happens to touch it —
# in this case the build-telemetry drain, whose write failed against a
# build_sessions with no conversation_id.
#
# This order also matches what production actually does on every deploy: an
# existing database, then `alembic upgrade head` over the top of it. Local now
# exercises the same migration path rather than skipping it.
local_resource(
    'seed-db',
    cmd='./scripts/seed-local-db.sh',
    resource_deps=['postgres'],
    deps=['scripts/seed-local-db.sh'],
    labels=['data'],
)

# Alembic is the only migration authority; everything else waits on it so no
# service ever starts against an un-migrated schema.
k8s_resource('migrate', resource_deps=['seed-db', 'gcp-adc-secret'], labels=['data'])

# Services depend on seed-db so their pools open against a populated database
# rather than connecting first and seeing rows appear underneath them.
#
# builder ALSO waits on valkey, and that dependency is load-bearing rather than
# tidy. app/core/valkey.py latches `_unavailable` on the first failed connection
# and never retries for the life of the process — deliberately, so a
# misconfigured deployment pays one timeout per pod instead of one per request.
# The API starts a buffer gauge loop at startup that connects immediately, so a
# builder that comes up before Valkey does latches OFF permanently and silently
# serves every turn on the inline path. It looks like a working cluster. Only a
# pod restart clears it.
#
# It waits on pubsub-setup for a milder reason: publishing to a topic that does
# not exist yet fails the dispatch and falls back to inline for that turn.
k8s_resource(
    'builder',
    resource_deps=['migrate', 'valkey', 'pubsub-setup'],
    port_forwards='8000:8000',
    labels=['services'],
)

# The worker cannot start at all without its subscription — app/worker.py raises
# on an empty PUBSUB_SUBSCRIPTION and, given one, fails its streaming pull if the
# subscription is absent. Same Valkey latch applies: it writes every turn event
# to the stream, so a worker that latched off produces a turn nobody can read.
k8s_resource(
    'worker',
    resource_deps=['migrate', 'valkey', 'pubsub-setup'],
    labels=['services'],
)
k8s_resource('commerce', resource_deps=['migrate'], port_forwards='8080:8080', labels=['services'])
k8s_resource('admin', resource_deps=['migrate'], port_forwards='3001:3000', labels=['services'])

# CronJobs are deployed so their manifests stay exercised, but must not fire on
# a laptop — the pricing ETL burns SerpAPI quota. Trigger by hand from the Tilt
# UI, or: kubectl create job --from=cronjob/pricing-etl etl-manual-1
k8s_resource('pricing-etl', trigger_mode=TRIGGER_MODE_MANUAL, auto_init=False, labels=['jobs'])
k8s_resource('discovery', trigger_mode=TRIGGER_MODE_MANUAL, auto_init=False, labels=['jobs'])

# Unlike the two above, this one IS deployed on startup and is allowed to fire:
# it costs no API quota (it moves rows that were already paid for at build time)
# and the local overlay shortens its schedule to every 5 minutes. To drain
# immediately rather than waiting for the schedule:
#   kubectl create job --from=cronjob/telemetry-drain drain-now
k8s_resource('telemetry-drain', labels=['jobs'])
