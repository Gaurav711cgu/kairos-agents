import {test,expect} from '@playwright/test';
import cohort from '../lib/study004-cohort.json';
const repair='8b03a42f-149e-4d44-937f-0d61636f6042';
test('recorded public evidence, comparison, diff and downloads need no login',async({page})=>{
  await page.goto('/investigations/'+repair);
  await expect(page.getByRole('heading',{name:'Verified repair',exact:true}).first()).toBeVisible();
  await expect(page.getByRole('region',{name:'Before changed lines'})).toContainText('FILE_UPLOAD_PERMISSIONS = None');
  await expect(page.getByRole('region',{name:'After changed lines'})).toContainText('0o644');
  await expect(page.getByRole('region',{name:'Strategy comparison'})).toContainText('Single call');
  await expect(page.getByRole('region',{name:'Strategy comparison'})).toContainText('Tool loop');
  const download=page.waitForEvent('download');await page.getByRole('link',{name:'Download patch',exact:true}).click();expect((await download).suggestedFilename()).toMatch(/\.patch$/);
  const context=page.getByRole('button',{name:/Prepared the context/}).first();await context.focus();await page.keyboard.press('Enter');
  await expect(page.getByRole('heading',{name:'Evidence selected for the next call'})).toBeVisible();
});
test('public evidence and capacity remain readable at 390px',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/investigations/'+repair);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.getByRole('region',{name:'After changed lines'}).focus();await page.keyboard.press('ArrowRight');
  await page.goto('/capacity');await expect(page.getByRole('heading',{name:/435,270 requests.*A complete 42-minute test/})).toBeVisible();
  await expect(page.getByRole('region',{name:'Original capacity run'})).toContainText('The ten-client soak failed during a service restart.');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
test('public missing records show an explicit unavailable state',async({page})=>{
  await page.goto('/investigations/00000000-0000-4000-8000-000000000000');
  await expect(page.getByText('Investigation service returned HTTP 404.')).toBeVisible();
});

test('frozen build004 compares all three strategies and shows measured study cost',async({page,request})=>{
  test.skip(!cohort.complete,'Frozen evaluation must finish before final comparison acceptance.');
  await page.goto('/');
  await expect(page.getByText('10 recorded attempts',{exact:true})).toBeVisible();
  await expect(page.getByText(/The active comparison covers five locked Python cases/)).toBeVisible();
  await request.post('http://127.0.0.1:8195/testing/reset-reads');
  await page.goto('/investigations/'+cohort.ids[0]);
  const comparison=page.getByRole('region',{name:'Strategy comparison'});
  await expect(comparison).toContainText('Single call');
  await expect(comparison).toContainText('Tool loop');
  await expect(comparison).toContainText('Independent drafts');
  const reads=await (await request.get('http://127.0.0.1:8195/testing/reads')).json();
  expect(new Set(reads.ids).size).toBe(3);
  await page.goto('/study');
  await expect(page.getByRole('heading',{name:/\/ 12 verified/})).toHaveCount(3);
  await expect(page.getByText('Captured tokens',{exact:true})).toHaveCount(3);
  const download=page.waitForEvent('download');
  await page.getByRole('link',{name:'Download all attempts',exact:true}).click();
  expect((await download).suggestedFilename()).toBe('attempts.json');
});
