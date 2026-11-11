'use client';
import React, {useEffect, useRef, useState} from 'react';
import type {ReactNode} from 'react';

type ToastProps = {children:ReactNode; tone?:'info'|'error'; onDismiss:()=>void; duration?:number};
/** Informational messages auto-dismiss. Errors stay until dismissed. */
export function Toast({children,tone='info',onDismiss,duration=5000}:ToastProps){
  const [hovered,setHovered]=useState(false);
  const [focused,setFocused]=useState(false);
  const remaining=useRef(duration);
  const dismiss=useRef(onDismiss);
  dismiss.current=onDismiss;
  useEffect(()=>{
    if(tone==='error'||hovered||focused||duration<=0)return;
    const start=Date.now();
    const timer=window.setTimeout(()=>dismiss.current(),remaining.current);
    return ()=>{window.clearTimeout(timer);remaining.current=Math.max(0,remaining.current-(Date.now()-start))};
  },[tone,hovered,focused,duration]);
  return <div className={`ui-toast ${tone==='error'?'ui-toast-error':''}`}
    onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}
    onFocus={()=>setFocused(true)} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node|null))setFocused(false)}}>
    <div role={tone==='error'?'alert':'status'}>{children}</div>
    <button type="button" className="ui-toast-dismiss" aria-label="Dismiss notification" onClick={onDismiss}>×</button>
  </div>;
}
