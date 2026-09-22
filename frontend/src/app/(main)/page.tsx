/*
 * Shadowed by the `/` redirect in next.config.mjs, which answers before
 * routing reaches this file. Kept as the fallback if that entry is ever
 * removed. See the comment there.
 */
import { redirect } from "next/navigation"

export default function Page() {
  redirect("/build/new")
}
