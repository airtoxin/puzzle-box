import {test, expect} from '@playwright/test';

for (const black of [true,false]) test(`${black ? 'black' : 'white'} paths use declared degree and endpoint controls`, async ({page}) => {
  const errors=[]; page.on('pageerror',e => errors.push(e.message));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ', {exact:true}).setChecked(!black);
  if (black) await page.getByLabel('黒マスをつなぐ', {exact:true}).check();
  await page.locator('#rows').fill('3'); await page.locator('#cols').fill('3');
  await page.getByLabel('同色マスの隣接数を制限', {exact:true}).check();
  await page.getByLabel('同色マスの端点数を固定', {exact:true}).check();
  await page.getByLabel('隣接数を制限する色は黒（オフなら白）', {exact:true}).setChecked(black);
  await page.getByLabel('端点を数える色は黒（オフなら白）', {exact:true}).setChecked(black);
  await expect(page.getByLabel('同色の最少隣接数', {exact:true})).toHaveValue('1');
  await expect(page.getByLabel('同色の最多隣接数', {exact:true})).toHaveValue('2');
  await expect(page.getByLabel('同色の端点数', {exact:true})).toHaveValue('2');
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok');
  expect(data.record.rules.find(r => r.type === 'color-degree-range')).toEqual({type:'color-degree-range',minimum:1,maximum:2,black});
  expect(data.record.rules.find(r => r.type === 'color-endpoint-count')).toEqual({type:'color-endpoint-count',count:2,black});
  for (let i=0; i<9; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(data.record.solution[Math.floor(i/3)][i%3])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  if (black) {
    await page.getByLabel('同色の最少隣接数', {exact:true}).fill('2');
    await expect(page.locator('#generate')).toBeEnabled();
    const conflict=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
    expect((await (await conflict).json()).status).toBe('unsatisfiable');
    await page.getByLabel('同色の端点数', {exact:true}).fill('0');
    await expect(page.locator('#generate')).toBeEnabled();
    const cycle=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
    expect((await (await cycle).json()).status).toBe('ok');
  }
  expect(errors).toEqual([]);
});
