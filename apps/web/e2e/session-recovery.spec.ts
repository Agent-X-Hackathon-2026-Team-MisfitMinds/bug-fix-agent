import {test,expect} from '@playwright/test';
// These tests mock API responses; they do not validate server authentication or ownership.
const run={id:'recover-run',repository_full_name:'owner/private-repo',issue_number:42,issue_title:'Private mocked issue',status:'failed',confidence:null,pr_url:null,created_at:'2026-01-01T00:00:00Z',steps:[]};
for(const status of [401,403]){
  test(`pagination ${status} removes previously loaded private runs`,async({page})=>{
    await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true,github_login:'mock-user'}}));
    await page.route('**/api/runs*',route=>new URL(route.request().url()).searchParams.has('cursor')?route.fulfill({status,body:'private backend error'}):route.fulfill({json:{data:[run],next_cursor:'next',has_more:true}}));
    await page.goto('/dashboard');await expect(page.getByText(run.issue_title)).toBeVisible();await page.getByRole('button',{name:'Load more'}).click();
    if(status===401)await expect(page.getByText('Sign in with GitHub to see your runs.')).toBeVisible();
    else await expect(page.getByText('You don’t have access to this repository’s runs.')).toBeVisible();
    await expect(page.getByText(run.issue_title)).toHaveCount(0);await expect(page.getByText(run.repository_full_name)).toHaveCount(0);await expect(page.getByText('private backend error')).toHaveCount(0);
  });
}
test('expired session during sign-out clears loaded runs',async({page})=>{
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true,github_login:'mock-user'}}));
  await page.route('**/api/auth/logout',route=>route.fulfill({status:401,body:'expired'}));
  await page.route('**/api/runs',route=>route.fulfill({json:{data:[run],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');await expect(page.getByText(run.issue_title)).toBeVisible();await page.getByRole('button',{name:/Sign out/}).click();
  await expect(page.getByText('Sign in with GitHub to see your runs.')).toBeVisible();await expect(page.getByText(run.issue_title)).toHaveCount(0);
});
for(const status of [401,403,404]){
  test(`retry ${status} removes the previously loaded run`,async({page})=>{
    await page.route('**/api/runs/recover-run/retry',route=>route.fulfill({status,body:'private backend error'}));
    await page.route('**/api/runs/recover-run',route=>route.fulfill({json:run}));
    await page.goto('/dashboard/runs/recover-run');await expect(page.getByRole('heading',{name:run.issue_title})).toBeVisible();await page.getByRole('button',{name:'Retry run'}).click();
    if(status===401)await expect(page.getByText('Sign in with GitHub to view run details.')).toBeVisible();
    else if(status===403)await expect(page.getByText('You don’t have permission to view this run.')).toBeVisible();
    else await expect(page.getByText('No run found for recover-run.')).toBeVisible();
    await expect(page.getByText(run.issue_title)).toHaveCount(0);await expect(page.getByText(run.repository_full_name)).toHaveCount(0);await expect(page.getByText('private backend error')).toHaveCount(0);
  });
}
