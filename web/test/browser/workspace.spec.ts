import { test, expect } from '@playwright/test';

test('inspect original evidence, correct a relationship and restore it', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Inspect Iris', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Inspect Iris', exact: true }).click();
  await page.getByRole('button', { name: 'Read source ↗' }).first().click();
  await expect(page.getByRole('dialog')).toContainText('Iris owns Lumen.');
  await page.getByRole('button', { name: 'Close source' }).click();
  page.once('dialog', dialog => dialog.accept('Browser review: check source assignment.'));
  await page.getByRole('button', { name: 'Flag relationship' }).first().click();
  await expect(page.getByRole('status')).toContainText('Correction saved');
  await expect(page.getByRole('button', { name: 'Inspect Iris', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Corrections', exact: false }).first().click();
  page.once('dialog', dialog => dialog.accept('Browser review: source independently checked.'));
  await page.getByRole('button', { name: 'Restore evidence' }).first().click();
  await page.getByRole('button', { name: 'Graph', exact: false }).first().click();
  await expect(page.getByRole('button', { name: 'Inspect Iris', exact: true })).toBeVisible();
});

test('versioned document editing, job cancellation and deletion', async ({ page }) => {
  const documentId = 'browser-note-' + Date.now();
  await page.goto('/'); await page.getByRole('button', { name: 'Documents', exact: false }).first().click();
  await page.getByLabel('Document ID', { exact: true }).fill(documentId);
  await page.getByLabel('Title', { exact: true }).fill('Browser source lifecycle');
  await page.getByLabel('Source text').fill('Tara owns Willow.');
  await page.getByRole('button', { name: 'Save & index' }).click();
  await expect(page.getByRole('status')).toContainText('Document saved');
  await page.getByRole('button', { name: 'Indexing', exact: false }).first().click();
  const row = page.getByRole('row').filter({ hasText: documentId });
  await row.getByRole('button', { name: 'Cancel' }).click();
  await expect(row).toContainText('cancelled');
  await page.getByRole('button', { name: 'Documents', exact: false }).first().click();
  await page.getByRole('button', { name: /Browser source lifecycle/ }).click();
  await expect(page.getByLabel('Source text')).toHaveValue('Tara owns Willow.');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Delete document' }).click();
  await expect(page.getByRole('status')).toContainText('Document removed');
});

test('actual model query preserves visible evidence and the workspace fits a mobile viewport', async ({ page }) => {
  await page.goto('/'); await page.getByRole('button', { name: 'Compare', exact: false }).first().click();
  await page.getByLabel('Question', { exact: true }).fill('Who owns Lumen?');
  await page.getByRole('button', { name: 'vector', exact: true }).click();
  await expect(page.locator('.answer .badge')).toBeVisible({ timeout: 90000 });
  await expect(page.locator('.source-result').first()).toBeVisible();
  await page.locator('.source-result').first().click();
  await expect(page.getByRole('dialog')).toBeVisible(); await page.getByRole('button', { name: 'Close source' }).click();
  await page.getByRole('button', { name: 'Graph', exact: false }).first().click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/workspace-desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/workspace-mobile.png`, fullPage: true });
});
