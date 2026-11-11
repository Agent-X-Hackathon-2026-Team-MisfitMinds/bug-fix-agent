import {test, expect, type Page} from '@playwright/test';

// All responses below are intercepted test fixtures, not real GitHub or backend data.
const run = {
  id:'test-run-1', repository_full_name:'test-owner/test-repo', issue_number:42,
  issue_title:'Example issue from mocked API', status:'completed', confidence:null,
  pr_url:null, test_output:null, root_cause:null, created_at:'2026-01-01T00:00:00Z', steps:[],
};
async function session(page:Page, authenticated=true){
  await page.route('**/api/auth/session', route=>route.fulfill({json:{authenticated,github_login:'test-user'}}));
}

test('dashboard loading then empty, signed-out and permission states', async ({page})=>{
  await session(page);
  await page.route('**/api/runs', async route=>{await new Promise(resolve=>setTimeout(resolve,350));await route.fulfill({json:{data:[],next_cursor:null,has_more:false}})});
  await page.goto('/dashboard');
  await expect(page.getByRole('status').filter({hasText:'Loading your runs'})).toBeVisible();
  await expect(page.getByText('No runs yet.')).toBeVisible();
  await page.unroute('**/api/auth/session'); await session(page,false);
  await page.reload(); await expect(page.getByText('Sign in with GitHub to see your runs.')).toBeVisible();
  await page.unroute('**/api/auth/session');
  await page.route('**/api/auth/session',route=>route.fulfill({status:403,body:'forbidden'}));
  await page.reload();await expect(page.getByText('You don’t have access to this repository’s runs.')).toBeVisible();
});

test('dashboard error can be retried without showing internal details',async({page})=>{
  await session(page);let fail=true;
  await page.route('**/api/runs',route=>fail?route.fulfill({status:500,body:'secret internal error'}):route.fulfill({json:{data:[],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');await expect(page.getByRole('heading',{name:'Couldn’t load runs. Try again.'})).toBeVisible();
  await expect(page.getByText('secret internal error')).toHaveCount(0);
  fail=false;await page.getByRole('button',{name:'Try again'}).click();await expect(page.getByText('No runs yet.')).toBeVisible();
});

test('dashboard lists runs, handles pagination failure, and does not invent PRs',async({page})=>{
  await session(page);await page.route('**/api/runs*',route=>{
    const url=new URL(route.request().url());
    return url.searchParams.has('cursor')?route.fulfill({status:500,body:'error'}):route.fulfill({json:{data:[run],next_cursor:'next',has_more:true}});
  });
  await page.goto('/dashboard');await expect(page.getByText(run.issue_title)).toBeVisible();
  await expect(page.locator('tr').filter({hasText:run.issue_title}).getByText('Completed',{exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:/View draft PR/})).toHaveCount(0);
  await page.getByRole('button',{name:'Load more'}).click();
  await expect(page.getByRole('alert').filter({hasText:"Couldn't load more runs"})).toBeVisible();await expect(page.getByText(run.issue_title)).toBeVisible();
});

test('offline dashboard retains already loaded data',async({page,context})=>{
  await session(page);await page.route('**/api/runs',route=>route.fulfill({json:{data:[run],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');await expect(page.getByText(run.issue_title)).toBeVisible();
  await context.setOffline(true);await expect(page.getByText('You’re offline.',{exact:false})).toBeVisible();await expect(page.getByText(run.issue_title)).toBeVisible();
  await context.setOffline(false);await expect(page.getByText('You’re offline.',{exact:false})).toHaveCount(0);
});

test('run detail shows loading then missing, signed-out and forbidden states',async({page})=>{
  let status=404;
  await page.route('**/api/runs/test-run-1',async route=>{await new Promise(resolve=>setTimeout(resolve,250));await route.fulfill({status,body:'error'})});
  await page.goto('/dashboard/runs/test-run-1');await expect(page.getByRole('status').filter({hasText:'Loading run test-run-1'})).toBeVisible();
  await expect(page.getByText('No run found for test-run-1.')).toBeVisible();
  status=401;await page.reload();await expect(page.getByText('Sign in with GitHub to view run details.')).toBeVisible();
  status=403;await page.reload();await expect(page.getByText('You don’t have permission to view this run.')).toBeVisible();
});

test('run detail recovers from an error and does not invent evidence or a PR',async({page})=>{
  let fail=true;await page.route('**/api/runs/test-run-1',route=>fail?route.fulfill({status:500,body:'internal details'}):route.fulfill({json:run}));
  await page.goto('/dashboard/runs/test-run-1');await expect(page.getByRole('heading',{name:'Couldn’t load this run. Try again.'})).toBeVisible();
  fail=false;await page.getByRole('button',{name:'Try again'}).click();await expect(page.getByRole('heading',{name:run.issue_title})).toBeVisible();
  await expect(page.getByText('No test output available')).toBeVisible();await expect(page.getByText('No usable pull request link has been reported.')).toBeVisible();
  await expect(page.getByRole('link',{name:/Review draft PR/})).toHaveCount(0);
  await expect(page.locator('.actions').getByText('Completed',{exact:true})).toBeVisible();
});

test('run detail retains last loaded state when offline',async({page,context})=>{
  await page.route('**/api/runs/test-run-1',route=>route.fulfill({json:run}));
  await page.goto('/dashboard/runs/test-run-1');await expect(page.getByRole('heading',{name:run.issue_title})).toBeVisible();
  await context.setOffline(true);await expect(page.getByText('You’re offline.',{exact:false})).toBeVisible();await expect(page.getByRole('heading',{name:run.issue_title})).toBeVisible();
  await context.setOffline(false);await expect(page.getByText('You’re offline.',{exact:false})).toHaveCount(0);
});
