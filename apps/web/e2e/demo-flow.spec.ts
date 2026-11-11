import {test,expect} from '@playwright/test';
import {injectAxe,getViolations} from 'axe-playwright';

test('demo journey from sign-in to issue evidence',async({page})=>{
  await page.goto('/'); await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('button',{name:/Continue with GitHub/})).toBeDisabled();
  await page.getByRole('link',{name:'Open demo workspace'}).click();
  await expect(page.getByRole('heading',{name:'Good to see you.'})).toBeVisible();
  await page.getByRole('link',{name:'Browse repositories'}).click();
  await page.getByRole('link',{name:/fixie-demo.*seeded-repo/}).click();
  await page.getByRole('link',{name:/Off-by-one/}).click();
  await expect(page.getByRole('heading',{name:'Test evidence'})).toBeVisible();
  await expect(page.getByText('Simulated data:',{exact:false})).toBeVisible();
  await page.getByText('View test output').click();
  await expect(page.getByText('Illustrative output — not an actual test run.')).toBeVisible();
  await page.locator('summary').filter({hasText:'Read'}).click();
  await expect(page.getByText('Read the issue and its expected behavior.')).toBeVisible();
});
test('unreproduced example does not show a fake proof or PR',async({page})=>{
  await page.goto('/workspace/runs/sample-3');
  await expect(page.getByRole('heading',{name:'Couldn’t reproduce the issue'})).toBeVisible();
  await expect(page.getByText('No test output available')).toBeVisible();
  await expect(page.locator('.proof-pair')).toHaveCount(0);
  await expect(page.getByRole('link',{name:/Review draft PR/})).toHaveCount(0);
});
test('filters and searches example runs',async({page})=>{
  await page.goto('/workspace/runs');await expect(page.locator('.run-row')).toHaveCount(3);
  await page.getByRole('button',{name:'Ready for review'}).click();await expect(page.locator('.run-row')).toHaveCount(2);
  await page.getByRole('button',{name:'Couldn’t reproduce'}).click();await expect(page.locator('.run-row')).toHaveCount(1);
  await page.getByLabel('Search runs').fill('not-found');await expect(page.getByText('No matching runs')).toBeVisible();
  await page.getByRole('button',{name:'Clear filters'}).click();await expect(page.locator('.run-row')).toHaveCount(3);
});
for(const width of [360,1440]) test(`demo pages have no horizontal overflow at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:900});
  for(const path of ['/login','/workspace','/workspace/repositories','/workspace/repositories/demo','/workspace/runs','/workspace/runs/sample-1','/workspace/runs/sample-3']){
    await page.goto(path);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),path).toBeTruthy();
  }
});
test('key demo routes pass axe WCAG A/AA checks',async({page})=>{
  for(const path of ['/login','/workspace','/workspace/repositories','/workspace/repositories/demo','/workspace/runs','/workspace/runs/sample-1','/workspace/runs/sample-3']){
    await page.goto(path);await injectAxe(page);
    const violations=await getViolations(page,undefined,{axeOptions:{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}});
    expect(violations.map(v=>`${v.id}: ${v.nodes.length}`),path).toEqual([]);
  }
});
