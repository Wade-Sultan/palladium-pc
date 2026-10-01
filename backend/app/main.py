import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core import pubsub
from app.core.config import settings
from app.core.loadtest import LoadTestMiddleware, is_load_test_request
from app.core.logging import configure_logging
from app.core.metrics import PROBE_PATHS
from app.core.metrics import instrument as instrument_metrics
from app.core.metrics import start_exporter as start_metrics_exporter
from app.core.tracing import configure_tracing, shutdown_tracing
from app.core.valkey import close_client as close_valkey
from app.core.warmup import mark_dspy_warm
from app.services.chat_buffer import buffer_gauge_loop

# Before anything else logs, so uvicorn's startup lines are JSON too.
configure_logging()

logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


async def _warm_dspy_pipeline() -> None:
    """Import DSPy/litellm and configure the LM off the request path, so a
    cold-started instance can bind its port and start accepting connections
    immediately instead of blocking on this multi-second import chain."""
    try:
        from app.services.chat_pipeline import warm_dspy_pipeline

        await asyncio.to_thread(warm_dspy_pipeline)
    except Exception:
        logger.exception(
            "DSPy warm-up failed; it will be configured lazily on first /chat request instead."
        )
        if os.getenv("DSPY_ARTIFACT_URI"):
            # A pinned, invalid release must never silently serve baseline prompts.
            return
    mark_dspy_warm()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Started here rather than at import time so the port is only bound by the
    # process that actually serves, not by anything that merely imports
    # app.main (alembic, the test suite, `fastapi run`'s reloader parent).
    start_metrics_exporter()

    # Before the warm-up task, so the DSPy/litellm import chain it triggers is
    # itself traced. That chain is the slowest thing a cold pod does, and a
    # trace that starts after it hides exactly the part worth seeing.
    configure_tracing("palladium-api")

    # Fire-and-forget: don't await, so lifespan startup (and thus port
    # binding) isn't blocked on the dspy/litellm import chain.
    warm_task = asyncio.create_task(_warm_dspy_pipeline())
    app.state.dspy_warm_task = warm_task

    # The buffers-retained gauge, which used to be the worker's alone. It moved
    # here when the worker gained a scale-to-zero floor
    # (deploy/overlays/prod/keda-worker.yaml): the alert it feeds is an ABSENCE
    # condition over 10 minutes, so a metric only written by worker pods would
    # page every time the pool sat idle that long, which is now the expected
    # steady state rather than an outage. builder never drops below 2 replicas,
    # so hosting it here keeps the series continuous. The worker still runs the
    # same loop; both report the same instance-wide number and the alert already
    # reduces with REDUCE_MAX. See buffer_gauge_loop's docstring.
    gauge_task = asyncio.create_task(buffer_gauge_loop())
    try:
        yield
    finally:
        gauge_task.cancel()
        with suppress(asyncio.CancelledError):
            await gauge_task

        # A SIGTERM landing mid-cold-start leaves this task partway through the
        # import chain. Cancel and await it so shutdown isn't held open by it
        # and asyncio doesn't log "Task was destroyed but it is pending".
        if not warm_task.done():
            warm_task.cancel()
            with suppress(asyncio.CancelledError):
                await warm_task

        # Flushes anything the publisher has batched but not yet sent. Skipping
        # this drops turns that were accepted by /chat but never reached the
        # topic. The user watches a stream that no worker will ever write to.
        pubsub.close()
        await close_valkey()
        # Last: flushes spans describing the shutdown above.
        shutdown_tracing()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
    # Native request spans, plus child spans for dependency resolution, the
    # endpoint and serialization. They go through the global provider that
    # configure_tracing() installs, looked up per request, so a process with no
    # tracing configured (local, tests) emits nothing.
    telemetry={
        # Off, or tracing silently loses LangSmith. FastAPI's auto-configure runs
        # on the lifespan startup message, before the lifespan body above, and
        # with Managed OTel's injected OTEL_EXPORTER_OTLP_ENDPOINT it installs a
        # global TracerProvider of its own. The global can only be set once, so
        # configure_tracing()'s provider (LangSmith exporter, service.name) would
        # then be refused with a single warning. It would also start pushing
        # OTLP metrics and logs that GMP and stdout already carry.
        "auto_configure": False,
        # HTTP metrics belong to prometheus-fastapi-instrumentator (see
        # app/core/metrics.py). Inert today, as no OTel MeterProvider exists, but
        # adding one later would otherwise double-count every request.
        "metrics": False,
        # Load-test requests too: this span starts outside LoadTestMiddleware,
        # before the flag the tracing sampler drops everything else by is set.
        # See _build_load_test_sampler in app/core/tracing.py.
        "exclude": lambda scope: (
            scope.get("path") in PROBE_PATHS or is_load_test_request(scope)
        ),
    },
)

if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# add_middleware, so this wraps outside the router but inside CORS. Registered
# as a raw ASGI class rather than @app.middleware("http") on purpose. The
# latter is BaseHTTPMiddleware, which runs the endpoint in a separate task and
# would lose the ContextVar this sets. See app/core/loadtest.py.
app.add_middleware(LoadTestMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)

# After include_router: the instrumentator reads the route table to label
# timings by route template, so routes registered afterwards would be recorded
# under their raw path instead. Module level, not lifespan. Adding middleware
# to a running app raises RuntimeError.
instrument_metrics(app)
