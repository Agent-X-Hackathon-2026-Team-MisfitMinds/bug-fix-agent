import {Dashboard} from '@/components/dashboard';
import type {Metadata} from 'next';
export const metadata:Metadata={title:'Dashboard',robots:{index:false,follow:false}};
export default function DashboardPage(){return <Dashboard/>}
