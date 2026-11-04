import {test, expect} from '@playwright/test';

test('maximum run length changes an actual room and connectivity composition', async ({page}) => {
  const errors=[]; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.locator('#rows').fill('1'); await page.locator('#cols').fill('6');
  await page.getByLabel('各部屋の黒数を固定', {exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）', {exact:true}).fill('0 0 0 0 0 0');
  await page.getByLabel('黒マスをつなぐ', {exact:true}).check();
  await page.getByLabel('同色の連続長に上限を付ける', {exact:true}).check();
  await expect(page.getByLabel('同色の最大連続長', {exact:true})).toHaveValue('3');
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok');
  expect(data.record.rules.find(r => r.type === 'run-length-limit')).toEqual({type:'run-length-limit',max_length:3});
  expect(data.clues.length).toBeGreaterThan(0); expect(data.evidence.unique).toBe(true);
  await page.getByLabel('同色の最大連続長', {exact:true}).fill('2');
  await expect(page.locator('#generate')).toBeEnabled();
  const stricter=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const second=await (await stricter).json(); expect(second.status).toBe('ok'); expect(second.clues).toEqual([]);
  expect(second.record.solution).toEqual([[0,0,1,1,0,0]]);
  await page.getByLabel('同色の最大連続長', {exact:true}).fill('1');
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  expect(errors).toEqual([]);
});
