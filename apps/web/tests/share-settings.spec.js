import {test, expect} from '@playwright/test';

async function share(page) {
  await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#share-settings').click();
  return page.locator('#share-url').inputValue();
}
test('shared settings restore the same generation request', async ({page, browser}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('12');
  await page.locator('#hints input').last().uncheck();
  const url = await share(page);
  expect(url).toContain('#settings-v1=');
  const context = await browser.newContext(); const recipient = await context.newPage();
  await recipient.goto(url); await expect(recipient.locator('#share-status')).toContainText('読み込みました');
  await expect(recipient.locator('#generate')).toBeEnabled();
  const sent = recipient.waitForRequest(req => req.url().endsWith('/api/generate'));
  const response = recipient.waitForResponse('**/api/generate');
  await recipient.locator('#generate').click();
  const request = (await sent).postDataJSON();
  const payload = JSON.parse(Buffer.from(new URL(url).hash.slice('#settings-v1='.length), 'base64url').toString());
  expect(request).toEqual(payload);
  expect((await (await response).json()).status).toBe('ok');
  await context.close();
});
test('invalid, unknown, and oversized links fail without applying partial settings', async ({page}) => {
  await page.goto('/'); const url = await share(page);
  const payload = JSON.parse(Buffer.from(new URL(url).hash.slice('#settings-v1='.length), 'base64url').toString());
  for (const hash of ['#settings-v2=abc', '#settings-v1=' + 'a'.repeat(8192), '#settings-v1=' + Buffer.from(JSON.stringify({...payload, seed: 22, rules: [...payload.rules, {id:'unknown', parameters:{}}]})).toString('base64url')]) {
    const recipient = await page.context().newPage(); await recipient.goto('/' + hash);
    await expect(recipient.locator('#share-status')).toContainText('読み込めませんでした');
    await expect(recipient.locator('#seed')).toHaveValue('0');
    await expect(recipient.locator('#generate')).toBeEnabled(); await recipient.close();
  }
});
test('failed shared preview can be retried without reloading', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('7'); const url = await share(page);
  let failed = false;
  await page.route('**/api/plan', route => {
    if (!failed) {failed = true; return route.fulfill({status:503});}
    return route.continue();
  });
  const recipient = await page.context().newPage();
  await recipient.route('**/api/plan', route => {
    if (!failed) {failed = true; return route.fulfill({status:503});}
    return route.continue();
  });
  await recipient.goto(url); await expect(recipient.locator('#share-status')).toContainText('読み込めませんでした');
  await expect(recipient.locator('#generate')).toBeEnabled();
  await expect(recipient.locator('#seed')).toHaveValue('0');
  await recipient.locator('#load-shared-settings').click();
  await expect(recipient.locator('#share-status')).toContainText('読み込みました');
  await expect(recipient.locator('#seed')).toHaveValue('7');
  await expect(recipient.locator('#generate')).toBeEnabled(); await recipient.close();
});

test('room and number grids survive sharing in their declared rule order', async ({page, browser}) => {
  const catalogResponse = page.waitForResponse('**/api/catalog');
  await page.goto('/'); const catalog = await (await catalogResponse).json();
  await expect(page.locator('#generate')).toBeEnabled();
  const rules = catalog.profiles.find(p => p.id === 'shading').rules;
  const room = rules.findIndex(r => r.parameters.some(p => p.name === 'rooms'));
  const numbers = rules.findIndex(r => r.parameters.some(p => p.name === 'numbers'));
  await page.locator('#rules .rule-card').nth(room).locator('input[type=checkbox]').first().check();
  await page.locator('#rules .rule-card').nth(numbers).locator('input[type=checkbox]').first().check();
  await page.locator('textarea[data-kind=region-map]').fill('0 0 0\n1 1 1');
  await page.locator('textarea[data-kind=number-grid]:enabled').fill('1 2 3\n4 5 6');
  const url = await share(page);
  const context = await browser.newContext(); const other = await context.newPage();
  await other.goto(url); await expect(other.locator('#share-status')).toContainText('読み込みました');
  await expect(other.locator('textarea[data-kind=region-map]')).toHaveValue('0 0 0\n1 1 1');
  await expect(other.locator('textarea[data-kind=number-grid]:enabled')).toHaveValue('1 2 3\n4 5 6');
  await context.close();
});

