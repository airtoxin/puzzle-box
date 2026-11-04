import {test, expect} from '@playwright/test';

test('white-run rule declares shared rooms and keeps its condition through generation and checking', async ({page}) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスを離す', {exact:true}).check();
  await page.getByLabel('白い直線の3部屋またぎを禁止', {exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）', {exact:true}).fill('0 1 2\n0 1 2');
  await expect(page.locator('#rules textarea')).toHaveCount(1);
  await expect(page.locator('[data-room="0"]')).toHaveCount(2);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data = await (await generated).json(); expect(data.status).toBe('ok');
  expect(data.record.rules.find(r => r.type === 'no-white-across-three-rooms').rooms).toEqual([[0,1,2],[0,1,2]]);
  expect(data.evidence.unique).toBe(true); expect(data.evidence.irreducible).toBe(true);
  for (let r=0; r<2; r++) for (let c=0; c<3; c++) {
    const cell = page.locator(`[data-cell-index="${r*3+c}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(data.record.solution[r][c])) await cell.click();
  }
  const checked = page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.getByLabel('各部屋の黒数を固定', {exact:true}).check();
  await expect(page.locator('#rules textarea')).toHaveCount(1); // includes this third room-rule type
  await page.getByLabel('各部屋の黒数を固定', {exact:true}).uncheck();
  await page.getByLabel('黒マス数', {exact:true}).fill('1');
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  expect(errors).toEqual([]);
});
