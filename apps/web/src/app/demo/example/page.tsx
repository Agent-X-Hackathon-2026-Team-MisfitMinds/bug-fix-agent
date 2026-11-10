import type {Metadata} from 'next';
import {SampleRun} from '@/components/sample-run';
export const metadata:Metadata={title:'Example run',description:'Explore an illustrative Fixie run and its evidence.',robots:{index:false,follow:false}};
export default async function ExamplePage({searchParams}:{searchParams:{issue?:string}}){const params=searchParams;const n=Number(params.issue);return <SampleRun initial={Number.isInteger(n)&&n>=1&&n<=3?n-1:0}/>}
