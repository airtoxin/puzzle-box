import {test, expect} from '@playwright/test';

async function start(page) {
  await page.goto('/');await expect(page.locator('#generate')).toBeEnabled();
  await page.getByLabel('白マスをつなぐ',{exact:true}).uncheck();
  await page.getByLabel('色ごとに横・縦の連続を制限',{exact:true}).check();
  await page.getByLabel('各行の黒マス数',{exact:true}).uncheck();
  await page.getByLabel('各列の黒マス数',{exact:true}).uncheck();
}

test('directional colors and tied room majorities compose, generate and check a real answer',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await start(page);await page.locator('#rows').fill('3');
  await page.getByLabel('黒マス数',{exact:true}).fill('3');
  await page.getByLabel('各部屋の多数色の個数を固定',{exact:true}).check();
  await page.getByLabel('部屋配置（同じ数字が同じ部屋）',{exact:true}).fill('0 0 1\n0 0 1\n2 2 1');
  await expect(page.locator('#generate')).toBeEnabled();
  await expect(page.locator('#rules textarea:visible')).toHaveCount(1);
  await expect(page.locator('#rules')).toContainText('線や経路ではありません');
  const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  const data=await (await generated).json();expect(data.status).toBe('ok');expect(data.clues).toHaveLength(2);
  expect(['010010001','010100001','100010001','100100001']).toContain(data.record.solution.flat().join(''));
  expect(data.record.rules.find(r=>r.type==='room-majority-count').count).toBe(2);
  for(let i=0;i<9;i++) {
    const cell=page.locator(`[data-cell-index="${i}"]`);
    if(await cell.isEnabled()) while(await cell.getAttribute('data-value')!==String(data.record.solution.flat()[i])) await cell.click();
  }
  const checked=page.waitForResponse('**/api/check');await page.locator('#check').click();
  expect(await (await checked).json()).toEqual({status:'ok',correct:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('#board').screenshot({path:test.info().outputPath('directional-majority-board.png')});
  await page.getByLabel('各部屋の多数色の個数',{exact:true}).fill('1');
  await expect(page.locator('#generate')).toBeEnabled();
  const conflict=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
  expect((await (await conflict).json()).status).toBe('unsatisfiable');expect(errors).toEqual([]);
});

test('swapping direction and increasing the run limit change the constraints without new UI channels',async({page})=>{
  await start(page);await page.locator('#rows').fill('1');
  await page.getByLabel('黒マス数',{exact:true}).fill('0');
  await expect(page.locator('#rules textarea:visible')).toHaveCount(0);
  for(const [horizontal,maximum,status] of [[true,'2','unsatisfiable'],[false,'2','ok'],[true,'3','ok']]) {
    await page.getByLabel('横向きを黒で表す（オフなら白）',{exact:true}).setChecked(horizontal);
    await page.getByLabel('向きと直交する最大連続長',{exact:true}).fill(maximum);
    await expect(page.locator('#generate')).toBeEnabled();
    const generated=page.waitForResponse('**/api/generate');await page.locator('#generate').click();
    const data=await (await generated).json();expect(data.status).toBe(status);
    if(status==='ok') {
      expect(data.record.solution).toEqual([[0,0,0]]);
      const rule=data.record.rules.find(r=>r.type==='directional-run-limit');
      expect(rule.horizontal_black).toBe(horizontal);expect(rule.max_length).toBe(Number(maximum));
    }
  }
  await page.getByLabel('向きと直交する最大連続長',{exact:true}).fill('0');
  await expect(page.locator('#generate')).toBeDisabled();
});
