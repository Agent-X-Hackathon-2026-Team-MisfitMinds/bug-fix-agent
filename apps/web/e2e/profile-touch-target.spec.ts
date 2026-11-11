import {test,expect} from '@playwright/test';

for(const width of [360,768,1280]){
  test(`workspace sign-in profile link has a 44px touch target at ${width}px`,async({page})=>{
    await page.setViewportSize({width,height:800});
    await page.goto('/workspace');
    const link=page.getByRole('link',{name:'Go to sign in'});
    await expect(link).toBeVisible();
    const box=await link.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThanOrEqual(44);
    expect(box!.height).toBeGreaterThanOrEqual(44);
    await expect(link).toHaveAttribute('href','/login');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await link.click();
    await expect(page).toHaveURL(/\/login$/);
  });
}
