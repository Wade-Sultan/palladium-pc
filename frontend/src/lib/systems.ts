import type { SystemOption } from "@/types/build"

/** "DGX Spark (GB10)" reads as "DGX Spark" on a button or in a sentence. */
export const shortFamilyName = (system: Pick<SystemOption, "family_name">) =>
  system.family_name.replace(/\s*\(.*\)\s*$/, "")
