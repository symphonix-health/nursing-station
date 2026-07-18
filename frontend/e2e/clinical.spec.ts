import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const evidenceDir = path.resolve('../tests/screenshots')
const consoleErrors: string[] = []
const failedResponses: string[] = []

test.beforeEach(async ({ page }) => {
  consoleErrors.length = 0
  failedResponses.length = 0
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('response', response => { if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`) })
  await page.goto('/login')
  await page.getByLabel('Email').fill('amina.okafor@nursing.test')
  await page.getByLabel('Password').fill('Nursing2026!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/ward$/)
  await expect(page.getByRole('heading', { name: 'Medical Ward A' })).toBeVisible()
})

test.afterEach(async () => {
  expect(consoleErrors, `console errors: ${consoleErrors.join('\n')}`).toEqual([])
  expect(failedResponses, `failed responses: ${failedResponses.join('\n')}`).toEqual([])
})

test('ward board and patient safety banner are accessible', async ({ page }, testInfo) => {
  await expect(page.getByRole('grid', { name: /Medical Ward A ward board/ })).toBeVisible()
  await page.getByRole('row', { name: /Open Margaret Holloway/ }).click()
  await expect(page.getByRole('region', { name: 'Patient safety banner' })).toContainText('MRN-104287')
  await expect(page.getByRole('region', { name: 'Patient safety banner' })).toContainText('Penicillin')
  const result = await new AxeBuilder({ page }).analyze()
  await mkdir(evidenceDir, { recursive: true })
  await writeFile(path.join(evidenceDir, `axe-${testInfo.project.name}.json`), JSON.stringify(result, null, 2))
  expect(result.violations).toEqual([])
  await page.screenshot({ path: path.join(evidenceDir, `patient-overview-${testInfo.project.name}.png`), fullPage: true })
})

test('privacy mode masks identifiers across ward, patient, task, and medication surfaces', async ({ page }) => {
  await page.getByRole('button', { name: 'Privacy mode' }).click()
  await expect(page.getByRole('status')).toContainText('Privacy mode active')
  await expect(page.getByRole('grid')).not.toContainText('Margaret Holloway')
  await expect(page.getByRole('grid')).not.toContainText('MRN-104287')
  await page.getByRole('row', { name: 'Open patient in bed A-12' }).click()
  const banner = page.getByRole('region', { name: 'Patient safety banner' })
  await expect(banner).toContainText('Patient A-12')
  await expect(banner).not.toContainText('MRN-104287')
  await page.getByRole('tab', { name: 'Medications' }).click()
  await expect(page.getByRole('button', { name: /Ceftriaxone/ })).toBeDisabled()
  await page.getByRole('link', { name: 'Tasks' }).click()
  await expect(page.getByRole('main')).not.toContainText('Margaret Holloway')
  await expect(page.getByRole('button', { name: 'Exit privacy mode' })).toBeVisible()
})

test('records an observation through the real backend', async ({ page }) => {
  await page.getByRole('row', { name: /Open Margaret Holloway/ }).click()
  await page.getByRole('tab', { name: 'Observations' }).click()
  await page.getByLabel('Respiratory rate /min').fill('22')
  await page.getByLabel('SpO2 %').fill('94')
  await page.getByRole('button', { name: 'Confirm observation' }).click()
  await expect(page.getByText(/Observation confirmed. Warning score/)).toBeVisible()
})

test('high-alert medication keeps the independent co-sign gate visible', async ({ page }) => {
  await page.getByRole('row', { name: /Open Nkiru Adeyemi/ }).click()
  await page.getByRole('tab', { name: 'Medications' }).click()
  await page.getByRole('button', { name: /Insulin aspart/ }).click()
  await expect(page.getByRole('alert')).toContainText('HIGH-ALERT medication')
  await expect(page.getByLabel('Independent co-signer')).toBeVisible()
  await expect(page.getByText('MRN-104329 / DOB 1981-11-22', { exact: true })).toBeVisible()
})

test('task creation and cancellation are available as a server-confirmed workflow', async ({ page }, testInfo) => {
  const title = `Confirm mobility plan ${testInfo.project.name}`
  await page.getByRole('row', { name: /Open Margaret Holloway/ }).click()
  await page.getByRole('tab', { name: 'Tasks' }).click()
  await page.getByLabel('Task', { exact: true }).fill(title)
  await page.getByLabel('Instructions').fill('Review mobility plan with the patient and document understanding')
  await page.getByLabel('Due time').fill('2026-12-31T12:00')
  await page.getByRole('button', { name: 'Create task' }).click()
  const task = page.locator('.task').filter({ hasText: title })
  await expect(task).toBeVisible()
  await task.getByRole('button', { name: 'Cancel' }).click()
  await expect(task).toContainText('cancelled')
})

test('care plans can be discontinued and cannot remain presented as active', async ({ page }, testInfo) => {
  const problem = `Mobility transition ${testInfo.project.name}`
  await page.getByRole('row', { name: /Open Margaret Holloway/ }).click()
  await page.getByRole('tab', { name: 'Care plan' }).click()
  await page.getByLabel('Nursing problem').fill(problem)
  await page.getByLabel('Measurable goal').fill('Transfers safely with one nurse by end of shift')
  await page.getByLabel('Owned intervention').fill('Assess transfer technique before each mobilisation')
  await page.getByRole('button', { name: 'Add to care plan' }).click()
  const plan = page.locator('.task').filter({ hasText: problem })
  await expect(plan).toBeVisible()
  await plan.getByRole('button', { name: 'Discontinue' }).click()
  await expect(plan).toContainText('discontinued')
  await expect(plan.getByRole('button', { name: 'Discontinue' })).toHaveCount(0)
})

test('handover displays the captured unresolved work and current risk snapshot', async ({ page }) => {
  await page.getByRole('row', { name: /Open Margaret Holloway/ }).click()
  await page.getByRole('tab', { name: 'Handover' }).click()
  await page.getByRole('button', { name: 'Create pending handover' }).click()
  await expect(page.getByText(/Handover created/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Pending accountability and risk snapshot' }).locator('..')).toContainText('unresolved tasks')
  await expect(page.getByRole('heading', { name: 'Pending accountability and risk snapshot' }).locator('..')).toContainText('Oxygen therapy')
})

test('governance shows durable synthetic lineage and non-live declarations', async ({ page }) => {
  await page.getByRole('link', { name: 'Governance' }).click()
  await expect(page.getByRole('heading', { name: 'Landed synthetic seed' })).toBeVisible()
  await expect(page.getByText('seed.uk.nursing_station.phase1_v1')).toBeVisible()
  await expect(page.getByText(/real patient data: false/i)).toBeVisible()
  await expect(page.getByText(/live clinical source: false/i)).toBeVisible()
})

test('patient tabs support arrow keys, skip navigation, and 200 percent zoom', async ({ page }) => {
  await page.getByRole('row', { name: /Open Margaret Holloway/ }).click()
  const overview = page.getByRole('tab', { name: 'Overview' })
  await overview.focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: 'Observations' })).toHaveAttribute('aria-selected', 'true')
  await page.locator('.skip-link').focus()
  await expect(page.locator('.skip-link')).toBeFocused()
  await page.locator('.skip-link').press('Enter')
  await expect(page.locator('#main-content')).toBeFocused()
  await page.evaluate(() => { document.documentElement.style.zoom = '2' })
  const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }))
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.width + 1)
})

test('theme toggle and responsive navigation preserve clinical state', async ({ page }, testInfo) => {
  const toggle = page.getByRole('button', { name: /Theme:/ })
  await toggle.click()
  await toggle.click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByRole('heading', { name: 'Medical Ward A' })).toBeVisible()
  await mkdir(evidenceDir, { recursive: true })
  await page.screenshot({ path: path.join(evidenceDir, `ward-dark-${testInfo.project.name}.png`), fullPage: true })
})
