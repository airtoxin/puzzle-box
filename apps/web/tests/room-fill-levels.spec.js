import {test, expect} from '@playwright/test';

test('Aquarium levels reuse shared rooms and row/column hints and check a real answer',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.locator('#rows').fill('3');await page.locator('#cols').fill('3');
  await page.getByLabel('部屋の対象色を下から水平に満たす',{exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0 1 0\n0 1 0\n0 0 0');
  await page.getByLabel('黒・白のセルヒント',{exact:true}).uncheck();
  await expect(page.getByLabel('水に対応する色は黒（オフなら白）',{exact:true})).toBeChecked();
  await expect(page.locator('textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');
  expect(data.clues.length).toBeGreaterThan(0);
  expect(data.clues.every(c=>['row-count','column-count'].includes(c.type))).toBe(true);
  for (let i=0;i<9;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('aquarium-board.png')});
  await page.getByLabel('各部屋の黒数を固定',{exact:true}).check();
  await page.getByLabel('各部屋の黒マス数',{exact:true}).fill('1');
  await expect(page.locator('textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  expect(errors).toEqual([]);
});

test('white water reverses the fill direction but black counts still count black cells',async({page})=>{
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#rows').fill('3');await page.locator('#cols').fill('1');
  await page.getByLabel('黒マス数',{exact:true}).fill('1');
  await page.getByLabel('部屋の対象色を下から水平に満たす',{exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0\n0\n0');
  for (const [black,answer] of [[true,'001'],[false,'100']]) {
    await page.getByLabel('水に対応する色は黒（オフなら白）',{exact:true}).setChecked(black);
    await expect(page.locator('#generate')).toBeEnabled();
    const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
    const data=await (await generated).json();expect(data.status).toBe('ok');
    expect(data.record.solution.flat().join('')).toBe(answer);
    expect(data.record.rules.find(r=>r.type==='room-fill-levels').black).toBe(black);
    expect(data.clues).toEqual([]);
  }
});
