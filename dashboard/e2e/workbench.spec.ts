import { test, expect, type Page } from '@playwright/test';
const ids=['10000000-0000-4000-8000-000000000001','10000000-0000-4000-8000-000000000002'];
function record(id:string,title:string,status='completed') {
  return {id,task_id:title,configuration:'loop-v3',status,outcome:status==='completed'?'no_patch':null,summary:null,model_calls:0,patch_count:0,check_count:0,created_at:'2026-10-11T00:00:00Z',updated_at:'2026-10-11T00:00:00Z',started_at:null,deadline_at:null,published:false,parent_id:null,task_digest:'digest',title,
    task_snapshot:{title,issue:'Inspect a defect.',repository:'Isolated fixture',revision:'fixture',issue_url:null,source_url:'',source_digest:'digest',split:'development',provenance:'Browser fixture only.',entry_files:[],qualified:true,command:['python','check.py'],image:'fixture'},config_snapshot:{},steps:[],artifacts:[],integrity:{verified:true,scope:'Fixture'}};
}
const a=record(ids[0],'Fixture A'),b=record(ids[1],'Fixture B');
async function fixture(page:Page,role='admin') {
  await page.context().addCookies([{name:'kairos_session',value:'fixture-'+role,url:'http://127.0.0.1:3104'}]);
  await page.route('**/api/workbench/investigations**',async route=>{
    const path=new URL(route.request().url()).pathname.replace('/api/workbench/investigations','');
    const body=path==='/cases'?{cases:[{id:'Fixture A',title:'Fixture A',qualified:true,split:'development'}]}:path===''?{investigations:[a,b],next_cursor:null}:path.includes(ids[1])?b:a;
    await route.fulfill({json:body});
  });
  await page.goto('/workbench');await expect(page.getByRole('button',{name:'Fixture A Tool loop · No patch proposed'})).toBeVisible();
}
test('late detail response cannot overwrite a newer selection',async({page})=>{
  await fixture(page);
  await page.route('**/api/workbench/investigations/'+ids[0],async route=>{await new Promise(resolve=>setTimeout(resolve,1500));await route.fulfill({json:a});});
  await page.getByRole('button',{name:'Fixture A Tool loop · No patch proposed'}).click();
  await page.getByRole('button',{name:'Fixture B Tool loop · No patch proposed'}).click();
  await expect(page.locator('.private-investigation-detail h3').first()).toHaveText('Fixture B');
  await page.waitForTimeout(1800);
  await expect(page.locator('.private-investigation-detail h3').first()).toHaveText('Fixture B');
});
test('uncertain create keeps the command identity across reload',async({page})=>{
  await fixture(page);const keys:string[]=[];
  await page.route('**/api/workbench/investigations',async route=>{
    if(route.request().method()==='GET')return route.fulfill({json:{investigations:[a,b],next_cursor:null}});
    keys.push(route.request().headers()['idempotency-key']);
    if(keys.length===1)return route.abort('failed');
    return route.fulfill({status:202,json:a});
  });
  await page.getByRole('button',{name:'Queue investigation'}).click();
  await expect(page.locator('.investigation-workbench [role=alert]')).toBeVisible();await page.reload();
  await page.getByRole('button',{name:'Queue investigation'}).click();
  await expect.poll(()=>keys.length).toBe(2);expect(keys[1]).toBe(keys[0]);
});

