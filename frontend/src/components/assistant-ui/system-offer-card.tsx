"use client"

import type { DataMessagePartComponent } from "@assistant-ui/react"
import { useAssistantTransportSendCommand } from "@assistant-ui/react"
import { CheckIcon, CpuIcon, WrenchIcon } from "lucide-react"
import { useEffect, useState } from "react"
import { FaAmazon, FaEbay } from "react-icons/fa6"
import { useTurnRunning } from "@/components/assistant-ui/case-card"
import { MarketplaceButton } from "@/components/assistant-ui/marketplace-button"
import { AffiliateDisclosure } from "@/components/Common/AffiliateDisclosure"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { fetchListingsByPart, type PartListings } from "@/lib/listings"
import { shortFamilyName } from "@/lib/systems"
import { cn, formatCents } from "@/lib/utils"
import type {
  CustomEstimate,
  SystemOfferData,
  SystemOption,
} from "@/types/build"

const CUSTOM = "custom"

function useListings(partIds: string[]) {
  const [listings, setListings] = useState<Record<string, PartListings>>({})
  const key = partIds.join(",")
  useEffect(() => {
    let cancelled = false
    fetchListingsByPart(key.split(",").filter(Boolean)).then((result) => {
      if (!cancelled) setListings(result)
    })
    return () => {
      cancelled = true
    }
  }, [key])
  return listings
}

function BuyButtons({
  system,
  listings,
}: {
  system: SystemOption
  listings?: PartListings
}) {
  return (
    <div className="flex shrink-0 items-center gap-1">
      <MarketplaceButton
        url={listings?.amazon?.url}
        label="Amazon"
        icon={FaAmazon}
        className="mp-btn mp-btn-amazon"
        partLabel={system.name}
      />
      <MarketplaceButton
        url={listings?.ebay?.url}
        label="eBay"
        icon={FaEbay}
        className="mp-btn mp-btn-ebay"
        partLabel={system.name}
      />
    </div>
  )
}

function estimateGpuLine(estimate: CustomEstimate): string | null {
  if (!estimate.gpu_name) return null
  const count = estimate.gpu_count > 1 ? `${estimate.gpu_count}× ` : ""
  return `${count}${estimate.gpu_name}`
}

/**
 * The side by side. Only rows both columns can honestly fill: the estimate
 * knows its price and its GPU memory, and nothing about bandwidth or noise, so
 * those live in the strengths and limitations lists instead of a row with a
 * blank on one side that reads as "zero".
 */
function Comparison({ data }: { data: SystemOfferData }) {
  const { primary, estimate } = data
  const gpuLine = estimate ? estimateGpuLine(estimate) : null
  const rows: [string, string, string][] = [
    [
      "Price",
      `~${formatCents(primary.price_cents)}`,
      estimate ? `~${formatCents(estimate.total_cents)}` : "n/a",
    ],
  ]
  if (data.reason === "memory") {
    rows.push([
      "Memory for models",
      `${primary.gpu_memory_gb} GB`,
      estimate?.gpu_memory_gb != null ? `${estimate.gpu_memory_gb} GB` : "n/a",
    ])
  } else {
    rows.push(["Memory", `${primary.unified_memory_gb} GB unified`, "varies"])
  }
  if (gpuLine) rows.push(["Graphics", primary.chip, gpuLine])

  return (
    <div className="overflow-hidden rounded-lg border text-sm">
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] bg-muted/50 px-3 py-2 font-medium text-xs">
        <span />
        <span>{shortFamilyName(primary)}</span>
        <span>Custom PC (estimate)</span>
      </div>
      {rows.map(([label, system, custom]) => (
        <div
          key={label}
          className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] border-t px-3 py-2"
        >
          <span className="text-muted-foreground">{label}</span>
          <span>{system}</span>
          <span>{custom}</span>
        </div>
      ))}
    </div>
  )
}

