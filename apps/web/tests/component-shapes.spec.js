import {test, expect} from '@playwright/test';

test('component shape fragments reuse Boolean controls, generate and check a real answer', async ({page}) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.getByLabel('連結成分を長方形にする', {exact:true}).check();
  await page.getByLabel('連結成分の長方形を禁止', {exact:true}).check();
  const rectangular = page.locator('.rule-card').filter({has:page.getByLabel('連結成分を長方形にする', {exact:true})});
  const nonrectangular = page.locator('.rule-card').filter({has:page.getByLabel('連結成分の長方形を禁止', {exact:true})});
  const colorLabel = '黒を対象にする（オフなら白）';
  await expect(rectangular.getByLabel(colorLabel, {exact:true})).toBeChecked();
  await expect(nonrectangular.getByLabel(colorLabel, {exact:true})).not.toBeChecked();
  await expect(page.locator('#generate')).toBeEnabled();
  const generated = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data = await (await generated).json(); expect(data.status).toBe('ok');
  expect(data.record.rules).toEqual([{type:'count', count:2},
    {type:'rectangular-components', black:true}, {type:'nonrectangular-components', black:false}]);
  expect(data.evidence.unique).toBe(true); expect(data.evidence.irreducible).toBe(true);
  for (let r=0; r<2; r++) for (let c=0; c<3; c++) {
    const cell = page.locator(`[data-cell-index="${r*3+c}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(data.record.solution[r][c])) await cell.click();
  }
  const checked = page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  // Both requirements on black force black to be absent, contradicting count=2.
  await nonrectangular.getByLabel(colorLabel, {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  await expect(page.locator('#actions')).toBeHidden();
  expect(errors).toEqual([]);
});
