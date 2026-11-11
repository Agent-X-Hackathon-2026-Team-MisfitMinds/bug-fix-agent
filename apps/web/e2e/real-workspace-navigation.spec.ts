import {test,expect} from '@playwright/test';
import {injectAxe,getViolations} from 'axe-playwright';

// Simulated API responses: this does not test real authentication or backend ownership.
const run={id:'nav-run',repository_full_name:'owner/repo',issue_number:42,issue_title:'Mock run',status:'completed',confidence:null,pr_url:null,created_at:'2026-01-01T00:00:00Z',steps:[]};
test('real dashboard navigation stays separate from demo data',async({page})=>{
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true,github_login:'test-user'}}));
  await page.route('**/api/runs/nav-run',route=>route.fulfill({json:run}));
  await page.route('**/api/runs',route=>route.fulfill({json:{data:[run],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');const nav=page.getByRole('navigation',{name:'App navigation'});
  await expect(nav.getByRole('link',{name:'Your runs'})).toHaveAttribute('href','/dashboard');
  await expect(nav.getByRole('link',{name:'Your runs'})).toHaveAttribute('aria-current','page');
  await expect(nav.getByRole('link',{name:'Repositories'})).toHaveCount(0);
  await expect(page.getByText('Example workspace',{exact:true})).toHaveCount(0);
  await page.getByRole('link',{name:/Mock run/}).click();await expect(page).toHaveURL(/\/dashboard\/runs\/nav-run$/);
  await expect(page.getByRole('link',{name:'View demo workspace'})).toHaveAttribute('href','/workspace');
  await nav.getByRole('link',{name:'Your runs'}).click();await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByRole('link',{name:'View demo workspace'}).click();await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByText('Example workspace',{exact:true})).toBeVisible();await expect(page.getByText('Demo mode',{exact:true})).toBeVisible();
});

test('real dashboard shell works on mobile in both themes',async({page})=>{
  await page.setViewportSize({width:360,height:800});await page.emulateMedia({reducedMotion:'reduce'});
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true}}));
  await page.route('**/api/runs',route=>route.fulfill({json:{data:[],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');await expect(page.getByText('No runs yet.')).toBeVisible();
  const nav=page.getByRole('navigation',{name:'App navigation'});const link=nav.getByRole('link',{name:'Your runs'});
  const box=await link.boundingBox();expect(box!.height).toBeGreaterThanOrEqual(44);expect(box!.width).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  for(const theme of ['light','dark']){
    await page.evaluate(t=>{document.documentElement.dataset.theme=t},theme);
    await injectAxe(page);const violations=await getViolations(page,undefined,{axeOptions:{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}});
    expect(violations.map(v=>`${v.id}: ${v.nodes.length}`),theme).toEqual([]);
  }
});
