import React from "react";
import type { Metadata } from 'next'
import { ThemeProvider } from "@/components/theme-provider"
import "@/index.css"

export const metadata: Metadata = {
    title: 'Palladium Tech',
    description: "Palladium is an AI-powered PC building platform with strict database-enforced compatability and other tools to enhance the whole experience.",
    icons: {
        icon: '/assets/images/palladium-logo-main.png',
    },
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en" suppressHydrationWarning>
            <head>
                <script
                    dangerouslySetInnerHTML={{
                        __html: `(function(){try{var t=localStorage.getItem('app-theme');var d=document.documentElement;if(t==='dark'){d.classList.add('dark')}else if(t==='light'){d.classList.add('light')}else{if(window.matchMedia('(prefers-color-scheme: dark)').matches){d.classList.add('dark')}else{d.classList.add('light')}}}catch(e){}})()`,
                    }}
                />
            </head>
            <body>
                <ThemeProvider>
                    <div id="root">{children}</div>
                </ThemeProvider>
            </body>
        </html>
    )
}