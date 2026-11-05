import {test, expect} from '@playwright/test';

async function expectContainedPage(page) {
  const sizes = await page.evaluate(() => ({viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth}));
  expect(sizes.document).toBeLessThanOrEqual(sizes.viewport);
  const form = await page.locator('#recipe-form').boundingBox();
  expect(form.x).toBeGreaterThanOrEqual(0);
  expect(form.x + form.width).toBeLessThanOrEqual(sizes.viewport + 1);
}

for (const input of ['mouse', 'touch']) test.describe(`${input} on a partly covered cell`, () => {
  test.use({hasTouch:true});
  test('a tap changes the intended cell exactly once', async ({page}) => {
    const side = 8;
    await page.setViewportSize({width:390, height:844});
    await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
    await page.locator('#rows').fill('8'); await page.locator('#cols').fill('8');
    await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
    await page.getByLabel('黒マス数', {exact:true}).fill('0');
    await expect(page.locator('#generate')).toBeEnabled();
    const response = page.waitForResponse('**/api/generate');
    await page.locator('#generate').click();
    const generated = await (await response).json();
    expect(generated.status).toBe('ok'); expect(generated.clues).toEqual([]);
    const cells = page.locator('#board .cell');
    const index = 1, target = page.locator(`[data-cell-index="${index}"]`);
    await expect(target).toBeEnabled();
    const board = page.locator('#board');
    await board.focus(); await page.keyboard.press('Tab');
    await target.scrollIntoViewIfNeeded();
    const clue = page.locator('#board th[scope="row"]').nth(Math.floor(index / side));
    const [targetBox, clueBox] = await Promise.all([target.boundingBox(), clue.boundingBox()]);
    await board.evaluate((el, shift) => {el.scrollLeft += shift;}, targetBox.x - clueBox.x - clueBox.width + 10);
    const [partial, pinned] = await Promise.all([target.boundingBox(), clue.boundingBox()]);
    expect(partial.x).toBeLessThan(pinned.x + pinned.width);
    expect(partial.x + partial.width).toBeGreaterThan(pinned.x + pinned.width + 8);
    const x = pinned.x + pinned.width + 5, y = partial.y + partial.height / 2;
    expect(await page.evaluate(({x,y}) => document.elementFromPoint(x,y)?.getAttribute('data-cell-index'), {x,y})).toBe(String(index));
    const before = await cells.evaluateAll(items => items.map(el => el.getAttribute('data-value')));
    if (input === 'touch') await page.touchscreen.tap(x,y); else await page.mouse.click(x,y);
    const after = await cells.evaluateAll(items => items.map(el => el.getAttribute('data-value')));
    const expected = [...before]; expected[index] = '0';
    expect(after).toEqual(expected);
  });
});

async function expectBothBoardEndsReachable(page, targets) {
  const board = page.locator('#board');
  const viewport = await board.boundingBox();
  await board.evaluate(el => {el.scrollLeft = 0;});
  const first = await targets.first().boundingBox();
  expect(first.x).toBeGreaterThanOrEqual(viewport.x - 1);
  await board.evaluate(el => {el.scrollLeft = el.scrollWidth;});
  const last = await targets.last().boundingBox();
  expect(last.x + last.width).toBeLessThanOrEqual(viewport.x + viewport.width + 1);
}

