import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const NextConfig = {
    output: 'export',
    distDir: 'dist',
    basePath: process.env.NEXT_PUBLIC_BASE_PATH,
    turbopack: {
        root: resolve(__dirname, '..'),
    },
}

export default NextConfig
