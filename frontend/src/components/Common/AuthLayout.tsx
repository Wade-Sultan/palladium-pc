import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="flex min-h-svh flex-col p-6 md:p-10">
      <div className="flex items-center justify-between">
        <Logo variant="full" className="h-10" asLink={false} />
        <Appearance />
      </div>
      <div className="flex flex-1 items-center justify-center">
        <div className="w-full max-w-sm">{children}</div>
      </div>
      <Footer />
    </div>
  )
}
