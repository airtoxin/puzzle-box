import {test, expect} from '@playwright/test';

async function configure(page,length=3) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('丸を白の端点と一致させる',{exact:true}).check();
  await page.getByLabel('数字から見える白マス数を固定',{exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）',{exact:true}).fill(`${length} 0 0\n0 0 2`);
  await page.getByLabel('黒い2×2を禁止',{exact:true}).check();
  await page.getByLabel('白の2×2を禁止',{exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
}

test('numbered endpoints reuse visibility and place their length inside the large circles',async ({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await configure(page);
  await expect(page.locator('.endpoint-length .sight-number')).toHaveText(['3','2']);
  await expect(page.locator('#plan-note')).toContainText('丸自身を含む直線長');
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toEqual([]);
  expect(data.record.solution).toEqual([[0,0,0],[1,1,0]]);
  await expect(page.locator('.endpoint-length:disabled')).toHaveCount(2);
  for (let i=0;i<6;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if (await cell.isEnabled()) while (await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('numbered-endpoints.png')});
  expect(errors).toEqual([]);
});

for (const length of [1,4]) test(`length ${length} is well-formed but mathematically impossible in the example`,async ({page})=>{
  await configure(page,length);
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  expect((await (await generated).json()).status).toBe('unsatisfiable');
});
