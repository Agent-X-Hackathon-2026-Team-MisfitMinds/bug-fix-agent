import {test,expect} from '@playwright/test';

// API data is mocked; these tests check crawler directives, not access control.
for(const path of ['/dashboard','/dashboard/runs/crawl-test']){
  test(`${path} emits noindex and nofollow`,async({page})=>{
    await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true,github_login:'test-user'}}));
    await page.route('**/api/runs/crawl-test',route=>route.fulfill({json:{id:'crawl-test',repository_full_name:'owner/repo',issue_number:1,issue_title:'Mock run',status:'completed',confidence:null,pr_url:null,created_at:'2026-01-01T00:00:00Z',steps:[]}}));
    await page.route('**/api/runs',route=>route.fulfill({json:{data:[],next_cursor:null,has_more:false}}));
    await page.goto(path);
    const robots=page.locator('meta[name="robots"]');
    await expect(robots).toHaveAttribute('content',/\bnoindex\b/i);
    await expect(robots).toHaveAttribute('content',/\bnofollow\b/i);
  });
}

