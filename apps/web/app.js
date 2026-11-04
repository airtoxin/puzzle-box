const $ = id => document.getElementById(id);
const form = $('recipe-form');
let catalog, plan, artifact, input = [], fixed = new Set(), revision = 0, timer;
const selected = new Map();
const hints = new Map();
const messages = {
  unsatisfiable: 'この組合せを満たす盤面はありません。ルールや設定を変更してください。',
  insufficient_hints: '選んだヒントだけでは、どの完成盤面も一意に決まりません。セルヒントなどを追加してください。',
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
  return {format: catalog.request_format, rows: Number($('rows').value), cols: Number($('cols').value),
    seed: Number($('seed').value), budget_seconds: Number($('budget').value),
    rules: [...selected].filter(([, s]) => s.toggle.checked).map(([id, s]) => ({id,
      parameters: Object.fromEntries([...s.parameters].map(([name, field]) =>
        [name, field.type === 'checkbox' ? field.checked : Number(field.value)]))})),
    clue_kinds: [...hints].filter(([, toggle]) => toggle.checked).map(([id]) => id)};
}
async function post(path, data) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
  return response.json();
}
function clearArtifact() {
  artifact = undefined; $('actions').hidden = true; $('answer-status').textContent = '';
  $('reveal').textContent = '答えを表示';
}
function syncParameters() {
  const area = Number($('rows').value) * Number($('cols').value);
  for (const rule of catalog.rules) {
    const state = selected.get(rule.identifier);
    for (const spec of rule.parameters) {
      const field = state.parameters.get(spec.name);
      field.disabled = !state.toggle.checked;
      if (spec.kind === 'integer') field.max = spec.maximum === 'area' ? area : spec.maximum;
    }
  }
}
async function refresh() {
  const current = ++revision;
  clearArtifact(); plan = undefined; $('generate').disabled = true; syncParameters();
  if (!form.checkValidity()) {
    $('status').textContent = '入力値を確認してください。'; $('board').replaceChildren(); return;
  }
  try {
    const result = await post('/api/plan', readRequest());
    if (current !== revision) return;
    if (result.status !== 'ok') {
      $('status').textContent = `設定を組み合わせられません。${result.message || ''}`;
      $('board').replaceChildren(); return;
    }
    plan = result.plan;
    $('shape').textContent = `${plan.rows} × ${plan.cols}`;
    $('plan-note').textContent = '選択したルールとヒントが要求する盤面を表示しています。UIの適合は、問題の成立を保証しません。';
    $('status').textContent = '生成前のプレビューです。';
    renderBoard(); $('generate').disabled = false;
  } catch {
    if (current === revision) $('status').textContent = 'ローカルサーバーに接続できません。起動状態を確認してください。';
  }
}
function renderBoard(reveal = false) {
  if (!plan) return;
  $('preview-title').textContent = reveal ? '解答' : artifact ? '生成した問題' : '盤面プレビュー';
  const channels = new Set(plan.requirements.channels.map(c => c.name));
  const table = node('table'); table.setAttribute('aria-label', artifact ? '生成した問題' : '盤面プレビュー');
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
      const value = reveal ? artifact.record.solution[r][c] : artifact ? input[index] : -1;
      const button = node('button', undefined, 'cell');
      button.type = 'button'; button.disabled = !artifact || fixed.has(index) || reveal;
      if (fixed.has(index) && artifact) button.classList.add('fixed');
      const paint = value => {
        button.textContent = value === -1 ? '?' : value === 0 ? '○' : '■';
        button.dataset.value = value;
        button.setAttribute('aria-label', `${r + 1}行${c + 1}列: ${value === -1 ? '未入力' : value === 0 ? '白' : '黒'}${fixed.has(index) && artifact ? '（固定ヒント）' : ''}`);
      };
      paint(value);
      button.addEventListener('click', () => {
        input[index] = (input[index] + 2) % 3 - 1; $('answer-status').textContent = '';
        paint(input[index]); // Keep the actual focused button and Tab position.
      });
      const td = node('td'); td.append(button); tr.append(td);
    }
    table.append(tr);
  }
  $('board').replaceChildren(table);
}
function buildControls() {
  for (const rule of catalog.rules) {
    const card = node('div', undefined, 'rule-card'); const label = node('label', undefined, 'rule-title');
    const toggle = document.createElement('input'); toggle.type = 'checkbox'; toggle.checked = ['count', 'connected-white'].includes(rule.identifier);
    label.append(toggle, document.createTextNode(rule.label)); card.append(label, node('p', rule.summary));
    const parameters = new Map(), fields = node('div', undefined, 'parameters');
    for (const spec of rule.parameters) {
      if (!['integer', 'boolean'].includes(spec.kind)) throw new Error('Unsupported parameter kind');
      const field = document.createElement('input'); field.type = spec.kind === 'boolean' ? 'checkbox' : 'number';
      if (spec.kind === 'boolean') field.checked = spec.default;
      else {field.value = spec.default; field.min = spec.minimum; field.step = '1'; field.required = true;}
      const wrapper = node('label', spec.label, 'parameter'); wrapper.append(field); fields.append(wrapper); parameters.set(spec.name, field);
    }
    card.append(fields); $('rules').append(card); selected.set(rule.identifier, {toggle, parameters});
  }
  for (const hint of catalog.clues) {
    const toggle = document.createElement('input'); toggle.type = 'checkbox'; toggle.checked = true;
    const label = node('label', undefined, 'hint'); label.append(toggle, document.createTextNode(hint.label));
    $('hints').append(label); hints.set(hint.identifier, toggle);
  }
}
form.addEventListener('input', () => {clearTimeout(timer); ++revision; clearArtifact(); $('generate').disabled = true;
  timer = setTimeout(refresh, 120);});
