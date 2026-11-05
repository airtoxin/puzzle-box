import {test, expect} from '@playwright/test';
for (const family of ['shading', 'slitherlink', 'coupled']) {
  test(`${family} puzzle share round trip`, async ({page, browser}) => {
    await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
    if (family !== 'shading') {await page.locator('#family').selectOption(family); await expect(page.locator('#generate')).toBeEnabled();}
    const response = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
    const original = await (await response).json(); expect(original.status).toBe('ok');
    await page.locator('#share-puzzle').click(); const url = await page.locator('#puzzle-url').inputValue();
    const data = JSON.parse(Buffer.from(new URL(url).hash.slice('#puzzle-v1='.length), 'base64url'));
    expect(Object.keys(data).sort()).toEqual(['clues', 'format', 'request']); expect(data.clues).toEqual(original.clues);
    expect(JSON.stringify(data)).not.toContain('solution');
    const context = await browser.newContext(); const recipient = await context.newPage();
    const restoredResponse = recipient.waitForResponse('**/api/restore'); await recipient.goto(url);
    const restored = await (await restoredResponse).json(); expect(restored.status).toBe('ok');
    await expect(recipient.locator('#actions')).toBeVisible();
    await expect(recipient.locator('#generated-rules-list')).toHaveText(await page.locator('#generated-rules-list').allTextContents());
    expect(restored.clues).toEqual(original.clues); expect(restored.record.solution).toEqual(original.record.solution);
    if (family !== 'slitherlink') {
      const solution = family === 'shading' ? original.record.solution.flat() : original.cells.map(c => Number(original.record.solution.black_cells.some(x => x.join() === c.join())));
      for (let i = 0; i < solution.length; i++) {const cell = recipient.locator(`[data-cell-index="${i}"]`); if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(solution[i])) await cell.click();}
    }
    if (family !== 'shading') {
      const solution = family === 'coupled' ? original.record.solution.loop_edges : original.record.solution;
      for (let i = 0; i < original.edges.length; i++) {const edge = recipient.locator(`[data-edge-index="${i}"]`); const bit = Number(solution.some(x => x.join() === original.edges[i].join())); if (await edge.isEnabled()) while (await edge.getAttribute('data-value') !== String(bit)) await edge.click();}
    }
    const check = recipient.waitForResponse('**/api/check'); await recipient.locator('#check').click();
    expect(await (await check).json()).toEqual({status:'ok', correct:true});
    await recipient.locator('#reveal').click(); await expect(recipient.locator('#reveal')).toContainText('自分の解答');
    await context.close();
  });
}
test('timeout preserves existing answer', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#actions')).toBeVisible(); await page.locator('#share-puzzle').click();
  const url = await page.locator('#puzzle-url').inputValue(); const cell = page.locator('.cell:enabled').first();
  await cell.click(); const value = await cell.getAttribute('data-value');
  await page.route('**/api/restore', route => route.fulfill({json:{status:'timeout'}}));
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash); await page.locator('#load-shared-settings').click();
  await expect(page.locator('#navigation-status')).toContainText('維持'); await expect(cell).toHaveAttribute('data-value', value);
});

test('editing while a shared puzzle loads prevents replacement', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#actions')).toBeVisible(); await page.locator('#share-puzzle').click();
  const url = await page.locator('#puzzle-url').inputValue();
  let release, started; const gate = new Promise(r => {release = r;}); const waiting = new Promise(r => {started = r;});
  await page.route('**/api/restore', async route => {started(); await gate; await route.continue();});
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  const response = page.waitForResponse('**/api/restore');
  await page.locator('#load-shared-settings').click(); await waiting;
  const cell = page.locator('.cell:enabled').first(); await cell.click(); const value = await cell.getAttribute('data-value');
  release(); await response; await expect(page.locator('#navigation-status')).toContainText('中止');
  await expect(cell).toHaveAttribute('data-value', value);
});

