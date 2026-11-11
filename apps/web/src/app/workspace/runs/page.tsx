import {Workspace} from '@/components/workspace';
import type {Metadata} from 'next';
export const metadata:Metadata={title:'Example runs',robots:{index:false,follow:false}};
export default function RunsPage(){return <Workspace/>}
