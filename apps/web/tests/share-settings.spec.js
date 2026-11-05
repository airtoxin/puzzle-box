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
    await page.goto('/' + hash);
    await expect(page.locator('#share-status')).toContainText('読み込めませんでした');
    await expect(page.locator('#seed')).toHaveValue('0');
    await expect(page.locator('#generate')).toBeEnabled();
  }
});
test('failed shared preview leaves defaults usable', async ({page}) => {
  await page.goto('/'); const url = await share(page);
  let failed = false;
  await page.route('**/api/plan', route => {
    if (!failed) {failed = true; return route.fulfill({status:503});}
    return route.continue();
  });
  await page.goto(url); await expect(page.locator('#share-status')).toContainText('読み込めませんでした');
  await expect(page.locator('#generate')).toBeEnabled();
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


test('history traversal restores the settings in each URL', async ({page}) => {
  await page.goto('/'); const first = await share(page);
  await page.locator('#seed').fill('7'); const second = await share(page);
  await page.goto(first); await expect(page.locator('#seed')).toHaveValue('0');
  await page.goto(second); await expect(page.locator('#seed')).toHaveValue('7');
  await page.goBack(); await expect(page.locator('#seed')).toHaveValue('0');
  await page.goForward(); await expect(page.locator('#seed')).toHaveValue('7');
});

test('invalid hash navigation preserves a generated puzzle and entered answer', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  const response = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await response).json()).status).toBe('ok');
  const cell = page.locator('.cell:enabled').first(); await cell.click();
  const before = await cell.getAttribute('data-value');
  await page.evaluate(() => {location.hash = '#settings-v1=invalid';});
  await expect(page.locator('#share-status')).toContainText('読み込めませんでした');
  await expect(page.locator('#actions')).toBeVisible();
  await expect(cell).toHaveAttribute('data-value', before);
  await page.evaluate(() => history.back());
  await expect(page.locator('#actions')).toBeVisible();
  await expect(cell).toHaveAttribute('data-value', before);
  await page.evaluate(() => history.forward());
  await expect(page.locator('#share-status')).toContainText('読み込めませんでした');
  await expect(cell).toHaveAttribute('data-value', before);
});

test('key order does not affect links, and unrelated query parameters are excluded', async ({page}) => {
  const catalogResponse = page.waitForResponse('**/api/catalog');
  await page.goto('/'); const catalog = await (await catalogResponse).json();
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
  await page.goto('/#settings-v1=' + Buffer.from(JSON.stringify(reordered)).toString('base64url'));
  await expect(page.locator('#share-status')).toContainText('読み込みました');
});

test('a delayed clipboard completion reports that an old link was copied', async ({page, context}) => {
  await context.grantPermissions(['clipboard-write']);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {value: {writeText: () => new Promise(resolve => {window.finishCopy = resolve;})}});
  });
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#share-settings').click();
  await page.locator('#seed').fill('9');
  await page.evaluate(() => window.finishCopy());
  await expect(page.locator('#share-status')).toContainText('設定変更前');
  await expect(page.locator('#share-url')).toHaveValue('');
});

for (const family of ['slitherlink', 'coupled']) {
  test(`${family} settings restore and generate in a separate browser context`, async ({page, browser}) => {
    await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
    await page.locator('#family').selectOption(family);
    const url = await share(page);
    const context = await browser.newContext(); const recipient = await context.newPage();
    await recipient.goto(url); await expect(recipient.locator('#share-status')).toContainText('読み込みました');
    await expect(recipient.locator('#family')).toHaveValue(family);
    await expect(recipient.locator('#generate')).toBeEnabled();
    const response = recipient.waitForResponse('**/api/generate'); await recipient.locator('#generate').click();
    const result = await (await response).json();
    expect(result.status).toBe('ok');
    const request = JSON.parse(Buffer.from(new URL(url).hash.slice('#settings-v1='.length), 'base64url').toString());
    expect(result.request).toEqual(request);
    await context.close();
  });
}

