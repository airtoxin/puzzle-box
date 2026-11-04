import {test, expect} from '@playwright/test';

test('numbered and unnumbered white rectangles compose, sharing the existing area editor', async ({page}) => {
  const errors=[]; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.getByLabel('黒マス数', {exact:true}).fill('3');
  await page.getByLabel('数字がある白成分の面積を固定', {exact:true}).check();
  await page.getByLabel('白い島の面積（0は数字なし）', {exact:true}).fill('1 0 0\n0 0 0');
  await page.getByLabel('連結成分を長方形にする', {exact:true}).check();
  const rectangles=page.locator('.rule-card').filter({has:page.getByLabel('連結成分を長方形にする', {exact:true})});
  await rectangles.getByLabel('黒を対象にする（オフなら白）', {exact:true}).uncheck();
  await page.getByLabel('タテヨコ・ナナメで色をつなぐ', {exact:true}).check();
  await page.getByLabel('黒い2×2を禁止', {exact:true}).check();
  await expect(page.locator('#rules textarea:visible')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok'); expect(data.clues).toHaveLength(1);
  expect(['011100','010101']).toContain(data.record.solution.flat().join(''));
  await expect(page.locator('.area-number')).toHaveText(['1']);
  for (let i=0;i<6;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.getByLabel('白い島の面積を数字に合わせる', {exact:true}).check();
  await expect(page.locator('#rules textarea:visible')).toHaveCount(1);
  await expect(page.getByLabel('白い島の面積（0は数字なし）', {exact:true})).toHaveValue('1 0 0\n0 0 0');
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  expect(errors).toEqual([]);
});

test('zero area entries permit unnumbered white cells, without changing the old rule', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.getByLabel('黒マス数', {exact:true}).fill('0');
  await page.getByLabel('数字がある白成分の面積を固定', {exact:true}).check();
  await page.getByLabel('白い島の面積（0は数字なし）', {exact:true}).fill('0 0 0\n0 0 0');
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok'); expect(data.clues).toEqual([]);
  expect(data.record.solution).toEqual([[0,0,0],[0,0,0]]);
  await expect(page.locator('.area-number')).toHaveCount(0);
  await page.getByLabel('白い島の面積を数字に合わせる', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
});
