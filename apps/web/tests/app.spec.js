import {test, expect} from '@playwright/test';

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
  await cell.focus();
  await page.keyboard.press('Space');
  await expect(cell).toHaveAttribute('data-value', '0');
  await expect.soft(cell).toBeFocused();
  // Re-focus even before the fix so the hover regression is independently exercised.
  await cell.focus();
  await page.keyboard.press('Enter');
  await expect(cell).toHaveAttribute('data-value', '1');
  await expect.soft(cell).toBeFocused();
  await cell.hover();
  await expect.soft(cell).toHaveCSS('background-color', 'rgb(33, 60, 51)');
  await expect(cell).toHaveCSS('color', 'rgb(255, 255, 255)');
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
