"use client"

import posthog from "posthog-js"
import { useEffect } from "react"
import { useAnalyticsConsent } from "@/hooks/useAnalyticsConsent"
import { POSTHOG_HOST, POSTHOG_KEY, POSTHOG_UI_HOST } from "@/lib/analytics"

/**
 * PostHog, initialised only once this browser is known not to be internal.
 *
 * Deliberately *not* wired through `instrumentation-client.ts`, which is what
 * PostHog's Next.js guide suggests. That file runs before React mounts and so
 * before Firebase can say who is signed in, so it would capture the internal
 * user's `$pageview` and then be told to stop. Same reasoning as the GA tag;
 * `useAnalyticsConsent` holds the rule for both.
 *
 * `api_host` is a first-party relay path rather than PostHog's own hostname;
 * `next.config.mjs` holds the rewrites behind it.
 *
 * `defaults` pins the SDK's behaviour snapshot, matching PostHog's current
 * Next.js docs. It is what sets `capture_pageview: 'history_change'`, so
 * client-side App Router navigations are captured without a route listener
 * here. Newer snapshots exist (through '2026-08-30') and only add
 * session-recording options; bump deliberately, not reflexively.
 */
export default function PostHogAnalytics() {
  const consent = useAnalyticsConsent()

  useEffect(() => {
    if (!POSTHOG_KEY || consent === "pending") return

    if (!posthog.__loaded) {
      // Never boot the SDK for internal traffic: an instance that has never
      // loaded cannot leak a page view, whereas one that loads and then opts
      // out has already written persistence and sent its first event.
      if (consent === "block") return
      posthog.init(POSTHOG_KEY, {
        api_host: POSTHOG_HOST,
        ui_host: POSTHOG_UI_HOST,
        defaults: "2026-05-30",
      })
      return
    }

    // Loaded already, so this is a sign-in or sign-out mid-session.
    if (consent === "block") posthog.opt_out_capturing()
    else if (posthog.has_opted_out_capturing()) posthog.opt_in_capturing()
  }, [consent])

  return null
}