test('the latest hash wins while initial shared settings are loading', async ({page, browser}) => {
  await page.goto('/'); const first = await share(page);
  await page.locator('#seed').fill('7'); const second = await share(page);
  const context = await browser.newContext(); const recipient = await context.newPage();
  let release, started; const gate = new Promise(r => {release = r;});
  const waiting = new Promise(r => {started = r;}); let firstPlan = true;
  await recipient.route('**/api/plan', async route => {
    if (firstPlan) {firstPlan = false; started(); await gate;}
    await route.continue();
  });
  await recipient.goto(first, {waitUntil:'domcontentloaded'}); await waiting;
  await recipient.evaluate(hash => {location.hash = hash;}, new URL(second).hash);
  release();
  await expect(recipient.locator('#share-status')).toContainText('読み込みました');
  await expect(recipient.locator('#seed')).toHaveValue('7');
  await expect(recipient.locator('#generate')).toBeEnabled();
  await context.close();
});

for (const action of ['edit', 'check']) {
  test(`a delayed shared preview cannot erase a later board ${action}`, async ({page}) => {
    await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
    await page.locator('#seed').fill('7'); const url = await share(page);
    await page.locator('#seed').fill('0'); await expect(page.locator('#generate')).toBeEnabled();
    const response = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
    const result = await (await response).json(); expect(result.status).toBe('ok');
    if (action === 'check') {
      for (const [i, value] of result.record.solution.flat().entries()) {
        const cell = page.locator(`[data-cell-index="${i}"]`);
        if (await cell.isEnabled()) while (await cell.getAttribute('data-value') !== String(value)) await cell.click();
      }
    }
    let release, started; const gate = new Promise(r => {release = r;});
    const waiting = new Promise(r => {started = r;});
    await page.route('**/api/plan', async route => {started(); await gate; await route.continue();});
    await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash); await waiting;
    const cell = page.locator('.cell:enabled').first();
    if (action === 'edit') await cell.click();
    else { const checked = page.waitForResponse('**/api/check'); await page.locator('#check').click(); await checked; await expect(page.locator('#answer-status')).toContainText('正解'); }
    const before = await cell.getAttribute('data-value');
    release(); await expect(page.locator('#share-status')).toContainText('中止');
    await expect(page.locator('#actions')).toBeVisible(); await expect(cell).toHaveAttribute('data-value', before);
    await expect(page.locator('#seed')).toHaveValue('0');
  });
}

test('back to a hashless URL restores its previous settings', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('7'); const url = await share(page);
  await page.locator('#seed').fill('3'); await expect(page.locator('#generate')).toBeEnabled();
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  await expect(page.locator('#seed')).toHaveValue('7'); await expect(page.locator('#generate')).toBeEnabled();
  await page.goBack(); await expect(page.locator('#seed')).toHaveValue('3');
});

test('restoring another link clears an older displayed share URL', async ({page}) => {
  await page.goto('/'); const first = await share(page);
  await page.locator('#seed').fill('7'); const second = await share(page);
  await page.evaluate(hash => {location.hash = hash;}, new URL(first).hash);
  await expect(page.locator('#seed')).toHaveValue('0');
  await share(page); await expect(page.locator('#share-url')).not.toHaveValue('');
  await page.evaluate(hash => {location.hash = hash;}, new URL(second).hash);
  await expect(page.locator('#seed')).toHaveValue('7');
  await expect(page.locator('#share-url')).toHaveValue('');
});

