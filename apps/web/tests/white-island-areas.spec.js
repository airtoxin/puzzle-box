import {test, expect} from '@playwright/test';

async function configure(page) {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.getByLabel('黒マスをつなぐ', {exact:true}).check();
  await page.getByLabel('黒い2×2を禁止', {exact:true}).check();
  await page.getByLabel('白い島の面積を数字に合わせる', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
}

test('Nurikabe areas compose with independent labels, visibility and room inputs', async ({page}) => {
  const errors=[]; page.on('pageerror',e => errors.push(e.message));
  await configure(page);
  await page.getByLabel('白マスの数字を重複させない', {exact:true}).check();
  await page.getByLabel('固定数字（行ごとに入力）', {exact:true}).fill('1 2 3\n4 5 6');
  await page.getByLabel('数字から見える白マス数を固定', {exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）', {exact:true}).fill('0 0 0\n0 0 2');
  await page.getByLabel('各部屋内で黒をつなぐ', {exact:true}).check();
  await expect(page.locator('#rules textarea:visible')).toHaveCount(4);
  await expect(page.locator('.area-number')).toHaveText(['1','2']);
  await expect(page.locator('.sight-number')).toHaveText(['2']);
  await expect(page.locator('.cell-number')).toHaveText(['1','2','3','4','5','6']);
  await expect(page.locator('#generate')).toBeEnabled();
  // The default L-shaped room splits two black cells that connect globally
  // through a different room. UI compatibility does not imply feasibility.
  const invalid=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await invalid).json()).status).toBe('unsatisfiable');
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）', {exact:true}).fill('0 0 0\n1 1 1');
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok'); expect(data.clues).toEqual([]);
  expect(data.record.solution).toEqual([[0,1,0],[1,1,0]]);
  for (let i=0; i<6; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if (i === 0 || i === 5) {await expect(cell).toBeDisabled(); await expect(cell).toHaveAttribute('data-value','0');}
    else while (await cell.getAttribute('data-value') !== String(data.record.solution[Math.floor(i/3)][i%3])) await cell.click();
  }
  await expect(page.locator('[data-cell-index="5"]')).toHaveAccessibleName(/白.*数字6.*見える白2.*白い島の面積2.*部屋2/);
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('area-sight-number-room-board.png')});
  await page.getByLabel('白い島の面積（0は数字なし）', {exact:true}).fill('0 0 0\n0 0 0');
  await expect(page.locator('.area-number')).toHaveCount(0);
  await expect(page.locator('.sight-number')).toHaveText(['2']);
  await expect(page.locator('.cell-number')).toHaveText(['1','2','3','4','5','6']);
  expect(errors).toEqual([]);
});

for (const change of ['missing','changed','unrequested']) test(`${change} island area data is rejected`, async ({page}) => {
  await configure(page);
  if (change === 'unrequested') {
    await page.getByLabel('白い島の面積を数字に合わせる', {exact:true}).uncheck();
    await expect(page.locator('.area-number')).toHaveCount(0);
  }
  await page.route('**/api/plan', async route => {
    const response=await route.fetch(), data=await response.json();
    if (data.status === 'ok') {
      if (change === 'missing') delete data.plan.island_areas;
      else data.plan.island_areas=[[1,0,0],[0,0,3]];
    }
    await route.fulfill({json:data});
  });
  await page.locator('#seed').fill('1');
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled(); await expect(page.locator('.cell')).toHaveCount(0);
});
