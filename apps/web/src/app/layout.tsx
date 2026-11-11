import type { Metadata } from 'next';
import './globals.css';
import { Shell } from '@/components/shell';
const base=process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
export const metadata: Metadata = { metadataBase:new URL(base),title:{default:'Bug-Fix Agent: GitHub Issues → Tested PRs',template:'%s | Fixie'},description:'Add the agent-fix label to a GitHub issue. The agent reproduces the bug, writes a test, and opens a draft PR with red→green proof.',openGraph:{type:'website',title:'Fixie — proof before patch',description:'Turn GitHub issues into tested draft pull requests.'},twitter:{card:'summary_large_image'} };
const script=`try{var t=localStorage.getItem('theme');document.documentElement.dataset.theme=t||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}catch(e){}`;
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:script}} /></head><body><Shell>{children}</Shell></body></html>}
