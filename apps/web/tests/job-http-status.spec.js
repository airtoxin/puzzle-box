import {test, expect} from '@playwright/test';

test('generation HTTP errors cannot assert success or impossibility, but 409 busy is shown', async ({page}) => {
  await page.goto('/');
  await expect(page.locator('#generate')).toBeEnabled();
  let status = 503, payload, real;
  await page.route('**/api/generate', async route => {
    if (!real) {
      real = await (await route.fetch()).json();
      expect(real.status).toBe('ok');
    }
    await route.fulfill({status, json: payload || real});
  });
  for (const scenario of [
    {status:503, payload:null, expected:'生成・検証を完了できませんでした'},
    {status:503, payload:{status:'unsatisfiable'}, expected:'生成・検証を完了できませんでした'},
    {status:400, payload:{status:'insufficient_hints'}, expected:'生成・検証を完了できませんでした'},
    {status:409, payload:{status:'ok'}, expected:'生成・検証を完了できませんでした'},
    {status:409, payload:{status:'busy'}, expected:'別の生成が実行中です'},
  ]) {
    ({status, payload} = scenario);
    await page.locator('#generate').click();
    await expect(page.locator('#status')).toContainText(scenario.expected);
    await expect(page.locator('#actions')).toBeHidden();
    await expect(page.locator('#generate')).toBeEnabled();
  }
});

test('answer HTTP errors cannot assert correctness, but 409 busy is shown', async ({page}) => {
  await page.goto('/');
  await expect(page.locator('#generate')).toBeEnabled();
  const generated = page.waitForResponse('**/api/generate');
  await page.locator('#generate').click();
  const puzzle = await (await generated).json();
  expect(puzzle.status).toBe('ok');
  for (const [index, bit] of puzzle.record.solution.flat().entries()) {
    const cell = page.locator('#board .cell').nth(index);
    if (await cell.isEnabled()) {await cell.click(); if (bit) await cell.click();}
  }
  let status, payload;
  await page.route('**/api/check', route => route.fulfill({status, json:payload}));
  for (const scenario of [
    {status:503, payload:{status:'ok', correct:true}, expected:'正誤は未確定です'},
    {status:503, payload:{status:'ok', correct:false}, expected:'正誤は未確定です'},
    {status:400, payload:{status:'ok', correct:true}, expected:'正誤は未確定です'},
    {status:409, payload:{status:'ok', correct:true}, expected:'正誤は未確定です'},
    {status:409, payload:{status:'busy'}, expected:'別の生成が実行中です'},
  ]) {
    ({status, payload} = scenario);
    await page.locator('#check').click();
    await expect(page.locator('#answer-status')).toContainText(scenario.expected);
    await expect(page.locator('#answer-status')).not.toContainText('正解です');
    await expect(page.locator('#answer-status')).not.toContainText('正解ではありません');
    await expect(page.locator('#check')).toBeEnabled();
  }
});
