import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {nextShadingStep} from '../next-shading-step.js';

function connected(b,rows,cols){
  const white=b.flatMap((v,i)=>v===0?[i]:[]); if(white.length<2)return true;
  const seen=new Set([white[0]]),queue=[white[0]];
  while(queue.length){const i=queue.shift(),r=Math.floor(i/cols),c=i%cols;for(const [dr,dc] of [[-1,0],[1,0],[0,-1],[0,1]]){const rr=r+dr,cc=c+dc,j=rr*cols+cc;if(rr>=0&&rr<rows&&cc>=0&&cc<cols&&b[j]===0&&!seen.has(j)){seen.add(j);queue.push(j);}}}
  return white.every(i=>seen.has(i));
}
test('isolated-white exclusions and conflicts follow the cited rules on all partial 2x3 boards',()=>{
  const rows=2,cols=3,size=6,boards=Array.from({length:64},(_,m)=>Array.from({length:size},(_,i)=>(m>>i)&1));let deductions=0,exclusions=0,conflicts=0;
  for(const diagonal of [false,true]) for(const axis of ['row','column']) for(let line=0;line<(axis==='row'?rows:cols);line++){
    const cells=Array.from({length:size},(_,i)=>i).filter(i=>axis==='row'?Math.floor(i/cols)===line:i%cols===line);
    for(let count=0;count<=cells.length;count++){
      const clue=axis==='row'?{type:'row-count',row:line,count}:{type:'column-count',col:line,count};
      const valid=boards.filter(b=>cells.reduce((a,i)=>a+b[i],0)===count && connected(b,rows,cols) && b.every((v,i)=>!v||b.every((w,j)=>!w||i===j||(diagonal?Math.max(Math.abs(Math.floor(i/cols)-Math.floor(j/cols)),Math.abs(i%cols-j%cols)):Math.abs(Math.floor(i/cols)-Math.floor(j/cols))+Math.abs(i%cols-j%cols))!==1)));
      for(let state=0;state<3**size;state++){
        let n=state;const input=Array.from({length:size},()=>{const v=n%3-1;n=Math.floor(n/3);return v;});
        const result=nextShadingStep({rows,cols,rules:[{id:'non-touching',parameters:{diagonal}},{id:'connected-white',parameters:{nonempty:false}}]},[clue],input);
        const possible=valid.filter(b=>b.every((v,i)=>input[i]===-1||input[i]===v));
        if(result.status==='conflict'){conflicts++;if(possible.length)throw new Error(`false conflict ${JSON.stringify({axis,line,count,input,result})}`);}
        if(result.status!=='step'||!result.witness?.rejected?.length)continue;
        deductions++;if(input[result.index]!==-1||possible.some(b=>b[result.index]!==result.value))throw new Error('unsound step');
        for(const item of result.witness.rejected){
          exclusions++;const [isolated,other]=item.terminals, lineSet=new Set(result.witness.line),black=new Set(item.placement);
          const isWhite=i=>lineSet.has(i)?!black.has(i):input[i]===0;
          const neighbors=Array.from({length:size},(_,i)=>i).filter(i=>Math.abs(Math.floor(i/cols)-Math.floor(isolated/cols))+Math.abs(i%cols-isolated%cols)===1);
          if(isolated===other||!isWhite(isolated)||!isWhite(other)||neighbors.some(i=>lineSet.has(i)?!black.has(i):input[i]!==1)||JSON.stringify([...item.blockers].sort((a,b)=>a-b))!==JSON.stringify(neighbors))throw new Error(`bad witness ${JSON.stringify({input,item})}`);
          if(possible.some(b=>result.witness.line.every(i=>b[i]===(black.has(i)?1:0))))throw new Error('excluded valid placement');
        }
      }
    }
  }
  // The simpler white-connector deduction subsumes isolation steps on 2x3.
  expect(deductions).toBe(0);expect(exclusions).toBe(0);expect(conflicts).toBeGreaterThan(0);
});

test('one white alone is not rejected, and contradictions take priority',()=>{
  const rules=[{id:'non-touching',parameters:{diagonal:false}},{id:'connected-white',parameters:{nonempty:true}}];
  const single=nextShadingStep({rows:1,cols:3,rules},[{type:'row-count',row:0,count:2}],[-1,-1,-1]);
  expect(single.status).toBe('step');expect(single.witness.rejected).toHaveLength(0);
  const contradiction=nextShadingStep({rows:2,cols:3,rules},[{type:'row-count',row:0,count:1}],[-1,1,-1,1,-1,-1]);
  expect(contradiction.status).toBe('conflict');expect(contradiction.reason).toContain('1行1列の白');expect(contradiction.reason).toContain('1行3列');
});

