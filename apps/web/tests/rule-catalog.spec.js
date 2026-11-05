import {test, expect} from '@playwright/test';

test('search and groups preserve selections, parameters, and generated output', async ({page}) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  const groups = page.locator('.rule-group');
  await expect(groups).toHaveCount(5);
  const count = page.locator('[data-rule-id="count"]');
  const countInput = count.locator('input[type=number]');
  await countInput.fill('3');
  const search = page.getByLabel('ルールを検索');
  await search.fill('絶対に一致しない検索語');
  await expect(page.locator('#rule-empty')).toBeVisible();
  await expect(count).toBeVisible();
  await expect(countInput).toHaveValue('3');
  await expect(page.locator('[data-rule-id="room-black-count"]')).toBeHidden();
  await expect(page.locator('#generate')).toBeEnabled();
  await search.fill('room-black-count');
  await expect(page.locator('[data-rule-id="room-black-count"]')).toBeVisible();
  await expect(page.locator('#rule-count')).toContainText('検索結果 1 件');
  await search.fill('');
  const summary = groups.filter({hasText:'配置の基本'}).locator('summary');
  await summary.focus(); await page.keyboard.press('Enter');
  await expect(count).toBeHidden();
  await page.keyboard.press('Enter'); await expect(count).toBeVisible();
  await page.locator('#generate').click();
  await expect(page.locator('#generated-rules')).toBeVisible({timeout:45000});
  await expect(page.locator('#generated-rules-list')).toContainText(await count.locator('.rule-title').innerText());
  await page.locator('#share-settings').click();
  const url = await page.locator('#share-url').inputValue();
  expect(url).toContain('#settings-v1=');
  await search.fill('一致なしxyz');
  await expect(page.locator('#share-url')).toHaveValue(url);
  await expect(page.locator('#generated-rules')).toBeVisible();
  expect(errors).toEqual([]);
});

test('all board families and narrow screens retain accessible search and groups', async ({page}) => {
  await page.setViewportSize({width: 360, height: 800});
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  for (const family of ['shading', 'slitherlink', 'coupled']) {
    await page.locator('#family').selectOption(family);
    await expect(page.locator('#generate')).toBeEnabled();
    await expect(page.getByLabel('ルールを検索')).toBeVisible();
    await expect(page.locator('.rule-group summary').first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByLabel('ルールを検索').fill('一致なしxyz');
    await expect(page.locator('#rule-empty')).toBeVisible();
    await page.getByLabel('ルールを検索').fill('');
  }
});
