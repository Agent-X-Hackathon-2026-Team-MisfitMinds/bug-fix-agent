import {afterEach, describe, expect, it, vi} from 'vitest';
import {api, ApiError, prettyStatus, safeGithubUrl} from '../src/lib/api';
import {sampleRuns} from '../src/lib/sample-data';

afterEach(()=>vi.unstubAllGlobals());
describe('GitHub links',()=>{
  it('allows only HTTPS links to github.com',()=>{
    expect(safeGithubUrl('https://github.com/owner/repo/pull/1')).toBe('https://github.com/owner/repo/pull/1');
    for(const value of [null,'http://github.com/owner/repo','https://github.com.evil.example/x','javascript:alert(1)','not-a-url']) expect(safeGithubUrl(value)).toBeNull();
  });
});
describe('API client',()=>{
  it('requests the same-origin proxy with credentials and no cache',async()=>{
    const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({authenticated:true})});vi.stubGlobal('fetch',fetch);
    expect(await api('/auth/session')).toEqual({authenticated:true});
    expect(fetch).toHaveBeenCalledWith('/api/auth/session',expect.objectContaining({credentials:'same-origin',cache:'no-store'}));
  });
  it('surfaces HTTP status without exposing server internals',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:404}));
    await expect(api('/runs/example')).rejects.toMatchObject({status:404});
    expect(new ApiError(401).message).toBe('API error 401');
  });
});
describe('run presentation',()=>{
  it('labels the unreproduced state',()=>expect(prettyStatus('could_not_reproduce')).toBe("Couldn't reproduce"));
  it('never invents proof or a pull request for the unreproduced example',()=>{
    const run=sampleRuns.find(item=>item.status==='could_not_reproduce');
    expect(run).toBeDefined();expect(run?.pr_url).toBeNull();expect(run?.test_output).toBeNull();expect(run?.confidence).toBeNull();
  });
  it('uses the six documented steps in order',()=>{
    expect(sampleRuns[0].steps?.map(step=>step.step)).toEqual(['read','reproduce','diagnose','fix','verify','pr']);
  });
});
