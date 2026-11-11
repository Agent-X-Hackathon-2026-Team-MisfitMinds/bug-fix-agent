import Link from 'next/link';
import {notFound} from 'next/navigation';
import {sampleRuns} from '@/lib/sample-data';
import {RunView} from '@/components/run-view';
export default async function SamplePage({params}:{params:Promise<{sampleId:string}>}){const {sampleId}=await params;const run=sampleRuns.find(r=>r.id===sampleId);if(!run)notFound();return <div className="wrap run-page"><Link href="/workspace/runs" className="run-back">← <span>All runs</span></Link><div className="run-heading"><div><span className="review-overline">RUN OVERVIEW <span className="heading-separator">/</span> ISSUE #{run.issue_number}</span><h1>{run.issue_title}</h1><p>{run.repository_full_name} <span>·</span> Issue #{run.issue_number}</p></div><span className="example-label">Example run</span></div><div className="run-demo-note"><span>i</span> Simulated data: results and test output are not real evidence.</div><RunView run={run} illustrative/></div>}
