import {test, expect} from '@playwright/test';

for (const [field, value] of [['unique', null], ['irreducible', false]]) {
test(`a generated puzzle without ${field} proof stays unconfirmed`, async ({page}) => {
  await page.route('**/api/generate', async route => {
    const result = await (await route.fetch()).json();
    expect(result.status).toBe('ok');
    result.evidence[field] = value;
    await route.fulfill({json: result});
  });
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('完了できませんでした');
  await expect(page.locator('#actions')).toBeHidden();
});
}

test('a malformed answer verdict never appears correct or incorrect', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  const generated = page.waitForResponse('**/api/generate');
  await page.locator('#generate').click(); const result = await (await generated).json();
  expect(result.status).toBe('ok');
  for (const [index, bit] of result.record.solution.flat().entries()) {
    const cell = page.locator('#board .cell').nth(index);
    if (await cell.isEnabled()) {await cell.click(); if (bit) await cell.click();}
  }
  let verdict;
  await page.route('**/api/check', route => route.fulfill({json: verdict}));
  for (verdict of [{status:'ok'}, {status:'ok', correct:'false'}, {status:'ok', correct:1}, {status:'unconfirmed'}]) {
    await page.locator('#check').click();
    await expect(page.locator('#answer-status')).toContainText('正誤は未確定です');
    await expect(page.locator('#answer-status')).not.toContainText('正解です');
    await expect(page.locator('#answer-status')).not.toContainText('まだ正解ではありません');
  }
});
