import {test, expect} from '@playwright/test';

test('corner connection composes with orthogonal singleton areas without merging them', async ({page}) => {
  const errors=[]; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.locator('#cols').fill('2');
  await page.getByLabel('タテヨコ・ナナメで色をつなぐ', {exact:true}).check();
  await page.getByLabel('白い島の面積を数字に合わせる', {exact:true}).check();
  await page.getByLabel('白い島の面積（0は数字なし）', {exact:true}).fill('1 0\n0 1');
  await page.getByLabel('連結成分を長方形にする', {exact:true}).check();
  const rectangles=page.locator('.rule-card').filter({has:page.getByLabel('連結成分を長方形にする', {exact:true})});
  await rectangles.getByLabel('黒を対象にする（オフなら白）', {exact:true}).uncheck();
  await page.getByLabel('黒い2×2を禁止', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok'); expect(data.clues).toEqual([]);
  expect(data.record.solution).toEqual([[0,1],[1,0]]);
  await expect(page.locator('.area-number')).toHaveText(['1','1']);
  for (const index of [1,2]) {
    const cell=page.locator(`[data-cell-index="${index}"]`);
    while (await cell.getAttribute('data-value') !== '1') await cell.click();
  }
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  // Requiring orthogonal white connectivity as well is stronger and conflicts.
  await page.getByLabel('白マスをつなぐ', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  expect(errors).toEqual([]);
});

test('corner-connected color and nonempty controls preserve their distinct meanings', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.locator('#cols').fill('2');
  await page.getByLabel('黒マス数', {exact:true}).fill('4');
  await page.getByLabel('タテヨコ・ナナメで色をつなぐ', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  let response=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await response).json()).status).toBe('unsatisfiable');
  await page.getByLabel('頂点経由でつなぐ色を1つ以上にする', {exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
  response=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await response).json()).record.solution).toEqual([[1,1],[1,1]]);
  await page.getByLabel('頂点経由でつなぐ色は黒（オフなら白）', {exact:true}).check();
  await page.getByLabel('頂点経由でつなぐ色を1つ以上にする', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  response=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await response).json(); expect(data.status).toBe('ok');
  expect(data.record.rules.find(r => r.type === 'corner-connected-color')).toEqual({type:'corner-connected-color',black:true,nonempty:true});
});
