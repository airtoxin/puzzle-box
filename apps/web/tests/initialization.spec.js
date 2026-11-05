import {test, expect} from '@playwright/test';

test('catalog loading prevents edits until defaults and controls are ready', async ({page}) => {
  let releaseCatalog;
  const blocked = new Promise(resolve => {releaseCatalog = resolve;});
  let catalogStarted;
  const started = new Promise(resolve => {catalogStarted = resolve;});
  await page.route('**/api/catalog', async route => {
    catalogStarted(); await blocked; await route.continue();
  });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/', {waitUntil: 'domcontentloaded'}); await started;
  await expect(page.locator('#recipe-form')).toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('#rows')).toBeDisabled();
  await expect(page.locator('#cols')).toBeDisabled();
  await expect(page.locator('#family')).toBeDisabled();
  await expect(page.locator('#status')).toContainText('ルールを読み込んでいます');
  releaseCatalog();
  await expect(page.locator('#rows')).toBeEnabled();
  await expect(page.locator('#recipe-form')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#rows').fill('5'); await page.locator('#cols').fill('5');
  await expect(page.locator('#board .cell')).toHaveCount(25);
  await expect(page.locator('#rows')).toHaveValue('5');
  await expect(page.locator('#cols')).toHaveValue('5');
  expect(errors).toEqual([]);
});

test('catalog failures stay locked and can be retried until controls work', async ({page}) => {
  let attempts = 0;
  await page.route('**/api/catalog', async route => {
    if (++attempts < 3) return route.fulfill({status:503, body:'unavailable'});
    return route.continue();
  });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  const retry = page.locator('#retry-catalog');
  await expect(retry).toBeVisible();
  await expect(page.locator('#rows')).toBeDisabled();
  await expect(page.locator('#status')).toContainText('ルールを読み込めません');
  await retry.click();
  await expect(retry).toBeVisible();
  await expect(page.locator('#rows')).toBeDisabled();
  await retry.click();
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(retry).toBeHidden();
  await expect(page.locator('#rows')).toBeEnabled();
  await page.locator('#rows').fill('3');
  await expect(page.locator('#board .cell')).toHaveCount(9);
  expect(attempts).toBe(3); expect(errors).toEqual([]);
});

test('failed preview can be retried without losing edited settings', async ({page}) => {
  let failPlan = false;
  await page.route('**/api/plan', async route => {
    if (failPlan) return route.fulfill({status:503, body:'unavailable'});
    return route.continue();
  });
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  failPlan = true;
  await page.locator('#rows').fill('4');
  const retry = page.locator('#retry-plan'); await expect(retry).toBeVisible();
  await expect(page.locator('#rows')).toHaveValue('4');
  await expect(page.locator('#board')).toBeEmpty();
  await expect(page.locator('#generate')).toBeDisabled();
  failPlan = false;
  await retry.click();
  await expect(retry).toBeHidden();
  await expect(page.locator('#board .cell')).toHaveCount(12);
  await expect(page.locator('#rows')).toHaveValue('4');
  await expect(page.locator('#generate')).toBeEnabled();
});

for (const status of [408, 429]) {
  test(`transient HTTP ${status} preview failure offers retry`, async ({page}) => {
    let transient = false;
    await page.route('**/api/plan', route => transient
      ? route.fulfill({status, json: {status: 'error'}}) : route.continue());
    await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
    transient = true; await page.locator('#rows').fill('4');
    await expect(page.locator('#retry-plan')).toBeVisible();
    await expect(page.locator('#rows')).toHaveValue('4');
    transient = false; await page.locator('#retry-plan').click();
    await expect(page.locator('#board .cell')).toHaveCount(12);
    await expect(page.locator('#generate')).toBeEnabled();
  });
}

test('a delayed preview cannot replace a newer configuration', async ({page}) => {
  let releaseSlow, slowStarted;
  const gate = new Promise(resolve => {releaseSlow = resolve;});
  const started = new Promise(resolve => {slowStarted = resolve;});
  await page.route('**/api/plan', async route => {
    if (route.request().postDataJSON().rows === 4) {
      const response = await route.fetch(); slowStarted(); await gate;
      await route.fulfill({response});
    } else await route.continue();
  });
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#rows').fill('4'); await started;
  await page.locator('#rows').fill('5');
  await expect(page.locator('#board .cell')).toHaveCount(15);
  const oldResponse = page.waitForResponse(response => response.url().endsWith('/api/plan')
    && response.request().postDataJSON().rows === 4);
  releaseSlow(); await oldResponse;
  await page.evaluate(() => new Promise(requestAnimationFrame));
  await expect(page.locator('#board .cell')).toHaveCount(15);
  await expect(page.locator('#rows')).toHaveValue('5');
  await expect(page.locator('#generate')).toBeEnabled();
});

