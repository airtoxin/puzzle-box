import {test, expect} from '@playwright/test';

async function share(page) {
  await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#share-settings').click();
  return page.locator('#share-url').inputValue();
}
test('shared settings restore the same generation request', async ({page, browser}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('12');
  await page.locator('#hints input').last().uncheck();
  const url = await share(page);
  expect(url).toContain('#settings-v1=');
  const context = await browser.newContext(); const recipient = await context.newPage();
  await recipient.goto(url); await expect(recipient.locator('#share-status')).toContainText('読み込みました');
  await expect(recipient.locator('#generate')).toBeEnabled();
  const sent = recipient.waitForRequest(req => req.url().endsWith('/api/generate'));
  const response = recipient.waitForResponse('**/api/generate');
  await recipient.locator('#generate').click();
  const request = (await sent).postDataJSON();
  const payload = JSON.parse(Buffer.from(new URL(url).hash.slice('#settings-v1='.length), 'base64url').toString());
  expect(request).toEqual(payload);
  expect((await (await response).json()).status).toBe('ok');
  await context.close();
});
test('invalid, unknown, and oversized links fail without applying partial settings', async ({page}) => {
  await page.goto('/'); const url = await share(page);
  const payload = JSON.parse(Buffer.from(new URL(url).hash.slice('#settings-v1='.length), 'base64url').toString());
  for (const hash of ['#settings-v2=abc', '#settings-v1=' + 'a'.repeat(8192), '#settings-v1=' + Buffer.from(JSON.stringify({...payload, seed: 22, rules: [...payload.rules, {id:'unknown', parameters:{}}]})).toString('base64url')]) {
    await page.goto('/' + hash);
    await expect(page.locator('#share-status')).toContainText('読み込めませんでした');
    await expect(page.locator('#seed')).toHaveValue('0');
    await expect(page.locator('#generate')).toBeEnabled();
  }
});
test('failed shared preview leaves defaults usable', async ({page}) => {
  await page.goto('/'); const url = await share(page);
  let failed = false;
  await page.route('**/api/plan', route => {
    if (!failed) {failed = true; return route.fulfill({status:503});}
    return route.continue();
  });
  await page.goto(url); await expect(page.locator('#share-status')).toContainText('読み込めませんでした');
  await expect(page.locator('#generate')).toBeEnabled();
});

test('room and number grids survive sharing in their declared rule order', async ({page, browser}) => {
  const catalogResponse = page.waitForResponse('**/api/catalog');
  await page.goto('/'); const catalog = await (await catalogResponse).json();
  await expect(page.locator('#generate')).toBeEnabled();
  const rules = catalog.profiles.find(p => p.id === 'shading').rules;
  const room = rules.findIndex(r => r.parameters.some(p => p.name === 'rooms'));
  const numbers = rules.findIndex(r => r.parameters.some(p => p.name === 'numbers'));
  await page.locator('#rules .rule-card').nth(room).locator('input[type=checkbox]').first().check();
  await page.locator('#rules .rule-card').nth(numbers).locator('input[type=checkbox]').first().check();
  await page.locator('textarea[data-kind=region-map]').fill('0 0 0\n1 1 1');
  await page.locator('textarea[data-kind=number-grid]:enabled').fill('1 2 3\n4 5 6');
  const url = await share(page);
  const context = await browser.newContext(); const other = await context.newPage();
  await other.goto(url); await expect(other.locator('#share-status')).toContainText('読み込みました');
  await expect(other.locator('textarea[data-kind=region-map]')).toHaveValue('0 0 0\n1 1 1');
  await expect(other.locator('textarea[data-kind=number-grid]:enabled')).toHaveValue('1 2 3\n4 5 6');
  await context.close();
});

test('changing settings clears the old share link', async ({page}) => {
  await page.goto('/'); await share(page);
  await page.locator('#seed').fill('9');
  await expect(page.locator('#share-url')).toHaveValue('');
});


test('history traversal restores the settings in each URL', async ({page}) => {
  await page.goto('/'); const first = await share(page);
  await page.locator('#seed').fill('7'); const second = await share(page);
  await page.goto(first); await expect(page.locator('#seed')).toHaveValue('0');
  await page.goto(second); await expect(page.locator('#seed')).toHaveValue('7');
  await page.goBack(); await expect(page.locator('#seed')).toHaveValue('0');
  await page.goForward(); await expect(page.locator('#seed')).toHaveValue('7');
});
