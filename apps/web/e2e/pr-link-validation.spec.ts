import {test,expect} from '@playwright/test';
// All responses are mocked. A valid-looking URL does not prove a PR exists or is a draft.
const base={id:'mock-pr',repository_full_name:'owner/repo',issue_number:42,issue_title:'Mock issue',status:'completed',confidence:null,created_at:'2026-01-01T00:00:00Z',steps:[]};
test('a GitHub repository or issue URL is not presented as a pull request',async({page})=>{
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true}}));
  await page.route('**/api/runs/mock-pr',route=>route.fulfill({json:{...base,pr_url:'https://github.com/owner/repo/issues/1'}}));
  await page.route('**/api/runs',route=>route.fulfill({json:{data:[{...base,pr_url:'https://github.com/owner/repo/issues/1'}],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');await expect(page.getByRole('row').filter({hasText:'Mock issue'}).getByText('Completed',{exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:/View draft PR/})).toHaveCount(0);
  await page.getByRole('link',{name:/Mock issue/}).click();await expect(page.getByRole('heading',{name:'Run completed'})).toBeVisible();
  await expect(page.getByText('No usable pull request link has been reported.')).toBeVisible();
  await expect(page.getByRole('link',{name:/Review draft PR/})).toHaveCount(0);
});
test('a well-formed GitHub PR URL can be presented without altering the URL',async({page})=>{
  const url='https://github.com/owner/repo/pull/123';
  await page.route('**/api/runs/mock-pr',route=>route.fulfill({json:{...base,pr_url:url}}));
  await page.goto('/dashboard/runs/mock-pr');
  await expect(page.getByRole('heading',{name:'Ready for human review'})).toBeVisible();
  await expect(page.getByRole('link',{name:/Review draft PR/})).toHaveAttribute('href',url);
});
