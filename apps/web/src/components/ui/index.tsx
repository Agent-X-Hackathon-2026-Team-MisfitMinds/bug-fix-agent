import React from 'react';
import type {ButtonHTMLAttributes, HTMLAttributes, ReactNode} from 'react';

type ButtonProps=ButtonHTMLAttributes<HTMLButtonElement>&{variant?:'primary'|'secondary'|'danger';loading?:boolean};
/** Use for actions, not navigation. Loading buttons cannot be activated twice. */
export function Button({variant='secondary',loading=false,disabled,children,className='',type='button',...props}:ButtonProps){
  return <button {...props} type={type} className={`button ui-button ${variant==='primary'?'primary':variant==='danger'?'ui-button-danger':''} ${className}`.trim()} disabled={disabled||loading} aria-busy={loading||undefined}>{children}</button>;
}
export function Card({children,className='',...props}:HTMLAttributes<HTMLDivElement>){
  return <div {...props} className={`card ${className}`.trim()}>{children}</div>;
}
export function Skeleton({label='Loading…'}:{label?:string}){
  return <div className="notice" role="status">{label}<div className="state-skeleton" aria-hidden="true"><span/><span/><span/></div></div>;
}
export function EmptyState({title,children,action}:{title:string;children:ReactNode;action?:ReactNode}){
  return <Card><h2>{title}</h2><p>{children}</p>{action}</Card>;
}
export {Toast} from './toast';
type BadgeTone='neutral'|'success'|'warning'|'error';
export function StatusBadge({label,tone='neutral'}:{label:string;tone?:BadgeTone}){
  return <span className={`badge ${tone==='warning'?'warning':tone==='error'?'error':''}`.trim()}>{label}</span>;
}
