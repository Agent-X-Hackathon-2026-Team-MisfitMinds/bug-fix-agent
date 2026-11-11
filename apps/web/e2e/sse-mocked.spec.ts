import {test, expect, type Page} from '@playwright/test';

// These tests replace EventSource and API responses. They do not connect to a backend.
const baseRun={id:'test-run-1',repository_full_name:'test-owner/test-repo',issue_number:42,
  issue_title:'Mocked live run',status:'reproducing',confidence:null,pr_url:null,
  test_output:null,root_cause:'Initial snapshot',created_at:'2026-01-01T00:00:00Z',
  steps:[{id:'step-1',step:'read',status:'completed',output:null,error:null}]};

type FakeStream={url:string;closed:boolean;emitOpen:()=>void;emitError:()=>void;emitNamed:(name:string)=>void};
type StreamWindow=Window & {__streams:FakeStream[]};
async function mockEventSource(page:Page){
  await page.addInitScript(()=>{
    const w=window as StreamWindow;w.__streams=[];
    class FakeEventSource extends EventTarget {
      url:string;closed=false;onopen:(()=>void)|null=null;onerror:(()=>void)|null=null;
      constructor(url:string){super();this.url=url;w.__streams.push(this)}
      emitOpen(){if(!this.closed)this.onopen?.()}
      emitError(){if(!this.closed)this.onerror?.()}
      emitNamed(name:string){if(!this.closed)this.dispatchEvent(new MessageEvent(name,{data:'{}'}))}
      close(){this.closed=true}
    }
    window.EventSource=FakeEventSource as unknown as typeof EventSource;
  });
}
async function emit(page:Page,type:'open'|'error'|'step_updated'|'run_status_changed'){
  await page.evaluate((eventType)=>{
    const streams=(window as StreamWindow).__streams;
    const current=streams.filter(s=>!s.closed).at(-1);
    if(!current)throw new Error('No active fake stream');
    if(eventType==='open')current.emitOpen();else if(eventType==='error')current.emitError();else current.emitNamed(eventType);
  },type);
}
async function waitForStream(page:Page){await expect.poll(()=>page.evaluate(()=>(window as StreamWindow).__streams.filter(s=>!s.closed).length)).toBe(1)}

test('live stream refreshes a snapshot, reconnects and closes on completion',async({page})=>{
  await mockEventSource(page);let current={...baseRun};
  await page.route('**/api/runs/test-run-1',route=>route.fulfill({json:current}));
  await page.goto('/dashboard/runs/test-run-1');await waitForStream(page);
  await expect(page.getByText('Reconnecting…')).toBeVisible();
  expect(await page.evaluate(()=>(window as StreamWindow).__streams.filter(s=>!s.closed)[0].url)).toBe('/api/runs/test-run-1/events');
  await emit(page,'open');await expect(page.getByText('● Live')).toBeVisible();
  current={...baseRun,status:'fixing',root_cause:'Updated snapshot'};
  await emit(page,'step_updated');await expect(page.getByText('Updated snapshot')).toBeVisible();
  await emit(page,'step_updated');await expect(page.locator('.review-timeline li')).toHaveCount(1);
  await expect(page.getByText('● Live')).toBeVisible();await waitForStream(page);
  await emit(page,'error');await expect(page.getByText('Reconnecting…')).toBeVisible();
  current={...current,root_cause:'Snapshot after reconnect'};
  await emit(page,'open');await expect(page.getByText('Snapshot after reconnect')).toBeVisible();await expect(page.getByText('● Live')).toBeVisible();
  current={...current,status:'completed'};await emit(page,'run_status_changed');
  await expect(page.getByText('● Live')).toHaveCount(0);
  await expect.poll(()=>page.evaluate(()=>(window as StreamWindow).__streams.filter(s=>!s.closed).length)).toBe(0);
});

