export type RunStatus='pending'|'reproducing'|'fixing'|'verifying'|'completed'|'failed'|'could_not_reproduce';
export type Step={id:string;step:string;status:'pending'|'running'|'completed'|'failed';output:string|null;error:string|null};
export type Run={id:string;repository_full_name:string;issue_number:number;issue_title:string;issue_body?:string;status:RunStatus;confidence:string|null;pr_url:string|null;test_output?:string|null;root_cause?:string|null;created_at:string;steps?:Step[]};
export type PageResult={data:Run[];next_cursor:string|null;has_more:boolean};
export class ApiError extends Error{constructor(public status:number){super(`API error ${status}`)}}
export async function api<T>(path:string, options?:RequestInit):Promise<T>{const r=await fetch(`/api${path}`,{...options,credentials:'same-origin',cache:'no-store'});if(!r.ok)throw new ApiError(r.status);return r.json() as Promise<T>}
export function safeGithubUrl(value:string|null):string|null {if(!value)return null;try{const u=new URL(value);return u.protocol==='https:'&&u.hostname==='github.com'?u.href:null}catch{return null}}
export function prettyStatus(status:string){return ({could_not_reproduce:"Couldn't reproduce",completed:'PR opened',pending:'Pending',reproducing:'Reproducing',fixing:'Fixing',verifying:'Verifying',failed:'Failed'} as Record<string,string>)[status]||status}
