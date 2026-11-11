import {test,expect} from '@playwright/test';

// Dashboard data is mocked; this checks keyboard presentation, not real authentication.
test('app controls use the focus token with a 2px ring and 2px offset in both themes',async({page})=>{
  await page.setViewportSize({width:360,height:800});await page.emulateMedia({colorScheme:'light',reducedMotion:'reduce'});
  await page.route('**/api/auth/session',route=>route.fulfill({json:{authenticated:true}}));
  await page.route('**/api/runs',route=>route.fulfill({json:{data:[],next_cursor:null,has_more:false}}));
  await page.goto('/dashboard');await expect(page.getByText('No runs yet.')).toBeVisible();
  for(const theme of ['light','dark']){
    if(theme==='dark')await page.getByRole('button',{name:'Dark appearance'}).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
    await page.keyboard.press('Tab');
    for(const control of [page.getByRole('link',{name:'Your runs'}),page.getByRole('button',{name:'Sign out'}),page.locator('.sidebar-bottom button')]){
      await control.focus();await expect(control).toBeFocused();
      const style=await control.evaluate(el=>{
        const css=getComputedStyle(el);const token=getComputedStyle(document.documentElement).getPropertyValue('--ds-border-focus').trim();
        const probe=document.createElement('span');probe.style.color=token;document.body.appendChild(probe);
        const color=getComputedStyle(probe).color;probe.remove();
        return {token,focusVisible:el.matches(':focus-visible'),color:css.outlineColor,tokenColor:color,width:parseFloat(css.outlineWidth),offset:parseFloat(css.outlineOffset),style:css.outlineStyle};
      });
      expect(style.token,theme).not.toBe('');expect(style.focusVisible,theme).toBe(true);
      expect(style.style,theme).not.toBe('none');expect(style.color,theme).toBe(style.tokenColor);
      expect(style.width,theme).toBe(2);expect(style.offset,theme).toBe(2);
    }
  }
});
