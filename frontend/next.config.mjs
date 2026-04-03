/** @type {import('next').NextConfig} */
const NextConfig = {
    output: 'export',
    distDir: 'dist',
    basePath: process.env.NEXT_PUBLIC_BASE_PATH,
}

export default NextConfig