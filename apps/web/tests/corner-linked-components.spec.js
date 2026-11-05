import {test, expect} from '@playwright/test';

async function start(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('各成分を別の成分と角でつなぐ',{exact:true}).check();
}

test('corner links compose with global component and cell counts, then check a real answer',async({page})=>{
  await start(page);
  await page.getByLabel('黒マス数',{exact:true}).fill('3');
  await page.getByLabel('各部屋の対象色の成分数を固定',{exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0 0 0\n0 0 0');
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
  await page.locator('#board').screenshot({path:test.info().outputPath('corner-chain-board.png')});
  await page.getByLabel('黒マスをつなぐ',{exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
});

test('empty target colors are permitted and the Boolean changes the actual constraints',async({page})=>{
  await start(page);await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.locator('#rows').fill('1');
  await expect(page.locator('#rules textarea:visible')).toHaveCount(0);
  for(const [black,answer] of [[true,'000'],[false,'111']]) {
    await page.getByLabel('角でつなぐ色は黒（オフなら白）',{exact:true}).setChecked(black);
    await expect(page.locator('#generate')).toBeEnabled();
    const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
    const data=await (await generated).json();expect(data.status).toBe('ok');
    expect(data.record.solution.flat().join('')).toBe(answer);expect(data.clues).toEqual([]);
    expect(data.record.rules.find(r=>r.type==='corner-linked-components').black).toBe(black);
  }
});

test('six by six corner-linked puzzle renders and checks both answers',async({page})=>{
  await start(page);
  await page.locator('#rows').fill('6');
  await page.locator('#cols').fill('6');
  await page.getByLabel('黒マス数',{exact:true}).fill('6');
  const maxBudget=Number(await page.locator('#budget').getAttribute('max'));
  await page.locator('#budget').fill(String(Math.min(10,maxBudget)));
  const generated=page.waitForResponse('**/api/generate');
  await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');
  await expect(page.locator('#board [data-cell-index]')).toHaveCount(36);
  for(let i=0;i<36;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if(await cell.isEnabled()) while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  let checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  const editable=page.locator('#board [data-cell-index]:enabled').first();
  await expect(editable).toBeVisible();
  const original=await editable.getAttribute('data-value');
  expect(['0','1']).toContain(original);
  const opposite=String(1-Number(original));
  for(const target of [opposite,original,opposite]) {
    for(let turn=0;turn<3 && await editable.getAttribute('data-value')!==target;turn++) await editable.click();
    await expect(editable).toHaveAttribute('data-value',target);
  }
  checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:false});
});
