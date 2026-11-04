import {test, expect} from '@playwright/test';

async function start(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('各部屋の対象色の成分数を固定',{exact:true}).check();
  await page.getByLabel('成分の大きさを部屋ごとにそろえる',{exact:true}).check();
}

test('Nuritwin local components compose with global black connectivity and keep one cell hint',async({page})=>{
  await start(page);
  await page.locator('#rows').fill('3');await page.locator('#cols').fill('3');
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0 0 1\n0 1 1\n1 1 1');
  await page.getByLabel('黒マスをつなぐ',{exact:true}).check();
  await page.getByLabel('黒い2×2を禁止',{exact:true}).check();
  await page.getByLabel('各行の黒マス数',{exact:true}).uncheck();
  await page.getByLabel('各列の黒マス数',{exact:true}).uncheck();
  await expect(page.locator('textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toHaveLength(1);
  expect(['011110000','010110100']).toContain(data.record.solution.flat().join(''));
  for(let i=0;i<9;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if(await cell.isEnabled()) while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('nuritwin-board.png')});
  await page.getByLabel('各部屋の対象色の成分数',{exact:true}).fill('0');
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
});

test('color and zero component count change visible answers without counting witness choices',async({page})=>{
  await start(page);
  await page.locator('#rows').fill('1');
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0 0 0');
  for(const [black,count,answer] of [[true,2,'101'],[false,2,'010'],[true,0,'000']]) {
    await page.getByLabel('成分を数える色は黒（オフなら白）',{exact:true}).setChecked(black);
    await page.getByLabel('サイズをそろえる色は黒（オフなら白）',{exact:true}).setChecked(black);
    await page.getByLabel('各部屋の対象色の成分数',{exact:true}).fill(String(count));
    await expect(page.locator('#generate')).toBeEnabled();
    const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
    const data=await (await generated).json();expect(data.status).toBe('ok');
    expect(data.record.solution.flat().join('')).toBe(answer);expect(data.clues).toEqual([]);
  }
});
