import React from "react";

 export default function RootLayout({
    children,
 }: {
    children: React.ReactNode
 }) {
    return (
        <html lang="en">
            <head>
                <link rel="icon" type="image/svg+xml" href="/vite.svg" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
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