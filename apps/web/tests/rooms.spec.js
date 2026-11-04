import {test, expect} from '@playwright/test';

async function configure(page) {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マスの個数', {exact: true}).uncheck();
  await page.getByLabel('白マスをつなぐ', {exact: true}).uncheck();
  await page.getByLabel('各部屋の黒数を固定', {exact: true}).check();
  await page.getByLabel('黒マスを2個ずつにする', {exact: true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）', {exact: true}).fill('0 0 0\n1 1 1');
  await expect(page.locator('#generate')).toBeEnabled();
}

test('one declared room editor renders boundaries and keeps rules through answer checking', async ({page}) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await configure(page);
  await expect(page.locator('#rules textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('.room-board [data-room="0"]')).toHaveCount(3);
  await expect(page.locator('.room-board [data-room="1"]')).toHaveCount(3);
  await expect(page.locator('.room-board [data-room="0"].room-bottom')).toHaveCount(3);
  await expect(page.getByRole('button', {name: /^1行1列:.*部屋1/})).toBeDisabled();
  const response = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  const result = await (await response).json();
  expect(result.status).toBe('ok'); expect(result.clues).toEqual([]);
  expect(result.record.rules.find(r => r.type === 'room-black-count').rooms).toEqual([[0,0,0],[1,1,1]]);
  for (let r = 0; r < 2; r++) for (let c = 0; c < 3; c++) {
    const cell = page.locator(`[data-cell-index="${r*3+c}"]`);
    while (await cell.getAttribute('data-value') !== String(result.record.solution[r][c])) await cell.click();
  }
  const checked = page.waitForResponse('**/api/check'); await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok', correct:true});
  const download = page.waitForEvent('download'); await page.locator('#download').click();
  const stream = await (await download).createReadStream(), chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  expect(JSON.parse(Buffer.concat(chunks).toString('utf8'))).toEqual(result.record);
  await page.getByLabel('各部屋内で黒をつなぐ', {exact: true}).check();
  await expect(page.locator('#rules textarea[data-kind="region-map"]')).toHaveCount(1);
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict = page.waitForResponse('**/api/generate'); await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');
  await page.getByLabel('各部屋の黒数を固定', {exact: true}).uncheck();
  await expect(page.locator('#rules textarea[data-kind="region-map"]')).toBeEnabled();
  await page.locator('#rules textarea[data-kind="region-map"]').fill('0 x 0\n1 1 1');
  await expect(page.locator('#status')).toContainText('整数を空白');
  await expect(page.locator('#generate')).toBeDisabled();
  await page.locator('#rules textarea[data-kind="region-map"]').fill('0 1 0\n0 1 0');
  await expect(page.locator('#status')).toContainText('orthogonally connected');
  await page.locator('#rules textarea[data-kind="region-map"]').fill('0 0 0\n1 1 1');
  await expect(page.locator('#generate')).toBeEnabled();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:test.info().outputPath('rooms-mobile.png'),fullPage:true});
  expect(errors).toEqual([]);
});

for (const geometry of ['missing', 'different']) test(`${geometry} room geometry cannot be silently displayed`, async ({page}) => {
  await configure(page);
  await page.route('**/api/plan', async route => {
    const response = await route.fetch(), data = await response.json();
    if (data.status === 'ok') {
      if (geometry === 'missing') delete data.plan.rooms;
      else data.plan.rooms = [[0,0,1],[0,1,1]];
    }
    await route.fulfill({json:data});
  });
  await page.locator('#seed').fill('1');
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled();
  await expect(page.locator('.cell')).toHaveCount(0);
  await page.unroute('**/api/plan'); await page.locator('#seed').fill('2');
  await expect(page.locator('#generate')).toBeEnabled();
});
