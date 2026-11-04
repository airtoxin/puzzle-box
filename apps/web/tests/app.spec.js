import {test, expect} from '@playwright/test';

test('coupled cells and center edges require a complete joint answer', async ({page}) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/'); await page.locator('#family').selectOption('coupled');
  await expect(page.locator('#rules input:checked:disabled')).toHaveCount(3);
  await expect(page.locator('#rows')).toHaveAttribute('min', '2');
  await expect(page.locator('.cell')).toHaveCount(9); await expect(page.locator('.edge')).toHaveCount(12);
  await expect(page.locator('#generate')).toBeEnabled();
  const response = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const artifact = await (await response).json(); expect(artifact.status).toBe('ok');
  await expect(page.locator('#status')).toContainText('生成しました');
  expect(artifact.record.format).toBe('puzzle-box/yajilin-v1');
  expect(artifact.record.arrow_sites).toEqual([]);
  await expect(page.locator('.cell.fixed')).toHaveCount(artifact.clues.filter(c => c.type === 'black').length);
  expect(artifact.clues.some(c => c.type === 'black')).toBe(true);
  const firstCell = page.locator('.cell:enabled').first();
  await firstCell.focus(); await page.keyboard.press('Space'); await expect(firstCell).toBeFocused();
  const black = new Set(artifact.record.solution.black_cells.map(c => c.join(',')));
  for (let i = 0; i < artifact.cells.length; i++) {
    const cell = page.locator(`[data-cell-index="${i}"]`);
    if (await cell.isEnabled())
      while (await cell.getAttribute('data-value') !== String(Number(black.has(artifact.cells[i].join(','))))) await cell.click();
  }
  await page.locator('#check').click(); await expect(page.locator('#answer-status')).toContainText('未入力');
  const firstEdge = page.locator('.edge:enabled').first();
  await firstEdge.focus(); await page.keyboard.press('Space'); await expect(firstEdge).toBeFocused();
  await page.keyboard.press('Enter'); await expect(firstEdge).toBeFocused();
  for (const edge of await page.locator('.edge:enabled').all())
    while (await edge.getAttribute('data-value') !== '0') await edge.click();
  await page.locator('#check').click(); await expect(page.locator('#answer-status')).toContainText('まだ正解ではありません');
  const used = new Set(artifact.record.solution.loop_edges.map(e => e.join(',')));
  for (let i = 0; i < artifact.edges.length; i++) {
    const edge = page.locator(`[data-edge-index="${i}"]`);
    if (await edge.isEnabled() && used.has(artifact.edges[i].join(','))) await edge.click();
  }
  const checked = page.waitForResponse('**/api/check'); await page.locator('#check').click();
  const reply = await checked;
  const payload = reply.request().postDataJSON();
  expect(payload.format).toBe('puzzle-box/web-answer-v2');
  expect(Object.keys(payload.answer).sort()).toEqual(['cells', 'edges']);
  expect(await reply.json()).toEqual({status: 'ok', correct: true});
  await expect(page.locator('#answer-status')).toContainText('正解です');
  await page.locator('#reveal').click();
  await expect(page.locator('.cell:enabled,.edge:enabled')).toHaveCount(0);
  const download = page.waitForEvent('download'); await page.locator('#download').click();
  const stream = await (await download).createReadStream(); const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  expect(JSON.parse(Buffer.concat(chunks).toString('utf8'))).toEqual(artifact.record);
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: test.info().outputPath('coupled-mobile.png'), fullPage: true});
  await page.locator('#family').selectOption('slitherlink');
  await expect(page.locator('#rows')).toHaveAttribute('min', '1');
  await expect(page.locator('.cell')).toHaveCount(0); await expect(page.locator('.edge')).toHaveCount(12);
  await expect(page.locator('#actions')).toBeHidden(); expect(errors).toEqual([]);
});

test('coupled edge hints and insufficient hints use the same joint board', async ({page}) => {
  await page.goto('/'); await page.locator('#family').selectOption('coupled');
  await page.locator('#hints input').first().uncheck();
  await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('生成しました');
  expect(await page.locator('.edge.fixed:disabled').count()).toBeGreaterThan(0);
  await expect(page.locator('.cell.fixed')).toHaveCount(0);
  await page.locator('#hints input').last().uncheck();
  await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('どの完成盤面も一意に決まりません');
  await expect(page.locator('#actions')).toBeHidden();
});

