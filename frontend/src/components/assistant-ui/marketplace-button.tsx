import type { IconType } from "react-icons"
import { Button } from "@/components/ui/button"

/**
 * A single marketplace buy button: the brand's icon as a link to the
 * marketplace. Renders as a disabled button when no url is available so the
 * marketplace stays visible. `className` carries the per-brand hover-border
 * effect (see .mp-btn-* in index.css).
 */
export function MarketplaceButton({
  url,
  label,
  icon: Icon,
  className,
  partLabel,
}: {
  url: string | null | undefined
  label: string
  icon: IconType
  className?: string
  partLabel: string
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="icon-sm"
      className={className}
      disabled={!url}
      title={`Buy on ${label}`}
      aria-label={`Buy ${partLabel} on ${label}`}
      asChild={!!url}
    >
      {url ? (
        <a href={url} target="_blank" rel="noopener noreferrer sponsored">
          <Icon className="size-4" />
        </a>
      ) : (
        <Icon className="size-4" />
      )}
    </Button>
  )
}
