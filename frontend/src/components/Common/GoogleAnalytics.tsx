"use client"

import Script from "next/script"
import { useEffect } from "react"
import { useAnalyticsConsent } from "@/hooks/useAnalyticsConsent"
import { GA_MEASUREMENT_ID, setGaDisabled } from "@/lib/analytics"

/**
 * The gtag.js tag, held back until `useAnalyticsConsent` has ruled on this
 * browser. Nothing is injected while that decision is pending, because
 * `gtag('config', ...)` sends a page_view immediately — see the hook for why
 * that ordering matters.
 *
 * A later change (an internal user signing in, or signing out) is handled by
 * the `ga-disable-*` flag, which gtag re-reads on every hit. Unmounting the
 * <script> element would not help: it does not unload gtag.
 */
export default function GoogleAnalytics() {
  const consent = useAnalyticsConsent()

  useEffect(() => {
    if (consent === "pending") return
    setGaDisabled(consent === "block")
  }, [consent])

  if (consent !== "allow") return null

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
