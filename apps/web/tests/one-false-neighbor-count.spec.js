import {test, expect} from '@playwright/test';

async function configure(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('各部屋の隣接黒数にウソを1つだけ置く',{exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0 0 0\n0 0 0');
  await page.getByLabel('周囲の黒数（. は数字なし、0も有効）',{exact:true}).fill('1 . .\n2 . .');
  await page.getByLabel('各行の黒マス数',{exact:true}).uncheck();
  await page.getByLabel('各列の黒マス数',{exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
}

test('one false clue composes with non-touching and connected white, without extra givens',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await configure(page);
  await page.getByLabel('黒マスを離す',{exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(page.locator('#rules textarea:visible')).toHaveCount(2);
  await expect(page.locator('.neighbor-number')).toHaveText(['隣1','隣2']);
  await expect(page.locator('#rules')).toContainText('部屋外の隣も数えます');
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toEqual([]);
  expect(data.record.solution).toEqual([[0,1,0],[0,0,0]]);
  for(let i=0;i<6;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if([0,3].includes(i)) {await expect(cell).toBeDisabled();await expect(cell).toHaveAttribute('data-value','0');}
    else while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('one-false-count-board.png')});
  // Same parameter and channel can be rendered together but constraints conflict.
  await page.getByLabel('数字の周囲の黒マス数を固定',{exact:true}).check();
  await page.getByLabel('斜めの4マスも数える',{exact:true}).uncheck();
  await expect(page.locator('#rules textarea:visible')).toHaveCount(2);
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');expect(errors).toEqual([]);
});

test('a room without clues is unsatisfiable and malformed numeric input stays disabled',async({page})=>{
  await configure(page);
  const counts=page.getByLabel('周囲の黒数（. は数字なし、0も有効）',{exact:true});
  await counts.fill('. . .\n. . .');await expect(page.locator('#generate')).toBeEnabled();
  await expect(page.locator('.neighbor-number')).toHaveCount(0);
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  expect((await (await generated).json()).status).toBe('unsatisfiable');
  await counts.fill('null . 1\n. 1 .');await expect(page.locator('#generate')).toBeDisabled();
});
