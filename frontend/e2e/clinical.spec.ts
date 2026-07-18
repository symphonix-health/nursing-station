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

test('theme toggle and responsive navigation preserve clinical state', async ({ page }, testInfo) => {
  const toggle = page.getByRole('button', { name: /Theme:/ })
  await toggle.click()
  await toggle.click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByRole('heading', { name: 'Medical Ward A' })).toBeVisible()
  await mkdir(evidenceDir, { recursive: true })
  await page.screenshot({ path: path.join(evidenceDir, `ward-dark-${testInfo.project.name}.png`), fullPage: true })
})
