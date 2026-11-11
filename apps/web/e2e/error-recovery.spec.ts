import {test,expect} from '@playwright/test';

// Network fixtures are mocked; these checks do not verify the real API.
test('an unknown page shows a helpful 404 with a way home',async({page})=>{
  const response=await page.goto('/definitely-not-a-fixie-page');
  expect(response?.status()).toBe(404);
  await expect(page.getByRole('heading',{name:'Page not found'})).toBeVisible();
  await expect(page.getByRole('link',{name:'Go home',exact:true})).toHaveAttribute('href','/');
  await expect(page.locator('body')).not.toContainText('Error:');
});

test('maintenance page explains the outage and offers a way home',async({page})=>{
  await page.goto('/maintenance');
  await expect(page.getByRole('heading',{name:'We’ll be back soon.'})).toBeVisible();
  await expect(page.getByText('Fixie is temporarily unavailable while we work on it.')).toBeVisible();
  await expect(page.getByRole('link',{name:'Go home',exact:true})).toHaveAttribute('href','/');
});

test('offline retry shows a message and sends no request; online retry can proceed',async({page,context})=>{
  const run={id:'offline-retry',repository_full_name:'owner/repo',issue_number:42,issue_title:'Failed mock run',status:'failed',confidence:null,pr_url:null,test_output:null,root_cause:null,created_at:'2026-01-01T00:00:00Z',steps:[]};
  let retries=0;
  await page.route('**/api/runs/offline-retry/retry',route=>{retries++;return route.fulfill({json:{}})});
  await page.route('**/api/runs/offline-retry',route=>route.fulfill({json:run}));
  await page.goto('/dashboard/runs/offline-retry');
  const retry=page.getByRole('button',{name:'Retry run'});await expect(retry).toBeVisible();
  await context.setOffline(true);await expect(page.getByText('You’re offline.',{exact:false})).toBeVisible();
  await retry.click();await expect(page.getByRole('alert').filter({hasText:'You’re offline.'})).toBeVisible();
  expect(retries).toBe(0);
  await context.setOffline(false);await retry.click();
  await expect.poll(()=>retries).toBe(1);
  await expect(page.getByText('Retry queued.')).toBeVisible();
});
