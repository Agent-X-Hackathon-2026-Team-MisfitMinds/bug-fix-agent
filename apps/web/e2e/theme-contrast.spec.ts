import {test,expect} from '@playwright/test';

test('theme switch applies button colours together without an in-between background',async({page})=>{
  await page.emulateMedia({colorScheme:'light'});
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true}}));
  await page.route('**/api/runs',route=>route.fulfill({json:{data:[],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();
  const colours=await page.getByRole('button',{name:'Dark appearance'}).evaluate(el=>{
    (el as HTMLButtonElement).click();
    const button=document.querySelector('.section-head .ui-button');
    if(!button)throw new Error('Missing sign-out button');
    const style=getComputedStyle(button);return {background:style.backgroundColor,color:style.color};
  });
  expect(colours.background).toBe('rgb(45, 38, 33)');
  expect(colours.color).toBe('rgb(250, 242, 232)');
});