for (const width of [320, 390, 760, 800, 1280]) {
  test(`board families stay contained at ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height: 844});
    await page.goto('/');
    await expect(page.locator('#generate')).toBeEnabled();
    for (const side of [8, 10]) {
      await page.locator('#rows').fill(String(side));
      await page.locator('#cols').fill(String(side));
      await expect(page.locator('#generate')).toBeEnabled();
      await expect(page.locator('#board .cell')).toHaveCount(side * side);
      await expectContainedPage(page);
      await expectBothBoardEndsReachable(page, page.locator('#board .cell'));
      if (side === 10 && width <= 390) {
        const scroll = await page.locator('#board').evaluate(el => ({left: el.scrollLeft, max: el.scrollWidth-el.clientWidth}));
        expect(scroll.max).toBeGreaterThan(0);
        expect(scroll.left).toBeGreaterThan(0);
      }
      const board = await page.locator('#board').boundingBox();
      const rowClue = page.locator('#board th[scope="row"]').first();
      const rowBox = await rowClue.boundingBox();
      expect(rowBox.x).toBeGreaterThanOrEqual(board.x - 1);
      expect(rowBox.x + rowBox.width).toBeLessThanOrEqual(board.x + board.width + 1);
      await expect(rowClue).toHaveAccessibleName(/1/);
      if (side === 10 && width === 390) {
        await page.locator('.result').screenshot({path:test.info().outputPath('shading-390-right.png')});
      }
      const cell = await page.locator('#board .cell').first().boundingBox();
      expect(cell.width).toBeGreaterThanOrEqual(34);
      expect(cell.height).toBeGreaterThanOrEqual(34);
      await expect(page.locator('#board .cell').first()).toHaveAccessibleName(/1/);
      if (side === 10 && (width === 390 || width === 1280)) {
        await page.locator('#board').evaluate(el => {el.scrollLeft = 0;});
        await page.locator('.result').screenshot({path:test.info().outputPath(`shading-${width}.png`)});
      }
    }
    for (const [family, cells, edges] of [['slitherlink', 0, 12], ['coupled', 9, 12]]) {
      await page.locator('#family').selectOption(family);
      await expect(page.locator('#generate')).toBeEnabled();
      await expect(page.locator('#board .cell')).toHaveCount(cells);
      await expect(page.locator('#board .edge')).toHaveCount(edges);
      await expectContainedPage(page);
      await expectBothBoardEndsReachable(page, page.locator('#board .edge.horizontal'));
      await expect(page.locator('#board .edge').first()).toHaveAccessibleName(/1/);
      if (width === 390 || width === 1280) {
        await page.locator('.result').screenshot({path:test.info().outputPath(`${family}-${width}.png`)});
      }
    }
  });
}

for (const [side, width] of [[8,390], [10,320]]) {
test(`a ${side}x${side} generated board remains scrollable and operable at ${width}px`, async ({page}) => {
  await page.setViewportSize({width, height:844});
  await page.goto('/');
  await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#rows').fill(String(side)); await page.locator('#cols').fill(String(side));
  await page.getByLabel('白マスをつなぐ', {exact:true}).uncheck();
  // A zero-black count uniquely determines the board without fixed cells,
  // making the navigation path independent of solver-selected hints.
  await page.getByLabel('黒マス数', {exact:true}).fill('0');
  await expect(page.locator('#generate')).toBeEnabled();
  const response = page.waitForResponse('**/api/generate');
  await page.locator('#generate').click();
  const generated = await (await response).json();
  expect(generated.status).toBe('ok'); expect(generated.clues).toEqual([]);
  await expect(page.locator('#actions')).toBeVisible();
  await expectContainedPage(page);
  const board = page.locator('#board');
  await expect(page.getByRole('region', {name:'パズル盤面'})).toHaveAttribute('tabindex', '0');
  await board.evaluate(el => {el.scrollLeft = 0;});
  await board.focus(); await page.keyboard.press('ArrowRight');
  await expect.poll(() => board.evaluate(el => el.scrollLeft)).toBeGreaterThan(0);
  const cells = page.locator('#board .cell:enabled');
  await expect(cells).toHaveCount(side * side);
  await expectBothBoardEndsReachable(page, cells);
  const last = cells.last();
  await last.click(); await expect(last).toHaveAttribute('data-value', '0');
  await last.focus(); await page.keyboard.press('Enter');
  await expect(last).toHaveAttribute('data-value', '1');
  await expect(last).toBeFocused();
  // Tabbing must not leave a focused cell behind the sticky row clue.
  async function expectFocusedCellVisible() {
    const focused = page.locator('#board .cell:focus');
    await expect(focused).toHaveCount(1);
    const index = Number(await focused.getAttribute('data-cell-index'));
    const clue = page.locator('#board th[scope="row"]').nth(Math.floor(index / side));
    const [cellBox, clueBox, boardBox] = await Promise.all([focused.boundingBox(), clue.boundingBox(), board.boundingBox()]);
    expect(cellBox.x).toBeGreaterThanOrEqual(clueBox.x + clueBox.width + 2);
    expect(cellBox.x + cellBox.width).toBeLessThanOrEqual(boardBox.x + boardBox.width + 1);
  }
  const steps = Math.min(side, (await cells.count()) - 1);
  for (const key of ['Shift+Tab', 'Tab']) for (let i = 0; i < steps; i++) {
    await page.keyboard.press(key);
    await expectFocusedCellVisible();
  }
  await expectContainedPage(page);
});
}
