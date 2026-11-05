import {test, expect} from '@playwright/test';

async function start(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('数字セルが属する成分の面積を固定',{exact:true}).check();
  await expect(page.locator('.component-area-number')).toHaveText(['面1','面4']);
}

async function enterAndCheck(page,data) {
  for(let i=0;i<6;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if(await cell.isEnabled()) while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
}

function separate(a,b) {
  return a.x+a.width<=b.x || b.x+b.width<=a.x || a.y+a.height<=b.y || b.y+b.height<=a.y;
}

test('Choco Banana number cells remain editable black or white and do not reveal the answer',async({page})=>{
  await start(page);
  await expect(page.locator('[data-cell-index="0"]')).toHaveAttribute('data-value','-1');
  await expect(page.locator('[data-cell-index="5"]')).toHaveAttribute('data-value','-1');
  await page.getByLabel('連結成分を長方形にする',{exact:true}).check();
  await page.getByLabel('連結成分の長方形を禁止',{exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toEqual([]);
  expect(data.record.solution.flat()).toEqual([1,0,1,0,0,0]);
  for(const index of [0,5]) {
    await expect(page.locator(`[data-cell-index="${index}"]`)).toBeEnabled();
    await expect(page.locator(`[data-cell-index="${index}"]`)).toHaveAttribute('data-value','-1');
  }
  await enterAndCheck(page,data);
  await expect(page.locator('[data-cell-index="0"]')).toHaveAccessibleName(/黒.*所属成分の面積1/);
  await expect(page.locator('[data-cell-index="5"]')).toHaveAccessibleName(/白.*所属成分の面積4/);
  await expect(page.locator('[data-cell-index="0"] .component-area-number')).toHaveCSS('color','rgb(255, 255, 255)');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('choco-banana-board.png')});
});

test('seven numeric meanings and endpoint circles compose without sharing their grids',async({page})=>{
  await start(page);
  await page.getByLabel('白マスの数字を重複させない',{exact:true}).check();
  await page.getByLabel('固定数字（行ごとに入力）',{exact:true}).fill('1 2 3\n4 5 6');
  await page.getByLabel('数字から見える白マス数を固定',{exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）',{exact:true}).fill('0 0 0\n0 0 3');
  await page.getByLabel('数字がある白成分の面積を固定',{exact:true}).check();
  await page.getByLabel('白い島の面積（0は数字なし）',{exact:true}).fill('0 0 0\n0 0 4');
  await page.getByLabel('数字の周囲の黒マス数を固定',{exact:true}).check();
  await page.getByLabel('周囲の黒数（. は数字なし、0も有効）',{exact:true}).fill('. . .\n. . 1');
  await page.getByLabel('接する黒成分の面積合計を固定',{exact:true}).check();
  await page.getByLabel('接する黒成分の面積合計（. は丸なし）',{exact:true}).fill('. . .\n. . 1');
  await page.getByLabel('周囲8マスの黒い連続長を指定',{exact:true}).check();
  await page.getByLabel('黒の連続長（複数は1,2、なしは.、黒0個は0）',{exact:true}).fill('. . .\n. . 1');
  await page.getByLabel('丸を白の端点と一致させる',{exact:true}).check();
  await page.getByLabel('端点の丸（0は丸なし、1は丸あり）',{exact:true}).fill('0 1 0\n1 0 1');
  await expect(page.locator('#rules textarea:visible')).toHaveCount(8);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');
  await enterAndCheck(page,data);
  await page.setViewportSize({width:390,height:844});
  const labels=page.locator('[data-cell-index="5"] .cell-number,[data-cell-index="5"] .sight-number,[data-cell-index="5"] .area-number,[data-cell-index="5"] .neighbor-number,[data-cell-index="5"] .component-number,[data-cell-index="5"] .run-number,[data-cell-index="5"] .component-area-number');
  await expect(labels).toHaveCount(7);
  const boxes=await Promise.all((await labels.all()).map(label=>label.boundingBox()));
  for(let i=0;i<boxes.length;i++) for(let j=i+1;j<boxes.length;j++) expect(separate(boxes[i],boxes[j])).toBe(true);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('component-area-mixed.png')});
});

for(const [title,label,value,selector] of [
  ['白マスの数字を重複させない','固定数字（行ごとに入力）','1 2 3\n4 5 6','.cell-number'],
  ['数字から見える白マス数を固定','見える白マス数（0は指定なし）','1 0 0\n0 0 0','.sight-number'],
  ['数字がある白成分の面積を固定','白い島の面積（0は数字なし）','1 0 0\n0 0 0','.area-number'],
  ['数字の周囲の黒マス数を固定','周囲の黒数（. は数字なし、0も有効）','3 . .\n. . .','.neighbor-number'],
  ['接する黒成分の面積合計を固定','接する黒成分の面積合計（. は丸なし）','3 . .\n. . .','.component-number'],
  ['周囲8マスの黒い連続長を指定','黒の連続長（複数は1,2、なしは.、黒0個は0）','3 . .\n. . .','.run-number'],
]) test(`only component area and ${selector} labels remain separate`,async({page})=>{
  await start(page);
  await page.getByLabel(title,{exact:true}).check();await page.getByLabel(label,{exact:true}).fill(value);
  await expect(page.locator('#generate')).toBeEnabled();await page.setViewportSize({width:390,height:844});
  const cell=page.locator('[data-cell-index="0"]');
  const a=await cell.locator('.component-area-number').boundingBox(),b=await cell.locator(selector).boundingBox();
  expect(separate(a,b)).toBe(true);
  const mark=cell.locator('.cell-mark');
  if(await mark.isVisible()) {
    const m=await mark.boundingBox();expect(separate(a,m)&&separate(b,m)).toBe(true);
  }
});

test('zero is absent and never becomes a white given',async({page})=>{
  await start(page);
  await page.getByLabel('所属する成分の面積（0は数字なし）',{exact:true}).fill('0 0 0\n0 0 0');
  await expect(page.locator('.component-area-number')).toHaveCount(0);
  for(const cell of await page.locator('.cell').all()) await expect(cell).toHaveAttribute('data-value','-1');
});

for(const change of ['missing','changed','null-zero','unrequested']) test(`${change} component-area plan is rejected`,async({page})=>{
  await start(page);
  if(change==='unrequested') await page.getByLabel('数字セルが属する成分の面積を固定',{exact:true}).uncheck();
  await page.route('**/api/plan',async route=>{
    const response=await route.fetch(),data=await response.json();
    if(data.status==='ok') {
      if(change==='missing') delete data.plan.component_areas;
      else data.plan.component_areas=[[1,change==='null-zero'?null:0,0],[0,0,change==='changed'?5:4]];
    }
    await route.fulfill({json:data});
  });
  await page.locator('#seed').fill('1');
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled();await expect(page.locator('.cell')).toHaveCount(0);
});
