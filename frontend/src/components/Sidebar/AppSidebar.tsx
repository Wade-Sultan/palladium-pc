import { Hammer, MessagesSquare, BookOpen, MapPin, ScrollText} from "lucide-react"
import { FaGithub } from "react-icons/fa"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarSeparator,
} from "@/components/ui/sidebar"
import { type Item, Main } from "./Main"
import { User } from "./User"

const items: Item[] = [
  { icon: Hammer, title: "New Build", path: "/newbuild" },
  { icon: MessagesSquare, title: "My Builds", path: "/buildhistory" },
  { icon: BookOpen, title: "Guides", path: "/guides" },
  { icon: MapPin, title: "Find a Builder", path: "/findbuilder" },
]


function SidebarFooterLinks() {
  const currentYear = new Date().getFullYear()

  return (
    <>
      <SidebarSeparator />
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton tooltip="GitHub" asChild>
            <a
              href="https://github.com/Wade-Sultan/palladium-pc"
              target="_blank"
              rel="noopener noreferrer"
            >
              <FaGithub className="size-4" />
              <span>GitHub</span>
            </a>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton tooltip="Changelog" asChild>
            <a href="/changelog">
              <ScrollText className="size-4" />
              <span>Changelog</span>
            </a>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
      <p className="px-2 text-[11px] text-muted-foreground group-data-[collapsible=icon]:hidden">
        Palladium &middot; {currentYear}
      </p>
    </>
  )
}

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
        <SidebarFooterLinks />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
