import {test,expect} from '@playwright/test';
import {injectAxe,getViolations} from 'axe-playwright';

// Simulated run snapshots: this does not exercise real auth or backend data.
const run={id:'accessibility-run',repository_full_name:'owner/repo',issue_number:42,issue_title:'Mock issue',status:'completed',confidence:'high',pr_url:'https://github.com/owner/repo/pull/123',test_output:'Before: failing test\nAfter: passing test',root_cause:'A mocked diagnosis.',created_at:'2026-01-01T00:00:00Z',steps:[{id:'step-1',step:'read',status:'completed',output:'Mock output',error:null},{id:'step-2',step:'verify',status:'completed',output:'Tests passed',error:null}]};
for(const status of ['completed','failed'] as const){
  test(`mock ${status} run detail has no automated axe violations at mobile width in both themes`,async({page})=>{
    await page.setViewportSize({width:360,height:800});
    await page.emulateMedia({colorScheme:'light',reducedMotion:'reduce'});
    await page.route('**/api/runs/accessibility-run',route=>route.fulfill({json:{...run,status,pr_url:status==='completed'?run.pr_url:null}}));
    await page.goto('/dashboard/runs/accessibility-run');
    await expect(page.getByRole('heading',{name:run.issue_title})).toBeVisible();
    for(const theme of ['light','dark']){
      if(theme==='dark')await page.getByRole('button',{name:'Dark appearance'}).click();
      await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),theme).toBe(true);
      await injectAxe(page);
      const violations=await getViolations(page,undefined,{axeOptions:{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}});
      expect(violations.map(v=>`${v.id}: ${JSON.stringify(v.nodes.map(n=>({html:n.html,summary:n.failureSummary})))}`),theme).toEqual([]);
    }
  });
}
