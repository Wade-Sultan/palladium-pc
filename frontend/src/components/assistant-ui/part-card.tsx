"use client"

import type { DataMessagePartComponent } from "@assistant-ui/react"
import { useEffect, useState } from "react"
import { AffiliateDisclosure } from "@/components/Common/AffiliateDisclosure"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { fetchListingsByPart, type PartListings } from "@/lib/listings"
import type { PartData } from "@/types/build"

export const PartCard: DataMessagePartComponent<PartData> = ({ data }) => {
  const [listings, setListings] = useState<PartListings>({})
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let cancelled = false
    setListings({})
    setLoading(true)
    fetchListingsByPart([data.part_id]).then((result) => {
      if (!cancelled) {
        setListings(result[data.part_id] ?? {})
        setLoading(false)
      }
    })
    return () => {
      cancelled = true
    }
  }, [data.part_id])

  const links = Object.entries(listings).filter(([, listing]) => {
    if (!listing.is_active || !listing.url) return false
    try {
      return new URL(listing.url).protocol === "https:"
    } catch {
      return false
    }
  })
  return (
    <Card className="my-3 max-w-xl">
      <CardHeader>
        <p className="text-sm text-muted-foreground">
          Individual part · {data.component}
        </p>
        <CardTitle>{data.model}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Shown for reference. Your proposed build stays the same; fit has not
          been checked.
        </p>
        <div className="flex flex-wrap gap-2">
          {links.map(([marketplace, listing]) => (
            <Button asChild variant="outline" key={marketplace}>
              <a
                href={listing.url!}
                target="_blank"
                rel="noopener noreferrer sponsored"
              >
                View on {marketplace === "amazon" ? "Amazon" : "eBay"}
              </a>
            </Button>
          ))}
        </div>
        {loading ? (
          <output className="block text-sm">Loading listings…</output>
        ) : links.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No listings are available right now.
          </p>
        ) : (
          <AffiliateDisclosure />
        )}
      </CardContent>
    </Card>
  )
}