test('slower older snapshot cannot overwrite a newer one',async({page})=>{
  await mockEventSource(page);let response:'initial'|'slow'|'fast'='initial';
  await page.route('**/api/runs/test-run-1',async route=>{
    const value=response;
    if(value==='slow')await new Promise(resolve=>setTimeout(resolve,3000));
    await route.fulfill({json:{...baseRun,root_cause:value}});
  });
  await page.goto('/dashboard/runs/test-run-1');await waitForStream(page);
  await expect(page.getByText('initial',{exact:true})).toBeVisible();
  response='slow';const slowRequest=page.waitForRequest('**/api/runs/test-run-1');await emit(page,'step_updated');await slowRequest;
  response='fast';await emit(page,'step_updated');await expect(page.getByText('fast',{exact:true})).toBeVisible();
  await page.waitForTimeout(3300);await expect(page.getByText('fast',{exact:true})).toBeVisible();
  await expect(page.getByText('slow',{exact:true})).toHaveCount(0);
});

test('refresh failure retains last data and can be retried',async({page})=>{
  await mockEventSource(page);let fail=false;
  await page.route('**/api/runs/test-run-1',route=>fail?route.fulfill({status:500,body:'internal'}):route.fulfill({json:baseRun}));
  await page.goto('/dashboard/runs/test-run-1');await waitForStream(page);await emit(page,'open');await expect(page.getByText('● Live')).toBeVisible();
  fail=true;await emit(page,'step_updated');await expect(page.getByText('Couldn’t refresh run data.')).toBeVisible();
  await expect(page.getByText('Initial snapshot')).toBeVisible();await expect(page.getByText('● Live')).toBeVisible();
  fail=false;await page.getByRole('button',{name:'Try again'}).click();await expect(page.getByText('Couldn’t refresh run data.')).toHaveCount(0);
});

test('session expiry during refresh removes the run and closes the stream',async({page})=>{
  await mockEventSource(page);let signedOut=false;
  await page.route('**/api/runs/test-run-1',route=>signedOut?route.fulfill({status:401,body:'not signed in'}):route.fulfill({json:baseRun}));
  await page.goto('/dashboard/runs/test-run-1');await waitForStream(page);
  signedOut=true;await emit(page,'step_updated');
  await expect(page.getByText('Sign in with GitHub to view run details.')).toBeVisible();
  await expect(page.getByText('Initial snapshot')).toHaveCount(0);
  await expect.poll(()=>page.evaluate(()=>(window as StreamWindow).__streams.filter(s=>!s.closed).length)).toBe(0);
});

test('event bursts are coalesced and the latest terminal snapshot is still shown',async({page})=>{
  await page.clock.install();await mockEventSource(page);let requests=0;let current={...baseRun};
  await page.route('**/api/runs/test-run-1',route=>{requests++;return route.fulfill({json:current})});
  await page.goto('/dashboard/runs/test-run-1');await waitForStream(page);await expect(page.getByText('Initial snapshot')).toBeVisible();
  requests=0;await emit(page,'step_updated');await expect.poll(()=>requests).toBe(1);
  current={...baseRun,status:'completed',root_cause:'Latest coalesced snapshot'};
  for(let i=0;i<8;i++)await emit(page,'step_updated');
  expect(requests).toBe(1);
  await page.clock.fastForward(2001);await expect(page.getByText('Latest coalesced snapshot')).toBeVisible();
  expect(requests).toBe(2);
  await expect.poll(()=>page.evaluate(()=>(window as StreamWindow).__streams.filter(s=>!s.closed).length)).toBe(0);
});

test('a queued refresh is cancelled when leaving the run',async({page})=>{
  await page.clock.install();await mockEventSource(page);let requests=0;
  await page.route('**/api/runs/test-run-1',route=>{requests++;return route.fulfill({json:baseRun})});
  await page.goto('/dashboard/runs/test-run-1');await waitForStream(page);await expect(page.getByText('Initial snapshot')).toBeVisible();
  requests=0;await emit(page,'step_updated');await expect.poll(()=>requests).toBe(1);
  await emit(page,'step_updated');await page.goto('/login');
  await page.clock.fastForward(2500);expect(requests).toBe(1);
});