function Tradeoffs({ system }: { system: SystemOption }) {
  if (!system.strengths.length && !system.limitations.length) return null
  return (
    <div className="grid gap-3 text-sm sm:grid-cols-2">
      {system.strengths.length > 0 && (
        <div>
          <p className="mb-1 font-medium text-xs uppercase tracking-wide">
            Good at
          </p>
          <ul className="list-disc space-y-0.5 pl-4 text-muted-foreground">
            {system.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}
      {system.limitations.length > 0 && (
        <div>
          <p className="mb-1 font-medium text-xs uppercase tracking-wide">
            Watch out for
          </p>
          <ul className="list-disc space-y-0.5 pl-4 text-muted-foreground">
            {system.limitations.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/**
 * A complete-system offer: a ready-made machine the backend's rules found may
 * suit the user better than a custom build. Rendered by
 * makeAssistantDataUI({name: "system_offer"}).
 *
 * Works exactly like the case picker (see CaseOptionsCard), for the same
 * reasons: an answer is a `select-system` command on an ordinary /chat request,
 * so it gets worker dispatch and resume-on-reload for free, and `chosen` is set
 * by the server's re-emit rather than locally, so the card can never disagree
 * with what the backend actually did. `pending` only bridges the click.
 */
export const SystemOfferCard: DataMessagePartComponent<SystemOfferData> = (
  props,
) => {
  const data = props.data as SystemOfferData
  const sendCommand = useAssistantTransportSendCommand()
  const turnRunning = useTurnRunning()
  const [pending, setPending] = useState<string | null>(null)
  const systems = [data.primary, ...data.alternates]
  const listings = useListings(systems.map((s) => s.part_id))

  const resolved = data.chosen !== null
  const locked = resolved || pending !== null || turnRunning
  const choose = (choice: string) => {
    if (locked) return
    setPending(choice)
    sendCommand({ type: "select-system", token: data.token, choice })
  }

  const chosenSystem = systems.find((s) => s.part_id === data.chosen)
  if (resolved) {
    return (
      <div className="my-2 flex w-full max-w-(--thread-max-width) items-center justify-between gap-3 rounded-lg border px-3 py-2">
        <div className="flex min-w-0 items-center gap-2 text-sm">
          <CheckIcon className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate">
            {chosenSystem
              ? `You chose the ${chosenSystem.name}`
              : `You chose a custom build over the ${shortFamilyName(data.primary)}`}
          </span>
        </div>
        {chosenSystem && (
          <BuyButtons
            system={chosenSystem}
            listings={listings[chosenSystem.part_id]}
          />
        )}
      </div>
    )
  }

  const { primary } = data
  return (
    <div className="my-2 flex w-full max-w-(--thread-max-width) flex-col gap-1">
      <Card className="w-full">
        <CardHeader>
          <p className="flex items-center gap-1.5 text-muted-foreground text-xs uppercase tracking-wide">
            <CpuIcon className="size-3.5" />
            Ready-made alternative
          </p>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">{primary.name}</CardTitle>
            <Badge variant="secondary">
              ~{formatCents(primary.price_cents)}*
            </Badge>
          </div>
          {primary.summary && (
            <CardDescription>{primary.summary}</CardDescription>
          )}
          <p className="text-muted-foreground text-xs">
            {primary.chip} · {primary.unified_memory_gb} GB unified memory ·{" "}
            {primary.bandwidth_gbps} GB/s · {primary.os}
            {data.memory_need_gb != null &&
              ` · your models need ~${data.memory_need_gb} GB`}
          </p>
          <AffiliateDisclosure className="mt-1" />
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Comparison data={data} />
          <Tradeoffs system={primary} />
          <div className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2">
            <span className="text-sm">Where to buy</span>
            <BuyButtons system={primary} listings={listings[primary.part_id]} />
          </div>
          {data.alternates.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="font-medium text-xs uppercase tracking-wide">
                Also worth a look
              </p>
              {data.alternates.map((alt) => (
                <div
                  key={alt.part_id}
                  className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-sm">{alt.name}</p>
                    <p className="text-muted-foreground text-xs">
                      {alt.gpu_memory_gb} GB for models · {alt.bandwidth_gbps}{" "}
                      GB/s · {alt.os} · ~{formatCents(alt.price_cents)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <BuyButtons system={alt} listings={listings[alt.part_id]} />
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={locked}
                      onClick={() => choose(alt.part_id)}
                    >
                      {pending === alt.part_id ? "Choosing…" : "Choose"}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
        <CardFooter className="flex flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            className="w-full sm:flex-1"
            disabled={locked}
            onClick={() => choose(primary.part_id)}
          >
            {pending === primary.part_id
              ? "Choosing…"
              : `Go with the ${shortFamilyName(primary)}`}
          </Button>
          <Button
            type="button"
            variant="outline"
            className={cn("w-full sm:flex-1")}
            disabled={locked}
            onClick={() => choose(CUSTOM)}
          >
            <WrenchIcon className="size-4" />
            {pending === CUSTOM
              ? "Starting your build…"
              : "Build a custom PC instead"}
          </Button>
        </CardFooter>
      </Card>
      <p className="px-1 text-muted-foreground text-xs">
        *Approximate prices. The custom figure is an estimate, not a validated
        build.
      </p>
    </div>
  )
}
