import Image from "next/image"

interface UnderConstructionProps {
  /** Optional page name shown below the main message */
  pageName?: string
}

export function UnderConstruction({ pageName }: UnderConstructionProps) {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="flex flex-col items-center gap-6 text-center max-w-sm">
        <Image
          src="/assets/images/palladium-logo.svg"
          alt="Palladium"
          width={64}
          height={64}
          className="animate-[spin_12s_linear_infinite] opacity-60"
        />
        <div className="space-y-2">
          <h1 className="text-lg font-medium tracking-tight text-foreground">
            Under Construction
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {pageName
              ? `The ${pageName} page is currently being built. Check back soon.`
              : "This page is currently being built. Check back soon."}
          </p>
        </div>
      </div>
    </div>
  )
}
