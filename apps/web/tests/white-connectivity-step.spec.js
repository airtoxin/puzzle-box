import {test, expect} from '@playwright/test';
import {nextShadingStep} from '../next-shading-step.js';

// Independent union-find oracle for the completed white set.
function connected(board, rows, cols, nonempty) {
  const parent=board.map((_,i)=>i);
  const root=i=>{while(parent[i]!==i) i=parent[i];return i;};
  for(let i=0;i<board.length;i++) if(board[i]===0) {
    const r=Math.floor(i/cols),c=i%cols;
    for(const j of [c+1<cols ? i+1 : -1,r+1<rows ? i+cols : -1])
      if(j>=0 && board[j]===0) parent[root(i)]=root(j);
  }
  const whites=board.map((v,i)=>v===0?i:-1).filter(i=>i>=0);
  return whites.length===0 ? !nonempty : whites.every(i=>root(i)===root(whites[0]));
}

// Separate transitive-closure witness oracle; unknown cells may be white.
function reach(input,rows,cols,start,excluded) {
  const n=input.length, graph=Array.from({length:n},()=>Array(n).fill(false));
  for(let i=0;i<n;i++) if(i!==excluded && input[i]!==1) for(let j=0;j<n;j++)
    if(j!==excluded && input[j]!==1 && (i===j || Math.abs(Math.floor(i/cols)-Math.floor(j/cols))+Math.abs(i%cols-j%cols)===1)) graph[i][j]=true;
  for(let k=0;k<n;k++) for(let i=0;i<n;i++) for(let j=0;j<n;j++) graph[i][j] ||= graph[i][k] && graph[k][j];
  return graph[start].map((v,i)=>v?i:-1).filter(i=>i>=0);
}

test('white connector and conflict follow connectivity alone on every small partial board', () => {
  let proven=0, conflicts=0;
  for(const [rows,cols] of [[1,3],[3,1],[2,2],[2,3],[3,2]]) for(const nonempty of [false,true]) {
    const size=rows*cols, complete=Array.from({length:2**size},(_,bits)=>Array.from({length:size},(_,i)=>(bits>>i)&1));
    for(let state=0;state<3**size;state++) {
      let n=state; const input=Array.from({length:size},()=>{const v=n%3-1;n=Math.floor(n/3);return v;});
      const solutions=complete.filter(b=>connected(b,rows,cols,nonempty) && b.every((v,i)=>input[i]===-1 || input[i]===v));
      const result=nextShadingStep({rows,cols,rules:[{id:'connected-white',parameters:{nonempty}}]},[],input);
      if(result.status==='step') {
        proven++; expect(input[result.index]).toBe(-1); expect(result.value).toBe(0);
        expect(solutions.length).toBeGreaterThan(0);
        for(const board of solutions) expect(board[result.index]).toBe(0);
        const [a,b]=result.witness.terminals;
        expect(input[a]).toBe(0); expect(input[b]).toBe(0);
        const reached=reach(input,rows,cols,a,result.index);
        expect(result.witness.reachableWithoutCell).toEqual(reached); expect(reached).not.toContain(b);
        expect(reach(input,rows,cols,a,-1)).toContain(b);
      } else if(result.status==='conflict') {conflicts++; expect(solutions).toHaveLength(0);}
    }
  }
  expect(proven).toBeGreaterThan(0); expect(conflicts).toBeGreaterThan(0);
});

