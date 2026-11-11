import {test,expect} from '@playwright/test';
import {injectAxe,getViolations} from 'axe-playwright';

test('theme follows system preference and user choice persists after refresh',async({page})=>{
  await page.emulateMedia({colorScheme:'dark'});
  await page.goto('/workspace');
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await page.getByRole('button',{name:'Light appearance'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme','light');
  expect(await page.evaluate(()=>localStorage.getItem('theme'))).toBe('light');
  await page.reload();await expect(page.locator('html')).toHaveAttribute('data-theme','light');
  await page.getByRole('button',{name:'Dark appearance'}).click();
  await page.reload();await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
});

test('keyboard can navigate the app shell with a visible focus indicator',async({page,browserName})=>{
  // Windows Playwright WebKit skips ordinary links during Tab navigation.
  test.skip(browserName==='webkit'&&process.platform==='win32','Windows WebKit skips links on Tab; see frontend setup notes.');
  await page.goto('/workspace');
  const repo=page.getByRole('navigation',{name:'App navigation'}).getByRole('link',{name:'Repositories'});
  for(let i=0;i<12;i++){if(await repo.evaluate(el=>el===document.activeElement))break;await page.keyboard.press('Tab')}
  await expect(repo).toBeFocused();
  const focus=await repo.evaluate(el=>({visible:el.matches(':focus-visible'),style:getComputedStyle(el).outlineStyle,width:parseFloat(getComputedStyle(el).outlineWidth)}));
  expect(focus.visible).toBe(true);expect(focus.style).not.toBe('none');expect(focus.width).toBeGreaterThanOrEqual(2);
  await page.keyboard.press('Enter');await expect(page).toHaveURL(/\/workspace\/repositories$/);
  await expect(page.getByRole('navigation',{name:'App navigation'}).getByRole('link',{name:'Repositories'})).toHaveAttribute('aria-current','page');
});

test('mobile navigation has no horizontal overflow and shell actions are at least 44px',async({page})=>{
  await page.setViewportSize({width:360,height:800});await page.goto('/workspace');
  const nav=page.getByRole('navigation',{name:'App navigation'});
  for(const name of ['Dashboard','Repositories','Runs']){
    const link=nav.getByRole('link',{name});const box=await link.boundingBox();expect(box, name).not.toBeNull();expect(box!.height,name).toBeGreaterThanOrEqual(44);expect(box!.width,name).toBeGreaterThanOrEqual(44);
  }
  for(const locator of [page.locator('.sidebar-bottom button'),page.locator('.sidebar-bottom a')]){
    const box=await locator.boundingBox();expect(box).not.toBeNull();expect(box!.height).toBeGreaterThanOrEqual(44);expect(box!.width).toBeGreaterThanOrEqual(44);
  }
  for(const [name,path] of [['Repositories','/workspace/repositories'],['Runs','/workspace/runs'],['Dashboard','/workspace']] as const){
    await nav.getByRole('link',{name}).click();await expect(page).toHaveURL(new RegExp(path+'$'));
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),path).toBeTruthy();
  }
});

test('reduced motion preference removes transitions',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/workspace');
  const transition=await page.getByRole('link',{name:'Browse repositories'}).evaluate(el=>getComputedStyle(el).transitionDuration);
  expect(transition.split(',').every(part=>parseFloat(part)===0)).toBe(true);
});

test('mobile app navigation passes automated axe checks in both themes',async({page})=>{
  await page.setViewportSize({width:360,height:800});await page.emulateMedia({colorScheme:'light'});await page.goto('/workspace');
  for(const theme of ['light','dark']){
    if(theme==='dark')await page.getByRole('button',{name:'Dark appearance'}).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
    await injectAxe(page);
    const violations=await getViolations(page,undefined,{axeOptions:{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}});
    expect(violations.map(v=>`${v.id}: ${v.nodes.length}`),theme).toEqual([]);
  }
});