test('changing settings clears the old share link', async ({page}) => {
  await page.goto('/'); await share(page);
  await page.locator('#seed').fill('9');
  await expect(page.locator('#share-url')).toHaveValue('');
});



test('history changes preserve work and clearly offer applying a new link', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('7'); const url = await share(page);
  await page.locator('#seed').fill('0'); await expect(page.locator('#generate')).toBeEnabled();
  const response = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await response).json()).status).toBe('ok');
  const cell = page.locator('.cell:enabled').first(); await cell.click(); const before = await cell.getAttribute('data-value');
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  await expect(page.locator('#navigation-status')).toContainText('まだ読み込まれていません');
  await expect(page.locator('#load-shared-settings')).toBeVisible();
  await expect(cell).toHaveAttribute('data-value', before);
  await page.goBack(); await expect(page.locator('#navigation-status')).toContainText('維持されています');
  await expect(cell).toHaveAttribute('data-value', before);
  await page.goForward(); await expect(page.locator('#load-shared-settings')).toBeVisible();
  await page.locator('#load-shared-settings').click();
  await expect(page.locator('#seed')).toHaveValue('7');
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(page.locator('#load-shared-settings')).toBeHidden();
});

test('invalid hash navigation and failed explicit load preserve the current puzzle', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  const response = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await response).json()).status).toBe('ok');
  const cell = page.locator('.cell:enabled').first(); await cell.click(); const before = await cell.getAttribute('data-value');
  await page.evaluate(() => {location.hash = '#settings-v1=invalid';});
  await page.locator('#load-shared-settings').click();
  await expect(page.locator('#share-status')).toContainText('読み込めませんでした');
  await expect(page.locator('#navigation-status')).toContainText('まだ読み込まれていません');
  await expect(cell).toHaveAttribute('data-value', before);
  await expect(page.locator('#actions')).toBeVisible();
});

test('loading a link cancels safely when the user edits the current board', async ({page}) => {
  await page.addInitScript(() => {
    const original = window.fetch; window.__planRequests = []; window.__planBodies = [];
    window.fetch = (...args) => {
      if (args[0] !== '/api/plan') return original(...args);
      const result = original(...args).then(response => {
        const readJson = response.json.bind(response);
        response.json = (...jsonArgs) => {const body = readJson(...jsonArgs); window.__planBodies.push(body); return body;};
        return response;
      });
      window.__planRequests.push(result); return result;
    };
  });
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('7'); const url = await share(page);
  await page.locator('#seed').fill('0'); await expect(page.locator('#generate')).toBeEnabled();
  const response = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await response).json()).status).toBe('ok');
  let release, started; const gate = new Promise(r => {release = r;}); const waiting = new Promise(r => {started = r;});
  await page.route('**/api/plan', async route => {started(); await gate; await route.continue();});
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  await page.locator('#load-shared-settings').click(); await waiting;
  const cell = page.locator('.cell:enabled').first(); await cell.click(); const before = await cell.getAttribute('data-value');
  const pending = page.waitForResponse('**/api/plan'); release(); await pending;
  await page.evaluate(async () => {
    for (let i = 0; i < 3; i++) {
      await Promise.allSettled([...window.__planRequests]); await Promise.allSettled([...window.__planBodies]);
      await new Promise(requestAnimationFrame);
    }
  });
  await expect(page.locator('#actions')).toBeVisible(); await expect(cell).toHaveAttribute('data-value', before);
  await expect(page.locator('#seed')).toHaveValue('0');
  await expect(page.locator('#navigation-status')).toContainText('中止');
});

