"use client"
import { ChevronsUpDown, LogIn, LogOut, Settings, UserPlus } from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { getInitials } from "@/utils"

function UserInfo({ name }: { name: string }) {
  return (
    <div className="flex items-center gap-2.5 w-full min-w-0">
      <Avatar className="size-8">
        <AvatarFallback className="bg-zinc-600 text-white">
          {getInitials(name)}
        </AvatarFallback>
      </Avatar>
      <p className="text-sm font-medium truncate">{name}</p>
    </div>
  )
}

export function User() {
  const { user, signOut } = useAuth()
  const { isMobile, setOpenMobile } = useSidebar()
  const [mounted, setMounted] = useState(false)

  useEffect(() => setMounted(true), [])

  if (!mounted) return null

  const isGuest = !user
  const displayName = user?.displayName ?? user?.email?.split("@")[0] ?? "User"

  const handleMenuClick = () => {
    if (isMobile) setOpenMobile(false)
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
              data-testid="user-menu"
            >
              <UserInfo name={isGuest ? "Guest" : displayName} />
              <ChevronsUpDown className="ml-auto size-4 text-muted-foreground" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side="top"
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <UserInfo name={isGuest ? "Guest" : displayName} />
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {isGuest ? (
              <>
                <Link href="/signup" onClick={handleMenuClick}>
                  <DropdownMenuItem>
                    <UserPlus />
                    Create account
                  </DropdownMenuItem>
                </Link>
                <Link href="/login" onClick={handleMenuClick}>
                  <DropdownMenuItem>
                    <LogIn />
                    Sign in
                  </DropdownMenuItem>
                </Link>
              </>
            ) : (
              <>
                <Link href="/settings" onClick={handleMenuClick}>
                  <DropdownMenuItem>
                    <Settings />
                    Settings
                  </DropdownMenuItem>
                </Link>
                <DropdownMenuItem onClick={signOut}>
                  <LogOut />
                  Log Out
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
