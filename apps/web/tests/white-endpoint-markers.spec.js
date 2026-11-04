import {test, expect} from '@playwright/test';

async function configure(page) {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact:true}).uncheck();
  await page.getByLabel('丸を白の端点と一致させる', {exact:true}).check();
  await page.getByLabel('黒い2×2を禁止', {exact:true}).check();
  await page.getByLabel('白の2×2を禁止', {exact:true}).check();
  await expect(page.getByLabel('端点の丸（0は丸なし、1は丸あり）', {exact:true})).toHaveValue('1 0 0\n0 0 1');
  await expect(page.locator('.endpoint-marked')).toHaveCount(2);
  await expect(page.locator('#generate')).toBeEnabled();
}

async function enterAndCheck(page,data) {
  for (let i=0;i<6;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
}

test('unnumbered endpoint circles generate, remain fixed white and support real answer entry', async ({page}) => {
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await configure(page);
  await expect(page.locator('#plan-note')).toContainText('大きな丸は白の端点');
  await expect(page.locator('[data-cell-index="0"]')).toHaveAttribute('data-value','0');
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues.length).toBeGreaterThan(0);
  expect(['000110','011000','001100']).toContain(data.record.solution.flat().join(''));
  await expect(page.locator('.endpoint-marked:disabled')).toHaveCount(2);
  await expect(page.locator('[data-cell-index="5"]')).toHaveAccessibleName(/白.*白の端点の丸/);
  await enterAndCheck(page,data);
  await expect(page.locator('.endpoint-marked')).toHaveCount(2);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('endpoint-circles.png')});
  expect(errors).toEqual([]);
});

test('endpoint circles share a cell with separate labels, sight and area meanings', async ({page}) => {
  await configure(page);
  await page.getByLabel('白マスの数字を重複させない', {exact:true}).check();
  await page.getByLabel('固定数字（行ごとに入力）', {exact:true}).fill('1 2 3\n4 5 6');
  await page.getByLabel('数字から見える白マス数を固定', {exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）', {exact:true}).fill('3 0 0\n0 0 0');
  await page.getByLabel('数字がある白成分の面積を固定', {exact:true}).check();
  await page.getByLabel('白い島の面積（0は数字なし）', {exact:true}).fill('4 0 0\n0 0 0');
  await expect(page.locator('#rules textarea:visible')).toHaveCount(4);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toEqual([]);
  expect(data.record.solution).toEqual([[0,0,0],[1,1,0]]);
  await enterAndCheck(page,data);
  await expect(page.locator('[data-cell-index="0"]')).toHaveAccessibleName(/数字1.*見える白3.*白い島の面積4.*白の端点の丸/);
  await page.locator('#board').screenshot({path:test.info().outputPath('endpoint-mixed-numbers.png')});
});

test('binary marker input rejects 2 before generation', async ({page}) => {
  await configure(page);
  await page.getByLabel('端点の丸（0は丸なし、1は丸あり）', {exact:true}).fill('2 0 0\n0 0 1');
  await expect(page.locator('#status')).toContainText('0（丸なし）か1（丸あり）');
  await expect(page.locator('#generate')).toBeDisabled();
});

for (const change of ['missing','changed','unrequested']) test(`${change} endpoint marker plans are refused`,async ({page})=>{
  await configure(page);
  if (change==='unrequested') {
    await page.getByLabel('丸を白の端点と一致させる', {exact:true}).uncheck();
    await expect(page.locator('.endpoint-marked')).toHaveCount(0);
  }
  await page.route('**/api/plan',async route=>{
    const response=await route.fetch(),data=await response.json();
    if (data.status==='ok') {
      if (change==='missing') delete data.plan.endpoint_markers;
      else data.plan.endpoint_markers=[[0,0,0],[0,0,1]];
    }
    await route.fulfill({json:data});
  });
  await page.locator('#seed').fill('1');
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled();
  await expect(page.locator('.cell')).toHaveCount(0);
});
