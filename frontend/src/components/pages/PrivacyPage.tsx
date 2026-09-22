import Link from "next/link"

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-2.5">
      <h2 className="font-medium tracking-tight">{title}</h2>
      <div className="space-y-2.5 text-sm text-muted-foreground">
        {children}
      </div>
    </section>
  )
}

const LAST_UPDATED = "21 September 2026"

export default function PrivacyPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Privacy</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            What Palladium collects, who else sees it, and how to opt out · Last
            updated {LAST_UPDATED}
          </p>
        </div>

        <div className="space-y-8">
          <Section title="The short version">
            <p>
              Palladium keeps your account, the conversations you have with it,
              and the builds those conversations produce. It measures how the
              site is used. It does not sell your data, and it does not use your
              conversations to train models.
            </p>
            <p>
              The rest of this page is the detail behind those sentences,
              including the third parties involved and how to turn the
              measurement off.
            </p>
          </Section>

          <Section title="What you give us directly">
            <p>
              <span className="font-medium text-foreground">Your account.</span>{" "}
              Sign-in is handled by Firebase Authentication, a Google service.
              It holds your email address, your display name if you set one, and
              your password. Palladium never sees your password — if you sign in
              with Google, no password exists here at all. Alongside that,
              Palladium stores your email address and display name in its own
              database so builds can be attached to you.
            </p>
            <p>
              <span className="font-medium text-foreground">
                Your conversations and builds.
              </span>{" "}
              Every message you send and every reply you get is stored, along
              with the parts list produced from it. Kept with each conversation
              are the model names used, token counts and what the turn cost to
              run — the figures that tell us whether the system is working.
            </p>
            <p>
              <span className="font-medium text-foreground">
                Ratings and price alerts.
              </span>{" "}
              If you rate a build, that rating is stored against it. If you ask
              to be told when a part's price drops, Palladium stores your target
              price and emails you when it is reached.
            </p>
          </Section>

          <Section title="What happens to your conversations">
            <p>
              To answer you, Palladium sends the conversation to large language
              models it does not run itself. These are reached through
              OpenRouter, which routes each request to the model provider that
              serves it. Your messages therefore leave Palladium's servers and
              are processed by those providers under their own terms.
            </p>
            <p>
              Palladium does not use your conversations to train models, and
              does not sell or rent them. What it does use them for is running
              the product and understanding where the system gets things wrong.
            </p>
            <p>
              A practical consequence worth stating plainly: treat a Palladium
              conversation as you would any message typed into a website. It is
              a place to describe the machine you want, not a place to put
              anything confidential.
            </p>
          </Section>

          <Section title="Measurement">
            <p>
              Palladium uses Google Analytics and PostHog to see which pages are
              used and where the product is confusing, and Vercel's analytics
              for page performance. Between them these record the pages you
              visit, roughly where you are (derived from your IP address, not
              stored by us as a precise location), your browser and device type,
              and how you move through the site.
            </p>
            <p>
              PostHog is served through a path on this domain rather than
              PostHog's own. To be straightforward about why: content blockers
              block PostHog's hostname, and routing through our own domain means
              the measurement keeps working. It does not change what is
              collected, and the opt-out below still stops it.
            </p>
            <p>
              Neither tool receives your conversations or your build contents.
            </p>
          </Section>

          <Section title="Turning measurement off">
            {/*
              Plain anchors, not <Link>. The opt-out is read once on mount from
              window.location.search, so a client-side navigation would change
              the URL without re-running it and the link would appear to do
              nothing. A full page load is also the honest thing here: the
              reader can see the setting take effect.
            */}
            <p>
              Opening{" "}
              <a
                href="/privacy?analytics=off"
                className="font-medium text-foreground underline underline-offset-4"
              >
                this link
              </a>{" "}
              stops Google Analytics and PostHog for this browser, and it stays
              off until you clear your site data.{" "}
              <a
                href="/privacy?analytics=on"
                className="underline underline-offset-4"
              >
                This one
              </a>{" "}
              turns it back on. The setting is a single value in your browser's
              local storage; nothing about it is sent anywhere.
            </p>
            <p>
              Browser "Do Not Track" and "Global Privacy Control" signals are
              not currently honoured automatically. The link above is the
              reliable way to opt out.
            </p>
          </Section>

          <Section title="Cookies and local storage">
            <p>
              Google Analytics and PostHog each set their own cookies to tell
              one visit from the next. Firebase stores your sign-in session in
              the browser so you are not asked to log in on every page.
              Palladium itself stores two small values locally: your light or
              dark theme, and the measurement opt-out described above.
            </p>
            <p>
              Clearing your browser's site data for this domain removes all of
              it, including the opt-out.
            </p>
          </Section>

          <Section title="Who else your data reaches">
            <ul className="ml-4 list-disc space-y-2">
              <li>
                <span className="font-medium text-foreground">
                  Google Cloud
                </span>{" "}
                and <span className="font-medium text-foreground">Vercel</span>{" "}
                — hosting and databases. Everything Palladium stores lives here.
              </li>
              <li>
                <span className="font-medium text-foreground">
                  Firebase Authentication
                </span>{" "}
                (Google) — accounts and sign-in.
              </li>
              <li>
                <span className="font-medium text-foreground">OpenRouter</span>{" "}
                and the model providers it routes to — your conversations, as
                described above.
              </li>
              <li>
                <span className="font-medium text-foreground">Resend</span> —
                sends the price-drop emails, and so receives your email address
                when one goes out.
              </li>
              <li>
                <span className="font-medium text-foreground">
                  Google Analytics
                </span>{" "}
                and <span className="font-medium text-foreground">PostHog</span>{" "}
                — usage measurement.
              </li>
            </ul>
            <p>
              SerpApi is also used, to look up what parts cost. It is listed
              separately because nothing about you is sent to it: it receives a
              part's name and nothing else.
            </p>
          </Section>

          <Section title="Builds you share">
            <p>
              Sharing a build creates a link that anyone holding it can open
              without an account — that is the point of it. The page shows the
              parts list and nothing about you, but treat the link itself as
              public once you have sent it.
            </p>
          </Section>

          <Section title="Affiliate links">
            <p>
              The marketplace buttons on a build are affiliate links, and
              following one tells the marketplace you arrived from Palladium.
              What happens after that is covered by that marketplace's own
              privacy policy.{" "}
              <Link
                href="/about"
                className="underline underline-offset-4 hover:text-foreground"
              >
                How this works, and what it does not affect
              </Link>
              .
            </p>
          </Section>

          <Section title="Keeping and deleting">
            <p>
              Your account, conversations and builds are kept for as long as you
              have an account, because they are what the product shows you when
              you come back. Ask for your account to be deleted and it goes,
              along with the conversations and builds attached to it.
            </p>
            <p>
              Two things survive that deletion: emails already sent, which are
              out of our hands, and measurement records, which are not tied to
              your account in a way that lets us pick yours out.
            </p>
          </Section>

          <Section title="Your rights">
            <p>
              Depending on where you live, you may have the right to see a copy
              of what Palladium holds about you, to have it corrected, to have
              it deleted, and to object to it being used for measurement. Ask
              and it will be done — no charge, and no need to explain why.
            </p>
            <p>
              Palladium is an independent site run from the United States, and
              the services above are largely US-hosted. Using it means your data
              is handled there.
            </p>
          </Section>

          <Section title="Children">
            <p>
              Palladium is not intended for children under 13, and accounts are
              not knowingly created for them. If you believe a child has an
              account here, get in touch and it will be removed.
            </p>
          </Section>

          <Section title="Changes">
            <p>
              If this policy changes in a way that matters, the date at the top
              of this page changes with it. Material changes will be flagged in
              the product rather than left for you to notice.
            </p>
          </Section>

          <Section title="Getting in touch">
            <p>
              For anything on this page — a copy of your data, deletion, or a
              question — email{" "}
              <a
                href="mailto:privacy@palladiumtech.ai"
                className="font-medium text-foreground underline underline-offset-4"
              >
                privacy@palladiumtech.ai
              </a>
              .
            </p>
          </Section>
        </div>
      </div>
    </div>
  )
}
