import { dirname } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))

/**
 * Path that PostHog traffic is relayed through. Kept in sync with
 * POSTHOG_HOST in src/lib/analytics.ts — the rewrites below are the server
 * half of that setting, and changing one without the other silently drops
 * every event.
 *
 * Deliberately not PostHog's suggested "/ingest": that literal string is now
 * itself a blocklist entry in several filter lists, which defeats the point of
 * proxying. Any unremarkable first-party path works.
 */
const POSTHOG_RELAY_PATH = "/relay"

/** @type {import('next').NextConfig} */
const NextConfig = {
  ...(process.env.NEXT_PUBLIC_BASE_PATH && {
    basePath: process.env.NEXT_PUBLIC_BASE_PATH,
  }),

  /**
   * PostHog's API endpoints end in a trailing slash (`/e/`, `/flags/`). Next's
   * default is to 308-redirect those to the slashless form, which turns every
   * capture into a redirect PostHog's client does not follow — events vanish
   * with no error anywhere.
   *
   * The cost is that this is a global switch: `/about/` no longer redirects to
   * `/about`, so both spellings serve 200. Add per-page `alternates.canonical`
   * metadata if that ever matters for SEO.
   */
  skipTrailingSlashRedirect: true,

  /**
   * `/` and `/newbuild` are entry points that both land on `/build/new`.
   *
   * The page files behind them call `redirect()`, but those routes are
   * statically prerendered, so that redirect resolves in the browser after
   * hydration rather than over HTTP — the server answers 200 with the whole
   * app shell first. Two costs: every visitor downloads and hydrates a page
   * they are about to leave, and the analytics tags in the root layout mount
   * while the URL is still `/`, racing the redirect. Whichever wins decides
   * whether the visit is attributed to `/` or `/build/new`, so entry-page data
   * ends up split between them.
   *
   * Redirecting here happens before any of that, so the browser never renders
   * the shell on the way through.
   *
   * Temporary (307) rather than permanent on purpose: a 308 is cached hard by
   * browsers and tells search engines to treat `/build/new` as canonical,
   * which is painful to walk back the day `/` becomes a real landing page.
   * Switch to `permanent: true` only once that is settled.
   *
   * The page files stay as a fallback: if these entries are ever removed, `/`
   * goes back to redirecting slowly rather than 404ing.
   */
  async redirects() {
    return [
      // The optional trailing slash matters because skipTrailingSlashRedirect
      // above stops Next normalising `/newbuild/` to `/newbuild` first, which
      // would otherwise miss this rule and fall through to the slow path.
      { source: "/newbuild(/)?", destination: "/build/new", permanent: false },
      { source: "/", destination: "/build/new", permanent: false },
    ]
  },

  async rewrites() {
    return [
      // Order matters — Next matches sequentially, and the catch-all below
      // would otherwise swallow the asset routes. Static assets and the
      // snippet array live on a different origin from the ingestion API.
      {
        source: `${POSTHOG_RELAY_PATH}/static/:path*`,
        destination: "https://us-assets.i.posthog.com/static/:path*",
      },
      {
        source: `${POSTHOG_RELAY_PATH}/array/:path*`,
        destination: "https://us-assets.i.posthog.com/array/:path*",
      },
      {
        source: `${POSTHOG_RELAY_PATH}/:path*`,
        destination: "https://us.i.posthog.com/:path*",
      },
    ]
  },
}

export default NextConfig