for (const action of ['edit', 'generate']) {
  test(`a delayed shared preview reports cancellation after form ${action}`, async ({page}) => {
    await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
    await page.locator('#seed').fill('7'); const url = await share(page);
    await page.locator('#seed').fill('0'); await expect(page.locator('#generate')).toBeEnabled();
    let release, started; const gate = new Promise(r => {release = r;});
    const waiting = new Promise(r => {started = r;});
    await page.route('**/api/plan', async route => {
      if (route.request().postDataJSON().seed === 7) {started(); await gate;}
      await route.continue();
    });
    await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash); await waiting;
    if (action === 'edit') await page.locator('#seed').fill('3');
    else {const generated = page.waitForResponse('**/api/generate'); await page.locator('#generate').click(); await generated;}
    release(); await expect(page.locator('#share-status')).toContainText('中止');
    await expect(page.locator('#seed')).toHaveValue(action === 'edit' ? '3' : '0');
    if (action === 'generate') await expect(page.locator('#actions')).toBeVisible();
  });
}

test('a pending preview does not cancel a valid link navigation', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('7'); const url = await share(page);
  let release, started; const gate = new Promise(r => {release = r;});
  const waiting = new Promise(r => {started = r;});
  await page.route('**/api/plan', async route => {
    if (route.request().postDataJSON().seed === 7) {started(); await gate;}
    await route.continue();
  });
  const preview = page.waitForResponse(response => response.url().endsWith('/api/plan') && response.request().postDataJSON().seed === 3);
  await page.locator('#seed').fill('3');
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  await waiting; await preview; release();
  await expect(page.locator('#share-status')).toContainText('読み込みました');
  await expect(page.locator('#seed')).toHaveValue('7');
  await expect(page.locator('#generate')).toBeEnabled();
});

test('duplicate hashless history entries keep their own settings', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('1'); const first = await share(page);
  await page.locator('#seed').fill('2'); const second = await share(page);
  await page.locator('#seed').fill('0'); await expect(page.locator('#generate')).toBeEnabled();
  await page.evaluate(hash => {location.hash = hash;}, new URL(first).hash);
  await expect(page.locator('#seed')).toHaveValue('1'); await expect(page.locator('#generate')).toBeEnabled();
  await page.evaluate(() => {location.hash = '';}); await expect(page).toHaveURL(/\/#?$/);
  await page.locator('#seed').fill('3'); await expect(page.locator('#generate')).toBeEnabled();
  await page.evaluate(hash => {location.hash = hash;}, new URL(second).hash);
  await expect(page.locator('#seed')).toHaveValue('2'); await expect(page.locator('#generate')).toBeEnabled();
  await page.goBack(); await expect(page.locator('#seed')).toHaveValue('3'); await expect(page.locator('#generate')).toBeEnabled();
  await page.goBack(); await expect(page.locator('#seed')).toHaveValue('1'); await expect(page.locator('#generate')).toBeEnabled();
  await page.goBack(); await expect(page.locator('#seed')).toHaveValue('0');
});

test('sharing while a link is loading cancels the pending restore', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('7'); const url = await share(page);
  await page.locator('#seed').fill('0'); await expect(page.locator('#generate')).toBeEnabled();
  let release, started; const gate = new Promise(r => {release = r;});
  const waiting = new Promise(r => {started = r;});
  await page.route('**/api/plan', async route => {started(); await gate; await route.continue();});
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash); await waiting;
  await page.locator('#share-settings').click();
  await expect(page.locator('#share-status')).toContainText('中止');
  release(); await expect(page.locator('#seed')).toHaveValue('0');
  const shared = await page.locator('#share-url').inputValue();
  const request = JSON.parse(Buffer.from(new URL(shared).hash.slice('#settings-v1='.length), 'base64url').toString());
  expect(request.seed).toBe(0);
});

test('back restores outgoing edits while their preview was pending', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('7'); const url = await share(page);
  let release, started; const gate = new Promise(r => {release = r;});
  const waiting = new Promise(r => {started = r;});
  await page.route('**/api/plan', async route => {
    if (route.request().postDataJSON().seed === 3) {started(); await gate;}
    await route.continue();
  });
  await page.locator('#seed').fill('3'); await waiting;
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  await expect(page.locator('#seed')).toHaveValue('7');
  await expect(page.locator('#generate')).toBeEnabled();
  release(); await page.goBack();
  await expect(page.locator('#seed')).toHaveValue('3');
  await expect(page.locator('#generate')).toBeEnabled();
});

