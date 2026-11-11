import {describe,it,expect,vi} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import type {ReactElement} from 'react';
import ErrorPage from '../src/app/error';

describe('error page fallback',()=>{
  it('renders a helpful message without leaking error details',()=>{
    const error=new Error('sensitive internal details');
    const html=renderToStaticMarkup(ErrorPage({error,reset:()=>{}}));
    expect(html).toContain('Something went wrong');
    expect(html).toContain('Try again');
    expect(html).not.toContain('sensitive internal details');
    expect(html).not.toContain(error.stack!);
  });
  it('wires the retry button to the provided reset callback',()=>{
    const reset=vi.fn();
    const tree=ErrorPage({error:new Error('test'),reset});
    const children=tree.props.children as ReactElement<{onClick?:()=>void}>[];
    const button=children.find(child=>child.type==='button');
    expect(button).toBeDefined();
    expect(button?.props.onClick).toBe(reset);
    button?.props.onClick?.();
    expect(reset).toHaveBeenCalledOnce();
  });
});
