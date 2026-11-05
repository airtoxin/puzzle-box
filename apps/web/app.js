import {UnsupportedUiError, canonicalRunClues, assertRenderablePlan} from './plan-contract.js';

const $ = id => document.getElementById(id);
const form = $('recipe-form');
let catalog, profile, plan, artifact, input = [], fixed = new Set(), revision = 0, timer;
const selected = new Map();
const hints = new Map();
const gridKinds = ['region-map', 'number-grid', 'clue-grid', 'marker-grid', 'run-clue-grid'];
class GridInputError extends Error {}
function rejectUnsupportedUi() {
  plan = undefined; clearArtifact(); $('board').replaceChildren(); $('generate').disabled = true;
  $('status').textContent = 'このUI定義には対応していません。画面を更新するか、対応済みの設定を選び直してください。';
}
const messages = {
  unsatisfiable: 'この組合せを満たす盤面はありません。ルールや設定を変更してください。',
  insufficient_hints: '選んだヒントだけでは、どの完成盤面も一意に決まりません。セルや辺の固定ヒントなどを追加してください。',
  search_exhausted: '候補探索の上限に達しました。一意になる問題はまだ見つかっていませんが、不可能とは判定していません。Seedやヒント形式を変えて試してください。',
  timeout: '計算予算に達したため打ち切りました。解なしとは判定していません。サイズやルール、予算を調整してください。',
  unconfirmed: '生成・検証を完了できませんでした。解なしや唯一解とは判定していません。',
  busy: '別の生成が実行中です。終了してからもう一度お試しください。',
};
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function readRequest() {
  return {format: 'puzzle-box/web-request-v2', family: profile.id, rows: Number($('rows').value), cols: Number($('cols').value),
    seed: Number($('seed').value), budget_seconds: Number($('budget').value),
    rules: [...selected].filter(([, s]) => s.toggle.checked).map(([id, s]) => ({id,
      parameters: Object.fromEntries([...s.parameters].map(([name, field]) =>
        [name, gridKinds.includes(field.dataset.kind) ? readGrid(field) : field.type === 'checkbox' ? field.checked : Number(field.value)]))})),
    clue_kinds: [...hints].filter(([, toggle]) => toggle.checked).map(([id]) => id)};
}
function readGrid(field) {
  const rows = field.value.trim().split(/\r?\n/).map(row => row.trim().split(/\s+/));
  if (field.dataset.kind === 'run-clue-grid') {
    try {
      if (field.value.length > 512 || rows.some(row => row.some(n => n !== '.' && !/^\d+(,\d+)*$/.test(n)))) throw new UnsupportedUiError();
      return canonicalRunClues(rows.map(row => row.map(n => n === '.' ? null : n.split(',').map(Number))),Number($('rows').value),Number($('cols').value));
    } catch {throw new GridInputError(`${field.dataset.label}は .、0、または1,2のように、白い区切りを含め8マス以内の連続長を入力してください。`);}
  }
  const nullable = field.dataset.kind === 'clue-grid';
  if (field.value.length > 512 || rows.some(row => row.some(n => !/^\d+$/.test(n) && !(nullable && n === '.'))))
    throw new GridInputError(`${field.dataset.label}は、各行に整数を空白で区切って入力してください。`);
  const values = rows.map(row => row.map(n => n === '.' ? null : Number(n)));
  if (field.dataset.kind === 'marker-grid' && values.some(row => row.some(n => n !== 0 && n !== 1)))
    throw new GridInputError(`${field.dataset.label}は、0（丸なし）か1（丸あり）で入力してください。`);
  return values;
}
// Catalog and preview requests are safe to retry. Their timeout includes both
// headers and JSON body; generation and checking keep their existing budgets.
async function fetchJsonWithTimeout(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {...options, signal: controller.signal});
    if (path === '/api/catalog' ? !response.ok
      : response.status === 408 || response.status === 429 || response.status >= 500)
      throw new Error('Service temporarily unavailable');
    return await response.json();
  } finally {clearTimeout(timeout);}
}
async function post(path, data) {
  const options = {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)};
  if (path === '/api/plan') return fetchJsonWithTimeout(path, options);
  const response = await fetch(path, options);
  return response.json();
}
function clearArtifact() {
  artifact = undefined; $('actions').hidden = true; $('answer-status').textContent = '';
  $('reveal').textContent = '答えを表示';
}
function syncParameters() {
  const area = Number($('rows').value) * Number($('cols').value);
  const edges = 2 * area + (profile.board.topology === 'rectangular-cell-centers' ? -1 : 1) * (Number($('rows').value) + Number($('cols').value));
  for (const rule of profile.rules) {
    const state = selected.get(rule.identifier);
    for (const spec of rule.parameters) {
      const field = state.parameters.get(spec.name);
      field.disabled = ![...selected.values()].some(s => s.toggle.checked && [...s.parameters.values()].includes(field));
      if (gridKinds.includes(spec.kind)) field.closest('.shared-parameters').hidden = field.disabled;
      if (spec.kind === 'integer') field.max = spec.maximum === 'area' ? area : spec.maximum === 'edges' ? edges : spec.maximum;
    }
  }
}
async function refresh() {
  const current = ++revision;
  clearArtifact(); plan = undefined; $('generate').disabled = true; $('retry-plan').hidden = true; syncParameters();
  if (!form.checkValidity()) {
    $('status').textContent = '入力値を確認してください。'; $('board').replaceChildren(); return;
  }
  try {
    const request = readRequest(), result = await post('/api/plan', request);
    if (current !== revision) return;
    if (result.status !== 'ok') {
      $('status').textContent = `設定を組み合わせられません。${result.message || ''}`;
      $('board').replaceChildren(); return;
    }
    assertRenderablePlan(result.plan, request); plan = result.plan;
    $('shape').textContent = `${plan.rows} × ${plan.cols}`;
    $('plan-note').textContent = isCoupled() ? '線はマスの中心同士を結びます。黒白と辺は別々に入力し、両方の整合を確認します。' : '選択したルールとヒントが要求する盤面を表示しています。UIの適合は、問題の成立を保証しません。';
    const numericLegend = [['numbers','通常の数字は固定ラベル'], ['sight_counts','丸数字は見える白数'],
      ['orthogonal_counts','「接n」は上下左右の黒数（数字セルの色は自由、0もヒント）'], ['component_areas','「面n」は所属する同色成分の面積（数字セルの色は自由）'], ['island_areas','四角の数字は白い島の面積'], ['neighbor_counts','「隣n」は周囲の黒数（0もヒント）'],
      ['component_counts','「塊n」は接する黒成分の面積合計（同じ成分は1回）'],
      ['endpoint_markers','マス全体を囲む大きな丸は白の端点（白い隣接マスは1個）'], ['black_run_clues','「連1,2」等は周囲8マスの黒い連続長（順序不問、0もヒント）']]
      .filter(([key]) => plan[key] !== undefined).map(([,text]) => text);
    if (numericLegend.length) $('plan-note').textContent += ` ${numericLegend.join('、')}。`;
    if (plan.endpoint_markers && plan.sight_counts) $('plan-note').textContent += ' 端点上の可視数は丸自身を含む直線長です。';
    $('status').textContent = '生成前のプレビューです。';
    renderBoard(); $('generate').disabled = false;
  } catch (error) {
    if (current === revision) {
      if (error instanceof UnsupportedUiError) rejectUnsupportedUi();
      else if (error instanceof GridInputError) {$('status').textContent = error.message; $('board').replaceChildren();}
      else {
        $('status').textContent = 'プレビューを読み込めません。接続を確認して再試行してください。';
        $('board').replaceChildren(); $('shape').textContent = '';
        $('plan-note').textContent = 'プレビューを表示できません。';
        $('retry-plan').hidden = false;
      }
    }
  }
}
function renderBoard(reveal = false) {
  if (!plan) return;
  $('preview-title').textContent = reveal ? '解答' : artifact ? '生成した問題' : '盤面プレビュー';
  const channels = new Set(plan.requirements.channels.map(c => c.name));
  if (isCoupled()) {renderCoupled(reveal); return;}
  if (plan.requirements.channels.find(c => c.name === 'answer')?.kind === 'binary-edges') {
    renderLoop(reveal, channels); return;
  }
  const table = node('table'); table.setAttribute('aria-label', artifact ? '生成した問題' : '盤面プレビュー');
  if (channels.has('rooms')) table.classList.add('room-board');
  if (channels.has('endpoint-markers')) table.classList.add('endpoint-marker-board');
  if (channels.has('black-runs')) table.classList.add('black-run-board');
  if (channels.has('orthogonal-counts')) table.classList.add('orthogonal-count-board');
  if (channels.has('component-areas')) table.classList.add('component-area-board');
  if (channels.has('neighbor-counts') && ['numbers','sight-counts','island-areas'].some(c => channels.has(c))) table.classList.add('multi-numeric-board');
  if (channels.has('component-counts') && ['numbers','sight-counts','island-areas','neighbor-counts'].some(c => channels.has(c))) table.classList.add('dense-numeric-board');
  const values = artifact?.clues || [];
  const rowCounts = new Map(values.filter(c => c.type === 'row-count').map(c => [c.row, c.count]));
  const colCounts = new Map(values.filter(c => c.type === 'column-count').map(c => [c.col, c.count]));
  if (channels.has('column-counts')) {
    const tr = node('tr');
    if (channels.has('row-counts')) tr.append(node('td', ''));
    for (let c = 0; c < plan.cols; c++) {
      const th = node('th', String(colCounts.get(c) ?? '−')); th.scope = 'col';
      th.setAttribute('aria-label', `${c + 1}列の黒マス数: ${colCounts.get(c) ?? 'ヒントなし'}`); tr.append(th);
    }
    table.append(tr);
  }
  for (let r = 0; r < plan.rows; r++) {
    const tr = node('tr');
    if (channels.has('row-counts')) {
      const th = node('th', String(rowCounts.get(r) ?? '−')); th.scope = 'row';
      th.setAttribute('aria-label', `${r + 1}行の黒マス数: ${rowCounts.get(r) ?? 'ヒントなし'}`); tr.append(th);
    }
    for (let c = 0; c < plan.cols; c++) {
      const index = r * plan.cols + c;
      const givenWhite = plan.sight_counts?.[r][c] > 0 || plan.island_areas?.[r][c] > 0 || plan.endpoint_markers?.[r][c] === 1 || plan.black_run_clues?.[r][c] != null || plan.neighbor_counts?.[r][c] != null || plan.component_counts?.[r][c] != null;
      const value = reveal ? artifact.record.solution[r][c] : artifact ? input[index] : givenWhite ? 0 : -1;
      const td = node('td'); td.append(cellButton(index, r, c, value, reveal));
      if (channels.has('rooms')) {
        const room = plan.rooms[r][c]; td.dataset.room = room;
        for (const [side, dr, dc] of [['top', -1, 0], ['bottom', 1, 0], ['left', 0, -1], ['right', 0, 1]])
          if (plan.rooms[r+dr]?.[c+dc] !== room) td.classList.add(`room-${side}`);
      }
      tr.append(td);
    }
    table.append(tr);
  }
  $('board').replaceChildren(table);
}
function cellButton(index, r, c, value, reveal) {
  const button = node('button', undefined, 'cell');
  button.type = 'button'; button.dataset.cellIndex = index;
  button.disabled = !artifact || fixed.has(index) || reveal;
  if (fixed.has(index) && artifact) button.classList.add('fixed');
  const paint = value => {
    const mark = value === -1 ? '?' : value === 0 ? '○' : '■';
    const sight = plan.sight_counts?.[r][c] || 0;
    const area = plan.island_areas?.[r][c] || 0;
    const orthogonal = plan.orthogonal_counts?.[r][c], hasOrthogonal = orthogonal != null;
    const componentArea = plan.component_areas?.[r][c] || 0;
    button.classList.toggle('component-area-numbered', componentArea > 0);
    const neighbor = plan.neighbor_counts?.[r][c], hasNeighbor = neighbor != null;
    const component = plan.component_counts?.[r][c], hasComponent = component != null;
    const runs = plan.black_run_clues?.[r][c], hasRuns = runs != null;
    button.classList.toggle('black-run-numbered', hasRuns);
    button.classList.toggle('endpoint-length', plan.endpoint_markers?.[r][c] === 1 && sight > 0
      && !plan.numbers && !area && !hasNeighbor && !hasComponent && !hasRuns && !componentArea && !hasOrthogonal);
    if (plan.numbers || sight || area || hasNeighbor || hasComponent || hasRuns || componentArea || hasOrthogonal) {
      button.classList.add('numbered-cell');
      const labels = [];
      if (hasOrthogonal) labels.push(node('span', `接${orthogonal}`, 'orthogonal-number'));
      if (componentArea) labels.push(node('span', `面${componentArea}`, 'component-area-number'));
      if (hasRuns) labels.push(node('span', `連${runs.join(',')}`, 'run-number'));
      if (plan.numbers) labels.push(node('span', String(plan.numbers[r][c]), 'cell-number'));
      if (sight) labels.push(node('span', String(sight), 'sight-number'));
      if (area) labels.push(node('span', String(area), 'area-number'));
      if (hasNeighbor) {
        labels.push(node('span', `隣${neighbor}`, 'neighbor-number')); button.classList.add('neighbor-numbered');
        if (plan.numbers || sight || area || hasComponent) button.classList.add('mixed-neighbor-number');
      }
      if (hasComponent) {
        labels.push(node('span', `塊${component}`, 'component-number')); button.classList.add('component-numbered');
        if (plan.numbers || sight || area || hasNeighbor) button.classList.add('mixed-component-number');
      }
      if (plan.numbers && (sight || area)) button.classList.add('dual-numbered');
      if (sight && area) button.classList.add('mixed-numeric-givens');
      button.replaceChildren(...labels, node('span', mark, 'cell-mark'));
    } else button.textContent = mark;
    button.classList.toggle('endpoint-marked', plan.endpoint_markers?.[r][c] === 1);
    button.dataset.value = value;
    button.setAttribute('aria-label', `${r+1}行${c+1}列: ${value === -1 ? '未入力' : value === 0 ? '白' : '黒'}${plan.numbers ? `（数字${plan.numbers[r][c]}）` : ''}${sight ? `（見える白${sight}）` : ''}${area ? `（白い島の面積${area}）` : ''}${hasNeighbor ? `（隣接黒数${neighbor}）` : ''}${hasComponent ? `（接する黒成分の面積合計${component}）` : ''}${componentArea ? `（所属成分の面積${componentArea}）` : ''}${hasOrthogonal ? `（上下左右の黒数${orthogonal}、数字セルの色は自由）` : ''}${hasRuns ? `（周囲の黒い連続長${runs.join(',')}）` : ''}${plan.endpoint_markers?.[r][c] === 1 ? '（白の端点の丸）' : ''}${plan.rooms ? `（部屋${plan.rooms[r][c]+1}）` : ''}${fixed.has(index) && artifact ? '（固定ヒント）' : ''}`);
  };
  paint(value);
  button.addEventListener('click', () => {
    input[index] = (input[index]+2)%3-1; paint(input[index]); $('answer-status').textContent = '';
  });
  return button;
}
function buildControls() {
  selected.clear(); hints.clear(); $('rules').replaceChildren(); $('hints').replaceChildren();
  const sharedGrids = new Map();
  for (const rule of profile.rules) {
    const card = node('div', undefined, 'rule-card'); const label = node('label', undefined, 'rule-title');
    const toggle = document.createElement('input'); toggle.type = 'checkbox';
    toggle.checked = rule.required || profile.defaults.rules.includes(rule.identifier); toggle.disabled = rule.required;
    label.append(toggle, document.createTextNode(rule.label)); card.append(label, node('p', rule.summary));
    if (rule.requirements.max_cells < profile.board.max_cells) card.append(node('p', `このルールは最大${rule.requirements.max_cells}セルです。`));
    const parameters = new Map(), fields = node('div', undefined, 'parameters');
    for (const spec of rule.parameters) {
      if (!['integer', 'boolean', ...gridKinds].includes(spec.kind)) throw new Error('Unsupported parameter kind');
      const grid = gridKinds.includes(spec.kind);
      // Input syntax alone does not make two data sets the same parameter.
      const sharedKey = `${spec.kind}:${spec.name}`;
      if (grid && sharedGrids.has(sharedKey)) {parameters.set(spec.name, sharedGrids.get(sharedKey)); continue;}
      const field = document.createElement(grid ? 'textarea' : 'input'); field.dataset.kind = spec.kind; field.dataset.label = spec.label;
      if (!grid) field.type = spec.kind === 'boolean' ? 'checkbox' : 'number';
      if (spec.kind === 'boolean') field.checked = spec.default;
      else if (grid) {
        field.value = spec.default.map(row => row.map(n => n === null ? '.' : Array.isArray(n) ? n.join(',') : n).join(' ')).join('\n'); field.rows = 3; field.maxLength = 512; field.required = true;
        sharedGrids.set(sharedKey, field);
      }
      else {field.value = spec.default; field.min = spec.minimum; field.step = '1'; field.required = true;}
      const wrapper = node('label', spec.label, 'parameter'); wrapper.append(field); parameters.set(spec.name, field);
      if (grid) {
        const common = node('div', undefined, 'shared-parameters'); common.append(wrapper,
          node('p', spec.kind === 'region-map'
            ? '部屋を使うルールで共有します。盤面と同じ行・列数で、0以上の整数を空白区切りで入力します。各部屋は上下左右でつながる必要があります。'
            : spec.kind === 'run-clue-grid' ? 'セルを空白で区切り、. はヒントなし、0は黒なし、1,2は別々の黒い連続区間です。順序は問いません。'
            : spec.kind === 'marker-grid' ? '盤面と同じ行・列数で0（丸なし）か1（白の端点の丸）を入力します。数字の直線長ではありません。'
            : spec.name === 'orthogonal_counts' ? '数字を空白区切りで入力します。0も数字ヒントで、数字なしは . です。この数字だけではセルの色を固定しません。他のルールや固定ヒントで色が決まることはあります。'
            : spec.kind === 'clue-grid' ? '数字を空白区切りで入力します。0も数字ヒントで、数字なしは . です。数字マスは白として固定します。'
            : '盤面と同じ行・列数で、0〜99の整数を空白区切りで入力します。数字は問題に固定されます。0の意味は各ルールの説明を確認してください。'));
        $('rules').prepend(common);
      } else fields.append(wrapper);
    }
    card.append(fields); $('rules').append(card); selected.set(rule.identifier, {toggle, parameters});
  }
  for (const hint of profile.clues) {
    const toggle = document.createElement('input'); toggle.type = 'checkbox'; toggle.checked = true;
    const label = node('label', undefined, 'hint'); label.append(toggle, document.createTextNode(hint.label));
    $('hints').append(label); hints.set(hint.identifier, toggle);
  }
}
function isCoupled() {return plan?.requirements.topology === 'rectangular-cell-centers';}
function loopEdges() {
  const edges = [];
  const rows = plan.rows - Number(isCoupled()), cols = plan.cols - Number(isCoupled());
  for (let r = 0; r <= rows; r++) for (let c = 0; c < cols; c++) edges.push([r,c,r,c+1]);
  for (let r = 0; r < rows; r++) for (let c = 0; c <= cols; c++) edges.push([r,c,r+1,c]);
  return edges;
}
function edgeButton(edge, index, value, reveal, offset = 0) {
  const horizontal = edge[0] === edge[2], target = offset + index;
  const button = node('button', undefined, `edge ${horizontal ? 'horizontal' : 'vertical'}`);
  button.type = 'button'; button.dataset.edgeIndex = index;
  button.disabled = !artifact || fixed.has(target) || reveal;
  if (artifact && fixed.has(target)) button.classList.add('fixed');
  const paint = value => {
    button.dataset.value = value;
    button.textContent = value === -1 ? '?' : value === 0 ? '×' : horizontal ? '━' : '┃';
    button.setAttribute('aria-label', `${horizontal ? '横辺' : '縦辺'} ${edge[0]+1}行${edge[1]+1}列: ${value === -1 ? '未入力' : value === 0 ? '線なし' : '線あり'}${artifact && fixed.has(target) ? '（固定ヒント）' : ''}`);
  };
  paint(value);
  button.addEventListener('click', () => {input[target] = (input[target]+2)%3-1; paint(input[target]); $('answer-status').textContent = '';});
  return button;
}
function renderLoop(reveal, channels) {
  const edges = loopEdges(), indices = new Map(edges.map((e, i) => [e.join(','), i]));
  const solution = new Set(artifact?.record.solution.map(e => e.join(',')) || []);
  const numbers = new Map((artifact?.clues || []).filter(c => c.type === 'cell-count').map(c => [`${c.row},${c.col}`, c.count]));
  const table = node('table', undefined, 'loop-board'); table.setAttribute('aria-label', 'ループ盤面');
  for (let r = 0; r <= 2 * plan.rows; r++) {
    const tr = node('tr');
    for (let c = 0; c <= 2 * plan.cols; c++) {
      const td = node('td');
      if (r % 2 === 0 && c % 2 === 0) {const dot = node('span', '●', 'vertex'); dot.setAttribute('aria-hidden', 'true'); td.append(dot);}
      else if (r % 2 && c % 2) {
        const count = channels.has('cell-counts') ? numbers.get(`${(r-1)/2},${(c-1)/2}`) : undefined;
        const clue = node('span', String(count ?? '·'), 'loop-clue');
        clue.setAttribute('aria-label', `${(r+1)/2}行${(c+1)/2}列の辺数: ${count ?? 'ヒントなし'}`); td.append(clue);
      } else {
        const horizontal = r % 2 === 0;
        const edge = horizontal ? [r/2,(c-1)/2,r/2,(c+1)/2] : [(r-1)/2,c/2,(r+1)/2,c/2];
        const index = indices.get(edge.join(','));
        td.append(edgeButton(edge, index, reveal ? Number(solution.has(edge.join(','))) : artifact ? input[index] : -1, reveal));
      }
      tr.append(td);
    }
    table.append(tr);
  }
  $('board').replaceChildren(table);
}
function renderCoupled(reveal) {
  const area = plan.rows * plan.cols, edges = loopEdges(), indices = new Map(edges.map((e, i) => [e.join(','), i]));
  const black = new Set(artifact?.record.solution.black_cells.map(c => c.join(',')) || []);
  const used = new Set(artifact?.record.solution.loop_edges.map(e => e.join(',')) || []);
  const table = node('table', undefined, 'coupled-board'); table.setAttribute('aria-label', '黒白とセル中心のループ盤面');
  for (let r = 0; r < 2*plan.rows-1; r++) {
    const tr = node('tr');
    for (let c = 0; c < 2*plan.cols-1; c++) {
      const td = node('td');
      if (r%2 === 0 && c%2 === 0) {
        const index = r/2*plan.cols+c/2;
        td.append(cellButton(index, r/2, c/2, reveal ? Number(black.has(`${r/2},${c/2}`)) : artifact ? input[index] : -1, reveal));
      } else if (r%2 !== c%2) {
        const edge = r%2 === 0 ? [r/2,(c-1)/2,r/2,(c+1)/2] : [(r-1)/2,c/2,(r+1)/2,c/2];
        const index = indices.get(edge.join(','));
        td.append(edgeButton(edge, index, reveal ? Number(used.has(edge.join(','))) : artifact ? input[area+index] : -1, reveal, area));
      }
      tr.append(td);
    }
    table.append(tr);
  }
  $('board').replaceChildren(table);
}
function chooseProfile() {
  clearTimeout(timer); ++revision;
  profile = catalog.profiles.find(p => p.id === $('family').value);
  $('rows').value = profile.defaults.rows; $('cols').value = profile.defaults.cols;
  $('rows').max = $('cols').max = profile.board.max_cells;
  $('rows').min = profile.board.min_rows; $('cols').min = profile.board.min_cols;
  $('size-note').textContent = `最大${profile.board.max_cells}セル。選ぶルールにより上限が下がります。大きさとルールによっては時間内に生成できません。Seedが同じでも、環境の変更をまたぐ一致は保証しません。`;
  buildControls(); $('recipe-fields').disabled = false; refresh();
}
$('family').addEventListener('change', chooseProfile);
form.addEventListener('input', () => {clearTimeout(timer); ++revision; clearArtifact(); $('generate').disabled = true; $('retry-plan').hidden = true;
  timer = setTimeout(refresh, 120);});
