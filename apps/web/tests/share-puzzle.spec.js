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
