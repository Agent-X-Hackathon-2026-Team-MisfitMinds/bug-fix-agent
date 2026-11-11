import {test,expect} from '@playwright/test';
import {injectAxe,getViolations} from 'axe-playwright';

const example={id:'test-run-1',repository_full_name:'test-owner/test-repo',issue_number:42,issue_title:'Mocked issue',status:'completed',confidence:null,pr_url:null,created_at:'2026-01-01T00:00:00Z',steps:[]};

test('reusable button has keyboard focus, a 44px target and prevents double actions while loading',async({page})=>{
  await page.setViewportSize({width:360,height:800});
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true}}));
  await page.route('**/api/runs*',async route=>{
    if(new URL(route.request().url()).searchParams.has('cursor')){
      await new Promise(resolve=>setTimeout(resolve,800));await route.fulfill({json:{data:[],next_cursor:null,has_more:false}});
    }else await route.fulfill({json:{data:[example],next_cursor:'next',has_more:true}});
  });
  await page.goto('/dashboard');const button=page.getByRole('button',{name:'Load more'});await expect(button).toBeVisible();
  const box=await button.boundingBox();expect(box).not.toBeNull();expect(box!.width).toBeGreaterThanOrEqual(44);expect(box!.height).toBeGreaterThanOrEqual(44);
  for(let i=0;i<35;i++){if(await button.evaluate(el=>el===document.activeElement))break;await page.keyboard.press('Tab')}
  await expect(button).toBeFocused();
  const focus=await button.evaluate(el=>({visible:el.matches(':focus-visible'),width:parseFloat(getComputedStyle(el).outlineWidth),offset:parseFloat(getComputedStyle(el).outlineOffset)}));
  expect(focus.visible).toBe(true);expect(focus.width).toBe(2);expect(focus.offset).toBe(2);
  await page.keyboard.press('Enter');const loading=page.getByRole('button',{name:'Loading…'});
  await expect(loading).toBeDisabled();await expect(loading).toHaveAttribute('aria-busy','true');
  await expect(loading).toHaveCount(0);
});

test('reusable empty state passes automated axe checks in light and dark modes',async({page})=>{
  await page.setViewportSize({width:360,height:800});await page.emulateMedia({colorScheme:'light'});
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true}}));
  await page.route('**/api/runs',route=>route.fulfill({json:{data:[],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');await expect(page.getByText('No runs yet.')).toBeVisible();
  for(const theme of ['light','dark']){
    if(theme==='dark')await page.getByRole('button',{name:'Dark appearance'}).click();
    await injectAxe(page);const violations=await getViolations(page,undefined,{axeOptions:{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}});
    expect(violations.map(v=>`${v.id}: ${JSON.stringify(v.nodes.map(n=>({html:n.html,summary:n.failureSummary})))}`),theme).toEqual([]);
  }
});
