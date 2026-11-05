import {test, expect} from '@playwright/test';

test('catalog loading prevents edits until defaults and controls are ready', async ({page}) => {
  let releaseCatalog;
  const blocked = new Promise(resolve => {releaseCatalog = resolve;});
  let catalogStarted;
  const started = new Promise(resolve => {catalogStarted = resolve;});
  await page.route('**/api/catalog', async route => {
    catalogStarted(); await blocked; await route.continue();
  });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/', {waitUntil: 'domcontentloaded'}); await started;
  await expect(page.locator('#recipe-form')).toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('#rows')).toBeDisabled();
  await expect(page.locator('#cols')).toBeDisabled();
  await expect(page.locator('#family')).toBeDisabled();
  await expect(page.locator('#status')).toContainText('ルールを読み込んでいます');
  releaseCatalog();
  await expect(page.locator('#rows')).toBeEnabled();
  await expect(page.locator('#recipe-form')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#rows').fill('5'); await page.locator('#cols').fill('5');
  await expect(page.locator('#board .cell')).toHaveCount(25);
  await expect(page.locator('#rows')).toHaveValue('5');
  await expect(page.locator('#cols')).toHaveValue('5');
  expect(errors).toEqual([]);
});

test('catalog failures stay locked and can be retried until controls work', async ({page}) => {
  let attempts = 0;
  await page.route('**/api/catalog', async route => {
    if (++attempts < 3) return route.fulfill({status:503, body:'unavailable'});
    return route.continue();
  });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  const retry = page.locator('#retry-catalog');
  await expect(retry).toBeVisible();
  await expect(page.locator('#rows')).toBeDisabled();
  await expect(page.locator('#status')).toContainText('ルールを読み込めません');
  await retry.click();
  await expect(retry).toBeVisible();
  await expect(page.locator('#rows')).toBeDisabled();
  await retry.click();
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(retry).toBeHidden();
  await expect(page.locator('#rows')).toBeEnabled();
  await page.locator('#rows').fill('3');
  await expect(page.locator('#board .cell')).toHaveCount(9);
  expect(attempts).toBe(3); expect(errors).toEqual([]);
});

test('failed preview can be retried without losing edited settings', async ({page}) => {
  let failPlan = false;
  await page.route('**/api/plan', async route => {
    if (failPlan) return route.fulfill({status:503, body:'unavailable'});
    return route.continue();
  });
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  failPlan = true;
  await page.locator('#rows').fill('4');
  const retry = page.locator('#retry-plan'); await expect(retry).toBeVisible();
  await expect(page.locator('#rows')).toHaveValue('4');
  await expect(page.locator('#board')).toBeEmpty();
  await expect(page.locator('#generate')).toBeDisabled();
  failPlan = false;
  await retry.click();
  await expect(retry).toBeHidden();
  await expect(page.locator('#board .cell')).toHaveCount(12);
  await expect(page.locator('#rows')).toHaveValue('4');
  await expect(page.locator('#generate')).toBeEnabled();
});