async function textContrast(locator, property = 'color') {
  const colors = await locator.evaluate((el, property) => {
    const foreground = getComputedStyle(el)[property];
    let background = 'rgba(0, 0, 0, 0)';
    for (let node = el; node && background === 'rgba(0, 0, 0, 0)'; node = node.parentElement)
      background = getComputedStyle(node).backgroundColor;
    return [foreground, background];
  }, property);
  const luminance = color => color.match(/[\d.]+/g).slice(0, 3)
    .map(Number).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
    .reduce((total, v, i) => total + v * [.2126, .7152, .0722][i], 0);
  const values = colors.map(luminance).sort((a, b) => a - b);
  return (values[1] + .05) / (values[0] + .05);
}

test('rule-declared controls, hint channels, real generation and answer interaction', async ({page}) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('button', {name: 'この組合せで生成する →'})).toBeEnabled();
  await expect(page.getByLabel('黒マス数', {exact: true})).toHaveAttribute('max', '6');
  await expect(page.getByLabel('斜めに接することも禁止')).toBeDisabled();
  await page.getByLabel('黒マスを離す', {exact: true}).check();
  await expect(page.getByLabel('斜めに接することも禁止')).toBeEnabled();
  await page.getByLabel('各列の黒マス数', {exact: true}).uncheck();
  await expect(page.getByRole('columnheader')).toHaveCount(0);
  await page.getByLabel('各列の黒マス数', {exact: true}).check();
  await expect(page.getByRole('columnheader')).toHaveCount(3);
  await expect(page.getByRole('button', {name: 'この組合せで生成する →'})).toBeEnabled();
  const response = page.waitForResponse('**/api/generate');
  await page.getByRole('button', {name: 'この組合せで生成する →'}).click();
  const generated = await (await response).json();
  expect(generated.status).toBe('ok');
  await expect(page.locator('#status')).toContainText('唯一解・ヒント既約性を検証済み');
  expect(generated.request.rules.map(r => r.id)).toEqual(['count', 'non-touching', 'connected-white']);
  await page.getByRole('button', {name: '解答を確認', exact: true}).click();
  await expect(page.locator('#answer-status')).toContainText('未入力');
  for (let r = 0; r < 2; r++) for (let c = 0; c < 3; c++) {
    const cell = page.getByRole('button', {name: new RegExp(`^${r+1}行${c+1}列:`)});
    if (await cell.isEnabled()) {
      await cell.click();
      if (generated.record.solution[r][c]) await cell.click();
    }
  }
  await page.getByRole('button', {name: '解答を確認', exact: true}).click();
  await expect(page.locator('#answer-status')).toContainText('正解です');
  const download = page.waitForEvent('download');
  await page.getByRole('button', {name: '問題JSONを保存'}).click();
  expect((await download).suggestedFilename()).toBe('puzzle.json');
  await page.getByRole('button', {name: '答えを表示', exact: true}).click();
  await expect(page.locator('.cell:enabled')).toHaveCount(0);
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({path: test.info().outputPath('generated.png'), fullPage: true});
  expect(errors).toEqual([]);
});

test('finite contradictions and insufficient hints are distinct', async ({page}) => {
  await page.goto('/');
  await expect(page.getByRole('button', {name: 'この組合せで生成する →'})).toBeEnabled();
  await page.getByLabel('白マスをつなぐ', {exact: true}).uncheck();
  await page.getByLabel('黒マスを離す', {exact: true}).check();
  await page.getByLabel('黒マス数', {exact: true}).fill('6');
  await expect(page.getByRole('button', {name: 'この組合せで生成する →'})).toBeEnabled();
  await page.getByRole('button', {name: 'この組合せで生成する →'}).click();
  await expect(page.locator('#status')).toContainText('満たす盤面はありません');
  await page.getByLabel('黒マスを離す', {exact: true}).uncheck();
  await page.getByLabel('黒マス数', {exact: true}).fill('1');
  await page.getByLabel('列数', {exact: true}).fill('2');
  await page.getByLabel('黒・白のセルヒント').uncheck();
  await page.getByLabel('各列の黒マス数', {exact: true}).uncheck();
  await expect(page.getByRole('button', {name: 'この組合せで生成する →'})).toBeEnabled();
  await page.getByRole('button', {name: 'この組合せで生成する →'}).click();
  await expect(page.locator('#status')).toContainText('どの完成盤面も一意に決まりません');
  await expect(page.locator('#actions')).toBeHidden();
});

