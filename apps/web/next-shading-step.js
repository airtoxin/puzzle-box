// A single conditional deduction from visible entries; never reads a solution.
// At most 100 cells and eight rules are accepted by the Web plan contract.
export function nextShadingStep(request, clues, input) {
  const {rows, cols, rules} = request;
  const constraints = [];
  const connectedWhite = rules.some(rule => rule.id === 'connected-white');
  const all = Array.from({length: rows * cols}, (_, i) => i);
  const count = (cells, target, source) => constraints.push({kind:'count', cells, target, source});
  for (const clue of clues) {
    if (clue.type === 'row-count') count(all.filter(i => Math.floor(i / cols) === clue.row), clue.count, `${clue.row + 1}行の黒数ヒント`);
    if (clue.type === 'column-count') count(all.filter(i => i % cols === clue.col), clue.count, `${clue.col + 1}列の黒数ヒント`);
  }
  for (const rule of rules) {
    if (rule.id === 'count') count(all, rule.parameters.count, '黒マスの個数ルール');
    if (rule.id === 'non-touching') {
      for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
        for (const [dr, dc] of (rule.parameters.diagonal ? [[0,1],[1,-1],[1,0],[1,1]] : [[0,1],[1,0]])) {
          const nr = r + dr, nc = c + dc;
          if (nr < rows && nc >= 0 && nc < cols)
            constraints.push({kind:'non-touching', cells:[r*cols+c,nr*cols+nc], source:'黒マスを離すルール'});
        }
      }
    }
    if (rule.id === 'no-white-2x2') {
      for (let r = 0; r + 1 < rows; r++) for (let c = 0; c + 1 < cols; c++)
        constraints.push({kind:'has-black', cells:[r*cols+c,r*cols+c+1,(r+1)*cols+c,(r+1)*cols+c+1], source:'白の2×2を禁止するルール'});
    }
  }
  const position = i => `${Math.floor(i / cols)+1}行${i % cols+1}列`;
  let step;
  for (const item of constraints) {
    const unknown = item.cells.filter(i => input[i] === -1);
    const black = item.cells.filter(i => input[i] === 1);
    const white = item.cells.filter(i => input[i] === 0);
    if (item.kind === 'count') {
      if (black.length > item.target || black.length + unknown.length < item.target)
        return {status:'conflict', reason:`${item.source}と入力が矛盾しています。入力を見直してください。`};
      if (!step && unknown.length && (black.length === item.target || black.length + unknown.length === item.target)) {
        const value = black.length === item.target ? 0 : 1;
        step = {status:'step', index:unknown[0], value, source:item.source, evidence:{kind:'scope', cells:item.cells},
          reason:`対象範囲の黒は${item.target}マス。入力済みの黒は${black.length}マス、未入力は${unknown.length}マスなので、残りはすべて${value ? '黒' : '白'}です。`};
      }
    } else if (item.kind === 'non-touching') {
      if (black.length === 2) return {status:'conflict', reason:`${item.source}では${black.map(position).join('と')}を両方黒にできません。入力を見直してください。`};
      if (!step && black.length === 1 && unknown.length === 1)
        step = {status:'step', index:unknown[0], value:0, source:item.source, evidence:{kind:'premises', cells:black},
          reason:`${position(black[0])}が黒なので、接するこのマスは白です。`};
    } else {
      if (white.length === 4) return {status:'conflict', reason:`${item.source}に反する白だけの2×2があります（左上は${position(item.cells[0])}）。入力を見直してください。`};
      if (!step && white.length === 3 && unknown.length === 1)
        step = {status:'step', index:unknown[0], value:1, source:item.source, evidence:{kind:'scope', cells:item.cells},
          reason:`左上が${position(item.cells[0])}の2×2では、他の3マスが白なので、このマスは黒です。`};
    }
  }
  // Enumerate a short clued line under non-touching and visible entries.
  // Outside unknowns remain unconstrained: only known outside black cells can
  // rule a placement out. List every placement used in the explanation.
  const separation = rules.find(rule => rule.id === 'non-touching');
  if (separation) for (const line of constraints) {
    if (line.kind !== 'count' || line.cells.length > 10 || line.source === '黒マスの個数ルール') continue;
    const cells = line.cells, lineSet = new Set(cells), external = new Set();
    const neighbors = i => {
      const r=Math.floor(i/cols), c=i%cols, result=[];
      for (let dr=-1;dr<=1;dr++) for(let dc=-1;dc<=1;dc++) {
        if ((!dr && !dc) || (!separation.parameters.diagonal && Math.abs(dr)+Math.abs(dc)!==1)) continue;
        const nr=r+dr,nc=c+dc; if(nr>=0 && nr<rows && nc>=0 && nc<cols) result.push(nr*cols+nc);
      }
      return result;
    };
    const around = cells.map(neighbors);
    for (const adjacent of around) for (const i of adjacent) if (!lineSet.has(i) && input[i]===1) external.add(i);
    const placements=[];
    for (let mask=0;mask<2**cells.length;mask++) {
      let blacks=0, valid=true;
      for(let k=0;k<cells.length;k++) {
        const value=(mask>>k)&1; blacks+=value;
        if(input[cells[k]]!==-1 && input[cells[k]]!==value) {valid=false; break;}
        if(value && around[k].some(i => lineSet.has(i) ? ((mask>>cells.indexOf(i))&1)===1 : input[i]===1)) {valid=false; break;}
      }
      if(valid && blacks===line.target) {placements.push(mask); if(placements.length>8) break;}
    }
    if(!placements.length) return {status:'conflict',
      reason:`${line.source}と黒マスを離すルールでは、この行または列に可能な黒の配置がありません。ルール・ヒントまたは入力を見直してください。`};
    // Keep both the presented cases and any eliminated cases bounded.
    if(placements.length>8) continue;
    const rejected=[], remaining=[];
    for (const mask of placements) {
      if (!connectedWhite) {remaining.push(mask); continue;}
      // A hypothetical line-white cell surrounded by black or board edges
      // cannot connect to another known or hypothetical line-white cell.
      const white=all.filter(i=>lineSet.has(i) ? !((mask>>cells.indexOf(i))&1) : input[i]===0);
      if (white.length<2) {remaining.push(mask); continue;}
      let witness;
      for(const i of white) {
        const r=Math.floor(i/cols),c=i%cols,neighbors=[];
        for(const [dr,dc] of [[-1,0],[1,0],[0,-1],[0,1]]) {
          const nr=r+dr,nc=c+dc; if(nr>=0&&nr<rows&&nc>=0&&nc<cols)neighbors.push(nr*cols+nc);
        }
        if(neighbors.every(j=>lineSet.has(j) ? ((mask>>cells.indexOf(j))&1)===1 : input[j]===1)) {
          witness={mask,terminals:[i,white.find(j=>j!==i)],blockers:neighbors}; break;
        }
      }
      if(witness) rejected.push(witness); else remaining.push(mask);
    }
    const axis=line.source.includes('行') ? '列' : '行';
    const describe=mask=>{const positions=cells.flatMap((i,j)=>(mask>>j)&1 ? [`${axis==='列' ? i%cols+1 : Math.floor(i/cols)+1}${axis}`] : []); return `【${positions.join('・') || 'なし'}】`;};
    const explainExclusion=({mask,terminals})=>`${describe(mask)}では、${position(terminals[0])}の白は上下左右が黒か盤の端で囲まれ、別の白${position(terminals[1])}とつながりません`;
    if(!remaining.length) return {status:'conflict', reason:`${line.source}と黒マスを離すルールで可能な配置はすべて白連結と矛盾します。${rejected.map(explainExclusion).join('。')}。ルール・ヒントまたは入力を見直してください。`};
    if(step) continue;
    const forced = choices => cells.findIndex((i,k)=>input[i]===-1 && choices.every(mask=>((mask>>k)&1)===((choices[0]>>k)&1)));
    const simple=forced(placements), choices=simple>=0 ? placements : remaining;
    const excluded=simple>=0 ? [] : rejected;
    const k=simple>=0 ? simple : forced(remaining);
    if(k<0) continue;
    const value=(choices[0]>>k)&1;
    const lists=choices.map(describe).join('、');
    const exclusions=excluded.map(explainExclusion).join('。');
    step={status:'step',index:cells[k],value,source:`${line.source}と黒マスを離すルール${excluded.length ? 'と白マスをつなぐルール' : ''}`,
      evidence:{kind:'scope',cells:[...new Set([...cells,...external,...excluded.flatMap(x=>[...x.terminals,...x.blockers])])]},
      witness:{line:cells,placements:choices.map(mask=>cells.filter((_,i)=>(mask>>i)&1)), rejected:excluded.map(({mask,terminals,blockers})=>({placement:cells.filter((_,i)=>(mask>>i)&1),terminals,blockers}))},
      reason:`入力済みのマスと周囲の黒を踏まえると、${excluded.length ? exclusions+'。' : ''}この行または列の残る黒の配置は${lists}の${choices.length}通り。いずれもこのマスは${value ? '黒' : '白'}です。`};
  }
  if (connectedWhite) {
    // Unknown cells are traversable: if even this maximally permissive graph
    // separates known whites, no completion can connect them.
    const white = all.filter(i => input[i] === 0);
    if (white.length >= 2) {
      const start = white[0];
      const reachable = excluded => {
        const seen = new Set([start]), pending = [start];
        while (pending.length) {
          const i = pending.pop(), r = Math.floor(i / cols), c = i % cols;
          for (const [dr,dc] of [[-1,0],[1,0],[0,-1],[0,1]]) {
            const nr=r+dr, nc=c+dc, n=nr*cols+nc;
            if (nr>=0 && nr<rows && nc>=0 && nc<cols && n!==excluded && input[n]!==1 && !seen.has(n)) {
              seen.add(n); pending.push(n);
            }
          }
        }
        return seen;
      };
      const initial = reachable(-1), disconnected = white.find(i => !initial.has(i));
      if (disconnected !== undefined) return {status:'conflict',
        reason:`白マスをつなぐルールでは、${position(start)}と${position(disconnected)}の白をつなげません。入力を見直してください。`};
      // Prefer the simpler local deduction already found, but still detect a
      // connectivity conflict above before offering it.
      if (!step) for (const candidate of all) {
        if (input[candidate] !== -1) continue;
        const reached = reachable(candidate), other = white.find(i => !reached.has(i));
        if (other !== undefined) {
          step = {status:'step', index:candidate, value:0, source:'白マスをつなぐルール',
            reason:`このマスを黒にすると、他の未入力をすべて白としても${position(start)}と${position(other)}の白が分断されます。白をつなぐため、このマスは白です。`,
            evidence:{kind:'terminals', cells:[start,other]},
            witness:{terminals:[start,other], reachableWithoutCell:[...reached].sort((a,b)=>a-b)}};
          break;
        }
      }
    }
  }
  return step || {status:'stalled'};
}