form.addEventListener('submit', async event => {
  event.preventDefault(); clearTimeout(timer);
  if (!plan || !form.reportValidity()) return;
  ++revision; clearArtifact(); renderBoard(); form.inert = true; $('generate').disabled = true;
  $('status').textContent = '生成・唯一解検証中…';
  try {
    const request = readRequest(), result = await post('/api/generate', request);
    if (result.status === 'ok') {
      assertRenderablePlan(result.plan, request);
      artifact = result; plan = result.plan; fixed = new Set();
      const isLoop = plan.requirements.channels.find(c => c.name === 'answer')?.kind === 'binary-edges';
      const area = plan.rows * plan.cols;
      input = Array(isCoupled() ? area + loopEdges().length : isLoop ? loopEdges().length : area).fill(-1);
      for (const grid of [plan.sight_counts, plan.island_areas, plan.endpoint_markers]) if (grid) for (let r = 0; r < plan.rows; r++) for (let c = 0; c < plan.cols; c++) {
        if (grid[r][c] > 0) {const index = r*plan.cols+c; input[index] = 0; fixed.add(index);}
      }
      for (const grid of [plan.neighbor_counts,plan.component_counts,plan.black_run_clues]) if (grid) for (let r = 0; r < plan.rows; r++) for (let c = 0; c < plan.cols; c++) {
        if (grid[r][c] !== null) {const index = r*plan.cols+c; input[index] = 0; fixed.add(index);}
      }
      for (const clue of result.clues) {
        let index, value;
        if (clue.type === 'edge' && (isLoop || isCoupled())) {
          index = (isCoupled() ? area : 0) + loopEdges().findIndex(e => e.join(',') === clue.edge.join(',')); value = clue.used;
        } else if (isCoupled() && clue.type === 'black') {index = clue.cell[0]*plan.cols+clue.cell[1]; value = clue.black;}
        else if (!isCoupled() && !isLoop && clue.type === 'cell') {index = clue.row*plan.cols+clue.col; value = clue.value;}
        else continue;
        input[index] = value; fixed.add(index);
      }
      $('entry-note').textContent = isCoupled() ? 'セルは未入力 → 白 → 黒、辺は未入力 → 線なし（×）→ 線あり。両方を入力してください。固定ヒントは変更できません。' : isLoop ? '辺を押すと、未入力 → 線なし（×）→ 線ありの順に切り替わります。固定ヒントは変更できません。' : '未知のマスを押すと、未入力 → 白 → 黒の順に切り替わります。固定ヒントは変更できません。';
      renderBoard(); $('actions').hidden = false;
      $('status').textContent = `生成しました。唯一解・ヒント既約性を検証済み。\n${result.clues.length}個のヒント / ` + (result.evidence.method === 'cp-sat'
        ? `ソルバーで別解がないことを証明。${result.evidence.candidates}候補を探索。`
        : `${result.evidence.enumerated_boards}盤面を独立列挙して照合。`);
    } else $('status').textContent = messages[result.status] || `設定を確認してください。${result.message || ''}`;
  } catch (error) {
    if (error instanceof UnsupportedUiError) rejectUnsupportedUi();
    else $('status').textContent = '通信が途切れました。生成の成否は未確認です。予算内でサーバーの処理が終了するまでお待ちください。';
  }
  finally { form.inert = false; $('generate').disabled = !plan; }
});
$('check').addEventListener('click', async () => {
  if (!artifact) return;
  if (input.includes(-1)) {$('answer-status').textContent = '未入力のマスまたは辺があります。'; return;}
  form.inert = $('board').inert = $('answer-buttons').inert = true;
  $('answer-status').textContent = 'サーバーでルールとヒントを確認中…';
  try {
    const answer = isCoupled() ? {cells: input.slice(0, plan.rows*plan.cols), edges: input.slice(plan.rows*plan.cols)} : [...input];
    const result = await post('/api/check', {format: isCoupled() ? 'puzzle-box/web-answer-v2' : 'puzzle-box/web-answer-v1', request: artifact.request, clues: artifact.clues, answer});
    $('answer-status').textContent = result.status === 'ok' ? (result.correct ? '正解です。すべてのルールとヒントを満たしています。' : 'まだ正解ではありません。ルールとヒントを確認してください。') : messages[result.status] || '解答を検証できませんでした。';
  } catch {$('answer-status').textContent = '通信が途切れました。解答の正しさは未確認です。';}
  finally {form.inert = $('board').inert = $('answer-buttons').inert = false; $('check').focus();}
});
$('reveal').addEventListener('click', () => {
  if (!artifact) return;
  const show = $('reveal').textContent === '答えを表示'; renderBoard(show);
  $('reveal').textContent = show ? '自分の解答へ戻る' : '答えを表示';
});
$('download').addEventListener('click', () => {
  if (!artifact) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(artifact.record, null, 2) + '\n'], {type: 'application/json'}));
  const link = node('a'); link.href = url; link.download = 'puzzle.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
