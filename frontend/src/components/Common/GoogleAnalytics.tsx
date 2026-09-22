"use client"

import { onAuthStateChanged } from "firebase/auth"
import Script from "next/script"
import { useEffect, useState } from "react"
import {
  analyticsEnabled,
  applyOptOutFromQuery,
  GA_MEASUREMENT_ID,
  isInternalEmail,
  setGaDisabled,
} from "@/lib/analytics"
import { auth } from "@/lib/firebase"

/**
 * The gtag.js tag, held back until Firebase has told us who (if anyone) is
 * signed in.
 *
 * The ordering is the whole point. `gtag('config', ...)` sends a page_view
 * immediately, and Firebase restores a session asynchronously — so a tag that
 * loaded on mount would have already reported the internal user's visit by the
 * time we learned they were internal. Nothing is injected while the decision is
 * pending; the cost is the few hundred ms of auth restore on the first page
 * view, paid by everyone, in exchange for an exclusion that cannot race.
 *
 * Later changes (an internal user signing in, or signing out) are handled by
 * the `ga-disable-*` flag instead, which gtag re-reads on every hit.
 */
export default function GoogleAnalytics() {
  const [decision, setDecision] = useState<"pending" | "allow" | "block">(
    "pending",
  )

  useEffect(() => {
    if (!analyticsEnabled()) {
      setDecision("block")
      return
    }

    const optedOut = applyOptOutFromQuery(window.location.search)

    const unsubscribe = onAuthStateChanged(auth, (user) => {
      const internal = optedOut || isInternalEmail(user?.email)
      setGaDisabled(internal)
      setDecision(internal ? "block" : "allow")
    })
    return () => unsubscribe()
  }, [])

  // Once blocked, the tag is never injected; once allowed, it stays mounted and
  // is muted through `ga-disable-*` rather than unmounted, because removing the
  // <script> element does not unload gtag.
  if (decision !== "allow") return null

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
        strategy="afterInteractive"
      />
      <Script id="ga-init" strategy="afterInteractive">
        {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GA_MEASUREMENT_ID}');`}
      </Script>
    </>
  )
}
