"use client"

import type { LucideIcon } from "lucide-react"
import { BookOpen, Hammer, MapPin, MessagesSquare } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

type Item = {
  icon: LucideIcon
  title: string
  path: string
}

const items: Item[] = [
  { icon: Hammer, title: "New Build", path: "/newbuild" },
  { icon: MessagesSquare, title: "My Builds", path: "/buildhistory" },
  { icon: BookOpen, title: "Guides", path: "/guides" },
  { icon: MapPin, title: "Find a Builder", path: "/findbuilder" },
]

export function Main() {
  const { isMobile, setOpenMobile } = useSidebar()
  const currentPath = usePathname()

  const handleMenuClick = () => {
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  return (
    <SidebarGroup>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => {
            const isActive = currentPath === item.path

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  tooltip={item.title}
                  isActive={isActive}
                  asChild
                >
                  <Link href={item.path} onClick={handleMenuClick}>
                    <item.icon />
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
