import {test, expect} from '@playwright/test';

async function configure(page) {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  await page.getByLabel('数字の周囲の黒マス数を固定', {exact:true}).check();
  await expect(page.getByLabel('周囲の黒数（. は数字なし、0も有効）', {exact:true})).toHaveValue('0 . 1\n. 1 .');
  await expect(page.locator('#generate')).toBeEnabled();
}

test('zero clues and nulls retain their meaning with four other numeric and room inputs', async ({page}) => {
  const errors=[]; page.on('pageerror',e => errors.push(e.message));
  await configure(page);
  await page.getByLabel('白マスの数字を重複させない', {exact:true}).check();
  await page.getByLabel('固定数字（行ごとに入力）', {exact:true}).fill('1 2 3\n4 5 6');
  await page.getByLabel('数字から見える白マス数を固定', {exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）', {exact:true}).fill('4 0 0\n0 0 0');
  await page.getByLabel('白い島の面積を数字に合わせる', {exact:true}).check();
  await page.getByLabel('白い島の面積（0は数字なし）', {exact:true}).fill('5 0 0\n0 0 0');
  await page.getByLabel('各部屋内で黒をつなぐ', {exact:true}).check();
  await page.getByLabel('各部屋に黒を1つ以上置く', {exact:true}).uncheck();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）', {exact:true}).fill('0 0 0\n1 1 1');
  await expect(page.locator('#rules textarea:visible')).toHaveCount(5);
  await expect(page.locator('.neighbor-number')).toHaveText(['隣0','隣1','隣1']);
  await expect(page.locator('#plan-note')).toContainText('0もヒント');
  await page.getByLabel('黒マスの個数', {exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const bad=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await bad).json()).status).toBe('unsatisfiable'); // Fixed total 2 contradicts the unique one-mine board.
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json(); expect(data.status).toBe('ok'); expect(data.clues).toEqual([]);
  expect(data.record.solution).toEqual([[0,0,0],[0,0,1]]);
  expect(data.record.rules.find(r => r.type === 'adjacent-black-counts').neighbor_counts).toEqual([[0,null,1],[null,1,null]]);
  for (let i=0; i<6; i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if ([0,2,4].includes(i)) {await expect(cell).toBeDisabled(); await expect(cell).toHaveAttribute('data-value','0');}
    else while (await cell.getAttribute('data-value') !== String(data.record.solution[Math.floor(i/3)][i%3])) await cell.click();
  }
  await expect(page.locator('[data-cell-index="0"]')).toHaveAccessibleName(/白.*数字1.*見える白4.*白い島の面積5.*隣接黒数0.*部屋1/);
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('neighbor-mixed-board.png')});
  await page.getByLabel('周囲の黒数（. は数字なし、0も有効）', {exact:true}).fill('. . 1\n. 1 .');
  await expect(page.locator('.neighbor-number')).toHaveText(['隣1','隣1']);
  await expect(page.locator('.sight-number')).toHaveText(['4']);
  await expect(page.locator('.area-number')).toHaveText(['5']);
  await page.getByLabel('周囲の黒数（. は数字なし、0も有効）', {exact:true}).fill('null . 1\n. 1 .');
  await expect(page.locator('#generate')).toBeDisabled();
  expect(errors).toEqual([]);
});

for (const change of ['missing','zero-to-null','unrequested']) test(`${change} neighbor counts are rejected`, async ({page}) => {
  await configure(page);
  if (change === 'unrequested') {
    await page.getByLabel('数字の周囲の黒マス数を固定', {exact:true}).uncheck();
    await expect(page.locator('.neighbor-number')).toHaveCount(0);
  }
  await page.route('**/api/plan', async route => {
    const response=await route.fetch(), data=await response.json();
    if (data.status === 'ok') {
      if (change === 'missing') delete data.plan.neighbor_counts;
      else data.plan.neighbor_counts=[[null,null,1],[null,1,null]];
    }
    await route.fulfill({json:data});
  });
  await page.locator('#seed').fill('1');
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled(); await expect(page.locator('.cell')).toHaveCount(0);
});

test('a zero changed to null in a generated plan cannot expose an answer', async ({page}) => {
  await configure(page);
  await page.route('**/api/generate', async route => {
    const response=await route.fetch(), data=await response.json();
    expect(data.status).toBe('ok');
    data.plan.neighbor_counts[0][0]=null;
    await route.fulfill({json:data});
  });
  await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled();
  await expect(page.locator('#actions')).toBeHidden(); await expect(page.locator('#board')).toBeEmpty();
});