for (const operation of ['catalog', 'plan']) {
  test(`a stalled ${operation} request times out and can be retried`, async ({page}) => {
    await page.clock.install();
    let release, markStarted, stall = true;
    const gate = new Promise(resolve => {release = resolve;});
    const started = new Promise(resolve => {markStarted = resolve;});
    await page.route(`**/api/${operation}`, async route => {
      if (stall) {markStarted(); await gate;}
      try {await route.continue();} catch {} // The browser may have aborted the stalled request.
    });
    if (operation === 'plan') {
      stall = false; await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
      stall = true; await page.locator('#rows').fill('4'); await page.clock.fastForward(121);
    } else await page.goto('/', {waitUntil: 'domcontentloaded'});
    await started; await page.clock.fastForward(15001);
    const retry = page.locator(`#retry-${operation}`);
    await expect(retry).toBeVisible();
    if (operation === 'catalog') await expect(page.locator('#rows')).toBeDisabled();
    else await expect(page.locator('#rows')).toHaveValue('4');
    stall = false; release(); await retry.click();
    await expect(page.locator('#generate')).toBeEnabled();
    await expect(page.locator('#board .cell')).toHaveCount(operation === 'catalog' ? 6 : 12);
  });
}

test('invalid plan input remains an input error rather than a retry prompt', async ({page}) => {
  let invalid = false;
  await page.route('**/api/plan', route => invalid
    ? route.fulfill({status:400, json: {status: 'invalid', message: 'invalid test setting'}}) : route.continue());
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  invalid = true; await page.locator('#rows').fill('4');
  await expect(page.locator('#status')).toContainText('invalid test setting');
  await expect(page.locator('#retry-plan')).toBeHidden();
  await expect(page.locator('#generate')).toBeDisabled();
});

test('a preview response with a stalled JSON body times out', async ({page}) => {
  await page.clock.install();
  await page.addInitScript(() => {
    const originalFetch = window.fetch;
    window.fetch = (path, options) => {
      if (path !== '/api/plan' || !window.__stallPlanBody) return originalFetch(path, options);
      window.__planBodyStarted = true;
      const body = new ReadableStream({start(controller) {
        options.signal.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')));
      }});
      return Promise.resolve(new Response(body, {status: 200}));
    };
  });
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.evaluate(() => {window.__stallPlanBody = true;});
  await page.locator('#rows').fill('4'); await page.clock.fastForward(121);
  await page.waitForFunction(() => window.__planBodyStarted);
  await page.clock.fastForward(15001);
  await expect(page.locator('#retry-plan')).toBeVisible();
  await expect(page.locator('#rows')).toHaveValue('4');
  await page.evaluate(() => {window.__stallPlanBody = false;});
  await page.locator('#retry-plan').click();
  await expect(page.locator('#board .cell')).toHaveCount(12);
  await expect(page.locator('#generate')).toBeEnabled();
});

for (const operation of ['catalog', 'plan']) {
  test(`a rejected ${operation} response aborts its unread body`, async ({page}) => {
    await page.addInitScript(() => {
      const originalFetch = window.fetch;
      window.fetch = (path, options) => {
        if (path !== window.__rejectOperation || !window.__rejectEnabled) return originalFetch(path, options);
        const body = new ReadableStream({start(controller) {
          options.signal.addEventListener('abort', () => {
            window.__rejectedBodyAborted = true;
            controller.error(new DOMException('Aborted', 'AbortError'));
          });
        }});
        return Promise.resolve(new Response(body, {status: path === '/api/catalog' ? 503 : 429}));
      };
    });
    if (operation === 'catalog') {
      await page.addInitScript(() => {window.__rejectOperation = '/api/catalog'; window.__rejectEnabled = true;});
    }
    await page.goto('/');
    if (operation === 'plan') {
      await expect(page.locator('#generate')).toBeEnabled();
      await page.evaluate(() => {window.__rejectOperation = '/api/plan'; window.__rejectEnabled = true;});
      await page.locator('#rows').fill('4');
    }
    const retry = page.locator(`#retry-${operation}`);
    await expect(retry).toBeVisible();
    await expect.poll(() => page.evaluate(() => window.__rejectedBodyAborted === true)).toBe(true);
    await page.evaluate(() => {window.__rejectEnabled = false;});
    await retry.click(); await expect(page.locator('#generate')).toBeEnabled();
  });
}
