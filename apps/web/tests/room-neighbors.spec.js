import {test, expect} from '@playwright/test';

async function start(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('異なる部屋の対象色を辺で接触させない',{exact:true}).check();
  await page.getByLabel('辺で隣り合う部屋の対象色の個数を変える',{exact:true}).check();
}

test('Shimaguni fragments compose with room connectivity, retained cells and server checking',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await start(page);
  await page.getByLabel('各部屋内で黒をつなぐ',{exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0 0 0\n1 1 1');
  await page.getByLabel('各行の黒マス数',{exact:true}).uncheck();
  await page.getByLabel('各列の黒マス数',{exact:true}).uncheck();
  await expect(page.locator('textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toHaveLength(2);
  expect(['001110','011100','100011','110001']).toContain(data.record.solution.flat().join(''));
  for(let i=0;i<6;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if(await cell.isEnabled()) while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('shimaguni-board.png')});
  await page.getByLabel('黒・白のセルヒント',{exact:true}).uncheck();
  await page.getByLabel('各行の黒マス数',{exact:true}).check();
  await page.getByLabel('各列の黒マス数',{exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const insufficient=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  expect((await (await insufficient).json()).status).toBe('insufficient_hints');
  expect(errors).toEqual([]);
});

test('count-color and contact-color remain independent while room layout is shared',async({page})=>{
  await start(page);
  await page.locator('#rows').fill('1');
  await page.getByLabel('各部屋の黒数を固定',{exact:true}).check();
  await page.getByLabel('各部屋の黒マス数',{exact:true}).fill('1');
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0 0 1');
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  await page.getByLabel('部屋ごとの個数を比べる色は黒（オフなら白）',{exact:true}).uncheck();
  await expect(page.getByLabel('境界越しの接触を禁止する色は黒（オフなら白）',{exact:true})).toBeChecked();
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');
  expect(data.record.solution.flat().join('')).toBe('101');expect(data.clues).toEqual([]);
  expect(data.record.rules.find(r=>r.type==='no-color-across-rooms').black).toBe(true);
  expect(data.record.rules.find(r=>r.type==='adjacent-room-counts-differ').black).toBe(false);
  await expect(page.locator('textarea[data-kind="region-map"]')).toHaveCount(1);
});
