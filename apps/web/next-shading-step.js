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
