"""Create the topics and subscriptions the app expects, against the emulator.

Run as a Job by the local overlay. Production does not need this: those
resources are provisioned out of band by an operator, and the app has never
created them itself. The emulator, by contrast, starts completely empty and
persists nothing, so something has to declare them on every boot.

USES THE APP'S OWN CLIENT LIBRARY, not gcloud or raw REST. The point of running
an emulator at all is to exercise the real publish/subscribe path, and the parts
most likely to be wrong are the ones the app depends on and the emulator only
partly implements — message ordering above all. Creating the subscription
through google-cloud-pubsub means a gap shows up here, at bootstrap, with a
clear error, rather than as turns silently running out of order later.

IDEMPOTENT. Re-running is a no-op, so Tilt can trigger it freely and a restarted
emulator can be repaired by triggering it again.

WHAT DEGRADES, AND LOUDLY. The emulator does not implement every field a real
subscription takes. Rather than trimming the request down to the lowest common
denominator, this asks for production's exact configuration first and falls back
one field at a time, printing what it lost. A local subscription missing its
dead-letter policy is fine; one missing message ordering is not, and that is the
one case here that fails outright instead of degrading — two turns in a
conversation running out of order is precisely the bug local testing exists to
catch.
"""

from __future__ import annotations

import os
import sys
import time

from google.api_core import exceptions
from google.cloud import pubsub_v1

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
TOPIC = os.environ["PUBSUB_TOPIC"]
SUBSCRIPTION = os.environ["PUBSUB_SUBSCRIPTION"]
# Same convention as the provisioning runbook: the dead-letter topic is the main
# topic's name with a -dead suffix, and it gets a subscription of its own so
# dead-lettered turns are inspectable rather than a black hole.
DEAD_TOPIC = f"{TOPIC}-dead"
DEAD_SUBSCRIPTION = f"{TOPIC}-dead-sub"

# Matches PUBSUB_ACK_EXTENSION_S, and Pub/Sub's own ceiling.
ACK_DEADLINE_S = 600
MAX_DELIVERY_ATTEMPTS = 5


def _wait_for_emulator(publisher: pubsub_v1.PublisherClient, attempts: int = 30) -> None:
    """Block until the emulator answers, or give up.

    The Deployment's readiness probe is a TCP check, which the JVM satisfies
    slightly before the gRPC service is actually serving. Listing topics is the
    cheapest call that proves the difference.
    """
    last: Exception | None = None
    for n in range(1, attempts + 1):
        try:
            list(publisher.list_topics(request={"project": f"projects/{PROJECT}"}))
            return
        except Exception as exc:  # noqa: BLE001 — any failure here means "not up yet"
            last = exc
            print(f"emulator not ready (attempt {n}/{attempts}): {type(exc).__name__}")
            time.sleep(2)
    raise SystemExit(f"emulator never became ready: {last}")


def _create_topic(publisher: pubsub_v1.PublisherClient, name: str) -> str:
    path = publisher.topic_path(PROJECT, name)
    try:
        publisher.create_topic(request={"name": path})
        print(f"created topic {name}")
    except exceptions.AlreadyExists:
        print(f"topic {name} already exists")
    return path


def _create_subscription(
    subscriber: pubsub_v1.SubscriberClient,
    name: str,
    topic_path: str,
    *,
    ordered: bool,
    dead_letter_topic: str | None = None,
) -> None:
    path = subscriber.subscription_path(PROJECT, name)

    full = {
        "name": path,
        "topic": topic_path,
        # NOT optional, and not a nicety. Two turns published for one
        # conversation must run in order or the second reads a history the first
        # has not finished writing. A real subscription cannot have this added
        # after creation either — it is delete-and-recreate there too.
        "enable_message_ordering": ordered,
        "ack_deadline_seconds": ACK_DEADLINE_S,
    }
    if dead_letter_topic:
        full["dead_letter_policy"] = {
            "dead_letter_topic": dead_letter_topic,
            "max_delivery_attempts": MAX_DELIVERY_ATTEMPTS,
        }

    # Most complete request first; drop the optional half if the emulator
    # rejects it, and say so rather than leaving a silent difference from prod.
    for request, note in (
        (full, None),
        (
            {k: v for k, v in full.items() if k != "dead_letter_policy"},
            "emulator rejected dead_letter_policy — a poison turn will redeliver "
            "here instead of dead-lettering. Prod still DLQs it.",
        ),
    ):
        try:
            subscriber.create_subscription(request=request)
            print(f"created subscription {name} (ordering={ordered})")
            if note:
                print(f"  DEGRADED: {note}")
            return
        except exceptions.AlreadyExists:
            print(f"subscription {name} already exists")
            return
        except (exceptions.InvalidArgument, exceptions.MethodNotImplemented) as exc:
            if request is full:
                print(f"  retrying without dead_letter_policy: {exc.message}")
                continue
            # Ordering is the one field with no acceptable fallback.
            raise SystemExit(
                f"emulator could not create subscription {name}: {exc.message}\n"
                "Message ordering is required — without it a conversation's turns "
                "can run out of order, which is the class of bug this local "
                "environment exists to catch."
            ) from exc


def main() -> int:
    if not os.environ.get("PUBSUB_EMULATOR_HOST"):
        raise SystemExit(
            "PUBSUB_EMULATOR_HOST is unset. Refusing to run: without it these "
            "clients talk to REAL Pub/Sub, and this would create topics in an "
            "actual GCP project."
        )
    print(f"bootstrapping {os.environ['PUBSUB_EMULATOR_HOST']} (project {PROJECT})")

    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    # CLOSED EXPLICITLY, in a finally. Both clients hold gRPC channels with
    # non-daemon background threads, and an interpreter that has finished main()
    # still waits on those at shutdown — so without this the Job sits in Running
    # for minutes after printing "complete". That is not merely untidy: Tilt and
    # `kubectl wait` treat the Job as incomplete for the whole delay, and the
    # worker (which resource_deps on it) starts against a subscription that does
    # not exist yet and crash-loops until it does.
    try:
        _wait_for_emulator(publisher)

        # Dead-letter topic first: the subscription below references it at
        # creation time.
        dead_path = _create_topic(publisher, DEAD_TOPIC)
        topic_path = _create_topic(publisher, TOPIC)

        _create_subscription(
            subscriber,
            SUBSCRIPTION,
            topic_path,
            ordered=True,
            dead_letter_topic=dead_path,
        )
        # No ordering on the dead-letter subscription: it exists to be read by a
        # human, and there is no per-conversation sequence left to preserve.
        _create_subscription(subscriber, DEAD_SUBSCRIPTION, dead_path, ordered=False)
    finally:
        # Best effort, and never allowed to mask a real failure above: a client
        # that will not close cleanly does not make the topics any less created.
        # The two clients do not share a shutdown method: SubscriberClient has
        # close(), PublisherClient has stop(). Try both names rather than
        # asserting which is which, so a library rename degrades to a warning
        # instead of a traceback after the work is already done.
        for client in (subscriber, publisher):
            for method in ("close", "stop"):
                shutdown = getattr(client, method, None)
                if shutdown is None:
                    continue
                try:
                    shutdown()
                except Exception as exc:  # noqa: BLE001
                    print(f"  (ignoring {type(client).__name__}.{method}(): {exc})")
                break
            else:
                print(f"  (no shutdown method on {type(client).__name__})")

    print("pub/sub bootstrap complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
