import {test, expect} from '@playwright/test';

for (const operation of ['generate', 'check']) for (const stage of ['headers', 'body']) {
  test(`stalled ${operation} ${stage} unlocks the UI without a verdict`, async ({page}) => {
    await page.addInitScript(() => {
      const originalFetch = window.fetch;
      window.fetch = (path, options) => {
        if (path !== `/api/${window.__stallOperation}`) return originalFetch(path, options);
        window.__jobStarted = true;
        const abort = () => {window.__jobAborted = true;};
        options.signal.addEventListener('abort', abort, {once: true});
        if (window.__stallStage === 'headers') return new Promise((resolve, reject) => {
          options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), {once: true});
        });
        const body = new ReadableStream({start(controller) {
          options.signal.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')), {once: true});
        }});
        return Promise.resolve(new Response(body, {status: 200}));
      };
    });
    await page.goto('/');
    await expect(page.locator('#generate')).toBeEnabled();
    if (operation === 'generate') {
      await page.locator('#budget').fill('3');
      await expect(page.locator('#generate')).toBeEnabled();
    }
    if (operation === 'check') {
      const generated = page.waitForResponse('**/api/generate');
      await page.locator('#generate').click();
      const result = await (await generated).json();
      expect(result.status).toBe('ok');
      for (const [index, bit] of result.record.solution.flat().entries()) {
        const cell = page.locator('#board .cell').nth(index);
        if (await cell.isEnabled()) {await cell.click(); if (bit) await cell.click();}
      }
    }
    const budget = Number(await page.locator('#budget').inputValue());
    await page.clock.install();
    await page.evaluate(({operation, stage}) => {window.__stallOperation = operation; window.__stallStage = stage;}, {operation, stage});
    await page.locator(operation === 'generate' ? '#generate' : '#check').click();
    await page.waitForFunction(() => window.__jobStarted);
    // The timer starts just before the mocked fetch; leave room for the few
    // milliseconds spent observing that the request has started.
    await page.clock.fastForward((budget + 15) * 1000 - 1000);
    expect(await page.evaluate(() => window.__jobAborted === true)).toBe(false);
    await page.clock.fastForward(1001);
    await expect.poll(() => page.evaluate(() => window.__jobAborted)).toBe(true);
    const status = page.locator(operation === 'generate' ? '#status' : '#answer-status');
    await expect(status).toContainText('未確認');
    await expect(status).not.toContainText('正解です');
    await expect(status).not.toContainText('正解ではありません');
    await expect(page.locator('#recipe-form')).not.toHaveAttribute('inert', '');
    if (operation === 'generate') {
      await expect(page.locator('#actions')).toBeHidden();
      await expect(page.locator('#generate')).toBeEnabled();
    } else {
      await expect(page.locator('#board')).not.toHaveAttribute('inert', '');
      await expect(page.locator('#actions')).toBeVisible();
      await expect(page.locator('#check')).toBeEnabled();
    }
    await page.evaluate(() => {window.__stallOperation = null;});
    if (operation === 'generate') {
      await page.locator('#budget').fill('10');
      await page.clock.fastForward(121);
      await expect(page.locator('#generate')).toBeEnabled();
    }
    await page.locator(operation === 'generate' ? '#generate' : '#check').click();
    if (operation === 'generate') await expect(page.locator('#actions')).toBeVisible();
    else await expect(page.locator('#answer-status')).toContainText('正解です');
  });
}