test('invalid and oversized puzzle links preserve current work', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#actions')).toBeVisible(); const cell = page.locator('.cell:enabled').first(); await cell.click();
  const value = await cell.getAttribute('data-value');
  for (const hash of ['#puzzle-v1=invalid', '#puzzle-v1=' + 'a'.repeat(8192), '#puzzle-v2=abc']) {
    await page.evaluate(hash => {location.hash = hash;}, hash); await expect(page.locator('#load-shared-settings')).toBeVisible();
    await page.locator('#load-shared-settings').click(); await expect(page.locator('#share-status')).toContainText('読み込めません');
    await expect(cell).toHaveAttribute('data-value', value); await expect(page.locator('#actions')).toBeVisible();
  }
});

async function startMixed(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('数字セルが属する成分の面積を固定',{exact:true}).check();
  await expect(page.locator('.component-area-number')).toHaveText(['面1','面4']);
}

test('shared puzzle keeps all numeric and marker explanations', async ({page, browser}) => {
  await startMixed(page);
  await page.getByLabel('白マスの数字を重複させない',{exact:true}).check();
  await page.getByLabel('固定数字（行ごとに入力）',{exact:true}).fill('1 2 3\n4 5 6');
  await page.getByLabel('数字から見える白マス数を固定',{exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）',{exact:true}).fill('0 0 0\n0 0 3');
  await page.getByLabel('数字がある白成分の面積を固定',{exact:true}).check();
  await page.getByLabel('白い島の面積（0は数字なし）',{exact:true}).fill('0 0 0\n0 0 4');
  await page.getByLabel('数字の周囲の黒マス数を固定',{exact:true}).check();
  await page.getByLabel('周囲の黒数（. は数字なし、0も有効）',{exact:true}).fill('. . .\n. . 1');
  await page.getByLabel('接する黒成分の面積合計を固定',{exact:true}).check();
  await page.getByLabel('接する黒成分の面積合計（. は丸なし）',{exact:true}).fill('. . .\n. . 1');
  await page.getByLabel('周囲8マスの黒い連続長を指定',{exact:true}).check();
  await page.getByLabel('黒の連続長（複数は1,2、なしは.、黒0個は0）',{exact:true}).fill('. . .\n. . 1');
  await page.getByLabel('丸を白の端点と一致させる',{exact:true}).check();
  await page.getByLabel('端点の丸（0は丸なし、1は丸あり）',{exact:true}).fill('0 1 0\n1 0 1');
  await expect(page.locator('#rules textarea:visible')).toHaveCount(8);
  await expect(page.locator('#generate')).toBeEnabled();
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');
  const explanation = await page.locator('#plan-note').textContent();
  for (const text of ['固定ラベル', '見える白', '周囲の黒', '面積', '端点']) expect(explanation).toContain(text);
  await page.locator('#share-puzzle').click(); const url = await page.locator('#puzzle-url').inputValue();
  const context = await browser.newContext(); const recipient = await context.newPage();
  await recipient.goto(url); await expect(recipient.locator('#actions')).toBeVisible();
  await expect(recipient.locator('#plan-note')).toHaveText(explanation);
  await expect(recipient.locator('#generated-rules-list')).toHaveText(await page.locator('#generated-rules-list').allTextContents());
  await context.close();
});

async function configureEndpoints(page,length=3) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数',{exact:true}).uncheck();
  await page.getByLabel('丸を白の端点と一致させる',{exact:true}).check();
  await page.getByLabel('数字から見える白マス数を固定',{exact:true}).check();
  await page.getByLabel('見える白マス数（0は指定なし）',{exact:true}).fill(`${length} 0 0\n0 0 2`);
  await page.getByLabel('黒い2×2を禁止',{exact:true}).check();
  await page.getByLabel('白の2×2を禁止',{exact:true}).check();
  await expect(page.locator('#generate')).toBeEnabled();
}

test('shared endpoints retain visibility explanation', async ({page, browser}) => {
  await configureEndpoints(page); const response=page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await response).json()).status).toBe('ok');
  const note=await page.locator('#plan-note').textContent(); expect(note).toContain('自身を含む直線長');
  await page.locator('#share-puzzle').click(); const url=await page.locator('#puzzle-url').inputValue();
  const context=await browser.newContext(); const recipient=await context.newPage(); await recipient.goto(url);
  await expect(recipient.locator('#actions')).toBeVisible(); await expect(recipient.locator('#plan-note')).toHaveText(note); await context.close();
});

