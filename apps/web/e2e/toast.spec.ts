import {test,expect} from '@playwright/test';
import {injectAxe,getViolations} from 'axe-playwright';

// All API responses in these tests are mocked; no real retry is started.
const failedRun={id:'toast-test',repository_full_name:'test-owner/test-repo',issue_number:42,issue_title:'Mocked failed run',status:'failed',confidence:null,pr_url:null,created_at:'2026-01-01T00:00:00Z',steps:[]};

test('success notification pauses on hover and focus and dismisses after remaining time',async({page})=>{
  await page.clock.install();
  await page.route('**/api/runs/toast-test/retry',route=>route.fulfill({json:{ok:true}}));
  await page.route('**/api/runs/toast-test',route=>route.fulfill({json:failedRun}));
  await page.goto('/dashboard/runs/toast-test');
  await page.getByRole('button',{name:'Retry run'}).click();
  const toast=page.locator('.ui-toast');await expect(toast.getByRole('status')).toHaveText('Retry queued.');
  await page.clock.fastForward(2000);
  await toast.hover();await page.clock.fastForward(7000);await expect(toast).toBeVisible();
  const close=toast.getByRole('button',{name:'Dismiss notification'});await close.focus();
  await page.mouse.move(0,0);await page.clock.fastForward(7000);await expect(toast).toBeVisible();
  await close.blur();await page.clock.fastForward(4000);await expect(toast).toHaveCount(0);
});

test('error notification stays visible and can be dismissed by keyboard',async({page})=>{
  await page.clock.install();await page.setViewportSize({width:360,height:800});
  await page.route('**/api/runs/toast-test/retry',route=>route.fulfill({status:500,body:'server error'}));
  await page.route('**/api/runs/toast-test',route=>route.fulfill({json:failedRun}));
  await page.goto('/dashboard/runs/toast-test');await page.getByRole('button',{name:'Retry run'}).click();
  const toast=page.locator('.ui-toast');await expect(toast.getByRole('alert')).toHaveText('Couldn’t retry this run. Try again.');
  await page.clock.fastForward(10000);await expect(toast).toBeVisible();
  const close=toast.getByRole('button',{name:'Dismiss notification'});const box=await close.boundingBox();expect(box!.width).toBeGreaterThanOrEqual(44);expect(box!.height).toBeGreaterThanOrEqual(44);
  for(const theme of ['light','dark']){
    await page.evaluate(t=>{document.documentElement.dataset.theme=t},theme);
    await injectAxe(page);const violations=await getViolations(page,undefined,{axeOptions:{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}});
    expect(violations.map(v=>`${v.id}: ${v.nodes.length}`),theme).toEqual([]);
  }
  await close.focus();await expect(close).toBeFocused();await page.keyboard.press('Enter');await expect(toast).toHaveCount(0);
});