test('a later simple line takes priority over an isolation fallback in either clue order',()=>{
  const rules=[{id:'non-touching',parameters:{diagonal:false}},{id:'connected-white',parameters:{nonempty:true}}];
  const request={rows:4,cols:3,rules};
  const input=[0,-1,-1,1,0,-1,0,-1,-1,-1,-1,-1];
  const clues=[{type:'row-count',row:0,count:1},{type:'row-count',row:3,count:2}];
  for(const ordered of [clues,[...clues].reverse()]) {
    const result=nextShadingStep(request,ordered,input);
    expect(result).toMatchObject({status:'step',index:9,value:1,source:'4行の黒数ヒントと黒マスを離すルール'});
    expect(result.witness.rejected).toHaveLength(0);
  }
  // A later impossible line must still override both kinds of proposed step.
  const conflict=nextShadingStep(request,[clues[0],{type:'row-count',row:3,count:3}],input);
  expect(conflict.status).toBe('conflict');
});

test('a simple white connector precedes the isolation fallback',()=>{
  const request={rows:2,cols:3,rules:[{id:'non-touching',parameters:{diagonal:false}},{id:'connected-white',parameters:{nonempty:true}}]};
  const result=nextShadingStep(request,[{type:'row-count',row:0,count:1}],[0,-1,-1,1,0,-1]);
  expect(result).toMatchObject({status:'step',index:1,value:0,source:'白マスをつなぐルール'});
});

test('isolation witness is retained when no simpler step exists',()=>{
  const {request,clues}=JSON.parse(readFileSync(new URL('./fixtures/measurement-benchmark-1.json',import.meta.url),'utf8'));
  const {input}=JSON.parse(readFileSync(new URL('./fixtures/white-isolation-state.json',import.meta.url),'utf8'));
  const result=nextShadingStep(request,clues,input);
  expect(result).toMatchObject({status:'step',index:30,value:1});
  expect(result.source).toContain('白マスをつなぐルール');
  expect(result.witness.rejected).toHaveLength(2);
  for(const witness of result.witness.rejected) {
    expect(witness.terminals).toEqual([33,2]);
    expect([...witness.blockers].sort((a,b)=>a-b)).toEqual([23,32,34,43]);
  }
});

test('10x10 benchmark cases retain bounded, reproducible progress',()=>{
  const results=[0,1,2].map(seed=>{const {request,clues}=JSON.parse(readFileSync(new URL(`./fixtures/measurement-benchmark-${seed}.json`,import.meta.url),'utf8'));const input=Array(100).fill(-1);for(const clue of clues)if(clue.type==='cell')input[clue.row*10+clue.col]=clue.value;let steps=0,r;while(steps<100){r=nextShadingStep(request,clues,input);if(r.status!=='step')break;input[r.index]=r.value;steps++;}return {steps,remaining:input.filter(v=>v===-1).length,status:r.status};});
  expect(results).toEqual([{steps:69,remaining:16,status:'stalled'},{steps:68,remaining:18,status:'stalled'},{steps:65,remaining:13,status:'stalled'}]);
});

test('board explains the excluded black placement and clears it on input',async({page})=>{
  const {clues}=JSON.parse(readFileSync(new URL('./fixtures/measurement-benchmark-1.json',import.meta.url),'utf8'));
  const {input}=JSON.parse(readFileSync(new URL('./fixtures/white-isolation-state.json',import.meta.url),'utf8'));
  const fixed=new Set(clues.filter(c=>c.type==='cell').map(c=>c.row*10+c.col));
  const entries=input.flatMap((value,i)=>value===-1||fixed.has(i)?[]:[{type:'cell',row:Math.floor(i/10),col:i%10,value}]);
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#rows').fill('10');await page.locator('#cols').fill('10');
  await page.getByLabel('黒マス数',{exact:true}).fill('25');await page.getByLabel('黒マスを離す',{exact:true}).check();
  await page.route('**/api/generate',async route=>{const response=await route.fetch(),result=await response.json();expect(result.status).toBe('ok');await route.fulfill({json:{...result,clues:[...clues,...entries]}});});
  await expect(page.locator('#generate')).toBeEnabled();await page.locator('#generate').click();await expect(page.locator('#actions')).toBeVisible({timeout:45000});await page.locator('#next-step').click();
  const text=page.locator('#next-step-result');await expect(text).toContainText('【1列・3列・5列】');await expect(text).toContainText('4行4列の白');await expect(text).toContainText('別の白1行3列');await expect(text).toContainText('【1列・3列・7列】');await expect(text).toContainText('現在の入力が正しいと仮定');
  const target=page.locator('[data-cell-index="30"]');await expect(target).toHaveClass(/next-step-target/);await expect(target).toHaveAttribute('data-value','-1');await expect(page.locator('.next-step-evidence').first()).toBeVisible();await target.click();await expect(text).toBeEmpty();await expect(page.locator('.next-step-evidence')).toHaveCount(0);
});
