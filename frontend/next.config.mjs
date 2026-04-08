import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const NextConfig = {
    ...(process.env.NEXT_PUBLIC_BASE_PATH && {
        basePath: process.env.NEXT_PUBLIC_BASE_PATH,
    }),
}

export default NextConfig
