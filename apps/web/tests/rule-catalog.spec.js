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
    const searchStyle = await page.locator('#rule-search').evaluate(el => ({height: el.getBoundingClientRect().height, fontSize: parseFloat(getComputedStyle(el).fontSize)}));
    expect(searchStyle.height).toBeGreaterThanOrEqual(44); expect(searchStyle.fontSize).toBeGreaterThanOrEqual(16);
    await expect(page.locator('.rule-group summary').first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByLabel('ルールを検索').fill('一致なしxyz');
    await expect(page.locator('#rule-empty')).toBeVisible();
    await page.getByLabel('ルールを検索').fill('');
  }
});

test('Enter in rule search does not submit or replace an in-progress puzzle', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#generate').click();
  await expect(page.locator('#actions')).toBeVisible({timeout:45000});
  const cell = page.locator('#board .cell:enabled').first();
  await cell.click();
  const answer = await cell.getAttribute('data-value');
  await page.locator('#share-settings').click();
  const url = await page.locator('#share-url').inputValue();
  expect(url).toContain('#settings-v1=');
  let generationRequests = 0;
  page.on('request', request => {if (request.url().endsWith('/api/generate')) generationRequests++;});
  await page.evaluate(() => {
    window.searchSubmitCount = 0;
    document.querySelector('#recipe-form').addEventListener('submit', () => window.searchSubmitCount++);
  });
  const search = page.locator('#rule-search');
  await search.fill('connected'); await search.press('Enter');
  expect(await page.evaluate(() => window.searchSubmitCount)).toBe(0);
  expect(generationRequests).toBe(0);
  await expect(page.locator('#share-url')).toHaveValue(url);
  await expect(page.locator('#actions')).toBeVisible();
  await expect(page.locator('#generated-rules')).toBeVisible();
  await expect(cell).toHaveAttribute('data-value', answer);
});


test('unchecking a retained selection moves focus to search', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  const search = page.locator('#rule-search');
  await search.fill('不一致xyz');
  const toggle = page.locator('[data-rule-id="count"] input[type=checkbox]');
  await toggle.focus(); await page.keyboard.press('Space');
  await expect(search).toBeFocused();
  await expect(page.locator('[data-rule-id="count"]')).toBeHidden();
});

test('loading shared settings while searching retains the query and selected rules', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  const toggle = page.locator('[data-rule-id="no-black-2x2"] input[type=checkbox]');
  await toggle.check(); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#share-settings').click();
  const url = await page.locator('#share-url').inputValue();
  expect(url).toContain('#settings-v1=');
  await toggle.uncheck();
  const search = page.locator('#rule-search'); await search.fill('不一致xyz');
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  await page.locator('#load-shared-settings').click();
  await expect(page.locator('#share-status')).toContainText('読み込みました');
  await expect(search).toHaveValue('不一致xyz');
  await expect(page.locator('[data-rule-id="no-black-2x2"]')).toBeVisible();
  await expect(page.locator('[data-rule-id="no-black-2x2"] input[type=checkbox]')).toBeChecked();
});

test('loading a shared puzzle during a search keeps selected rules visible', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  await page.locator('#share-puzzle').click();
  const url = await page.locator('#puzzle-url').inputValue();
  expect(url).toContain('#puzzle-v1=');
  await page.locator('[data-rule-id="count"] input[type=checkbox]').uncheck();
  const search = page.locator('#rule-search'); await search.fill('不一致xyz');
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  await page.locator('#load-shared-settings').click();
  await expect(page.locator('#actions')).toBeVisible({timeout:45000});
  await expect(page.locator('#share-status')).toContainText('読み込みました');
  await expect(search).toHaveValue('不一致xyz');
  await expect(page.locator('[data-rule-id="count"]')).toBeVisible();
  await expect(page.locator('[data-rule-id="count"] input[type=checkbox]')).toBeChecked();
});
