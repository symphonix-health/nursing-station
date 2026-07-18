/**
 * Resolve Nursing Station development ports from the workspace registry.
 * There is no literal fallback: an absent allocation is a configuration error.
 */
const { readFileSync } = require('node:fs')
const path = require('node:path')

const REPO = process.env.WS_REPO || path.basename(path.resolve(__dirname, '..'))
const REPO_ENV = REPO.toUpperCase().replace(/[^A-Z0-9]+/g, '_')
const REGISTRY_PATH = path.resolve(
  __dirname,
  '..',
  '..',
  'workspace-tooling',
  'ports.workspace.json',
)

function readRegistry() {
  try {
    return JSON.parse(readFileSync(REGISTRY_PATH, 'utf8'))
  } catch (error) {
    throw new Error(
      `[${REPO}] cannot read workspace ports registry at ${REGISTRY_PATH}: ${error.message}`,
    )
  }
}

function repoPorts() {
  const registry = readRegistry()
  const byRepo = {}
  for (const [key, info] of Object.entries(registry.repo_blocks || {})) {
    if (key.startsWith('_')) {
      if (info && typeof info === 'object') {
        for (const [nestedKey, nestedInfo] of Object.entries(info)) {
          if (!nestedKey.startsWith('_') && nestedInfo && typeof nestedInfo === 'object') {
            byRepo[nestedKey] = nestedInfo.blocks || []
          }
        }
      }
    } else if (info && typeof info === 'object') {
      byRepo[key] = info.blocks || []
    }
  }
  const blocks = byRepo[REPO]
  if (!blocks || !blocks.length) {
    throw new Error(`[${REPO}] has no allocation in ${REGISTRY_PATH}`)
  }
  return blocks
    .map(block => Number(Array.isArray(block) ? block[0] : Number.NaN))
    .filter(Number.isFinite)
}

function resolveFrontendPort() {
  if (process.env.VITE_PORT) return Number(process.env.VITE_PORT)
  const override = process.env[`${REPO_ENV}_FRONTEND_PORT`]
  if (override) return Number(override)
  const port = repoPorts().find(value => value >= 5000 && value <= 5999)
  if (port === undefined) throw new Error(`[${REPO}] has no Vite port allocation`)
  return port
}

function resolveBackendPort() {
  if (process.env.WS_BACKEND_PORT) return Number(process.env.WS_BACKEND_PORT)
  const override = process.env[`${REPO_ENV}_BACKEND_PORT`]
  if (override) return Number(override)
  const port = repoPorts().find(value => value < 5000 || value > 5999)
  if (port === undefined) throw new Error(`[${REPO}] has no backend port allocation`)
  return port
}

function resolveBackendTarget() {
  return process.env.VITE_BACKEND_TARGET || `http://127.0.0.1:${resolveBackendPort()}`
}

module.exports = {
  REPO,
  REGISTRY_PATH,
  resolveFrontendPort,
  resolveBackendPort,
  resolveBackendTarget,
}
