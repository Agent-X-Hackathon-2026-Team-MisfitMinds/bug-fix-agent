import {describe,it,expect} from 'vitest';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {Button,Card,EmptyState,Skeleton,StatusBadge,Toast} from '../src/components/ui';

describe('Button',()=>{
  it('renders a non-submit action by default',()=>{const html=renderToStaticMarkup(h(Button,{},'Retry'));expect(html).toContain('type="button"');expect(html).toContain('Retry')});
  it('supports a primary button and native disabled state',()=>{const html=renderToStaticMarkup(h(Button,{variant:'primary',disabled:true},'Continue'));expect(html).toContain('primary');expect(html).toContain('disabled=""')});
  it('renders a danger action',()=>{const html=renderToStaticMarkup(h(Button,{variant:'danger'},'Delete'));expect(html).toContain('ui-button-danger')});
  it('prevents repeat actions while loading and exposes busy state',()=>{const html=renderToStaticMarkup(h(Button,{loading:true},'Loading…'));expect(html).toContain('disabled=""');expect(html).toContain('aria-busy="true"')});
});
describe('Card',()=>{
  it('renders its content and extra attributes',()=>{const html=renderToStaticMarkup(h(Card,{'aria-label':'Summary',className:'extra'},'Hello'));expect(html).toContain('card extra');expect(html).toContain('aria-label="Summary"');expect(html).toContain('Hello')});
});
describe('Skeleton',()=>{
  it('announces loading and hides decorative placeholders',()=>{const html=renderToStaticMarkup(h(Skeleton,{label:'Loading runs…'}));expect(html).toContain('role="status"');expect(html).toContain('Loading runs…');expect(html).toContain('aria-hidden="true"')});
});
describe('EmptyState',()=>{
  it('shows the title, explanation and action',()=>{const html=renderToStaticMarkup(h(EmptyState,{title:'No runs yet.',action:h('a',{href:'/how-it-works'},'Learn more')},'Add the label.'));expect(html).toContain('No runs yet.');expect(html).toContain('Add the label.');expect(html).toContain('href="/how-it-works"')});
  it('escapes untrusted text',()=>{const html=renderToStaticMarkup(h(EmptyState,{title:'<script>alert(1)</script>'},'Text'));expect(html).not.toContain('<script>');expect(html).toContain('&lt;script&gt;')});
});
describe('Toast',()=>{
  it('uses a status announcement for information',()=>expect(renderToStaticMarkup(h(Toast,{onDismiss:()=>{}},'Saved'))).toContain('role="status"'));
  it('uses an alert announcement for an error',()=>expect(renderToStaticMarkup(h(Toast,{tone:'error',onDismiss:()=>{}},'Try again'))).toContain('role="alert"'));
});
describe('StatusBadge',()=>{
  it('renders each supported tone and keeps the status in text',()=>{for(const tone of ['neutral','success','warning','error'] as const){const html=renderToStaticMarkup(h(StatusBadge,{label:`Status ${tone}`,tone}));expect(html).toContain(`Status ${tone}`);expect(html).toContain(`ui-status-${tone}`);if(tone==='error'||tone==='warning')expect(html).toContain(tone)}});
});
