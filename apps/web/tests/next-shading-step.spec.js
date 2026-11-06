import {test, expect} from '@playwright/test';
import {nextShadingStep} from '../next-shading-step.js';

test('every proposed deduction follows from the cited supported constraints on all partial 2x3 boards', () => {
  const rows=2, cols=3, all = Array.from({length:64}, (_, bits) => Array.from({length:6}, (_, i) => (bits >> i) & 1));
  const scenarios = [
    ...Array.from({length:7}, (_, n) => ({rules:[{id:'count',parameters:{count:n}}], clues:[], valid:b => b.reduce((a,x)=>a+x,0) === n})),
    ...[false,true].map(diagonal => ({rules:[{id:'non-touching',parameters:{diagonal}}],clues:[],valid:b => b.every((v,i) => !v || b.every((w,j) => !w || i === j || (diagonal ? Math.max(Math.abs(Math.floor(i/3)-Math.floor(j/3)),Math.abs(i%3-j%3)) : Math.abs(Math.floor(i/3)-Math.floor(j/3))+Math.abs(i%3-j%3)) !== 1))})),
    {rules:[{id:'no-white-2x2',parameters:{}}],clues:[],valid:b => [0,1].every(c => [c,c+1,c+3,c+4].some(i=>b[i]===1))},
    {rules:[],clues:[{type:'row-count',row:1,count:1},{type:'column-count',col:0,count:0}],valid:b => b.slice(3).reduce((a,x)=>a+x,0)===1 && b[0]+b[3]===0},
  ];
  // Check the cited constraint in isolation, not just the full puzzle: a
  // wrong explanation must not pass merely because another rule fixes a cell.
  const citedSatisfied = (source, board, scenario) => {
    if (source === '黒マスの個数ルール') {
      const target=scenario.rules.find(r=>r.id==='count').parameters.count;
      return board.reduce((a,x)=>a+x,0)===target;
    }
    if (source === '黒マスを離すルール') {
      const diagonal=scenario.rules.find(r=>r.id==='non-touching').parameters.diagonal;
      return board.every((v,i)=>!v || board.every((w,j)=>!w || i===j ||
        (diagonal ? Math.max(Math.abs(Math.floor(i/3)-Math.floor(j/3)),Math.abs(i%3-j%3)) :
          Math.abs(Math.floor(i/3)-Math.floor(j/3))+Math.abs(i%3-j%3))!==1));
    }
    if (source === '白の2×2を禁止するルール')
      return [0,1].every(c=>[c,c+1,c+3,c+4].some(i=>board[i]===1));
    const clue=scenario.clues.find(c=>source === `${c.type==='row-count' ? c.row+1+'行' : c.col+1+'列'}の黒数ヒント`);
    if (!clue) throw new Error(`Unknown source ${source}`);
    const scope=board.filter((_,i)=>clue.type==='row-count' ? Math.floor(i/cols)===clue.row : i%cols===clue.col);
    return scope.reduce((a,x)=>a+x,0)===clue.count;
  };
  scenarios.push({rules:[{id:'count',parameters:{count:2}},{id:'non-touching',parameters:{diagonal:false}}],clues:[],
    valid:b=>b.reduce((a,x)=>a+x,0)===2 && b.every((v,i)=>!v || b.every((w,j)=>!w || i===j || Math.abs(Math.floor(i/3)-Math.floor(j/3))+Math.abs(i%3-j%3)!==1))});
  for (const scenario of scenarios) for (let state=0;state<729;state++) {
    let n=state; const input=Array.from({length:6},()=>{const v=n%3-1;n=Math.floor(n/3);return v;});
    const completions=all.filter(b => scenario.valid(b) && b.every((v,i)=>input[i]===-1 || input[i]===v));
    const result=nextShadingStep({rows,cols,rules:scenario.rules},scenario.clues,input);
    if (result.status==='step') {
      expect(input[result.index]).toBe(-1);
      for (const board of completions) expect(board[result.index]).toBe(result.value);
      const cited=all.filter(b=>citedSatisfied(result.source,b,scenario) && b.every((v,i)=>input[i]===-1 || input[i]===v));
      expect(cited.length).toBeGreaterThan(0);
      for (const board of cited) expect(board[result.index]).toBe(result.value);
    } else if (result.status==='conflict') expect(completions).toHaveLength(0);
  }
});

