import {test, expect} from '@playwright/test';
import {nextShadingStep} from '../next-shading-step.js';

test('subtracted count deductions follow both cited counts on every partial 2x3 board', () => {
  const rows=2, cols=3, size=rows*cols;
  const boards=Array.from({length:1<<size},(_,mask)=>Array.from({length:size},(_,i)=>(mask>>i)&1));
  let deductions=0, conflicts=0;
  for (const axis of ['row','column']) for (let line=0;line<(axis==='row'?rows:cols);line++) {
    const indices=Array.from({length:size},(_,i)=>i).filter(i=>axis==='row'?Math.floor(i/cols)===line:i%cols===line);
    for(let total=0;total<=size;total++) for(let count=0;count<=indices.length;count++) {
      const clue=axis==='row'?{type:'row-count',row:line,count}:{type:'column-count',col:line,count};
      const valid=boards.filter(b=>b.reduce((a,x)=>a+x,0)===total && indices.reduce((a,i)=>a+b[i],0)===count);
      for(let state=0;state<3**size;state++) {
        let n=state; const input=Array.from({length:size},()=>{const v=n%3-1;n=Math.floor(n/3);return v;});
        const possible=valid.filter(b=>b.every((v,i)=>input[i]===-1||input[i]===v));
        const result=nextShadingStep({rows,cols,rules:[{id:'count',parameters:{count:total}}]},[clue],input);
        if(result.status==='step' && result.source.includes('と')) {
          deductions++;
          if (!possible.length || input[result.index] !== -1 || indices.includes(result.index) || possible.some(b=>b[result.index]!==result.value))
            throw new Error(`unsound deduction: ${JSON.stringify({axis,line,total,count,input,result})}`);
        } else if(result.status==='conflict') {conflicts++; if(possible.length) throw new Error(`false conflict: ${JSON.stringify({axis,line,total,count,input,result})}`);}
      }
    }
  }
  expect(deductions).toBeGreaterThan(0); expect(conflicts).toBeGreaterThan(0);
});

test('inconsistent counts do not blame an empty input', () => {
  const result=nextShadingStep({rows:2,cols:3,rules:[{id:'count',parameters:{count:0}}]},[{type:'row-count',row:0,count:1}],Array(6).fill(-1));
  expect(result.status).toBe('conflict');
  expect(result.reason).toContain('ルール・ヒントまたは入力');
});

test('five generated 10x10 examples: count subtraction unblocks three identical hint sets', () => {
  const rules=[{id:'count',parameters:{count:2}},{id:'connected-white',parameters:{nonempty:true}}];
  const clueSets=[
    [{type:'cell',row:9,col:0,value:0},{type:'row-count',row:0,count:1},{type:'row-count',row:9,count:1},{type:'column-count',col:0,count:1},{type:'column-count',col:9,count:1}],
    ...Array.from({length:3},()=>[{type:'cell',row:9,col:9,value:1},{type:'row-count',row:0,count:1},{type:'column-count',col:0,count:1}]),
    [{type:'cell',row:0,col:0,value:1},{type:'cell',row:9,col:9,value:1}],
  ];
  const observed=clueSets.map(clues=>{
    const input=Array(100).fill(-1); for(const c of clues)if(c.type==='cell')input[c.row*10+c.col]=c.value;
    let steps=0; while(steps<100){const result=nextShadingStep({rows:10,cols:10,rules},clues,input); if(result.status!=='step')break; input[result.index]=result.value; steps++;}
    return {steps,remaining:input.filter(v=>v===-1).length};
  });
  expect(observed).toEqual([{steps:0,remaining:99},{steps:99,remaining:0},{steps:99,remaining:0},{steps:99,remaining:0},{steps:98,remaining:0}]);
});

test('10x10 shows both sources and marks the scope without entering a cell', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#rows').fill('10'); await page.locator('#cols').fill('10');
  await page.route('**/api/generate',async route=>{
    const response=await route.fetch(), result=await response.json(); expect(result.status).toBe('ok');
    const clues=[{type:'cell',row:9,col:9,value:1},{type:'row-count',row:0,count:1},{type:'column-count',col:0,count:1}];
    await route.fulfill({json:{...result,clues}});
  });
  await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#actions')).toBeVisible(); await page.locator('#next-step').click();
  await expect(page.locator('#next-step-result')).toContainText('黒マスの個数ルールと1行の黒数ヒント');
  await expect(page.locator('#next-step-result')).toContainText('現在の入力が正しいと仮定');
  await expect(page.locator('[data-cell-index="10"]')).toHaveClass(/next-step-target/);
  await expect(page.locator('[data-cell-index="10"]')).toHaveAttribute('data-value','-1');
  await expect(page.locator('.next-step-evidence')).toHaveCount(99);
  await page.locator('[data-cell-index="10"]').click(); await expect(page.locator('.next-step-evidence')).toHaveCount(0);
});
