import {test,expect} from '@playwright/test';

// Mocked requests only: the real server's idempotency and rate limits require integration tests.
const run={id:'retry-check',repository_full_name:'owner/repo',issue_number:42,issue_title:'Mock failed run',status:'failed',confidence:null,pr_url:null,created_at:'2026-01-01T00:00:00Z',steps:[]};
for(const failure of ['network', 'rate-limit'] as const){
  test(`retry retains the idempotency key after ${failure} and gives useful feedback`,async({page})=>{
    const keys:string[]=[];
    await page.route('**/api/runs/retry-check',route=>route.fulfill({json:run}));
    await page.route('**/api/runs/retry-check/retry',route=>{
      keys.push(route.request().headers()['idempotency-key']||'');
      if(keys.length===1){
        if(failure==='network')return route.abort('failed');
        return route.fulfill({status:429,json:{error:{code:'RATE_LIMITED',message:'internal details'}}});
      }
      return route.fulfill({json:{status:'retry_queued',run_id:'retry-check'}});
    });
    await page.goto('/dashboard/runs/retry-check');
    const retry=page.getByRole('button',{name:'Retry run'});await retry.click();
    const error=failure==='network'?'Couldn’t retry this run. Try again.':'Too many retry attempts. Please wait before trying again.';
    await expect(page.getByRole('alert').filter({hasText:error})).toBeVisible();
    await expect(page.getByText('internal details')).toHaveCount(0);
    await retry.click();await expect(page.getByText('Retry queued.')).toBeVisible();
    expect(keys).toHaveLength(2);expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/i);expect(keys[1]).toBe(keys[0]);
  });
}

test('a retry conflict prompts a status check and a later attempt gets a new key',async({page})=>{
  const keys:string[]=[];
  await page.route('**/api/runs/retry-check',route=>route.fulfill({json:run}));
  await page.route('**/api/runs/retry-check/retry',route=>{
    keys.push(route.request().headers()['idempotency-key']||'');
    return keys.length===1?route.fulfill({status:409,json:{error:{code:'CONFLICT',message:'sensitive server detail'}}}):route.fulfill({json:{status:'retry_queued',run_id:'retry-check'}});
  });
  await page.goto('/dashboard/runs/retry-check');const retry=page.getByRole('button',{name:'Retry run'});
  await retry.click();
  await expect(page.getByRole('alert').filter({hasText:'This run could not be retried. Refresh the page to check its status.'})).toBeVisible();
  await expect(page.getByText('sensitive server detail')).toHaveCount(0);
  await retry.click();await expect(page.getByText('Retry queued.')).toBeVisible();
  expect(keys).toHaveLength(2);expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/i);expect(keys[1]).not.toBe(keys[0]);
});
