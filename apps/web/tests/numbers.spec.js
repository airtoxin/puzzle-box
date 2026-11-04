import {test, expect} from '@playwright/test';

async function configure(page) {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.getByLabel('黒マスを離す', {exact:true}).check();
  await page.getByLabel('白マスの数字を重複させない', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
}

test('number grid and room boundaries compose and survive answer entry', async ({page}) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await configure(page);
  await expect(page.getByLabel('固定数字（行ごとに入力）', {exact:true})).toBeVisible();
  await expect(page.locator('.cell-number')).toHaveText(['1','1','2','2','3','2']);
  await page.getByLabel('各部屋の黒数を固定', {exact:true}).check();
  await page.getByLabel('各部屋の黒マス数', {exact:true}).fill('1');
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）', {exact:true}).fill('0 0 0\n1 1 1');
  await expect(page.locator('#rules textarea:visible')).toHaveCount(2);
  await expect(page.locator('#generate')).toBeEnabled();
  const response = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data = await (await response).json(); expect(data.status).toBe('ok'); expect(data.clues).toEqual([]);
  expect(data.record.rules.find(r => r.type === 'distinct-white-numbers').numbers).toEqual([[1,1,2],[2,3,2]]);
  await expect(page.locator('.room-board [data-room="0"]')).toHaveCount(3);
  for (let i=0; i<6; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`), value=data.record.solution[Math.floor(i/3)][i%3];
    while (await cell.getAttribute('data-value') !== String(value)) await cell.click();
  }
  await expect(page.locator('[data-cell-index="0"] .cell-number')).toHaveText('1');
  await expect(page.locator('[data-cell-index="0"]')).toHaveAccessibleName(/黒.*数字1.*部屋1/);
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('number-room-board.png')});
  await page.getByLabel('固定数字（行ごとに入力）', {exact:true}).fill('99 99 0\n0 1 0');
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(page.locator('.cell-number')).toHaveText(['99','99','0','0','1','0']);
  await page.getByLabel('固定数字（行ごとに入力）', {exact:true}).fill('1 x 2\n2 3 2');
  await expect(page.locator('#status')).toContainText('固定数字'); await expect(page.locator('#generate')).toBeDisabled();
  expect(errors).toEqual([]);
});

for (const kind of ['missing','changed']) test(`${kind} fixed numbers cannot be silently displayed`, async ({page}) => {
  await configure(page);
  await page.route('**/api/plan', async route => {
    const response=await route.fetch(), data=await response.json();
    if (data.status === 'ok') {
      if (kind === 'missing') delete data.plan.numbers;
      else data.plan.numbers=[[0,0,1],[1,2,1]]; // same equality pattern, different visible labels
    }
    await route.fulfill({json:data});
  });
  await page.locator('#seed').fill('1');
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled(); await expect(page.locator('.cell')).toHaveCount(0);
});
