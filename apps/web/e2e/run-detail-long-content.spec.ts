import {test,expect} from '@playwright/test';

// The snapshot is mocked; this tests presentation, not real backend integration.
const longText='longunbrokencontent'.repeat(30);
const run={id:'long-content',repository_full_name:'owner/'+('repository'.repeat(25)),issue_number:42,issue_title:'Issue '+longText,status:'completed',confidence:'high',pr_url:null,test_output:'Output '+longText,root_cause:'Cause '+longText,issue_body:'Body '+longText,created_at:'2026-01-01T00:00:00Z',steps:[{id:'step1',step:'read',status:'completed',output:'Step '+longText,error:null}]};
for(const width of [360,768]){
  test(`long run text does not create page overflow at ${width}px`,async({page})=>{
    await page.setViewportSize({width,height:900});
    await page.route('**/api/runs/long-content',route=>route.fulfill({json:run}));
    await page.goto('/dashboard/runs/long-content');
    await expect(page.getByRole('heading',{level:1})).toHaveText(run.issue_title);
    await expect(page.getByText(run.root_cause)).toBeVisible();
    await expect(page.getByText(run.issue_body)).toBeVisible();
    await page.locator('.step-details summary').first().click();
    await expect(page.getByText('Step '+longText)).toBeVisible();
    expect(await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:window.innerWidth}))).toEqual({width,viewport:width});
  });
}
