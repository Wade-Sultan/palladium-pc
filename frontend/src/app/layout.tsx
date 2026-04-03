import React from "react";
import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'Palladium Tech',
    description: "Palladium is an AI-powered PC building platform with strict database-enforced compatability and other tools to enhance the whole experience."
}

 export default function RootLayout({
    children,
 }: {
    children: React.ReactNode
 }) {
    return (
        <html lang="en">
            <head>
                <link rel="icon" type="image/svg+xml" href="/vite.svg" />
                <title>Palladium</title>
                <link rel="icon" type="image/x-icon" href="/assets/images/palladium-logo-main.png" />
            </head>
            <body>
                <div id="root">{children}</div>
                <script type="module" src="./src/main.tsx"></script>
            </body>
        </html>
    )
    
 }