test('uncertain fork keeps its identity across reload',async({page})=>{
  await fixture(page);const keys:string[]=[];
  await page.route('**/api/workbench/investigations/'+ids[0]+'/fork',async route=>{
    keys.push(route.request().headers()['idempotency-key']);if(keys.length===1)return route.abort('failed');return route.fulfill({status:202,json:b});
  });
  await page.getByRole('button',{name:'Fixture A Tool loop · No patch proposed'}).click();
  await page.getByRole('button',{name:'Create a fresh fork'}).click();
  await expect(page.locator('.investigation-workbench [role=alert]')).toBeVisible();await page.reload();
  await page.getByRole('button',{name:'Retry saved fork'}).click();
  await expect.poll(()=>keys.length).toBe(2);expect(keys[1]).toBe(keys[0]);
  await expect(page.locator('.private-investigation-detail h3').first()).toHaveText('Fixture B');
});
test('viewer controls, evidence download and keyboard work at 390px',async({page})=>{
  await page.setViewportSize({width:390,height:844});await fixture(page,'viewer');
  await expect(page.getByRole('button',{name:'Queue investigation'})).toBeDisabled();
  const row=page.getByRole('button',{name:'Fixture A Tool loop · No patch proposed'});await row.focus();await page.keyboard.press('Enter');
  await expect(page.getByRole('button',{name:'Create a fresh fork'})).toBeDisabled();
  await expect(page.getByRole('button',{name:'Publish evidence'})).toHaveCount(0);
  await page.route('**/api/workbench/investigations/'+ids[0]+'/bundle',route=>route.fulfill({body:JSON.stringify(a),headers:{'Content-Type':'application/json','Content-Disposition':'attachment; filename="fixture.json"'}}));
  const download=page.waitForEvent('download');await page.getByRole('link',{name:'Download evidence'}).click();expect((await download).suggestedFilename()).toBe('fixture.json');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
test('visible progress refreshes evidence and stops at a terminal state',async({page})=>{
  await fixture(page);let polls=0;
  await page.route('**/api/workbench/investigations/'+ids[0],route=>route.fulfill({json:record(ids[0],'Fixture A',polls?'completed':'running')}));
  await page.route('**/api/workbench/investigations/'+ids[0]+'/progress',route=>{polls++;return route.fulfill({json:{id:ids[0],status:'completed',outcome:'no_patch',model_calls:0,patch_count:0,check_count:0,phase:'completed',latest_sequence:0,updated_at:'2026-10-11T00:00:00Z'}});});
  await page.getByRole('button',{name:'Fixture A Tool loop · No patch proposed'}).click();
  await expect.poll(()=>polls).toBe(1);await page.waitForTimeout(2400);expect(polls).toBe(1);
  await expect(page.getByRole('heading',{name:'No patch proposed',exact:true})).toBeVisible();
});
test('cancel, publication and replay show captured evidence without execution',async({page})=>{
  await fixture(page);const executions=0;
  await page.route('**/api/workbench/investigations/'+ids[0],route=>route.fulfill({json:record(ids[0],'Fixture A','queued')}));
  await page.route('**/api/workbench/investigations/'+ids[0]+'/cancel',route=>route.fulfill({json:{...a,status:'cancelled',outcome:'cancelled'}}));
  await page.route('**/api/workbench/investigations/'+ids[0]+'/publish',route=>route.fulfill({json:{...a,published:true}}));
  await page.route('**/api/workbench/investigations/'+ids[0]+'/replay',route=>route.fulfill({json:{mode:'recorded-playback',network_calls:executions,tool_executions:executions,investigation:a}}));
  await page.getByRole('button',{name:'Fixture A Tool loop · No patch proposed'}).click();await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Cancelled',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Publish evidence'}).click();await expect(page.getByRole('button',{name:'Publish evidence'})).toBeDisabled();
  await page.getByRole('button',{name:'Replay saved steps'}).click();await expect(page.getByRole('status').filter({hasText:'Recorded playback'})).toBeVisible();expect(executions).toBe(0);
});

test('poll errors back off for 30 seconds and navigation cancels reads',async({page})=>{
  await fixture(page);await page.clock.install();let polls=0;
  await page.route('**/api/workbench/investigations/'+ids[0],route=>route.fulfill({json:record(ids[0],'Fixture A','running')}));
  await page.route('**/api/workbench/investigations/'+ids[0]+'/progress',route=>{polls++;return route.fulfill({status:503,json:{detail:'Fixture outage'}});});
  await page.getByRole('button',{name:'Fixture A Tool loop · No patch proposed'}).click();
  await page.clock.runFor(2100);await expect.poll(()=>polls).toBe(1);
  await expect(page.locator('.investigation-workbench [role=alert]')).toContainText('30 seconds');
  await page.clock.runFor(29000);expect(polls).toBe(1);
  await page.clock.runFor(1100);await expect.poll(()=>polls).toBe(2);
  await page.getByRole('button',{name:'Fixture B Tool loop · No patch proposed'}).click();
  await page.clock.runFor(31000);expect(polls).toBe(2);
});
