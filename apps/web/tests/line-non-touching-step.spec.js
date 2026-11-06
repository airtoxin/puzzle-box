import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {nextShadingStep} from '../next-shading-step.js';

test('line placements follow the cited clue and non-touching on every partial 2x3 board',()=>{
  const rows=2,cols=3,size=rows*cols,boards=Array.from({length:1<<size},(_,m)=>Array.from({length:size},(_,i)=>(m>>i)&1));
  let deductions=0;
  for(const diagonal of [false,true]) for(const axis of ['row','column']) for(let line=0;line<(axis==='row'?rows:cols);line++){
    const cells=Array.from({length:size},(_,i)=>i).filter(i=>axis==='row'?Math.floor(i/cols)===line:i%cols===line);
    for(let count=0;count<=cells.length;count++){
      const clue=axis==='row'?{type:'row-count',row:line,count}:{type:'column-count',col:line,count};
      const valid=boards.filter(b=>cells.reduce((a,i)=>a+b[i],0)===count && b.every((v,i)=>!v||b.every((w,j)=>!w||i===j||(diagonal?Math.max(Math.abs(Math.floor(i/cols)-Math.floor(j/cols)),Math.abs(i%cols-j%cols)):Math.abs(Math.floor(i/cols)-Math.floor(j/cols))+Math.abs(i%cols-j%cols))!==1)));
      for(let state=0;state<3**size;state++){
        let n=state;const input=Array.from({length:size},()=>{const v=n%3-1;n=Math.floor(n/3);return v;});
        const result=nextShadingStep({rows,cols,rules:[{id:'non-touching',parameters:{diagonal}}]},[clue],input);
        const possible=valid.filter(b=>b.every((v,i)=>input[i]===-1||input[i]===v));
        if(result.status==='conflict' && possible.length) throw new Error(`false conflict: ${JSON.stringify({diagonal,axis,line,count,input,result})}`);
        if(result.status!=='step'||!result.source.includes('と黒マスを離す'))continue;
        deductions++;
        const expected=[...new Set(possible.map(b=>JSON.stringify(cells.filter(i=>b[i]===1))))].sort();
        const actual=result.witness.placements.map(x=>JSON.stringify(x)).sort();
        if(!possible.length||input[result.index]!==-1||possible.some(b=>b[result.index]!==result.value)||JSON.stringify(actual)!==JSON.stringify(expected))
          throw new Error(`bad deduction or witness: ${JSON.stringify({diagonal,axis,line,count,input,result,expected})}`);
      }
    }
  }
  expect(deductions).toBeGreaterThan(0);
});

test('a conflicting line takes priority over an otherwise available step',()=>{
  const request={rows:2,cols:3,rules:[{id:'non-touching',parameters:{diagonal:false}}]};
  const result=nextShadingStep(request,[{type:'row-count',row:0,count:2}],[-1,-1,-1,1,-1,-1]);
  expect(result.status).toBe('conflict'); expect(result.reason).toContain('可能な黒の配置がありません');
});

test('unsupported long lines or long placement lists stop without inventing a step',()=>{
  const rule=[{id:'non-touching',parameters:{diagonal:false}}];
  expect(nextShadingStep({rows:1,cols:11,rules:rule},[{type:'row-count',row:0,count:1}],Array(11).fill(-1)).status).toBe('stalled');
  expect(nextShadingStep({rows:1,cols:10,rules:rule},[{type:'row-count',row:0,count:1}],Array(10).fill(-1)).status).toBe('stalled');
});

test('three 10x10 benchmark examples improve without consulting saved solutions',()=>{
  const results=[0,1,2].map(seed=>{
    const {request,clues}=JSON.parse(readFileSync(new URL(`./fixtures/measurement-benchmark-${seed}.json`,import.meta.url),'utf8'));
    const input=Array(100).fill(-1);for(const clue of clues)if(clue.type==='cell')input[clue.row*10+clue.col]=clue.value;
    let steps=0,result;while(steps<100){result=nextShadingStep(request,clues,input);if(result.status!=='step')break;input[result.index]=result.value;steps++;}
    return {steps,remaining:input.filter(v=>v===-1).length,status:result.status};
  });
  expect(results).toEqual([{steps:69,remaining:16,status:'stalled'},{steps:54,remaining:32,status:'stalled'},{steps:65,remaining:13,status:'stalled'}]);
});

test('a clued line shows all black placements without editing the board',async({page})=>{
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスを離す',{exact:true}).check();
  await page.route('**/api/generate',async route=>{const response=await route.fetch(),result=await response.json();expect(result.status).toBe('ok');await route.fulfill({json:{...result,clues:[{type:'row-count',row:0,count:2}]}});});
  await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  await page.locator('#next-step').click();
  await expect(page.locator('#next-step-result')).toContainText('1行の黒数ヒントと黒マスを離すルール');
  await expect(page.locator('#next-step-result')).toContainText('【1列・3列】');
  await expect(page.locator('#next-step-result')).toContainText('現在の入力が正しいと仮定');
  await expect(page.locator('[data-cell-index="0"]')).toHaveClass(/next-step-target/);
  await expect(page.locator('[data-cell-index="0"]')).toHaveAttribute('data-value','-1');
  await expect(page.locator('.next-step-evidence')).toHaveCount(2);
  await page.locator('[data-cell-index="0"]').click(); await expect(page.locator('.next-step-evidence')).toHaveCount(0);
});
