import {test, expect} from '@playwright/test';

test('generated rules track the successful puzzle across edits, failure and regeneration', async ({page}) => {
  await page.goto('/');
  const section = page.getByRole('region', {name: 'この問題のルール'});
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(section).toBeHidden();
  await page.locator('#generate').click();
  await expect(section).toBeVisible();
  await expect(section).toContainText('黒マス数：2');
  await expect(section).toContainText('白マスを1つ以上にする：はい');
  await page.getByLabel('黒マス数', {exact:true}).fill('3');
  await expect(section).toBeHidden();
  await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#generate').click();
  await expect(section).toBeVisible();
  await expect(section).toContainText('黒マス数：3');
  await page.route('**/api/generate', route => route.fulfill({json:{status:'unsatisfiable'}}));
  await page.locator('#generate').click();
  await expect(section).toBeHidden();
});

test('rules appear for loop and coupled boards at narrow width', async ({page}) => {
  await page.setViewportSize({width: 320, height: 800});
  await page.goto('/');
  for (const [family, label] of [['slitherlink','空でない1本のループ'], ['coupled','白マスすべてを通る']]) {
    await page.locator('#family').selectOption(family);
    await expect(page.locator('#generate')).toBeEnabled();
    await page.locator('#generate').click();
    const section = page.getByRole('region', {name:'この問題のルール'});
    await expect(section).toBeVisible();
    await expect(section).toContainText(label);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});

test('shared settings restore the rules shown after generation', async ({page}) => {
  await page.goto('/'); await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('黒マス数', {exact:true}).fill('3');
  await expect(page.locator('#generate')).toBeEnabled();
  await page.locator('#share-settings').click();
  const url = await page.locator('#share-url').inputValue();
  const recipient = await page.context().newPage();
  await recipient.goto(url); await expect(recipient.locator('#generate')).toBeEnabled();
  await recipient.locator('#generate').click();
  await expect(recipient.getByRole('region', {name:'この問題のルール'})).toContainText('黒マス数：3');
});
