import {test, expect} from '@playwright/test';

test('a declared boundary rule removes an enclosed component and makes fixed Cave numbers unique', async ({page}) => {
  const errors=[]; page.on('pageerror',e => errors.push(e.message));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.locator('#rows').fill('3'); await page.locator('#cols').fill('3');
  await page.getByLabel('数字から見える白マス数を固定', {exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）', {exact:true}).fill('5 3 5\n0 0 0\n0 0 0');
  await page.getByLabel('全ての連結成分を外枠につなぐ', {exact:true}).check();
  await page.getByLabel('黒・白のセルヒント', {exact:true}).uncheck();
  await page.getByLabel('各行の黒マス数', {exact:true}).uncheck();
  await page.getByLabel('各列の黒マス数', {exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok'); expect(data.clues).toEqual([]);
  expect(data.record.rules.find(r => r.type === 'components-touch-border').black).toBe(true);
  expect(data.record.solution).toEqual([[0,0,0],[0,1,0],[0,1,0]]);
  for (let i=0; i<9; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(data.record.solution[Math.floor(i/3)][i%3])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.getByLabel('全ての連結成分を外枠につなぐ', {exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
  const missing=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await missing).json()).status).toBe('insufficient_hints');
  await page.getByLabel('全ての連結成分を外枠につなぐ', {exact:true}).check();
  await page.getByLabel('外枠へつなぐ色は黒（オフなら白）', {exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
  const white=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await white).json()).status).toBe('insufficient_hints');
  expect(errors).toEqual([]);
});
