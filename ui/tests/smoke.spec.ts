import { test, expect } from '@playwright/test';

test('lobby loads', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Dungeons & Dragons UI')).toBeVisible();
  await expect(page.getByText('Session Lobby')).toBeVisible();
});

test('dashboard loads after selecting session', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /example-rogue/ }).click();
  await expect(page.getByText('Dashboard for example-rogue')).toBeVisible();
});