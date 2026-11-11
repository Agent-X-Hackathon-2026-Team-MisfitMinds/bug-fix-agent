import {test,expect} from '@playwright/test';

// Demo data and API responses are mocked.
test('empty dashboard links to the demo workspace, not the removed marketing page',async({page})=>{
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true}}));
  await page.route('**/api/runs',route=>route.fulfill({json:{data:[],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');
  const link=page.getByRole('link',{name:'Explore demo workspace'});
  await expect(link).toHaveAttribute('href','/workspace');
  await link.click();
  await expect(page).toHaveURL(/\/workspace$/);
});

test('example run returns to the demo workspace',async({page})=>{
  await page.goto('/demo/example');
  const link=page.getByRole('link',{name:'Back to workspace'});
  await expect(link).toHaveAttribute('href','/workspace');
  await link.click();
  await expect(page).toHaveURL(/\/workspace$/);
});
