import {test,expect} from '@playwright/test';

// These pages use demo data or mocked API responses; deployed behavior is not covered.
for(const path of ['/workspace','/dashboard','/dashboard/runs/motion-test']){
  test(`${path} disables animation and transition durations for reduced motion`,async({page})=>{
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true}}));
    await page.route('**/api/runs/motion-test',route=>route.fulfill({json:{id:'motion-test',repository_full_name:'owner/repo',issue_number:1,issue_title:'Mock run',status:'completed',confidence:null,pr_url:null,created_at:'2026-01-01T00:00:00Z',steps:[]}}));
    await page.route('**/api/runs',route=>route.fulfill({json:{data:[],next_cursor:null,has_more:false}}));
    await page.goto(path);
    if(path==='/dashboard')await expect(page.getByText('No runs yet.')).toBeVisible();
    if(path.includes('motion-test'))await expect(page.getByRole('heading',{name:'Mock run'})).toBeVisible();
    const nonzero=await page.locator('body').evaluate(body=>{
      const bad:string[]=[];
      for(const el of [body,...body.querySelectorAll('*')]){
        for(const pseudo of [null,'::before','::after']){
          const css=getComputedStyle(el,pseudo);
          for(const [name,value] of [['transition',css.transitionDuration],['animation',css.animationDuration]]){
            if(value.split(',').some(part=>parseFloat(part)>0))bad.push(`${el.tagName}${pseudo||''} ${name}=${value}`);
          }
        }
      }
      return bad;
    });
    expect(nonzero).toEqual([]);
  });
}
