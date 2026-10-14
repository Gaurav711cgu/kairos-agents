import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import type { Investigation } from '../lib/investigations';

const runtime=process.env.KAIROS_REVIEWER_RUNTIME;
if(!runtime) throw new Error('A private owned reviewer runtime must be selected explicitly.');
const origin=process.env.KAIROS_REVIEWER_URL||'http://127.0.0.1:3310';
const prefix='/api/workbench/investigations';
const task='django__django-11066';
const hash=(value:Buffer)=>crypto.createHash('sha256').update(value).digest('hex');

test('real browser submission reaches local inference, captured outcome, downloads and replay',async({page})=>{
  const privateState=JSON.parse(await fs.readFile(path.join(runtime!,'services.json'),'utf8'));
  expect(privateState.inference).toBe(true);
  expect(privateState.worker).toBe(true);
  const credentials=JSON.parse(await fs.readFile(path.join(runtime!,'identity.local.json'),'utf8'));
  const account=credentials.accounts.find((item:{role:string})=>item.role==='admin');
  if(!account)throw new Error('Generated local administrator is missing.');
  await page.goto('/workbench');
  await expect(page.getByText('Evidence viewer · Original investigation captures',{exact:true})).toHaveCount(0);
  await page.getByRole('link',{name:'Sign in',exact:true}).click();
  await page.getByLabel('Username').fill(account.username);
  await page.getByLabel('Password',{exact:true}).fill(account.password);
  await page.getByRole('button',{name:'Sign In',exact:true}).click();
  await page.waitForURL(origin+'/workbench');
  await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();
  await expect(page.getByLabel('Historical case')).toBeEnabled();
  await page.getByLabel('Historical case').selectOption(task);
  await page.getByLabel('Approach').selectOption('loop-v7');
  const accepted=page.waitForResponse(response=>response.url().endsWith(prefix)&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Queue investigation',exact:true}).click();
  const response=await accepted;
  expect(response.status()).toBe(202);
  const queued=await response.json() as Investigation;
  expect(queued.task_id).toBe(task);
  expect(queued.configuration).toBe('loop-v7');
  const observed:{status:string;phase:string;model_calls:number;check_count:number;latest_sequence:number}[]=[];
  await expect.poll(async()=>{
    const update=await page.request.get(prefix+'/'+queued.id+'/progress');
    expect(update.status()).toBe(200);
    const progress=await update.json();
    observed.push({status:progress.status,phase:progress.phase,model_calls:progress.model_calls,check_count:progress.check_count,latest_sequence:progress.latest_sequence});
    return ['completed','failed','cancelled'].includes(progress.status);
  },{timeout:620000,intervals:[2000]}).toBe(true);
  const detail=await page.request.get(prefix+'/'+queued.id);
  expect(detail.status()).toBe(200);
  const record=await detail.json() as Investigation;
  expect(record.integrity.verified).toBe(true);
  expect(record.model_calls).toBeGreaterThan(0);
  expect(record.steps.some(step=>step.kind==='model'&&step.state==='captured'&&step.result)).toBe(true);
  expect(record.steps.some(step=>step.name==='initial_source')).toBe(true);
  // This acceptance checks real execution and honest rendering. Repair quality is recorded separately.
  await page.getByRole('button',{name:'Refresh this attempt',exact:true}).click();
  await expect(page.locator('.private-investigation-detail')).toContainText(record.model_calls+' model');
  await expect(page.getByRole('region',{name:'Investigation outcome'})).toBeVisible();
  const selected=page.getByRole('button',{name:/Prepared the context/}).first();
  await selected.focus();await page.keyboard.press('Enter');
  await expect(page.getByRole('heading',{name:'Evidence selected for the next call'})).toBeVisible();
  const output=path.join(runtime!,'execution-acceptance');await fs.mkdir(output,{recursive:true,mode:0o700});
  await page.screenshot({path:path.join(output,'live-result-desktop.png'),fullPage:true});
  let patch:Buffer|null=null;
  if(await page.getByRole('link',{name:'Download patch',exact:true}).count()){
    const pending=page.waitForEvent('download');await page.getByRole('link',{name:'Download patch',exact:true}).click();
    const location=await(await pending).path();expect(location).not.toBeNull();patch=await fs.readFile(location!);
    await fs.writeFile(path.join(output,'candidate.patch'),patch,{mode:0o600});
  }
  const pending=page.waitForEvent('download');await page.getByRole('link',{name:'Download evidence',exact:true}).click();
  const location=await(await pending).path();expect(location).not.toBeNull();const bundle=await fs.readFile(location!);
  expect(JSON.parse(bundle.toString())).toEqual(record);
  await fs.writeFile(path.join(output,'investigation.json'),bundle,{mode:0o600});
  const replay=await page.request.get(prefix+'/'+record.id+'/replay');expect(replay.status()).toBe(200);
  const playback=await replay.json();expect(playback.network_calls).toBe(0);expect(playback.tool_executions).toBe(0);
  expect(playback.investigation.model_calls).toBe(record.model_calls);
  await page.getByRole('button',{name:'Replay saved steps',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Recorded playback'})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:path.join(output,'live-result-mobile.png'),fullPage:true});
  await fs.writeFile(path.join(output,'rendered-result.txt'),await page.locator('main').innerText(),{mode:0o600});
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await expect(page.getByRole('link',{name:'Sign in',exact:true})).toBeVisible();
  await fs.writeFile(path.join(output,'receipt.json'),JSON.stringify({
    version:'interactive-execution008-v1',workflow_passed:true,repair_verified:record.outcome==='verified_repair',
    investigation_id:record.id,task_id:record.task_id,configuration:record.configuration,
    status:record.status,outcome:record.outcome,model_calls:record.model_calls,patch_count:record.patch_count,
    check_count:record.check_count,started_at:record.started_at,finished_at:record.updated_at,
    bundle:{bytes:bundle.length,sha256:hash(bundle)},patch:patch?{bytes:patch.length,sha256:hash(patch)}:null,
    observed_progress:observed,replay:{network_calls:0,tool_executions:0},
    scope:'One browser-submitted exposed development demonstration; separate from frozen evaluation.'
  },null,2)+'\n',{mode:0o600});
});
