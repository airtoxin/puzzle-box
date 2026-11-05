import {test,expect} from '@playwright/test';

async function start(page) {
  const reply=page.waitForResponse('**/api/catalog');await page.goto('/');
  const catalog=await (await reply).json();const rule=id=>catalog.rules.find(r=>r.identifier===id);
  await expect(page.locator('#generate')).toBeEnabled();
  for(const id of ['count','connected-white']) await page.getByLabel(rule(id).label,{exact:true}).uncheck();
  await page.locator('#rows').fill('3');await page.locator('#cols').fill('3');
  for(const id of ['white-island-areas','rectangular-components','no-black-2x2','unequal-corner-component-sizes'])
    await page.getByLabel(rule(id).label,{exact:true}).check();
  await page.getByLabel(rule('white-island-areas').parameters.find(p=>p.name==='areas').label,{exact:true}).fill('0 0 1\n0 5 0\n0 0 0');
  for(const id of ['row-count','column-count']) await page.getByLabel(catalog.clues.find(c=>c.identifier===id).label,{exact:true}).uncheck();
  return {catalog,rule};
}

async function generate(page) {
  await expect(page.locator('#generate')).toBeEnabled();
  const reply=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  return (await reply).json();
}

test('Nuribou fragments render existing island numbers and check a generated board',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const {catalog}=await start(page);
  await expect(page.locator('#capabilities li').first()).toContainText(`${catalog.rules.length}ルール`);
  // The component implementation's internal room is not a user UI requirement.
  await expect(page.locator('#rules textarea[data-kind="region-map"]:visible')).toHaveCount(0);
  const data=await generate(page);expect(data.status).toBe('ok');expect(data.evidence.unique).toBe(true);
  expect(data.clues.length).toBeGreaterThan(0);
  expect(data.record.rules.find(r=>r.type==='unequal-corner-component-sizes')).toEqual({type:'unequal-corner-component-sizes',black:true});
  for(const [index,area] of [[2,'1'],[4,'5']]) {
    const cell=page.locator(`[data-cell-index="${index}"]`);
    await expect(cell).toBeDisabled();await expect(cell).toHaveAttribute('data-value','0');
    await expect(cell.locator('.area-number')).toHaveText(area);
  }
  for(let i=0;i<9;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if(await cell.isEnabled()) {
      await expect(cell).toHaveAttribute('data-value','-1');
      for(let turn=0;turn<3 && await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i]);turn++) await cell.click();
      await expect(cell).toHaveAttribute('data-value',String(data.record.solution.flat()[i]));
    }
  }
  let checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('nuribou-board.png')});
  const cell=page.locator('.cell:enabled').first(),opposite=String(1-Number(await cell.getAttribute('data-value')));
  for(let turn=0;turn<3 && await cell.getAttribute('data-value')!==opposite;turn++) await cell.click();
  await expect(cell).toHaveAttribute('data-value',opposite);
  checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:false});
  await page.getByLabel(catalog.clues.find(c=>c.identifier==='cell').label,{exact:true}).uncheck();
  expect((await generate(page)).status).toBe('insufficient_hints');
  expect(errors).toEqual([]);
});

test('the selected color is a strict independent Boolean editor',async({page})=>{
  const {rule}=await start(page);
  const color=page.getByLabel(rule('unequal-corner-component-sizes').parameters.find(p=>p.name==='black').label,{exact:true});
  await expect(color).toBeChecked();await color.uncheck();
  const data=await generate(page);expect(data.status).toBe('ok');
  expect(data.record.rules.find(r=>r.type==='unequal-corner-component-sizes')).toEqual({type:'unequal-corner-component-sizes',black:false});
  // The rectangle rule's own color checkbox remains independent.
  const rectangleCard=page.locator('.rule-card').filter({has:page.getByLabel(rule('rectangular-components').label,{exact:true})});
  const rectangles=rectangleCard.getByLabel(rule('rectangular-components').parameters.find(p=>p.name==='black').label,{exact:true});
  await expect(rectangles).toBeChecked();
});
