import { defineConfig } from 'vite'
import { createRequire } from 'node:module'
import react from '@vitejs/plugin-react'

const nodeRequire = createRequire(import.meta.url)
const { resolveBackendTarget, resolveFrontendPort } = nodeRequire('./resolve-ports.cjs') as typeof import('./resolve-ports.cjs')
const backendTarget = resolveBackendTarget()

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: resolveFrontendPort(),
    strictPort: true,
    proxy: { '/api': backendTarget, '/health': backendTarget },
  },
})
