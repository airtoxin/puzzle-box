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
