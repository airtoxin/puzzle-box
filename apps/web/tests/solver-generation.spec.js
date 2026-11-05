import {test, expect} from '@playwright/test';

test('5x5 solver generation, answer checking and download work on mobile', async ({page}, info) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/');
  await page.getByLabel('行数', {exact: true}).fill('5');
  await page.getByLabel('列数', {exact: true}).fill('5');
  await page.getByLabel('黒マス数', {exact: true}).fill('6');
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(page.locator('#board .cell')).toHaveCount(25);
  const response = page.waitForResponse('**/api/generate');
  await page.locator('#generate').click();
  const result = await (await response).json();
  expect(result.status).toBe('ok');
  expect(result.evidence).toMatchObject({method: 'cp-sat', unique: true, irreducible: true});
  await expect(page.locator('#status')).toContainText('ソルバーで別解がないことを証明');
  for (const [index, bit] of result.record.solution.flat().entries()) {
    const cell = page.locator('#board .cell').nth(index);
    if (await cell.isEnabled()) {
      await cell.click();
      if (bit) await cell.click();
    }
  }
  await page.locator('#check').click();
  await expect(page.locator('#answer-status')).toContainText('正解です');
  const editable = page.locator('#board .cell:enabled').first();
  // Cycle to the other complete binary state, skipping the unknown state.
  await editable.click();
  if (await editable.getAttribute('data-value') === '-1') await editable.click();
  await page.locator('#check').click();
  await expect(page.locator('#answer-status')).toContainText('まだ正解ではありません');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: info.outputPath('solver-5x5-mobile.png'), fullPage: true});
  expect(errors).toEqual([]);
});

test('per-rule limits and inconclusive search results are explicit', async ({page}) => {
  await page.goto('/');
  const card = page.locator('.rule-card').filter({hasText: '同じ大きさの成分の角接触を禁止'});
  await expect(card).toContainText('このルールは最大9セル');
  await page.getByLabel('行数', {exact: true}).fill('4');
  await page.getByLabel('列数', {exact: true}).fill('4');
  await card.locator('input[type=checkbox]').first().check();
  await expect(page.locator('#generate')).toBeDisabled();
  await card.locator('input[type=checkbox]').first().uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
  await page.route('**/api/generate', route => route.fulfill({json: {status: 'search_exhausted'}}));
  await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('不可能とは判定していません');
});
