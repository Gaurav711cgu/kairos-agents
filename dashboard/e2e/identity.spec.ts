import {test,expect,type Page} from '@playwright/test';
import fs from 'node:fs';
const credentials=JSON.parse(fs.readFileSync('../.runtime/identity.local.json','utf8')) as {accounts:{username:string;password:string;role?:string}[]};
async function login(page:Page,role:string) {
  const account=credentials.accounts.find(item=>item.role===role)!;
  await page.goto('/workbench');await page.getByRole('link',{name:'Sign in',exact:true}).click();
  await page.getByLabel('Username').fill(account.username);await page.getByLabel('Password',{exact:true}).fill(account.password);
  await page.getByRole('button',{name:'Sign In',exact:true}).click();await page.waitForURL('**:3105/workbench');
  await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();
}
test('real OIDC login, durable queue, cancel, fork, replay, publish, download, logout',async({page})=>{
  await login(page,'admin');const saved=page.waitForResponse(response=>response.url().endsWith('/api/workbench/investigations') && response.request().method()==='POST');await page.getByRole('button',{name:'Queue investigation'}).click();await saved;
  await expect(page.getByRole('button',{name:'Cancel',exact:true})).toBeEnabled();await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Cancelled',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Create a fresh fork'}).click();await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await page.getByRole('button',{name:'Replay saved steps'}).click();await expect(page.getByRole('status').filter({hasText:'Recorded playback'})).toBeVisible();
  await page.getByRole('button',{name:'Publish evidence'}).click();await expect(page.getByRole('button',{name:'Publish evidence'})).toBeDisabled();
  const download=page.waitForEvent('download');await page.getByRole('link',{name:'Download evidence'}).click();expect((await download).suggestedFilename()).toMatch(/^kairos-.*\.json$/);
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByRole('link',{name:'Sign in',exact:true})).toBeVisible();
  expect((await page.request.get('/api/workbench/investigations')).status()).toBe(401);
});
test('real viewer role denies writes on server as well as controls',async({page})=>{
  await login(page,'viewer');await expect(page.getByRole('button',{name:'Queue investigation'})).toBeDisabled();
  const response=await page.request.post('/api/workbench/investigations',{headers:{Origin:'http://127.0.0.1:3105','Idempotency-Key':crypto.randomUUID()},data:{task_id:'kairos-clock-lease',configuration:'loop-v3'}});
  expect(response.status()).toBe(403);
});

test('real operator cannot read another tenant private investigation',async({page,browser})=>{
  const adminContext=await browser.newContext(),adminPage=await adminContext.newPage();
  await login(adminPage,'admin');const saved=adminPage.waitForResponse(response=>response.url().endsWith('/api/workbench/investigations') && response.request().method()==='POST');
  await adminPage.getByRole('button',{name:'Queue investigation'}).click();const privateAttemptId=(await (await saved).json()).id;
  await adminPage.getByRole('button',{name:'Cancel',exact:true}).click();await adminContext.close();
  await login(page,'operator');
  expect((await page.request.get('/api/workbench/investigations/'+privateAttemptId)).status()).toBe(404);
  expect((await page.request.get('/api/workbench/investigations/'+privateAttemptId+'/progress')).status()).toBe(404);
  expect((await page.request.get('/api/workbench/investigations/'+privateAttemptId+'/bundle')).status()).toBe(404);
  const listing=await page.request.get('/api/workbench/investigations');expect((await listing.json()).investigations).toEqual([]);
});
