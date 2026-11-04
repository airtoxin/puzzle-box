import {test, expect} from '@playwright/test';

async function configure(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.locator('#rows').fill('3');await page.locator('#cols').fill('3');
  await page.getByLabel('周囲8マスの黒い連続長を指定',{exact:true}).check();
  await page.getByLabel('黒の連続長（複数は1,2、なしは.、黒0個は0）',{exact:true}).fill('. 2,1 .\n. 6 .\n. . .');
  await page.getByLabel('黒マスをつなぐ',{exact:true}).check();
  await page.getByLabel('黒い2×2を禁止',{exact:true}).check();
  await expect(page.locator('.run-number')).toHaveText(['連1,2','連6']);
  await expect(page.locator('#generate')).toBeEnabled();
}

async function enterAndCheck(page,data) {
  for(let i=0;i<9;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if(await cell.isEnabled()) while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
}

test('unordered cyclic clues compose into a real Tapa problem with a retained hint',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await configure(page);
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toHaveLength(1);
  expect(['100101111','001101111']).toContain(data.record.solution.flat().join(''));
  expect(data.record.rules.find(r=>r.type==='adjacent-black-runs').run_clues[0][1]).toEqual([1,2]);
  await expect(page.locator('[data-cell-index="1"]')).toBeDisabled();
  await expect(page.locator('[data-cell-index="4"]')).toHaveAccessibleName(/白.*周囲の黒い連続長6/);
  await enterAndCheck(page,data);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('tapa-board.png')});
  expect(errors).toEqual([]);
});

test('run clues stay distinct from labels, sight, area, adjacent count and whole component size',async({page})=>{
  await configure(page);
  await page.getByLabel('白マスの数字を重複させない',{exact:true}).check();
  await page.getByLabel('固定数字（行ごとに入力）',{exact:true}).fill('1 2 3\n4 5 6\n7 8 9');
  await page.getByLabel('数字から見える白マス数を固定',{exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）',{exact:true}).fill('0 3 0\n0 0 0\n0 0 0');
  await page.getByLabel('数字がある白成分の面積を固定',{exact:true}).check();
  await page.getByLabel('白い島の面積（0は数字なし）',{exact:true}).fill('0 3 0\n0 0 0\n0 0 0');
  await page.getByLabel('数字の周囲の黒マス数を固定',{exact:true}).check();
  await page.getByLabel('周囲の黒数（. は数字なし、0も有効）',{exact:true}).fill('. 3 .\n. . .\n. . .');
  await page.getByLabel('接する黒成分の面積合計を固定',{exact:true}).check();
  await page.getByLabel('接する黒成分の面積合計（. は丸なし）',{exact:true}).fill('. 6 .\n. . .\n. . .');
  await expect(page.locator('#rules textarea:visible')).toHaveCount(6);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toHaveLength(1);
  await enterAndCheck(page,data);
  await expect(page.locator('[data-cell-index="1"]')).toHaveAccessibleName(/数字2.*見える白3.*白い島の面積3.*隣接黒数3.*接する黒成分の面積合計6.*周囲の黒い連続長1,2/);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  const labelBox=await page.locator('[data-cell-index="1"] .cell-number').boundingBox();
  const runBox=await page.locator('[data-cell-index="1"] .run-number').boundingBox();
  expect(labelBox.y+labelBox.height).toBeLessThanOrEqual(runBox.y);
  await page.locator('#board').screenshot({path:test.info().outputPath('tapa-mixed-board.png')});
});

test('zero run clue is visible and absent cells remain unmarked',async({page})=>{
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('周囲8マスの黒い連続長を指定',{exact:true}).check();
  const field=page.getByLabel('黒の連続長（複数は1,2、なしは.、黒0個は0）',{exact:true});
  await field.fill('0 . .\n. . .');
  await expect(page.locator('.run-number')).toHaveText(['連0']);
  await expect(page.locator('[data-cell-index="0"]')).toHaveAttribute('data-value','0');
  await field.fill('. . .\n. . .');
  await expect(page.locator('.run-number')).toHaveCount(0);
  await expect(page.locator('[data-cell-index="0"]')).toHaveAttribute('data-value','-1');
});

for (const [title,label,value,selector,runs] of [
  ['数字から見える白マス数を固定','見える白マス数（0は指定なし）','1 0 0\n0 0 0','.sight-number','3'],
  ['数字がある白成分の面積を固定','白い島の面積（0は数字なし）','1 0 0\n0 0 0','.area-number','3'],
  ['数字の周囲の黒マス数を固定','周囲の黒数（. は数字なし、0も有効）','3 . .\n. . .','.neighbor-number','3'],
  ['接する黒成分の面積合計を固定','接する黒成分の面積合計（. は丸なし）','3 . .\n. . .','.component-number','3'],
  ['数字の周囲の黒マス数を固定','周囲の黒数（. は数字なし、0も有効）','0 . .\n. . .','.neighbor-number','0'],
  ['接する黒成分の面積合計を固定','接する黒成分の面積合計（. は丸なし）','0 . .\n. . .','.component-number','0'],
]) test(`only run clues and ${selector} ${runs} remain separately readable`,async({page})=>{
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('周囲8マスの黒い連続長を指定',{exact:true}).check();
  await page.getByLabel('黒の連続長（複数は1,2、なしは.、黒0個は0）',{exact:true}).fill(`${runs} . .\n. . .`);
  await page.getByLabel(title,{exact:true}).check();
  await page.getByLabel(label,{exact:true}).fill(value);
  await expect(page.locator('#generate')).toBeEnabled();
  await page.setViewportSize({width:390,height:844});
  const cell=page.locator('[data-cell-index="0"]');
  const a=await cell.locator('.run-number').boundingBox(),b=await cell.locator(selector).boundingBox();
  expect(a.x+a.width<=b.x || b.x+b.width<=a.x || a.y+a.height<=b.y || b.y+b.height<=a.y).toBe(true);
  await expect(cell).toHaveAccessibleName(/周囲の黒い連続長/);
});

test('impossible cyclic partitions are rejected as malformed input',async({page})=>{
  await configure(page);
  await page.getByLabel('黒の連続長（複数は1,2、なしは.、黒0個は0）',{exact:true}).fill('. 1,7 .\n. 6 .\n. . .');
  await expect(page.locator('#status')).toContainText('白い区切りを含め8マス以内');
  await expect(page.locator('#generate')).toBeDisabled();
});

for(const change of ['missing','changed','scalar-zero','unrequested']) test(`${change} black-run plans are rejected`,async({page})=>{
  await configure(page);
  if(change==='unrequested') {
    await page.getByLabel('周囲8マスの黒い連続長を指定',{exact:true}).uncheck();
    await expect(page.locator('.run-number')).toHaveCount(0);
  }
  await page.route('**/api/plan',async route=>{
    const response=await route.fetch(),data=await response.json();
    if(data.status==='ok') {
      if(change==='missing') delete data.plan.black_run_clues;
      else data.plan.black_run_clues=[[null,change==='scalar-zero'?0:[1,1],null],[null,[6],null],[null,null,null]];
    }
    await route.fulfill({json:data});
  });
  await page.locator('#seed').fill('1');
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled();
  await expect(page.locator('.cell')).toHaveCount(0);
});
