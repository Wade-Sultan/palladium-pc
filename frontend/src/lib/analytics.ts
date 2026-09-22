/**
 * Analytics configuration — Google Analytics (GA4) and PostHog — plus the
 * internal-traffic exclusion both of them share.
 *
 * Three things here are deliberate:
 *
 * 1. Both vendor credentials are literal defaults rather than required env
 *    vars. Both `.env` files are gitignored, so a missing Vercel variable would
 *    mean "analytics silently off in production" — the failure nobody notices
 *    for a month. A GA measurement ID and a PostHog project token are both
 *    public write-only ingestion keys that ship in the client bundle either
 *    way, so committing them costs nothing and removes a deploy-time footgun.
 *    Neither is a secret; do not treat them as one, and do not put anything
 *    that *is* a secret in this file — it is all client-side.
 *
 * 2. The env vars still win where they are set, which is what makes a scratch
 *    GA property or a throwaway PostHog project possible without a code change.
 *
 * 3. Internal traffic is excluded client-side, by identity, not by IP filter in
 *    the GA console or an "internal users" rule in PostHog. Those break the
 *    moment you're on a phone, a VPN or a coffee shop; a signed-in email does
 *    not. One rule decides for both vendors, so they can never disagree about
 *    whose traffic counts.
 */

export const GA_MEASUREMENT_ID =
  process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-B7Z92SVYXV"

/**
 * Both env names are read because PostHog's docs renamed this variable:
 * `NEXT_PUBLIC_POSTHOG_KEY` is what older guides and the setup wizard write,
 * `NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN` is the current one. Next inlines each
 * literal `process.env.NEXT_PUBLIC_*` reference at build time, so reading both
 * costs nothing at runtime.
 */
export const POSTHOG_KEY =
  process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN ||
  process.env.NEXT_PUBLIC_POSTHOG_KEY ||
  "phc_pTE7SNyyTL7QBNEkaHHtZdiDde2pejsVhyNUHjPN39r6"

/**
 * PostHog is addressed through a first-party path, not `us.i.posthog.com`
 * directly: that hostname is on every mainstream blocklist, and this audience
 * blocks more than most. The rewrites in `next.config.mjs` are the other half
 * of this — the path here must match POSTHOG_RELAY_PATH there or every event
 * 404s silently.
 *
 * Relative, so it follows whatever origin the app is served from. It is
 * prefixed with the base path because Next prefixes rewrite sources the same
 * way, keeping the two aligned if NEXT_PUBLIC_BASE_PATH is ever set.
 *
 * Setting NEXT_PUBLIC_POSTHOG_HOST to a full URL bypasses the proxy, which is
 * how you tell "the proxy is broken" apart from "PostHog is broken".
 */
export const POSTHOG_HOST =
  process.env.NEXT_PUBLIC_POSTHOG_HOST ||
  `${process.env.NEXT_PUBLIC_BASE_PATH || ""}/relay`

/**
 * Where the SDK sends you for "view in PostHog" links (the toolbar, session
 * recordings). Not an ingestion endpoint, so it is never proxied — the relay
 * path would not serve the app UI.
 */
export const POSTHOG_UI_HOST = "https://us.posthog.com"

/**
 * Manual kill switch, so internal traffic can also be excluded when signed out.
 * One key for both vendors — a browser is either counted or it isn't.
 */
const OPT_OUT_KEY = "palladium:analytics-optout"

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
 * `?analytics=off` sets the opt-out on this browser, `?analytics=on` clears it
 * (`?ga=` is accepted as an alias). Lets a signed-out internal browser, or a
 * second device, be excluded without a code change. Returns the resulting
 * opt-out state.
 */
export function applyOptOutFromQuery(search: string): boolean {
  const params = new URLSearchParams(search)
  const value = params.get("analytics") ?? params.get("ga")
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
