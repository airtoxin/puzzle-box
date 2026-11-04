import {test, expect} from '@playwright/test';

async function configure(page) {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.getByLabel('黒マスを離す', {exact:true}).check();
  await page.getByLabel('数字から見える白マス数を固定', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
}

test('sight counts, Hitori labels, and rooms have independent inputs and compose', async ({page}) => {
  const errors=[]; page.on('pageerror', e => errors.push(e.message));
  await configure(page);
  await page.getByLabel('白マスの数字を重複させない', {exact:true}).check();
  await page.getByLabel('各部屋の黒数を固定', {exact:true}).check();
  await page.getByLabel('各部屋の黒マス数', {exact:true}).fill('1');
  await expect(page.locator('#rules textarea:visible')).toHaveCount(3);
  await expect(page.locator('.sight-number')).toHaveText(['3','2']);
  await expect(page.locator('.cell-number')).toHaveText(['1','1','2','2','3','2']);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok'); expect(data.clues).toEqual([]);
  expect(data.record.rules.find(r => r.type === 'white-visibility-counts').counts).toEqual([[0,3,2],[0,0,0]]);
  for (let i=0; i<6; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    const value=String(data.record.solution[Math.floor(i/3)][i%3]);
    if (i === 1 || i === 2) {
      await expect(cell).toBeDisabled(); await expect(cell).toHaveAttribute('data-value','0');
    } else while (await cell.getAttribute('data-value') !== value) await cell.click();
  }
  await expect(page.locator('[data-cell-index="1"]')).toHaveAccessibleName(/白.*数字1.*見える白3.*部屋1/);
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('sight-number-room-board.png')});
  await page.getByLabel('見える白マス数（0は指定なし）', {exact:true}).fill('0 4 0\n0 0 0');
  await expect(page.locator('.sight-number')).toHaveText(['4']);
  await expect(page.locator('.cell-number')).toHaveText(['1','1','2','2','3','2']);
  await page.getByLabel('数字から見える白マス数を固定', {exact:true}).uncheck();
  await expect(page.locator('.sight-number')).toHaveCount(0);
  await expect(page.locator('.cell-number')).toHaveCount(6);
  expect(errors).toEqual([]);
});

for (const change of ['missing','changed','unrequested']) test(`${change} sight data is rejected`, async ({page}) => {
  await configure(page);
  if (change === 'unrequested') {
    await page.getByLabel('数字から見える白マス数を固定', {exact:true}).uncheck();
    await expect(page.locator('.sight-number')).toHaveCount(0);
  }
  await page.route('**/api/plan', async route => {
    const response=await route.fetch(), data=await response.json();
    if (data.status === 'ok') {
      if (change === 'missing') delete data.plan.sight_counts;
      else data.plan.sight_counts=[[0,4,0],[0,0,0]];
    }
    await route.fulfill({json:data});
  });
  await page.locator('#seed').fill('1');
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled(); await expect(page.locator('.cell')).toHaveCount(0);
});