async function loadCatalog() {
  $('retry-catalog').hidden = true;
  $('recipe-fields').disabled = true; form.setAttribute('aria-busy', 'true');
  $('status').textContent = 'ルールを読み込んでいます…';
  $('plan-note').textContent = 'ルールの宣言を読み込み中…';
  try {
    catalog = await fetchJsonWithTimeout('/api/catalog');
    if (catalog.format !== 'puzzle-box/web-catalog-v1') throw new Error('Unsupported catalog');
    $('budget').max = catalog.limits.max_budget_seconds;
    if (Number($('budget').value) > catalog.limits.max_budget_seconds) $('budget').value = catalog.limits.max_budget_seconds;
    if (catalog.hosting) {
      $('hosting-label').textContent = catalog.hosting.label + ' · セルと辺';
      $('hosting-note').textContent = `小盤面のWeb実験。計算は1回${catalog.hosting.budget_seconds}秒まで。混雑時や利用枠の上限では使えない場合があります。`;
    }
    $('capabilities').replaceChildren(...catalog.profiles.map(p =>
      node('li', `${p.label}：${p.rules.length}ルール、最大${p.board.max_cells}セル`)));
    $('family').replaceChildren();
    for (const p of catalog.profiles) {const option = node('option', p.label); option.value = p.id; $('family').append(option);}
    chooseProfile();
  } catch {
    $('recipe-fields').disabled = true;
    $('status').textContent = 'ルールを読み込めません。接続を確認して再試行してください。';
    $('plan-note').textContent = 'プレビューを表示できません。';
    $('retry-catalog').hidden = false;
  } finally { form.setAttribute('aria-busy', 'false'); }
}
$('retry-catalog').addEventListener('click', loadCatalog);
$('retry-plan').addEventListener('click', () => {clearTimeout(timer); refresh();});
loadCatalog();
