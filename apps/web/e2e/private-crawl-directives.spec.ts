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

test('robots.txt disallows the private application routes',async({request})=>{
  const response=await request.get('/robots.txt');
  expect(response.ok()).toBe(true);
  const text=await response.text();
  for(const path of ['/dashboard','/auth/','/api/']){
    expect(text.split(/\r?\n/).some(line=>line.trim()===`Disallow: ${path}`),path).toBe(true);
  }
});

test('sitemap does not list private application routes',async({request})=>{
  const response=await request.get('/sitemap.xml');
  expect(response.ok()).toBe(true);
  const xml=await response.text();
  const locations=Array.from(xml.matchAll(/<loc>\s*([^<]+)\s*<\/loc>/g),match=>new URL(match[1].trim()).pathname);
  expect(locations.length).toBeGreaterThan(0);
  expect(locations.filter(path=>/^\/(dashboard|auth|api)(\/|$)/.test(path))).toEqual([]);
});
