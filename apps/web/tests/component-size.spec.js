import {test, expect} from '@playwright/test';

test('fixed components generate both colors and distinguish a connectivity conflict', async ({page}) => {
  const errors=[]; page.on('pageerror',e => errors.push(e.message));
  await page.goto('/'); await page.locator('#rows').fill('3'); await page.locator('#cols').fill('3');
  await page.getByLabel('黒マス数', {exact:true}).fill('6');
  await page.getByLabel('同色の連結成分のサイズを固定', {exact:true}).check();
  const card=page.locator('.rule-card').filter({has:page.getByLabel('同色の連結成分のサイズを固定', {exact:true})});
  await expect(card.getByLabel('各連結成分のマス数', {exact:true})).toHaveValue('3');
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok');
  expect(data.record.rules.find(r => r.type === 'color-component-size')).toEqual({type:'color-component-size',size:3,black:true});
  expect(data.evidence.unique).toBe(true);
  for (let i=0; i<9; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(data.record.solution[Math.floor(i/3)][i%3])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await card.getByLabel('黒を対象にする（オフなら白）', {exact:true}).uncheck();
  await page.getByLabel('黒マス数', {exact:true}).fill('3'); // six whites cannot be a single size-three component
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.getByLabel('黒マスをつなぐ', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const white=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const second=await (await white).json(); expect(second.status).toBe('ok');
  expect(second.record.rules.find(r => r.type === 'color-component-size').black).toBe(false);
  expect(errors).toEqual([]);
});
