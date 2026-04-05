"use client"
import Image from "next/image"
import Link from "next/link"

import { useTheme } from "@/components/theme-provider"
import { cn } from "@/lib/utils"

const iconLogo = "/assets/images/palladium-logo.svg"
const fullLogoDark = "/assets/images/palladium-combined-dark-mode.svg"
const fullLogoLight = "/assets/images/palladium-combined-light-mode.svg"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"

  const fullLogo = isDark ? fullLogoDark : fullLogoLight

  const content =
    variant === "responsive" ? (
      <>
        <Image
          src={fullLogo}
          alt="Palladium"
          width={0}
          height={24}
          style={{ width: "auto" }}
          className={cn("group-data-[collapsible=icon]:hidden", className)}
        />
        <Image
          src={iconLogo}
          alt="Palladium"
          width={20}
          height={20}
          className={cn("hidden group-data-[collapsible=icon]:block", className)}
        />
      </>
    ) : (
      <Image
        src={variant === "full" ? fullLogo : iconLogo}
        alt="Palladium"
        width={variant === "full" ? 0 : 20}
        height={variant === "full" ? 24 : 20}
        style={variant === "full" ? { width: "auto" } : undefined}
        className={className}
      />
    )

  if (!asLink) {
    return content
  }

  return <Link href="/newbuild">{content}</Link>
}
