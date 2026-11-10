import {RunDetail} from '@/components/dashboard';
import type {Metadata} from 'next';
export const metadata:Metadata={title:'Run details',robots:{index:false,follow:false}};
export default async function RunPage({params}:{params:{runId:string}}){const {runId}=params;return <RunDetail id={runId}/>}
