import {test, expect} from '@playwright/test';

async function emptyRules(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('各行の黒マス数',{exact:true}).uncheck();
  await page.getByLabel('各列の黒マス数',{exact:true}).uncheck();
}

async function generate(page) {
  await expect(page.locator('#generate')).toBeEnabled();
  const reply=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  return (await reply).json();
}

test('diagonal runs compose with rooms and orthogonal triples, retaining needed hints',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await emptyRules(page);await page.locator('#rows').fill('3');await page.locator('#cols').fill('3');
  await page.getByLabel('各部屋の黒数を固定',{exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0 0 1\n2 1 1\n2 3 3');
  await page.getByLabel('各部屋の黒マス数',{exact:true}).fill('1');
  await page.getByLabel('同色の3連続を禁止',{exact:true}).check();
  await page.getByLabel('斜めの同色連続長を制限',{exact:true}).check();
  await expect(page.getByLabel('斜めの最大連続長',{exact:true})).toHaveValue('2');
  const data=await generate(page);expect(data.status).toBe('ok');expect(data.evidence.unique).toBe(true);
  expect(data.clues.length).toBeGreaterThan(0);
  expect(data.record.rules.find(r=>r.type==='diagonal-run-limit')).toEqual({type:'diagonal-run-limit',max_length:2});
  await expect(page.locator('#board .cell')).toHaveCount(9);
  const editable=page.locator('#board .cell:enabled');expect(await editable.count()).toBeGreaterThan(0);
  for(let i=0;i<9;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if(await cell.isEnabled()) {
      await expect(cell).toHaveAttribute('data-value','-1');
      while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
    }
  }
  const correct=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await correct).json()).toEqual({status:'ok',correct:true});
  const cell=editable.first(),color=await cell.getAttribute('data-value');
  while(await cell.getAttribute('data-value')===color || await cell.getAttribute('data-value')==='-1') await cell.click();
  const wrong=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await wrong).json()).toEqual({status:'ok',correct:false});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('diagonal-runs-board.png')});
  await page.getByLabel('黒・白のセルヒント',{exact:true}).uncheck();
  const ambiguous=await generate(page);expect(ambiguous.status).toBe('insufficient_hints');
  expect(errors).toEqual([]);
});

test('diagonal and orthogonal maximums have independent editors and constraints',async({page})=>{
  await emptyRules(page);await page.locator('#rows').fill('2');await page.locator('#cols').fill('2');
  await page.getByLabel('同色の連続長に上限を付ける',{exact:true}).check();
  await page.getByLabel('斜めの同色連続長を制限',{exact:true}).check();
  await expect(page.getByLabel('同色の最大連続長',{exact:true})).toHaveValue('3');
  await expect(page.getByLabel('斜めの最大連続長',{exact:true})).toHaveValue('2');
  await page.getByLabel('同色の最大連続長',{exact:true}).fill('1');
  await page.getByLabel('斜めの最大連続長',{exact:true}).fill('1');
  expect((await generate(page)).status).toBe('unsatisfiable');
  await page.getByLabel('斜めの最大連続長',{exact:true}).fill('2');
  const data=await generate(page);expect(data.status).toBe('ok');
  expect(data.record.rules).toEqual([{type:'run-length-limit',max_length:1},{type:'diagonal-run-limit',max_length:2}]);
  expect(data.clues.length).toBeGreaterThan(0);
});

test('the diagonal integer editor enforces the Web range',async({page})=>{
  await emptyRules(page);await page.getByLabel('斜めの同色連続長を制限',{exact:true}).check();
  const field=page.getByLabel('斜めの最大連続長',{exact:true});
  await expect(field).toHaveAttribute('min','1');await expect(field).toHaveAttribute('max','25');
  for(const invalid of ['0','26']) {await field.fill(invalid);await expect(page.locator('#generate')).toBeDisabled();}
  await field.fill('25');await expect(page.locator('#generate')).toBeEnabled();
});
