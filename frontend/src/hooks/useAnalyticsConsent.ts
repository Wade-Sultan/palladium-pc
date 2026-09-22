"use client"

import { onAuthStateChanged } from "firebase/auth"
import { useEffect, useState } from "react"
import {
  analyticsEnabled,
  applyOptOutFromQuery,
  isInternalEmail,
} from "@/lib/analytics"
import { auth } from "@/lib/firebase"

/**
 * "pending" until Firebase has said who is signed in. Vendors must treat it as
 * "do not load yet" rather than "do not count this hit" — see below.
 */
export type AnalyticsConsent = "pending" | "allow" | "block"

/**
 * The single decision about whether this browser's traffic counts, shared by
 * every analytics vendor so they cannot drift apart.
 *
 * The "pending" state is the load-bearing part. Both SDKs report a page view
 * the moment they initialise, and Firebase restores a session asynchronously —
 * so anything that boots on mount has already reported the internal user's
 * visit by the time we learn they were internal. Callers must hold off
 * entirely while pending; the cost is the few hundred ms of auth restore on
 * the first page view, paid by everyone, in exchange for an exclusion that
 * cannot race.
 *
 * After that first decision the subscription stays live, so signing in or out
 * mid-session flips the value. By then each SDK has loaded, so vendors handle
 * the change with their own kill switch rather than by unloading.
 */
export function useAnalyticsConsent(): AnalyticsConsent {
  const [consent, setConsent] = useState<AnalyticsConsent>("pending")

  useEffect(() => {
    if (!analyticsEnabled()) {
      setConsent("block")
      return
    }

    const optedOut = applyOptOutFromQuery(window.location.search)

    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setConsent(optedOut || isInternalEmail(user?.email) ? "block" : "allow")
    })
    return () => unsubscribe()
  }, [])

  return consent
}
