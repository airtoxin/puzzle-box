import {test, expect} from '@playwright/test';

for (const family of ['shading', 'slitherlink', 'coupled']) {
  test(`answer history is reversible and isolated for ${family}`, async ({page}) => {
    await page.goto('/');
    if (family !== 'shading') await page.locator('#family').selectOption(family);
    await expect(page.locator('#generate')).toBeEnabled();
    const response = page.waitForResponse('**/api/generate');
    await page.locator('#generate').click();
    expect((await (await response).json()).status).toBe('ok');
    const target = page.locator(family === 'slitherlink' ? '.edge:enabled' : '.cell:enabled').first();
    const selector = family === 'slitherlink' ? `[data-edge-index="${await target.getAttribute('data-edge-index')}"]` : `[data-cell-index="${await target.getAttribute('data-cell-index')}"]`;
    const undo = page.locator('#undo'), redo = page.locator('#redo');
    await expect(undo).toBeDisabled(); await expect(redo).toBeDisabled();
    await target.click(); await target.click();
    await expect(target).toHaveAttribute('data-value', '1');
    await undo.click(); await expect(page.locator(selector)).toHaveAttribute('data-value', '0');
    await undo.click(); await expect(page.locator(selector)).toHaveAttribute('data-value', '-1');
    await expect(undo).toBeDisabled();
    await redo.click(); await expect(page.locator(selector)).toHaveAttribute('data-value', '0');
    await page.locator(selector).click(); await expect(redo).toBeDisabled();
    await page.locator('#reveal').click(); await expect(undo).toBeDisabled();
    await page.locator('#reveal').click(); await expect(undo).toBeEnabled();
    await undo.click(); await expect(page.locator(selector)).toHaveAttribute('data-value', '0');
    if (family === 'coupled') {
      const edge = page.locator('.edge:enabled').first();
      const edgeSelector = `[data-edge-index="${await edge.getAttribute('data-edge-index')}"]`;
      await edge.click(); await expect(page.locator(edgeSelector)).toHaveAttribute('data-value', '0');
      await undo.click(); await expect(page.locator(edgeSelector)).toHaveAttribute('data-value', '-1');
      await expect(page.locator(selector)).toHaveAttribute('data-value', '0');
      await redo.click(); await expect(page.locator(edgeSelector)).toHaveAttribute('data-value', '0');
    }
    await page.locator('#seed').fill('1'); await expect(page.locator('#actions')).toBeHidden();
    await expect(undo).toBeDisabled(); await expect(redo).toBeDisabled();
  });
}

test('history retains only the latest 1000 edits', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  const cell = page.locator('.cell:enabled').first();
  const selector = `[data-cell-index="${await cell.getAttribute('data-cell-index')}"]`;
  // Native click events exercise the same handlers, without 2001 round trips.
  await cell.evaluate(el => {for (let i = 0; i < 1001; i++) el.click();});
  await expect(page.locator(selector)).toHaveAttribute('data-value', '1');
  await page.locator('#undo').evaluate(el => {for (let i = 0; i < 1000; i++) el.click();});
  await expect(page.locator(selector)).toHaveAttribute('data-value', '0');
  await expect(page.locator('#undo')).toBeDisabled();
  await page.locator('#redo').evaluate(el => {for (let i = 0; i < 1000; i++) el.click();});
  await expect(page.locator(selector)).toHaveAttribute('data-value', '1');
  await expect(page.locator('#redo')).toBeDisabled();
});

test('fixed clues cannot enter history and buttons work with keyboard', async ({page}) => {
  await page.goto('/'); await page.locator('#family').selectOption('coupled');
  await expect(page.locator('#generate')).toBeEnabled(); await page.locator('#generate').click();
  await expect(page.locator('#actions')).toBeVisible();
  const fixed = page.locator('.cell.fixed').first(); await expect(fixed).toBeDisabled();
  const given = await fixed.getAttribute('data-value');
  await fixed.evaluate(el => el.click()); await expect(page.locator('#undo')).toBeDisabled();
  const cell = page.locator('.cell:enabled').first(); await cell.click();
  await page.locator('#undo').focus(); await page.keyboard.press('Space');
  await expect(cell).toHaveAttribute('data-value', '-1');
  await page.locator('#redo').focus(); await page.keyboard.press('Enter');
  await expect(cell).toHaveAttribute('data-value', '0');
  await expect(fixed).toHaveAttribute('data-value', given);
});

test('generation and shared puzzle restoration reset history', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  await page.locator('#share-puzzle').click(); const url = await page.locator('#puzzle-url').inputValue();
  await page.locator('.cell:enabled').first().click(); await expect(page.locator('#undo')).toBeEnabled();
  await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
  await expect(page.locator('#undo')).toBeDisabled(); await expect(page.locator('#redo')).toBeDisabled();
  await page.locator('.cell:enabled').first().click();
  await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
  await page.locator('#load-shared-settings').click();
  await expect(page.locator('#share-status')).toContainText('共有された問題を読み込みました');
  await expect(page.locator('#undo')).toBeDisabled(); await expect(page.locator('#redo')).toBeDisabled();
});

for (const action of ['undo', 'redo']) {
  test(`${action} cancels an in-flight shared puzzle restore`, async ({page}) => {
    await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
    await page.locator('#generate').click(); await expect(page.locator('#actions')).toBeVisible();
    await page.locator('#share-puzzle').click(); const url = await page.locator('#puzzle-url').inputValue();
    const cell = page.locator('.cell:enabled').first();
    const selector = `[data-cell-index="${await cell.getAttribute('data-cell-index')}"]`;
    await cell.click(); if (action === 'redo') await page.locator('#undo').click();
    let release, started; const gate = new Promise(r => {release = r;}); const waiting = new Promise(r => {started = r;});
    await page.route('**/api/restore', async route => {started(); await gate; await route.continue();});
    await page.evaluate(hash => {location.hash = hash;}, new URL(url).hash);
    const response = page.waitForResponse('**/api/restore');
    await page.locator('#load-shared-settings').click(); await waiting;
    await page.locator(`#${action}`).click();
    const value = action === 'undo' ? '-1' : '0';
    await expect(page.locator(selector)).toHaveAttribute('data-value', value);
    release(); await response;
    await expect(page.locator('#navigation-status')).toContainText('中止');
    await expect(page.locator(selector)).toHaveAttribute('data-value', value);
  });
}
