import React from "react";
import type { Metadata } from 'next'

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
        <html lang="en">
            <body>
                <div id="root">{children}</div>
            </body>
        </html>
    )
}