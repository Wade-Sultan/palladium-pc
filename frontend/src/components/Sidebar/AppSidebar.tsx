import { 
  Home,
  Hammer,
  MessagesSquare,
  BookOpen,
  MapPin,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import { type Item, Main } from "./Main"
import { User } from "./User"

const items: Item[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: Hammer, title: "New Build", path: "/build" },
  { icon: MessagesSquare, title: "My Builds", path: "/builds" },
  { icon: BookOpen, title: "Guides", path: "/guides" },
  { icon: MapPin, title: "Find a Builder", path: "/find-builder" },
]

export function AppSidebar() {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
