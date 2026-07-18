import { defineConfig, devices } from '@playwright/test'
import { createRequire } from 'node:module'

const nodeRequire = createRequire(import.meta.url)
const { resolveBackendPort, resolveFrontendPort } = nodeRequire('./resolve-ports.cjs') as typeof import('./resolve-ports.cjs')
const backendPort = resolveBackendPort()
const frontendPort = resolveFrontendPort()
const baseURL = `http://127.0.0.1:${frontendPort}`

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'chromium-desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'chromium-mobile', use: { ...devices['Pixel 5'] } },
  ],
  webServer: [
    {
      command: 'python -m nursing_station.main',
      cwd: '..',
      url: `http://127.0.0.1:${backendPort}/health`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: 'npm.cmd run dev',
      cwd: '.',
      url: baseURL,
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
})
