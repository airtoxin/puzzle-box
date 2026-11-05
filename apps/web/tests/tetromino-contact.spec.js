import {test, expect} from '@playwright/test';

test('tetromino contact supports and checks a six by six board', async ({page}) => {
  await page.goto('/');
  await expect(page.locator('#board .cell')).toHaveCount(6);
  await page.getByLabel('行数', {exact:true}).fill('6');
  await page.getByLabel('列数', {exact:true}).fill('6');
  await page.getByLabel('黒マス数', {exact:true}).fill('0');
  await page.getByLabel('同形テトロミノの部屋間接触を禁止', {exact:true}).check();
  await page.locator('textarea[data-kind="region-map"]')
    .fill('0 0 0 0 0 0\n0 0 0 0 0 0\n0 0 0 0 0 0\n1 1 1 1 1 1\n1 1 1 1 1 1\n1 1 1 1 1 1');
  await expect(page.locator('#board .cell')).toHaveCount(36);
  await expect(page.locator('#generate')).toBeEnabled();
  const response = page.waitForResponse('**/api/generate');
  await page.locator('#generate').click();
  const result = await (await response).json();
  expect(result.status).toBe('ok');
  expect(result.evidence).toMatchObject({unique:true, irreducible:true});
  for (let i=0; i<36; i++) {
    const cell = page.locator('#board .cell').nth(i);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== '0') await cell.click();
  }
  const checked = page.waitForResponse('**/api/check');
  await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
});

test('room tetromino contact is conditional and is independent of black two-by-two exclusion', async ({page}) => {
  const errors=[]; page.on('pageerror',e => errors.push(e.message));
  await page.goto('/'); await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.locator('#rows').fill('3'); await page.locator('#cols').fill('3');
  await page.getByLabel('各部屋の黒数を固定', {exact:true}).check();
  await page.getByLabel('各部屋の黒マス数', {exact:true}).fill('4');
  await page.getByLabel('各部屋内で黒をつなぐ', {exact:true}).check();
  await page.getByLabel('同形テトロミノの部屋間接触を禁止', {exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）', {exact:true}).fill('0 0 1\n0 0 1\n1 1 1');
  await expect(page.locator('textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok');
  expect(data.record.rules.some(r => r.type === 'no-touching-equal-tetrominoes')).toBe(true);
  for (let i=0; i<9; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(data.record.solution[Math.floor(i/3)][i%3])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.getByLabel('黒い2×2を禁止', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const square=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await square).json()).status).toBe('unsatisfiable');
  await page.getByLabel('黒い2×2を禁止', {exact:true}).uncheck();
  await page.locator('#rows').fill('2'); await page.locator('#cols').fill('4');
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）', {exact:true}).fill('0 0 0 0\n1 1 1 1');
  await expect(page.locator('#generate')).toBeEnabled();
  const same=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await same).json()).status).toBe('unsatisfiable');
  await page.getByLabel('同形テトロミノの部屋間接触を禁止', {exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
  const removed=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await removed).json()).status).toBe('ok'); expect(errors).toEqual([]);
});
