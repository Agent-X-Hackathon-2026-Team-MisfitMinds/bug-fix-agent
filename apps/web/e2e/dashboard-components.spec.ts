import {test,expect} from '@playwright/test';
import {injectAxe,getViolations} from 'axe-playwright';

// The runs and all API responses in this test are simulated.
const base={repository_full_name:'test-owner/test-repo',issue_number:42,confidence:null,pr_url:null,created_at:'2026-01-01T00:00:00Z',steps:[]};
const states=[['pending','Pending','neutral'],['reproducing','Reproducing','neutral'],['fixing','Fixing','neutral'],['verifying','Verifying','neutral'],['completed','Completed','success'],['failed','Failed','error'],['could_not_reproduce',"Couldn't reproduce",'warning']] as const;

test('dashboard status badges are clear, use text and pass automated accessibility checks',async({page})=>{
  await page.setViewportSize({width:360,height:800});await page.emulateMedia({reducedMotion:'reduce'});
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true,github_login:'mock-user'}}));
  await page.route('**/api/runs',route=>route.fulfill({json:{data:states.map(([status],i)=>({...base,id:`mock-${i}`,issue_title:`Mock issue ${i}`,status})),next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');
  for(const [i,[,label,tone]] of states.entries()){
    const row=page.getByRole('row').filter({hasText:`Mock issue ${i}`});
    await expect(row.locator('.badge')).toHaveText(label);await expect(row.locator('.badge')).toHaveClass(new RegExp(`ui-status-${tone}`));
  }
  const signout=page.getByRole('button',{name:/Sign out/});const box=await signout.boundingBox();expect(box!.width).toBeGreaterThanOrEqual(44);expect(box!.height).toBeGreaterThanOrEqual(44);
  for(const theme of ['light','dark']){
    await page.evaluate(t=>{document.documentElement.dataset.theme=t},theme);
    await injectAxe(page);const violations=await getViolations(page,undefined,{axeOptions:{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}});
    expect(violations.map(v=>`${v.id}: ${JSON.stringify(v.nodes.map(n=>({html:n.html,summary:n.failureSummary})))}`),theme).toEqual([]);
  }
});

test('retry action exposes loading and prevents repeated requests',async({page})=>{
  let retryCount=0;
  await page.route('**/api/runs/mock/retry',async route=>{retryCount++;await new Promise(resolve=>setTimeout(resolve,900));await route.fulfill({json:{ok:true}})});
  await page.route('**/api/runs/mock',route=>route.fulfill({json:{...base,id:'mock',issue_title:'Mock failed run',status:'failed'}}));
  await page.goto('/dashboard/runs/mock');const button=page.getByRole('button',{name:'Retry run'});await expect(button).toBeVisible();
  const box=await button.boundingBox();expect(box!.width).toBeGreaterThanOrEqual(44);expect(box!.height).toBeGreaterThanOrEqual(44);
  await button.click();const loading=page.getByRole('button',{name:'Retrying…'});
  await expect(loading).toBeDisabled();await expect(loading).toHaveAttribute('aria-busy','true');
  await expect(page.getByText('Retry queued.')).toBeVisible();expect(retryCount).toBe(1);
});