test('sharing cancels a pending puzzle restore', async ({page, browser}) => {
  await page.addInitScript(() => {
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
      const response = await originalFetch(...args);
      if (String(args[0]).endsWith('/api/restore')) {
        const originalJson = response.json.bind(response);
        response.json = async () => {
          const body = await originalJson();
          // The restoration handler has no further asynchronous work after
          // JSON parsing; the next task runs after its continuation completes.
          setTimeout(() => { window.restoreHandlerSettled = true; }, 0);
          return body;
        };
      }
      return response;
    };
  });
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  const context=await browser.newContext(); const other=await context.newPage(); await other.goto('/'); await expect(other.locator('#generate')).toBeEnabled();
  await other.locator('#seed').fill('7'); await expect(other.locator('#generate')).toBeEnabled(); await other.locator('#generate').click();
  await expect(other.locator('#actions')).toBeVisible(); await other.locator('#share-puzzle').click(); const url=await other.locator('#puzzle-url').inputValue();
  let release, started; const gate=new Promise(r=>{release=r;}), waiting=new Promise(r=>{started=r;});
  await page.route('**/api/restore',async route=>{started(); await gate; await route.continue();});
  await page.evaluate(hash=>{location.hash=hash;},new URL(url).hash); const restored=page.waitForResponse('**/api/restore');
  await page.locator('#load-shared-settings').click(); await waiting; await page.locator('#share-puzzle').click();
  const current=await page.locator('#puzzle-url').inputValue(); release(); await (await restored).finished();
  await page.waitForFunction(() => window.restoreHandlerSettled === true);
  await expect(page.locator('#navigation-status')).toContainText('中止'); await expect(page.locator('#puzzle-url')).toHaveValue(current);
  await expect(page.locator('#seed')).toHaveValue('0');
  expect(current).not.toBe(url); await context.close();
});

for (const outcome of ['resolve', 'reject']) test(`delayed clipboard ${outcome} after regeneration names stale puzzle`, async ({page}) => {
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', {value: {writeText: () => new Promise((resolve,reject) => {window.finishCopy = resolve; window.rejectCopy = reject;})}}));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  await page.locator('#share-puzzle').click(); await page.locator('#seed').fill('7'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  await page.evaluate(outcome => outcome === 'resolve' ? window.finishCopy() : window.rejectCopy(new Error('clipboard')), outcome);
  await expect(page.locator('#puzzle-share-status')).toContainText('作り直してください');
  await expect(page.locator('#puzzle-url')).toHaveValue('');
});


test('initial timeout offers to retry the puzzle link', async ({page, browser}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#actions')).toBeVisible(); await page.locator('#share-puzzle').click(); const url=await page.locator('#puzzle-url').inputValue();
  const context=await browser.newContext(); const recipient=await context.newPage(); let first=true;
  await recipient.route('**/api/restore', route => {if (first) {first=false; return route.fulfill({json:{status:'timeout'}});} return route.continue();});
  await recipient.goto(url); await expect(recipient.locator('#share-status')).toContainText('無効とは限りません');
  await expect(recipient.locator('#load-shared-settings')).toContainText('URLの問題を読み込む');
  await recipient.locator('#load-shared-settings').click(); await expect(recipient.locator('#actions')).toBeVisible();
  await expect(recipient.locator('#share-status')).toContainText('問題を読み込みました'); await context.close();
});


test('restoring a puzzle clears a previous preview retry', async ({page, browser}) => {
  const context=await browser.newContext(); const sender=await context.newPage();
  await sender.goto('/'); await expect(sender.locator('#generate')).toBeEnabled(); await sender.locator('#generate').click();
  await expect(sender.locator('#actions')).toBeVisible(); await sender.locator('#share-puzzle').click(); const url=await sender.locator('#puzzle-url').inputValue();
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.route('**/api/plan', route => route.fulfill({status:503}));
  await page.locator('#seed').fill('9'); await expect(page.locator('#retry-plan')).toBeVisible();
  await page.evaluate(hash => {location.hash=hash;}, new URL(url).hash);
  await page.locator('#load-shared-settings').click(); await expect(page.locator('#actions')).toBeVisible();
  await expect(page.locator('#retry-plan')).toBeHidden();
  await context.close();
});