test('connection conflict takes priority and alternative paths or one white do not invent a step', () => {
  const request={rows:2,cols:3,rules:[{id:'count',parameters:{count:3}},{id:'connected-white',parameters:{nonempty:true}}]};
  // Black count is already satisfied, but known whites cannot connect.
  expect(nextShadingStep(request,[],[0,1,-1,1,1,0]).status).toBe('conflict');
  const connectedOnly={rows:2,cols:3,rules:[{id:'connected-white',parameters:{nonempty:true}}]};
  expect(nextShadingStep(connectedOnly,[],[0,-1,-1,-1,-1,0]).status).toBe('stalled');
  expect(nextShadingStep(connectedOnly,[],[0,-1,-1,1,1,1]).status).toBe('stalled');
  expect(nextShadingStep(connectedOnly,[],[-1,-1,-1,-1,-1,-1]).status).toBe('stalled');
  // Nonempty=true alone is deliberately unsupported, including an already
  // all-black board and a single remaining unknown that must be white.
  const nonemptyOnly={rows:1,cols:2,rules:[{id:'connected-white',parameters:{nonempty:true}}]};
  expect(nextShadingStep(nonemptyOnly,[],[1,1]).status).toBe('stalled');
  expect(nextShadingStep(nonemptyOnly,[],[1,-1]).status).toBe('stalled');
});

test('board explains a white connector and clears it after an incorrect entry', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('各行の黒マス数',{exact:true}).uncheck();
  await page.getByLabel('各列の黒マス数',{exact:true}).uncheck();
  await expect(page.locator('#generate')).toBeEnabled();
  await page.route('**/api/generate',async route=>{
    const response=await route.fetch(), result=await response.json(); expect(result.status).toBe('ok');
    const clues=[{type:'cell',row:0,col:0,value:0},{type:'cell',row:1,col:0,value:1},
      {type:'cell',row:1,col:1,value:1},{type:'cell',row:1,col:2,value:0}];
    await route.fulfill({json:{...result,clues}});
  });
  await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  await expect(page.locator('#next-step-panel')).toContainText('白を1つ以上にする条件だけからは推論しません');
  const target=page.locator('[data-cell-index="1"]'); await page.locator('#next-step').click();
  await expect(page.locator('#next-step-result')).toContainText('1行2列は白');
  await expect(page.locator('#next-step-result')).toContainText('1行1列と2行3列');
  await expect(page.locator('#next-step-result')).toContainText('現在の入力が正しいと仮定');
  await expect(target).toHaveClass(/next-step-target/); await expect(target).toHaveAttribute('data-value','-1');
  await target.click(); await target.click(); await page.locator('#next-step').click();
  await expect(page.locator('#next-step-result')).toContainText('つなげません');
  await expect(target).not.toHaveClass(/next-step-target/);
});

test('10x10 benchmark recipe gains a step from connectivity after local rules stall', () => {
  // Matches benchmark_bounded_shading.py: 25 black, orthogonally non-touching,
  // connected white. This partial board is drawn from an explicit valid grid.
  const rows=10,cols=10,solution=Array(100).fill(0);
  for(let r=1;r<10;r+=2) for(let c=0;c<10;c+=2) solution[r*cols+c]=1;
  solution[90]=0; solution[3]=1;
  expect(solution.reduce((a,x)=>a+x,0)).toBe(25);
  for(let i=0;i<100;i++) if(solution[i]===1) {
    if(i%10<9) expect(solution[i+1]).toBe(0);
    if(i<90) expect(solution[i+10]).toBe(0);
  }
  expect(connected(solution,rows,cols,true)).toBe(true);
  const input=Array(100).fill(-1);
  for(const i of [0,2,4,11,13,22]) input[i]=0;
  input[3]=input[12]=1;
  expect(input.every((v,i)=>v===-1 || v===solution[i])).toBe(true);
  const rules=[{id:'count',parameters:{count:25}},{id:'non-touching',parameters:{diagonal:false}}];
  expect(nextShadingStep({rows,cols,rules},[],input).status).toBe('stalled');
  const result=nextShadingStep({rows,cols,rules:[...rules,{id:'connected-white',parameters:{nonempty:true}}]},[],input);
  expect(result).toMatchObject({status:'step',index:1,value:0,source:'白マスをつなぐルール'});
  expect(result.witness.terminals).toEqual([0,2]);
  expect(result.witness.reachableWithoutCell).toEqual(reach(input,rows,cols,0,1));
});
