import {test, expect} from '@playwright/test';

test('uniform rooms and white forests compose with existing constraints and retain one necessary clue', async ({page}) => {
  const errors=[]; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.getByLabel('部屋内を同じ色にする', {exact:true}).check();
  await page.getByLabel('同色マスの輪を禁止', {exact:true}).check();
  await expect(page.getByLabel('輪を禁止する色は黒（オフなら白）', {exact:true})).not.toBeChecked();
  await page.getByLabel('黒い2×2を禁止', {exact:true}).check();
  await page.getByLabel('白の2×2を禁止', {exact:true}).check();
  await expect(page.locator('textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok'); expect(data.clues).toHaveLength(1);
  expect(['110100','001011']).toContain(data.record.solution.flat().join(''));
  await expect(page.locator('[data-cell-index="0"]')).toHaveAccessibleName(/部屋1/);
  for (let i=0; i<6; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.getByLabel('各部屋の黒数を固定', {exact:true}).check();
  await page.getByLabel('各部屋の黒マス数', {exact:true}).fill('1');
  await expect(page.locator('textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  expect(errors).toEqual([]);
});

test('the forest color parameter changes server constraints rather than selecting optional edges', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#rows').fill('3'); await page.locator('#cols').fill('3');
  await page.getByLabel('黒マス数', {exact:true}).fill('1');
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.getByLabel('同色マスの輪を禁止', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  await page.getByLabel('輪を禁止する色は黒（オフなら白）', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok');
  expect(data.record.solution.flat().reduce((a,b) => a+b,0)).toBe(1);
  expect(data.record.rules.find(r => r.type === 'acyclic-color').black).toBe(true);
});
