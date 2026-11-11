import Link from 'next/link';
export default function NotFound(){return <div className="wrap page"><span className="eyebrow">404</span><h1>Page not found</h1><p className="muted">That page doesn’t exist or may have moved.</p><Link className="button primary" href="/">Go home</Link></div>}