test('timeout is inconclusive and mobile preview stays usable', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/');
  await expect(page.getByRole('button', {name: 'この組合せで生成する →'})).toBeEnabled();
  // Deterministic rendering test; backend timeout/worker cleanup is tested in Python.
  await page.route('**/api/generate', route => route.fulfill({json: {status: 'timeout', budget_seconds: 10}}));
  await page.getByRole('button', {name: 'この組合せで生成する →'}).click();
  await expect(page.locator('#status')).toContainText('解なしとは判定していません');
  await expect(page.locator('#actions')).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: test.info().outputPath('mobile.png'), fullPage: true});
});

test('keyboard cell entry retains focus and black cells keep contrast on hover', async ({page}) => {
  await page.goto('/');
  await expect(page.getByRole('button', {name: 'この組合せで生成する →'})).toBeEnabled();
  await page.getByRole('button', {name: 'この組合せで生成する →'}).click();
  await expect(page.locator('#status')).toContainText('生成しました');
  const cell = page.locator('.cell:enabled').first();
  await expect.soft(await textContrast(cell)).toBeGreaterThanOrEqual(4.5);
  await expect.soft(await textContrast(page.locator('h2 span').first())).toBeGreaterThanOrEqual(4.5);
  await expect.soft(await textContrast(page.locator('footer'))).toBeGreaterThanOrEqual(4.5);
  await expect(await textContrast(cell, 'borderTopColor')).toBeGreaterThanOrEqual(3);
  await expect(await textContrast(page.getByLabel('黒マス数', {exact: true}), 'borderTopColor')).toBeGreaterThanOrEqual(3);
  await cell.focus();
  await page.keyboard.press('Space');
  await expect(cell).toHaveAttribute('data-value', '0');
  await expect(await textContrast(cell)).toBeGreaterThanOrEqual(4.5);
  await expect.soft(cell).toBeFocused();
  await expect(await textContrast(cell, 'outlineColor')).toBeGreaterThanOrEqual(3);
  // Re-focus even before the fix so the hover regression is independently exercised.
  await cell.focus();
  await page.keyboard.press('Enter');
  await expect(cell).toHaveAttribute('data-value', '1');
  await expect.soft(cell).toBeFocused();
  await cell.hover();
  await expect.soft(cell).toHaveCSS('background-color', 'rgb(33, 60, 51)');
  await expect(cell).toHaveCSS('color', 'rgb(255, 255, 255)');
  await expect(await textContrast(cell)).toBeGreaterThanOrEqual(4.5);
  await page.keyboard.press('Tab');
  await expect(page.locator('.cell:enabled').nth(1)).toBeFocused();
});