test('shared URL excludes query parameters and tolerates object key order', async ({page}) => {
  const catalogResponse = page.waitForResponse('**/api/catalog'); await page.goto('/'); const catalog = await (await catalogResponse).json();
  await expect(page.locator('#generate')).toBeEnabled();
  const index = catalog.profiles.find(p => p.id === 'shading').rules.findIndex(r => r.identifier === 'room-black-count');
  await page.locator('#rules .rule-card').nth(index).locator('input[type=checkbox]').first().check();
  await page.locator('textarea[data-kind=region-map]').fill('0 0 0\n1 1 1');
  await page.evaluate(() => history.replaceState(null, '', '/?token=sentinel')); const url = await share(page);
  expect(new URL(url).search).toBe('');
  const request = JSON.parse(Buffer.from(new URL(url).hash.slice('#settings-v1='.length), 'base64url').toString());
  expect(request.rules.some(rule => Object.keys(rule.parameters).length > 1)).toBe(true);
  request.rules = request.rules.map(rule => ({parameters: Object.fromEntries(Object.entries(rule.parameters).reverse()), id:rule.id}));
  const reordered = Object.fromEntries(Object.entries(request).reverse());
  const recipient = await page.context().newPage(); await recipient.goto('/#settings-v1=' + Buffer.from(JSON.stringify(reordered)).toString('base64url'));
  await expect(recipient.locator('#share-status')).toContainText('読み込みました'); await recipient.close();
});

test('delayed clipboard completion warns when settings changed', async ({page}) => {
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', {value: {writeText: () => new Promise(resolve => {window.finishCopy = resolve;})}}));
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#share-settings').click(); await page.locator('#seed').fill('9');
  await page.evaluate(() => window.finishCopy()); await expect(page.locator('#share-status')).toContainText('設定変更前');
});

for (const family of ['slitherlink', 'coupled']) {
  test(`${family} settings restore and generate in another context`, async ({page, browser}) => {
    await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#family').selectOption(family);
    const url = await share(page); const context = await browser.newContext(); const recipient = await context.newPage();
    await recipient.goto(url); await expect(recipient.locator('#share-status')).toContainText('読み込みました');
    await expect(recipient.locator('#generate')).toBeEnabled();
    const response = recipient.waitForResponse('**/api/generate'); await recipient.locator('#generate').click();
    const result = await (await response).json(); expect(result.status).toBe('ok');
    const request = JSON.parse(Buffer.from(new URL(url).hash.slice('#settings-v1='.length), 'base64url').toString());
    expect(result.request).toEqual(request); await context.close();
  });
}

test('the latest hash wins while initial settings are loading', async ({page, browser}) => {
  await page.goto('/'); const first = await share(page); await page.locator('#seed').fill('7'); const second = await share(page);
  const context = await browser.newContext(); const recipient = await context.newPage();
  let release, started; const gate = new Promise(r => {release = r;}); const waiting = new Promise(r => {started = r;}); let firstPlan = true;
  await recipient.route('**/api/plan', async route => {if (firstPlan) {firstPlan = false; started(); await gate;} await route.continue();});
  await recipient.goto(first, {waitUntil:'domcontentloaded'}); await waiting;
  await recipient.evaluate(hash => {location.hash = hash;}, new URL(second).hash); release();
  await expect(recipient.locator('#share-status')).toContainText('読み込みました'); await expect(recipient.locator('#seed')).toHaveValue('7');
  await context.close();
});

test('sharing works when history writes are unavailable', async ({page}) => {
  await page.context().addInitScript(() => {history.replaceState = () => {throw new DOMException('blocked', 'SecurityError');};});
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  const url = await share(page); const recipient = await page.context().newPage(); await recipient.goto(url);
  await expect(recipient.locator('#share-status')).toContainText('読み込みました');
  await expect(recipient.locator('#generate')).toBeEnabled();
  await recipient.evaluate(() => {location.hash = '#invalid';});
  await expect(recipient.locator('#load-shared-settings')).toBeVisible();
  await recipient.evaluate(hash => new Promise(resolve => {
    window.addEventListener('hashchange', resolve, {once:true}); location.hash = hash;
  }), new URL(url).hash);
  await recipient.locator('#load-shared-settings').click();
  await expect(recipient.locator('#share-status')).toContainText('読み込みました');
  await expect(recipient.locator('#generate')).toBeEnabled(); await recipient.close();
});