test('large shading boards offer a conditional explanation without changing entries and clear it on edits', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#rows').fill('10'); await page.locator('#cols').fill('10');
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('黒マス数',{exact:true}).fill('0');
  await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#actions')).toBeVisible();
  const cell=page.locator('[data-cell-index="0"]'); await expect(cell).toHaveAttribute('data-value','-1');
  await page.locator('#next-step').click();
  await expect(page.locator('#next-step-result')).toContainText('1行1列は白');
  await expect(page.locator('#next-step-result')).toContainText('現在の入力が正しいと仮定');
  await expect(cell).toHaveAttribute('data-value','-1'); await expect(cell).toHaveClass(/next-step-target/);
  await expect(page.locator('.next-step-evidence')).toHaveCount(99);
  await expect(page.locator('#next-step-result')).toContainText('根拠の対象範囲');
  await cell.click(); await expect(cell).not.toHaveClass(/next-step-target/); await expect(page.locator('.next-step-evidence')).toHaveCount(0); await expect(page.locator('#next-step-result')).toBeEmpty();
  await cell.click(); await page.locator('#next-step').click();
  await expect(page.locator('#next-step-result')).toContainText('矛盾');
  await page.locator('#undo').click(); await expect(page.locator('#next-step-result')).toBeEmpty();
  await page.locator('#reveal').click(); await expect(page.locator('#next-step')).toBeDisabled();
  await page.locator('#reveal').click(); await expect(page.locator('#next-step')).toBeEnabled();
});

test('unsupported deductions stop honestly and non-shading boards do not offer them', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('黒マスをつなぐ',{exact:true}).check();
  await page.getByLabel('各行の黒マス数',{exact:true}).uncheck();
  await page.getByLabel('各列の黒マス数',{exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  await page.locator('#next-step').click();
  await expect(page.locator('#next-step-result')).toContainText('次の一手が見つかりません');
  await expect(page.locator('#next-step-result')).toContainText('他のルール');
  await page.locator('#family').selectOption('coupled'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  await expect(page.locator('#next-step-panel')).toBeHidden();
});

test('a non-touching deduction can unlock the total-count rule', () => {
  const request={rows:2, cols:3, rules:[{id:'count',parameters:{count:2}},{id:'non-touching',parameters:{diagonal:false}}]};
  const input=[1,-1,-1,-1,0,0];
  const first=nextShadingStep(request,[],input);
  expect(first).toMatchObject({status:'step',index:1,value:0,source:'黒マスを離すルール'});
  input[first.index]=first.value;
  const second=nextShadingStep(request,[],input);
  // The other neighbor of the black cell is also forced white before count can fill.
  expect(second).toMatchObject({status:'step',index:3,value:0});
  input[second.index]=second.value;
  expect(nextShadingStep(request,[],input)).toMatchObject({status:'step',index:2,value:1,source:'黒マスの個数ルール'});
});


test('evidence identifies the constraint used for each local deduction', () => {
  const request = rules => ({rows:2, cols:3, rules});
  expect(nextShadingStep(request([]), [{type:'row-count',row:1,count:0}], [-1,-1,-1,-1,-1,-1]).evidence)
    .toEqual({kind:'scope',cells:[3,4,5]});
  expect(nextShadingStep(request([{id:'non-touching',parameters:{diagonal:false}}]), [], [1,-1,-1,-1,-1,-1]).evidence)
    .toEqual({kind:'premises',cells:[0]});
  expect(nextShadingStep(request([{id:'no-white-2x2',parameters:{}}]), [], [0,0,-1,0,-1,-1]).evidence)
    .toEqual({kind:'scope',cells:[0,1,3,4]});
});
