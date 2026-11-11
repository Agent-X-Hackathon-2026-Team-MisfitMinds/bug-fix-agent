import {test,expect} from '@playwright/test';

test('demo run filters have 44px targets and work with a keyboard at mobile width',async({page})=>{
  await page.setViewportSize({width:360,height:800});
  await page.goto('/workspace/runs');
  const group=page.getByRole('group',{name:'Filter runs'});
  const buttons=group.getByRole('button');await expect(buttons).toHaveCount(3);
  for(const button of await buttons.all()){
    const box=await button.boundingBox();expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThanOrEqual(44);expect(box!.height).toBeGreaterThanOrEqual(44);
  }
  const filter=group.getByRole('button',{name:'Couldn’t reproduce'});
  await filter.focus();await expect(filter).toBeFocused();
  await page.keyboard.press('Enter');await expect(filter).toHaveAttribute('aria-pressed','true');
  await expect(page.locator('.run-row')).toHaveCount(1);
});
