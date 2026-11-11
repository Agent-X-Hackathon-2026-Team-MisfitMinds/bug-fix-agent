import {test,expect} from '@playwright/test';

// Real-dashboard test data is mocked; this does not test the backend.
const run={id:'touch-run',repository_full_name:'owner/repo',issue_number:42,issue_title:'Mock run for touch testing',status:'completed',confidence:null,pr_url:null,test_output:'Mock test output',root_cause:null,created_at:'2026-01-01T00:00:00Z',steps:[{id:'step-1',step:'read',status:'completed',output:'Mock read output',error:null}]};
for(const width of [360,1440]){
  test(`demo run detail controls have 44px targets and work with the keyboard at ${width}px`,async({page})=>{
    await page.setViewportSize({width,height:900});
    await page.goto('/workspace/runs/sample-1');
    const output=page.locator('.full-output summary');
    const steps=page.locator('.step-details summary');
    await expect(steps).toHaveCount(6);
    for(const control of [output,...await steps.all()]){
      const box=await control.boundingBox();expect(box).not.toBeNull();
      expect(box!.width).toBeGreaterThanOrEqual(44);expect(box!.height).toBeGreaterThanOrEqual(44);
    }
    const step=steps.first();await step.focus();await expect(step).toBeFocused();
    await page.keyboard.press('Enter');await expect(step.locator('..')).toHaveAttribute('open','');
    await expect(page.getByText('Read the issue and its expected behavior.')).toBeVisible();
    await page.keyboard.press('Enter');await expect(step.locator('..')).not.toHaveAttribute('open');
  });
}
test('mocked real run detail has 44px output and step controls on mobile',async({page})=>{
  await page.setViewportSize({width:360,height:900});
  await page.route('**/api/runs/touch-run',route=>route.fulfill({json:run}));
  await page.goto('/dashboard/runs/touch-run');
  await expect(page.getByRole('heading',{name:run.issue_title})).toBeVisible();
  for(const control of [page.locator('.full-output summary'),page.locator('.step-details summary')]){
    const box=await control.boundingBox();expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThanOrEqual(44);expect(box!.height).toBeGreaterThanOrEqual(44);
  }
});
