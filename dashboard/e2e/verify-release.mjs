/* global document, window, console */
// Inspect public evidence on the actual prepared release; no fixtures, login or inference.
import {chromium,expect} from '@playwright/test';
import fs from 'node:fs/promises';
const out='../evidence/build004';
const cohort=JSON.parse(await fs.readFile('lib/study004-cohort.json','utf8'));
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage();const errors=[];const checks={};
page.on('pageerror',error=>errors.push(error.message));
async function visit(path,shot){
  await page.goto('http://127.0.0.1:3100'+path);
  if(shot)await page.screenshot({path:out+'/'+shot,fullPage:true});
}
try{
  for(let i=0;i<3;i++){
    await visit('/');
    await expect(page.getByText('36 recorded attempts',{exact:true})).toBeVisible();
    await expect(page.getByText(/Published case file.*Original study/)).toBeVisible();
    await expect(page.getByText(/The active comparison covers twelve locked evaluation cases/)).toBeVisible();
  }
  checks.three_home_loads_current_cohort=true;
  await page.screenshot({path:out+'/home-desktop.png',fullPage:true});
  await page.screenshot({path:out+'/home-viewport.png'});
  await visit('/investigations/8b03a42f-149e-4d44-937f-0d61636f6042');
  await expect(page.getByRole('region',{name:'After changed lines'})).toContainText('0o644');
  await page.screenshot({path:out+'/repair-desktop.png',fullPage:true});
  await page.screenshot({path:out+'/repair-viewport.png'});
  const patchPromise=page.waitForEvent('download');
  await page.getByRole('link',{name:'Download patch',exact:true}).click();
  const patchText=await fs.readFile(await (await patchPromise).path(),'utf8');
  if(!patchText.includes('+FILE_UPLOAD_PERMISSIONS = 0o644'))throw new Error('Unexpected downloaded patch');
  checks.real_patch_download=true;
  const bundlePromise=page.waitForEvent('download');
  await page.getByRole('link',{name:'Download evidence',exact:true}).click();
  const bundle=JSON.parse(await fs.readFile(await (await bundlePromise).path(),'utf8'));
  if(bundle.id!=='8b03a42f-149e-4d44-937f-0d61636f6042'||!bundle.integrity.verified)throw new Error('Invalid downloaded evidence');
  checks.real_integrity_download=true;
  await page.getByRole('button',{name:/Prepared the context/}).first().focus();await page.keyboard.press('Enter');
  await expect(page.getByRole('heading',{name:'Evidence selected for the next call'})).toBeVisible();checks.keyboard_context=true;
  await visit('/investigations/'+cohort.ids[0]);
  const comparison=page.getByRole('region',{name:'Strategy comparison'});
  for(const name of ['Single call','Tool loop','Independent drafts'])await expect(comparison).toContainText(name);
  checks.three_real_comparison_records=true;
  await page.screenshot({path:out+'/investigation-desktop.png',fullPage:true});
  await visit('/study');await expect(page.getByRole('heading',{name:/\/ 12 verified/})).toHaveCount(3);checks.frozen_study=true;
  await page.screenshot({path:out+'/study-desktop.png',fullPage:true});
  await visit('/capacity');await expect(page.getByRole('heading',{name:/Quiet repeat passed.*The original soak failed/})).toBeVisible();checks.capacity_failure_visible=true;
  const quiet=page.getByRole('region',{name:'Quiet capacity repeat'});
  await expect(quiet).toContainText('272,855');await expect(quiet).toContainText('275.2 ms');
  const capacityDownload=page.waitForEvent('download');await page.getByRole('link',{name:'Download measurements'}).click();
  const measured=JSON.parse(await fs.readFile(await (await capacityDownload).path(),'utf8'));
  if(measured.quiet_repeat.raw_requests!==435270||!measured.quiet_repeat.target_met||measured.original_sustained_capacity_accepted!==false)throw new Error('Capacity download lost outcome history');
  checks.complete_capacity_repeat_and_download=true;
  await page.screenshot({path:out+'/capacity-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  for(const [path,shot] of [['/','home-mobile.png'],['/investigations/8b03a42f-149e-4d44-937f-0d61636f6042','repair-mobile.png'],['/study','study-mobile.png'],['/capacity','capacity-mobile.png']]){
    await visit(path);
    if(!await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth))throw new Error('Horizontal overflow on '+path);
    await page.screenshot({path:out+'/'+shot,fullPage:true});
  }
  checks.mobile_390_no_document_overflow=true;
  await visit('/investigations/00000000-0000-4000-8000-000000000000');
  await expect(page.getByText('Investigation service returned HTTP 404.')).toBeVisible();checks.missing_record_unavailable=true;
  checks.no_uncaught_browser_errors=errors.length===0;
  if(errors.length)throw new Error(errors.join('\n'));
  await fs.writeFile(out+'/browser-live004.json',JSON.stringify({passed:true,method:'Production standalone web and real PostgreSQL-backed API; no fixture identity, login or inference.',checks},null,2)+'\n');
  console.log(JSON.stringify(checks));
}finally{await context.close();await browser.close();}
