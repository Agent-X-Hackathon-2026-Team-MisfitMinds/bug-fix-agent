'use client';
export default function ErrorPage({reset}:{error:Error;reset:()=>void}){return <div className="wrap page"><span className="eyebrow">ERROR</span><h1>Something went wrong</h1><p className="muted">Please try again.</p><button className="button primary" onClick={reset}>Try again</button></div>}
