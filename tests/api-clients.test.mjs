import test from 'node:test';
import assert from 'node:assert/strict';
import {createDashboardAPI} from '../apps/dashboard/api.mjs';
import {createCaptionQueue} from '../apps/dashboard/caption-collector.mjs';
import {createTwitchAdapter, normalizeSnapshot, mapStanding} from '../public/api-adapter.mjs';
import {resolveAsset, createAppHandler} from '../scripts/app-handler.mjs';
import {createServer} from 'node:http';
const json = (value,status=200) => new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
test('dashboard uses cookie credentials, current CSRF, and propagates permission failures', async () => {
  const calls=[];
  const api=createDashboardAPI({fetcher:async (path,options) => {calls.push({path,options});
    if(path.includes('/auth/me')) return json({csrf_token:'test-csrf',selected_workspace:{permissions:['live_control']}});
    if(path.endsWith('/logout')) return new Response(null,{status:204});
    return json({error:{code:'forbidden',message:'Grant was revoked'}},403);
  }});
  await api.session('90001'); assert.equal(api.allowed('settings'),false); assert.equal(api.allowed('live_control'),true);
  await assert.rejects(api.command('/games/test/rounds',12),{status:403,code:'forbidden'});
  assert.equal(calls[1].options.credentials,'include'); assert.equal(calls[1].options.headers['X-CSRF-Token'],'test-csrf');
  const body=JSON.parse(calls[1].options.body); assert.equal(body.expected_version,12); assert.match(body.request_id,/^[a-f0-9-]{36}$/);
  await api.logout(); assert.equal(api.identity,null);
});
test('caption retries preserve exact source text, UUID, sequence and observation time',async () => {
  const calls=[]; let fail=true;
  const queue=createCaptionQueue({uuid:()=> 'stable-test-id',now:()=> '2026-11-02T12:00:00Z',send:async value=>{calls.push(structuredClone(value));if(fail)throw new Error('offline');}});
  queue.push('  original caption text  '); await queue.flush(); assert.equal(queue.pending,1);
  fail=false; await Promise.all([queue.flush(),queue.flush()]); assert.equal(queue.pending,0);
  assert.deepEqual(calls[0],calls[1]); assert.equal(calls.length,2); assert.equal(calls[1].segments[0].text,'  original caption text  ');
  queue.stop(); queue.push('ignored'); assert.equal(queue.pending,0);
});
function helper() {
 let authorized, listener, changed;
 return {ext:{viewer:{isLinked:true,id:'90002',onChanged:fn=>changed=fn},onAuthorized:fn=>authorized=fn,listen:(_topic,fn)=>listener=fn},
 authorize:value=>authorized(value), broadcast:value=>listener('broadcast','application/json',JSON.stringify(value)), changed:()=>changed()};
}
const tick=()=>new Promise(resolve=>setTimeout(resolve,10));
test('viewer maps runtime state, sends private retry-safe answers and displays actual points',async()=>{
 const h=helper(), calls=[]; let phase='answering', failed=false;
 const adapter=createTwitchAdapter({extension:h.ext,apiBaseUrl:'https://api.test/api/v1',pollMs:1e6,isDocumentHidden:()=>false,fetcher:async(path,opts)=>{
  calls.push({path,opts});
  if(path.endsWith('/answers')) {if(!failed){failed=true;throw new Error('network');}return json({status:'received'},202);}
  if(path.endsWith('/game-state'))return json({channel_id:'90001',game_id:'game-1',status:'active',version:phase==='answering'?1:2,round:{round_id:'round-1',phase,prompt:'A ____ wins.',closes_at:'2026-11-02T12:00:30Z',canonical_answer:phase==='results'?'spoon':undefined}});
  if(path.endsWith('/me'))return json({answer:' raw answer ',receipt:failed?{status:'received'}:null,result:phase==='results'?{outcome:'correct',awarded_points:1}:null});
  if(path.endsWith('/leaderboard'))return json({entries:[{participant_id:'90002',display_name:'Viewer',rank:1,points:1}],own_entry:{participant_id:'90002',display_name:'Viewer',rank:1,points:1}});
  throw new Error('Unexpected request '+path);
 }});
 let latest; adapter.subscribe(value=>latest=value);
 try {
  h.authorize({token:'test-jwt',channelId:'90001'});await tick();assert.equal(latest.roundId,'round-1');
  await assert.rejects(adapter.submit(' raw answer '),/network/);await adapter.submit(' raw answer ');
  const answers=calls.filter(value=>value.path.endsWith('/answers')); assert.deepEqual(JSON.parse(answers[0].opts.body),JSON.parse(answers[1].opts.body));
  assert.equal(JSON.parse(answers[1].opts.body).answer,' raw answer ');assert.equal(answers[1].opts.headers.Authorization,'Bearer test-jwt');assert.equal(answers[1].opts.credentials,'omit');
  phase='results';h.broadcast({event:'game_state_changed',channel_id:'other',version:2});await tick();assert.equal(latest.phase,'answering');
  h.broadcast({event:'game_state_changed',channel_id:'90001',version:2});await tick();assert.equal(latest.results.pointsAwarded,1);assert.equal(latest.results.revealedAnswer,'spoon');assert.equal(latest.leaderboard[0].score,1);assert.equal(latest.leaderboard[0].isYou,true);
 }finally{adapter.dispose();}
});
test('runtime state does not invent a five-round game or treat unrevealed data as results',()=>{
 const state=normalizeSnapshot({game_id:null,status:'idle',version:0,round:null});assert.equal(state.status,'idle');assert.equal(state.roundCount,undefined);assert.equal(state.results,null);
 assert.equal(mapStanding({participant_id:'a',display_name:'A',rank:3,points:2},'b').isYou,false);
});
test('unified server serves both clients and proxies cookies/CSRF without exposing private files',async()=>{
 const received=[];
 const backend=createServer((req,res)=>{received.push({url:req.url,csrf:req.headers['x-csrf-token'],cookie:req.headers.cookie});res.writeHead(200,{'Content-Type':'application/json','Set-Cookie':'test_session=opaque; HttpOnly; SameSite=Lax'});res.end('{"ok":true}');});
 await new Promise(resolve=>backend.listen(0,'127.0.0.1',resolve));
 const server=createServer(createAppHandler({apiOrigin:`http://127.0.0.1:${backend.address().port}`}));
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base=`http://127.0.0.1:${server.address().port}`;
 try {
  const page=await fetch(base+'/');assert.match(await page.text(),/live-start/);
  assert.equal((await fetch(base+'/viewer.html')).status,200);
  assert.match((await fetch(base+'/api-adapter.mjs')).headers.get('content-type'),/javascript/);
  assert.equal((await fetch(base+'/backend/.env')).status,403);
  assert.equal(resolveAsset('/dashboard/%5c..%5c.env'),null);
  const result=await fetch(base+'/api/v1/example',{method:'POST',headers:{Cookie:'test_session=opaque','X-CSRF-Token':'csrf'},body:'{}'});
  assert.match(result.headers.get('set-cookie'),/HttpOnly/);assert.deepEqual(received,[{url:'/api/v1/example',csrf:'csrf',cookie:'test_session=opaque'}]);
 }finally{server.closeAllConnections();backend.closeAllConnections();await Promise.all([new Promise(resolve=>server.close(resolve)),new Promise(resolve=>backend.close(resolve))]);}
});
test('a late workspace response cannot replace the newly selected identity',async()=>{
 const waiting=new Map();
 const api=createDashboardAPI({fetcher:path=>new Promise(resolve=>waiting.set(path,resolve))});
 const older=api.session('90001'), newer=api.session('90002');
 waiting.get('/api/v1/auth/me?channel_id=90002')(json({selected_workspace:{channel_id:'90002',permissions:['settings']}}));await newer;
 waiting.get('/api/v1/auth/me?channel_id=90001')(json({selected_workspace:{channel_id:'90001',permissions:['live_control']}}));await older;
 assert.equal(api.identity.selected_workspace.channel_id,'90002');assert.equal(api.allowed('live_control'),false);
});

// Twitch CDN assets live below an extension/version prefix, not at the host root.
test('native viewer assets resolve under a hosted Extension version prefix', async () => {
 const handler=createAppHandler(); const prefix='/extension/version/';
 const server=createServer((req,res)=>{
  if(!req.url.startsWith(prefix)){res.writeHead(404).end();return;}
  req.url='/'+req.url.slice(prefix.length);return handler(req,res);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base=`http://127.0.0.1:${server.address().port}${prefix}`;
 try {
  for(const page of ['viewer.html','mobile.html']){
   const html=await(await fetch(base+page)).text();
   for(const [,asset]of html.matchAll(/(?:src|href)="([^"]+)"/g)){
    if(asset.startsWith('https://'))continue;
    const url=new URL(asset,base+page);
    assert.ok(url.pathname.startsWith(prefix),asset);
    assert.equal((await fetch(url)).status,200,asset);
   }
  }
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
