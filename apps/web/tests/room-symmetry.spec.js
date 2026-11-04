import {test, expect} from '@playwright/test';

test('room half-turn symmetry selects a unique answer and detects odd-count conflicts', async ({page}) => {
  const errors=[]; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.locator('#rows').fill('1'); await page.locator('#cols').fill('6');
  await page.getByLabel('各部屋の黒数を固定', {exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）', {exact:true}).fill('0 0 0 0 0 0');
  await page.getByLabel('黒マスをつなぐ', {exact:true}).check();
  await page.getByLabel('同色の連続長に上限を付ける', {exact:true}).check();
  await page.getByLabel('各部屋の黒配置を180度対称にする', {exact:true}).check();
  await expect(page.locator('textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok'); expect(data.clues).toEqual([]);
  expect(data.record.solution).toEqual([[0,0,1,1,0,0]]);
  expect(data.record.rules.find(r => r.type === 'room-rotational-symmetry').rooms).toEqual([[0,0,0,0,0,0]]);
  for (let i=0; i<6; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    while (await cell.getAttribute('data-value') !== String(data.record.solution[0][i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.getByLabel('各部屋の黒マス数', {exact:true}).fill('1');
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  expect(errors).toEqual([]);
});