test('back restores the original entry after an edit cancels a pending link', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('7'); const url = await share(page);
  await page.locator('#seed').fill('0'); await expect(page.locator('#generate')).toBeEnabled();
  let release, started; const gate = new Promise(r => {release = r;});
  const waiting = new Promise(r => {started = r;});
  await page.route('**/api/plan', async route => {
    if (route.request().postDataJSON().seed === 7) {started(); await gate;}
    await route.continue();
  });
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash); await waiting;
  await page.locator('#seed').fill('3');
  await expect(page.locator('#share-status')).toContainText('中止');
  release(); await page.goBack();
  await expect(page.locator('#seed')).toHaveValue('0');
  await expect(page.locator('#generate')).toBeEnabled();
});

test('back after cancelling a link with a board edit preserves the puzzle and answer', async ({page}) => {
  await page.addInitScript(() => {
    const fetchOriginal = window.fetch; window.__planRequests = []; window.__planBodies = [];
    window.fetch = (...args) => {
      if (args[0] !== '/api/plan') return fetchOriginal(...args);
      const result = fetchOriginal(...args).then(response => {
        const readJson = response.json.bind(response);
        response.json = (...jsonArgs) => {
          const body = readJson(...jsonArgs); window.__planBodies.push(body); return body;
        };
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
  let release, started; const gate = new Promise(r => {release = r;});
  const waiting = new Promise(r => {started = r;});
  await page.route('**/api/plan', async route => {started(); await gate; await route.continue();});
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash); await waiting;
  const cell = page.locator('.cell:enabled').first(); await cell.click();
  const before = await cell.getAttribute('data-value');
  await expect(page.locator('#share-status')).toContainText('中止');
  const pendingResponse = page.waitForResponse(response => response.url().endsWith('/api/plan') && response.request().postDataJSON().seed === 7);
  release(); await pendingResponse;
  await page.evaluate(() => new Promise(resolve => {
    window.addEventListener('hashchange', resolve, {once:true}); history.back();
  }));
  await page.evaluate(async () => {
    // Include response bodies and any refresh triggered by applying a restored plan.
    for (let round = 0; round < 3; round++) {
      await Promise.allSettled([...window.__planRequests]);
      await Promise.allSettled([...window.__planBodies]);
      await new Promise(requestAnimationFrame);
    }
  });
  await expect(page.locator('#actions')).toBeVisible();
  await expect(cell).toHaveAttribute('data-value', before);
  await expect(page.locator('#seed')).toHaveValue('0');
});

test('distinct entries with the same URL restore their own settings', async ({page}) => {
  await page.goto('/#'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('1'); await expect(page.locator('#generate')).toBeEnabled();
  await page.evaluate(() => {location.hash = '#invalid';});
  await expect(page.locator('#share-status')).toContainText('読み込めませんでした');
  await page.evaluate(() => {location.hash = '';}); await expect(page).toHaveURL(/\/#$/);
  await page.locator('#seed').fill('2'); await expect(page.locator('#generate')).toBeEnabled();
  await page.goBack(); await expect(page).toHaveURL(/#invalid$/);
  await page.goBack(); await expect(page.locator('#seed')).toHaveValue('1');
});

test('family change is saved before its pending preview completes', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#seed').fill('7'); const url = await share(page);
  let release, started; const gate = new Promise(r => {release = r;});
  const waiting = new Promise(r => {started = r;});
  await page.route('**/api/plan', async route => {
    if (route.request().postDataJSON().family === 'slitherlink') {started(); await gate;}
    await route.continue();
  });
  await page.locator('#family').selectOption('slitherlink'); await waiting;
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  await expect(page.locator('#family')).toHaveValue('shading'); await expect(page.locator('#generate')).toBeEnabled();
  release(); await page.goBack();
  await expect(page.locator('#family')).toHaveValue('slitherlink');
  await expect(page.locator('#generate')).toBeEnabled();
});
