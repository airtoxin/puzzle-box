import {test, expect} from '@playwright/test';

const title='色を固定せず上下左右の黒数を指定';
const field='上下左右の黒数（. は数字なし、0も有効）';

async function start(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel(title,{exact:true}).check();
  await page.getByLabel('各行の黒マス数',{exact:true}).uncheck();
  await page.getByLabel('各列の黒マス数',{exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
}

function separate(a,b) {return a.x+a.width<=b.x || b.x+b.width<=a.x || a.y+a.height<=b.y || b.y+b.height<=a.y;}

async function enterAndCheck(page,data) {
  for(let i=0;i<data.record.solution.flat().length;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if(await cell.isEnabled()) while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
}

test('Paint Area uses a black numbered cell, five fragments and no additional hints',async({page})=>{
  await start(page);
  await expect(page.locator('[data-cell-index="0"]')).toHaveAttribute('data-value','-1');
  await page.getByLabel('部屋内を同じ色にする',{exact:true}).check();
  await page.getByLabel('黒マスをつなぐ',{exact:true}).check();
  await page.getByLabel('黒い2×2を禁止',{exact:true}).check();
  await page.getByLabel('白の2×2を禁止',{exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toEqual([]);
  expect(data.record.solution).toEqual([[1,1,0],[1,0,0]]);
  const number=page.locator('[data-cell-index="0"]');
  await expect(number).toBeEnabled();await expect(number).toHaveAttribute('data-value','-1');
  await expect(number.locator('.orthogonal-number')).toHaveText('接2');
  await enterAndCheck(page,data);
  await expect(number).toHaveAccessibleName(/黒.*上下左右の黒数2、数字セルの色は自由/);
  await expect(number.locator('.orthogonal-number')).toHaveCSS('color','rgb(255, 255, 255)');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('paint-area-board.png')});
});

test('zero is a visible clue and permits both colors, while null stays absent',async({page})=>{
  await start(page);await page.locator('#rows').fill('1');await page.locator('#cols').fill('1');
  await page.getByLabel(field,{exact:true}).fill('0');
  await page.getByLabel('黒マスの個数',{exact:true}).check();
  for(const color of [0,1]) {
    await page.getByLabel('黒マス数',{exact:true}).fill(String(color));
    await expect(page.locator('#generate')).toBeEnabled();
    const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
    const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toEqual([]);
    expect(data.record.solution).toEqual([[color]]);
    const cell=page.locator('[data-cell-index="0"]');await expect(cell).toBeEnabled();
    await expect(cell).toHaveAttribute('data-value','-1');await expect(cell.locator('.orthogonal-number')).toHaveText('接0');
    await enterAndCheck(page,data);
  }
  await page.getByLabel(field,{exact:true}).fill('.');await expect(page.locator('.orthogonal-number')).toHaveCount(0);
  await page.getByLabel(field,{exact:true}).fill('null');await expect(page.locator('#generate')).toBeDisabled();
});

test('eight independent numeric meanings use separate readable slots',async({page})=>{
  await start(page);await page.getByLabel(field,{exact:true}).fill('. . .\n. . 1');
  for(const [rule,label,value] of [
    ['数字セルが属する成分の面積を固定','所属する成分の面積（0は数字なし）','1 0 0\n0 0 4'],
    ['白マスの数字を重複させない','固定数字（行ごとに入力）','1 2 3\n4 5 6'],
    ['数字から見える白マス数を固定','見える白マス数（0は指定なし）','0 0 0\n0 0 3'],
    ['数字がある白成分の面積を固定','白い島の面積（0は数字なし）','0 0 0\n0 0 4'],
    ['数字の周囲の黒マス数を固定','周囲の黒数（. は数字なし、0も有効）','. . .\n. . 1'],
    ['接する黒成分の面積合計を固定','接する黒成分の面積合計（. は丸なし）','. . .\n. . 1'],
    ['周囲8マスの黒い連続長を指定','黒の連続長（複数は1,2、なしは.、黒0個は0）','. . .\n. . 1'],
  ]) {await page.getByLabel(rule,{exact:true}).check();await page.getByLabel(label,{exact:true}).fill(value);}
  await expect(page.locator('#rules textarea:visible')).toHaveCount(8);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');await enterAndCheck(page,data);
  await page.setViewportSize({width:390,height:844});
  const labels=page.locator('[data-cell-index="5"] > span:not(.cell-mark)');await expect(labels).toHaveCount(8);
  const boxes=await Promise.all((await labels.all()).map(label=>label.boundingBox()));
  const cellBox=await page.locator('[data-cell-index="5"]').boundingBox();
  for(const box of boxes) expect(box.x>=cellBox.x && box.y>=cellBox.y && box.x+box.width<=cellBox.x+cellBox.width && box.y+box.height<=cellBox.y+cellBox.height).toBe(true);
  for(let i=0;i<boxes.length;i++) for(let j=i+1;j<boxes.length;j++) expect(separate(boxes[i],boxes[j])).toBe(true);
  const mark=await page.locator('[data-cell-index="5"] .cell-mark').boundingBox();
  for(const box of boxes) expect(separate(box,mark)).toBe(true);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('eight-numeric-meanings.png')});
});

for(const [rule,label,value,selector] of [
  ['数字セルが属する成分の面積を固定','所属する成分の面積（0は数字なし）','3 0 0\n0 0 0','.component-area-number'],
  ['白マスの数字を重複させない','固定数字（行ごとに入力）','1 2 3\n4 5 6','.cell-number'],
  ['数字から見える白マス数を固定','見える白マス数（0は指定なし）','1 0 0\n0 0 0','.sight-number'],
  ['数字がある白成分の面積を固定','白い島の面積（0は数字なし）','1 0 0\n0 0 0','.area-number'],
  ['数字の周囲の黒マス数を固定','周囲の黒数（. は数字なし、0も有効）','2 . .\n. . .','.neighbor-number'],
  ['接する黒成分の面積合計を固定','接する黒成分の面積合計（. は丸なし）','2 . .\n. . .','.component-number'],
  ['周囲8マスの黒い連続長を指定','黒の連続長（複数は1,2、なしは.、黒0個は0）','1,1,1,1 . .\n. . .','.run-number'],
]) test(`only orthogonal counts and ${selector} stay separate`,async({page})=>{
  await start(page);await page.getByLabel(rule,{exact:true}).check();await page.getByLabel(label,{exact:true}).fill(value);
  await expect(page.locator('#generate')).toBeEnabled();await page.setViewportSize({width:390,height:844});
  const cell=page.locator('[data-cell-index="0"]');
  const a=await cell.locator('.orthogonal-number').boundingBox(),b=await cell.locator(selector).boundingBox();
  const cellBox=await cell.boundingBox();
  for(const box of [a,b]) expect(box.x>=cellBox.x && box.y>=cellBox.y && box.x+box.width<=cellBox.x+cellBox.width && box.y+box.height<=cellBox.y+cellBox.height).toBe(true);
  const mark=await cell.locator('.cell-mark').boundingBox();expect(separate(a,b)&&separate(a,mark)&&separate(b,mark)).toBe(true);
});

test('endpoint circles keep the count and answer mark visible',async({page})=>{
  await start(page);await page.getByLabel('丸を白の端点と一致させる',{exact:true}).check();
  await page.getByLabel('端点の丸（0は丸なし、1は丸あり）',{exact:true}).fill('1 0 0\n0 0 0');
  await expect(page.locator('#generate')).toBeEnabled();const cell=page.locator('[data-cell-index="0"]');
  await expect(cell).toHaveClass(/endpoint-marked/);await expect(cell.locator('.orthogonal-number')).toBeVisible();
  await expect(cell.locator('.cell-mark')).toBeVisible();
});

test('numbered white endpoints coexist with independent orthogonal counts',async({page})=>{
  await start(page);await page.getByLabel(field,{exact:true}).fill('1 . .\n. . .');
  await page.getByLabel('丸を白の端点と一致させる',{exact:true}).check();
  await page.getByLabel('端点の丸（0は丸なし、1は丸あり）',{exact:true}).fill('1 0 0\n0 0 1');
  await page.getByLabel('数字から見える白マス数を固定',{exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）',{exact:true}).fill('3 0 0\n0 0 2');
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');
  expect(data.record.solution).toEqual([[0,0,0],[1,1,0]]);
  await enterAndCheck(page,data);await page.setViewportSize({width:390,height:844});
  const cell=page.locator('[data-cell-index="0"]');await expect(cell).toHaveClass(/endpoint-marked/);
  await expect(cell.locator('.orthogonal-number')).toHaveText('接1');
  await expect(cell.locator('.sight-number')).toHaveText('3');
  const boxes=await Promise.all(['.orthogonal-number','.sight-number','.cell-mark'].map(selector=>cell.locator(selector).boundingBox()));
  for(let i=0;i<boxes.length;i++) for(let j=i+1;j<boxes.length;j++) expect(separate(boxes[i],boxes[j])).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('orthogonal-numbered-endpoints.png')});
});

for(const change of ['missing','changed','zero-to-null','unrequested']) test(`${change} orthogonal count plan is rejected`,async({page})=>{
  await start(page);if(change==='zero-to-null') await page.getByLabel(field,{exact:true}).fill('0 . .\n. . .');
  if(change==='unrequested') await page.getByLabel(title,{exact:true}).uncheck();
  await page.route('**/api/plan',async route=>{
    const response=await route.fetch(),data=await response.json();
    if(data.status==='ok') {
      if(change==='missing') delete data.plan.orthogonal_counts;
      else data.plan.orthogonal_counts=[[change==='zero-to-null'?null:3,null,null],[null,null,null]];
    }
    await route.fulfill({json:data});
  });
  await page.locator('#seed').fill('1');await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled();await expect(page.locator('.cell')).toHaveCount(0);
});

test('a changed generated count plan cannot expose an answer',async({page})=>{
  await start(page);
  await page.route('**/api/generate',async route=>{
    const response=await route.fetch(),data=await response.json();expect(data.status).toBe('ok');
    delete data.plan.orthogonal_counts;await route.fulfill({json:data});
  });
  await page.locator('#generate').click();await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled();await expect(page.locator('#actions')).toBeHidden();
  await expect(page.locator('#board')).toBeEmpty();
});
