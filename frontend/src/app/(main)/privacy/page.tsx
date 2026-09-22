import type { Metadata } from "next"

import PrivacyPage from "@/components/pages/PrivacyPage"

export const metadata: Metadata = {
  title: "Privacy | Palladium",
  description:
    "What Palladium collects, which third parties see it, and how to opt out of usage measurement.",
}

export default function Page() {
  return <PrivacyPage />
}
