import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const NextConfig = {
    distDir: 'dist',
    turbopack: {
        root: resolve(__dirname, '..'),
    },
}

export default NextConfig