form.addEventListener('submit', async event => {
  event.preventDefault(); clearTimeout(timer);
  if (!plan || !form.reportValidity()) return;
  ++revision; clearArtifact(); renderBoard(); form.inert = true; $('generate').disabled = true;
  $('status').textContent = '生成・唯一解検証中…';
  try {
    const result = await post('/api/generate', readRequest());
    if (result.status === 'ok') {
      artifact = result; plan = result.plan; input = Array(plan.rows * plan.cols).fill(-1); fixed = new Set();
      for (const clue of result.clues.filter(c => c.type === 'cell')) {
        const index = clue.row * plan.cols + clue.col; input[index] = clue.value; fixed.add(index);
      }
      renderBoard(); $('actions').hidden = false;
      $('status').textContent = `生成しました。唯一解・ヒント既約性を検証済み。\n${result.clues.length}個のヒント / ${result.evidence.enumerated_boards}盤面を独立列挙して照合。`;
    } else $('status').textContent = messages[result.status] || `設定を確認してください。${result.message || ''}`;
  } catch { $('status').textContent = '通信が途切れました。生成の成否は未確認です。予算内でサーバーの処理が終了するまでお待ちください。'; }
  finally { form.inert = false; $('generate').disabled = false; }
});
$('check').addEventListener('click', () => {
  if (!artifact) return;
  $('answer-status').textContent = input.includes(-1) ? '未入力のマスがあります。' :
    input.every((v, i) => v === artifact.record.solution[Math.floor(i / plan.cols)][i % plan.cols]) ?
      '正解です。すべてのルールとヒントを満たしています。' : 'まだ正解ではありません。ルールとヒントを確認してください。';
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
try {
  const response = await fetch('/api/catalog'); catalog = await response.json();
  if (catalog.format !== 'puzzle-box/web-catalog-v1') throw new Error('Unsupported catalog');
  buildControls(); await refresh();
} catch { $('status').textContent = 'UI定義を読み込めません。対応するローカルサーバーの起動状態を確認してください。'; }
