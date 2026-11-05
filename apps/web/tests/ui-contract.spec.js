import {test, expect} from '@playwright/test';
import {assertRenderablePlan, UnsupportedUiError} from '../plan-contract.js';

test('unselected clues do not require channels, and unknown clue kinds are rejected', () => {
  const request = {family: 'shading', rows: 2, cols: 2, rules: [], clue_kinds: []};
  const plan = {format: 'puzzle-box/web-plan-v2', family: 'shading', rows: 2, cols: 2,
    requirements: {topology: 'rectangular-cells', max_cells: 100, min_rows: 1, min_cols: 1,
      channels: [{name: 'answer', kind: 'binary-cells'}]}};
  expect(() => assertRenderablePlan(plan, request)).not.toThrow();
  expect(() => assertRenderablePlan(plan, {...request, clue_kinds: ['future-hint']})).toThrow(UnsupportedUiError);
});

test('unsupported coupled UI declarations stop preview and generation', async ({page}) => {
  const changes = [
    plan => {plan.requirements.topology = 'unknown-grid';},
    plan => {plan.requirements.channels.push({name: 'regions', kind: 'region-colors'});},
    plan => {plan.requirements.channels.find(c => c.name === 'answer-cells').kind = 'integer-cells';},
    plan => {plan.requirements.channels = plan.requirements.channels.filter(c => c.name !== 'answer-edges');},
    plan => {plan.requirements.channels.push({...plan.requirements.channels[0]});},
    plan => {plan.requirements.max_cells = 0;},
    plan => {plan.requirements.min_rows = true;},
    plan => {plan.requirements.min_rows = 4;},
    plan => {plan.requirements.channels = null;},
    plan => {plan.rows = 2;},
    plan => {plan.family = 'slitherlink';},
    plan => {plan.format = 'puzzle-box/web-plan-v999';},
  ];
  let change = changes[0], generationRequests = 0;
  page.on('request', request => {if (request.url().endsWith('/api/generate')) generationRequests++;});
  await page.route('**/api/plan', async route => {
    const response = await route.fetch();
    const result = await response.json();
    if (route.request().postDataJSON().family === 'coupled') change(result.plan);
    await route.fulfill({json: result});
  });
  for (change of changes) {
    await page.goto('/');
    await page.locator('#family').selectOption('coupled');
    await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
    await expect(page.locator('#generate')).toBeDisabled();
    await expect(page.locator('#board')).toBeEmpty();
    await expect(page.locator('#actions')).toBeHidden();
  }
  expect(generationRequests).toBe(0);
  await page.unroute('**/api/plan');
  await page.locator('#family').selectOption('slitherlink');
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(page.locator('.edge')).toHaveCount(12);
});

test('known UI combinations accept channel reordering and wider advertised limits', async ({page}) => {
  await page.route('**/api/plan', async route => {
    const response = await route.fetch(), result = await response.json();
    result.plan.requirements.channels.reverse();
    // A newer server's broader capacity need not exclude an already-supported
    // small board. The client still caps actual dimensions at its own limit.
    result.plan.requirements.max_cells = 36;
    await route.fulfill({json: result});
  });
  await page.goto('/');
  for (const [family, cells, edges] of [['shading', 6, 0], ['slitherlink', 0, 12], ['coupled', 9, 12]]) {
    await page.locator('#family').selectOption(family);
    await expect(page.locator('#generate')).toBeEnabled();
    await expect(page.locator('.cell')).toHaveCount(cells);
    await expect(page.locator('.edge')).toHaveCount(edges);
  }
});

test('selected clues require their own supported display channels', async ({page}) => {
  let missing;
  await page.route('**/api/plan', async route => {
    const result = await (await route.fetch()).json();
    result.plan.requirements.channels = result.plan.requirements.channels.filter(c => c.name !== missing);
    await route.fulfill({json: result});
  });
  for (const [family, channels] of [
    ['shading', ['givens', 'row-counts', 'column-counts']],
    ['slitherlink', ['cell-counts', 'edge-givens']],
    ['coupled', ['givens', 'edge-givens']],
  ]) {
    for (missing of channels) {
      await page.goto('/');
      if (family !== 'shading') await page.locator('#family').selectOption(family);
      await expect(page.locator('#generate')).toBeDisabled();
      await expect(page.locator('#board')).toBeEmpty();
      await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
    }
  }
});

test('a generation plan missing a selected clue channel cannot expose the puzzle', async ({page}) => {
  await page.goto('/');
  await expect(page.locator('#generate')).toBeEnabled();
  await page.route('**/api/generate', async route => {
    const result = await (await route.fetch()).json();
    expect(result.status).toBe('ok');
    result.plan.requirements.channels = result.plan.requirements.channels.filter(c => c.name !== 'row-counts');
    await route.fulfill({json: result});
  });
  await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled();
  await expect(page.locator('#board')).toBeEmpty();
  await expect(page.locator('#actions')).toBeHidden();
});

test('a changed generation UI contract cannot expose an unsupported answer', async ({page}) => {
  await page.goto('/');
  await page.locator('#family').selectOption('coupled');
  await page.locator('#rows').fill('2'); await page.locator('#cols').fill('2');
  await expect(page.locator('#generate')).toBeEnabled();
  await page.route('**/api/generate', async route => {
    const response = await route.fetch();
    const result = await response.json();
    expect(result.status).toBe('ok');
    // A real, small joint puzzle; only its declared edge channel is changed.
    result.plan.requirements.channels.find(c => c.name === 'answer-edges').kind = 'directed-edges';
    await route.fulfill({json: result});
  });
  await page.locator('#generate').click();
  await expect(page.locator('#status')).toContainText('このUI定義には対応していません');
  await expect(page.locator('#generate')).toBeDisabled();
  await expect(page.locator('#board')).toBeEmpty();
  await expect(page.locator('#actions')).toBeHidden();
  await page.unroute('**/api/generate');
  await page.locator('#seed').fill('1');
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(page.locator('.cell')).toHaveCount(4);
  await expect(page.locator('.edge')).toHaveCount(4);
});
