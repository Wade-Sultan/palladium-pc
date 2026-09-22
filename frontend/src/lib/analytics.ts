/**
 * Google Analytics (GA4) configuration and the internal-traffic exclusion that
 * goes with it.
 *
 * Two things here are deliberate:
 *
 * 1. The measurement ID is a literal default rather than a required env var.
 *    Both `.env` files are gitignored, so a missing Vercel variable would mean
 *    "analytics silently off in production" — the failure nobody notices for a
 *    month. The ID is public (it ships in the page source either way), so
 *    hardcoding it costs nothing and fails loudly-in-the-right-direction.
 *
 * 2. Internal traffic is excluded client-side, by identity, not by IP filter in
 *    the GA console. IP filters break the moment you're on a phone, a VPN or a
 *    coffee shop; a signed-in email does not.
 */

export const GA_MEASUREMENT_ID =
  process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-B7Z92SVYXV"

/** Manual kill switch, so internal traffic can also be excluded when signed out. */
const OPT_OUT_KEY = "palladium:ga-optout"

/**
 * Who counts as internal. An entry beginning with "@" matches a whole domain;
 * anything else is an exact address. Override (not extend) with
 * NEXT_PUBLIC_INTERNAL_EMAILS, comma-separated.
 */
const DEFAULT_INTERNAL_EMAILS = ["wadesultan@gmail.com", "@palladiumtech.ai"]

const INTERNAL_EMAILS = (
  process.env.NEXT_PUBLIC_INTERNAL_EMAILS
    ? process.env.NEXT_PUBLIC_INTERNAL_EMAILS.split(",")
    : DEFAULT_INTERNAL_EMAILS
)
  .map((entry) => entry.trim().toLowerCase())
  .filter(Boolean)

export function isInternalEmail(email: string | null | undefined): boolean {
  if (!email) return false
  const normalized = email.trim().toLowerCase()
  return INTERNAL_EMAILS.some((entry) =>
    entry.startsWith("@") ? normalized.endsWith(entry) : normalized === entry,
  )
}

/**
 * Whether the tag should load at all. Preview deploys and `npm run dev` share
 * the production property otherwise, which pollutes it with traffic that is
 * all internal by definition.
 */
export function analyticsEnabled(): boolean {
  if (!GA_MEASUREMENT_ID) return false
  const vercelEnv = process.env.NEXT_PUBLIC_VERCEL_ENV
  if (vercelEnv) return vercelEnv === "production"
  return process.env.NODE_ENV === "production"
}

export function readOptOut(): boolean {
  try {
    return window.localStorage.getItem(OPT_OUT_KEY) === "1"
  } catch {
    // Private mode / blocked storage: treat as "not opted out".
    return false
  }
}

export function setOptOut(optOut: boolean): void {
  try {
    if (optOut) window.localStorage.setItem(OPT_OUT_KEY, "1")
    else window.localStorage.removeItem(OPT_OUT_KEY)
  } catch {
    // Nothing useful to do; the in-memory decision for this page still holds.
  }
}

/**
 * `?ga=off` sets the opt-out on this browser, `?ga=on` clears it. Lets a
 * signed-out internal browser (or a second device) be excluded without a code
 * change. Returns the resulting opt-out state.
 */
export function applyOptOutFromQuery(search: string): boolean {
  const value = new URLSearchParams(search).get("ga")
  if (value === "off") setOptOut(true)
  else if (value === "on") setOptOut(false)
  return readOptOut()
}

/**
 * GA's documented per-property kill switch. Honoured at send time, so flipping
 * it after gtag.js has loaded still stops every subsequent hit — which is what
 * makes "internal user signs in mid-session" work.
 */
export function setGaDisabled(disabled: boolean): void {
  ;(window as unknown as Record<string, boolean>)[
    `ga-disable-${GA_MEASUREMENT_ID}`
  ] = disabled
}