test('all columns of a wide board are reachable at narrow desktop widths', async ({page}) => {
  await page.setViewportSize({width: 800, height: 800});
  await page.goto('/');
  await expect(page.getByRole('button', {name: 'この組合せで生成する →'})).toBeEnabled();
  await page.getByLabel('行数', {exact: true}).fill('1');
  await page.getByLabel('列数', {exact: true}).fill('9');
  await expect(page.locator('.cell')).toHaveCount(9);
  const board = page.locator('#board');
  const visible = await board.boundingBox();
  await board.evaluate(el => {el.scrollLeft = 0;});
  const first = await page.locator('.cell').first().boundingBox();
  expect.soft(first.x).toBeGreaterThanOrEqual(visible.x);
  await board.evaluate(el => {el.scrollLeft = el.scrollWidth;});
  const last = await page.locator('.cell').last().boundingBox();
  expect(last.x + last.width).toBeLessThanOrEqual(visible.x + visible.width + 1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('loop declarations, numeric and edge clues, keyboard entry and server answer checking', async ({page}) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByLabel('盤面の種類')).toHaveValue('shading');
  await page.getByLabel('盤面の種類').selectOption('slitherlink');
  await expect(page.getByLabel('空でない1本のループ', {exact: true})).toBeChecked();
  await expect(page.getByLabel('空でない1本のループ', {exact: true})).toBeDisabled();
  await expect(page.getByLabel('辺の本数', {exact: true})).toHaveAttribute('max', '12');
  await expect(page.locator('.edge')).toHaveCount(12);
  await page.getByLabel('Seed', {exact: true}).fill('2');
  await expect(page.locator('#generate')).toBeEnabled();
  const response = page.waitForResponse('**/api/generate');
  await page.locator('#generate').click();
  const artifact = await (await response).json();
  expect(artifact.status).toBe('ok');
  await expect(page.locator('#status')).toContainText('生成しました');
  expect(new Set(artifact.clues.map(c => c.type))).toEqual(new Set(['cell-count', 'edge']));
  for (const clue of artifact.clues.filter(c => c.type === 'cell-count'))
    await expect(page.getByLabel(`${clue.row+1}行${clue.col+1}列の辺数: ${clue.count}`, {exact: true})).toHaveText(String(clue.count));
  await expect(page.locator('.edge.fixed')).toHaveCount(artifact.clues.filter(c => c.type === 'edge').length);
  const first = page.locator('.edge:enabled').first();
  await expect(await textContrast(first)).toBeGreaterThanOrEqual(4.5);
  await first.focus(); await page.keyboard.press('Space');
  await expect(first).toBeFocused(); await expect(first).toHaveAttribute('data-value', '0');
  await page.keyboard.press('Enter');
  await expect(first).toBeFocused(); await expect(first).toHaveAttribute('data-value', '1');
  await first.hover(); await expect(await textContrast(first)).toBeGreaterThanOrEqual(4.5);
  // Enter an incorrect complete candidate first, preserving fixed clues.
  for (const edge of await page.locator('.edge:enabled').all())
    while (await edge.getAttribute('data-value') !== '0') await edge.click();
  await page.locator('#check').click();
  await expect(page.locator('#answer-status')).toContainText('まだ正解ではありません');
  for (let i = 0; i < artifact.edges.length; i++) {
    const edge = page.locator(`[data-edge-index="${i}"]`);
    if (await edge.isEnabled() && artifact.record.solution.some(e => e.join(',') === artifact.edges[i].join(','))) await edge.click();
  }
  const checked = page.waitForResponse('**/api/check');
  await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status: 'ok', correct: true});
  await expect(page.locator('#answer-status')).toContainText('正解です');
  await page.locator('#reveal').click();
  await expect(page.locator('.edge:enabled')).toHaveCount(0);
  const download = page.waitForEvent('download'); await page.locator('#download').click();
  expect((await download).suggestedFilename()).toBe('puzzle.json');
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: test.info().outputPath('loop-mobile.png'), fullPage: true});
  await page.getByLabel('盤面の種類').selectOption('shading');
  await expect(page.locator('.edge')).toHaveCount(0); await expect(page.locator('.cell')).toHaveCount(6);
  await expect(page.locator('#actions')).toBeHidden();
  expect(errors).toEqual([]);
});

test('loop contradiction and insufficient hints remain distinct', async ({page}) => {
  await page.goto('/'); await page.getByLabel('盤面の種類').selectOption('slitherlink');
  await page.getByLabel('辺の本数', {exact: true}).fill('5');
  await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('満たす盤面はありません');
  await page.getByLabel('辺の本数', {exact: true}).fill('8');
  await page.getByLabel('セルを囲む辺の数').uncheck();
  await page.getByLabel('線の有無を固定するヒント').uncheck();
  await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('どの完成盤面も一意に決まりません');
});

test('answer-check progress remains exposed to assistive technology while controls are locked', async ({page}) => {
  await page.goto('/'); await page.getByLabel('盤面の種類').selectOption('slitherlink');
  await page.getByLabel('ループの長さ', {exact: true}).uncheck();
  await page.getByLabel('行数', {exact: true}).fill('1'); await page.getByLabel('列数', {exact: true}).fill('1');
  await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('生成しました');
  for (const edge of await page.locator('.edge:enabled').all()) {await edge.click(); await edge.click();}
  let resume, intercepted;
  const pending = new Promise(resolve => {intercepted = resolve;});
  await page.route('**/api/check', async route => {
    await new Promise(resolve => {resume = resolve; intercepted();});
    await route.fulfill({json: {status: 'timeout', budget_seconds: 10}});
  });
  await page.locator('#check').click(); await pending;
  try {
    const session = await page.context().newCDPSession(page);
    const tree = await session.send('Accessibility.getFullAXTree');
    expect(tree.nodes.some(n => !n.ignored && n.name?.value === 'サーバーでルールとヒントを確認中…')).toBe(true);
    expect(await page.locator('#check').evaluate(el => el.closest('[inert]') !== null)).toBe(true);
    expect(await page.locator('#board').evaluate(el => el.inert)).toBe(true);
  } finally {resume();}
  await expect(page.locator('#answer-status')).toContainText('解なしとは判定していません');
  await expect(page.locator('#check')).toBeFocused();
  expect(await page.locator('#check').evaluate(el => el.closest('[inert]') === null)).toBe(true);
});
