// Executed by live_game_checks.py against real Uvicorn/PostgreSQL, with fixture Twitch only.
import assert from 'node:assert/strict';
import {createDashboardAPI} from '../../apps/dashboard/api.mjs';
import {createCaptionQueue} from '../../apps/dashboard/caption-collector.mjs';
import {createTwitchAdapter} from '../../public/api-adapter.mjs';
const base=process.env.FULLSTACK_TEST_BASE, channel=process.env.FULLSTACK_TEST_CHANNEL;
assert(base?.startsWith('http://127.0.0.1:') && /^\d+$/.test(channel));
const cookies=new Map();
async function cookieFetch(path,options={}) {
 const response=await fetch(path,{...options,redirect:'manual',headers:{...options.headers,Cookie:[...cookies].map(([key,value])=>key+'='+value).join('; ')}});
 for(const value of response.headers.getSetCookie()) { const first=value.split(';')[0], split=first.indexOf('=');cookies.set(first.slice(0,split),first.slice(split+1)); }
 return response;
}
const login=await cookieFetch(base+'/api/v1/auth/twitch');assert.equal(login.status,302);
const state=new URL(login.headers.get('location')).searchParams.get('state');
const callback=await cookieFetch(base+'/api/v1/auth/twitch/callback?'+new URLSearchParams({state,code:channel}));assert.equal(callback.status,200);
const api=createDashboardAPI({base:base+'/api/v1',fetcher:cookieFetch});
const identity=await api.session();assert.equal(identity.selected_workspace.role,'owner');assert.equal(identity.workspaces[0].login,'user'+channel);
let snapshot=await api.request('/dashboard/channels/'+channel);
assert(snapshot.stream_id); assert.equal(snapshot.game.status,'active');
const queue=createCaptionQueue({send:body=>api.request('/streams/'+snapshot.stream_id+'/transcript-batches',{method:'POST',body})});
queue.push('The incredible championship finished with a brilliant victory for our team.');await queue.flush();assert.equal(queue.pending,0);
snapshot=await api.request('/dashboard/channels/'+channel);assert(snapshot.candidates.length>0);
const round=await api.command('/games/'+snapshot.game.game_id+'/rounds',snapshot.game.version);
const selected=snapshot.candidates.find(candidate=>candidate.prompt===round.round.prompt);assert(selected);
let authorize;
const extension={viewer:{isLinked:true,id:'fixture-viewer'},onAuthorized:fn=>authorize=fn};
const viewer=createTwitchAdapter({extension,apiBaseUrl:base+'/api/v1',pollMs:1e6,isDocumentHidden:()=>false});
let stateView;viewer.subscribe(value=>stateView=value);
try {
 authorize({channelId:channel,token:process.env.FULLSTACK_TEST_VIEWER_TOKEN});
 await viewer.refresh();assert.equal(stateView.roundId,round.round.round_id);
 assert.equal(stateView.results,null);
 await viewer.submit('definitely incorrect');assert.equal(stateView.ownSubmission.answer,'definitely incorrect');
 await viewer.submit(selected.canonical_answer);assert.equal(stateView.ownSubmission.answer,selected.canonical_answer);
 await viewer.refresh();assert.equal(stateView.ownSubmission.answer,selected.canonical_answer);
 const deadline=new Date(round.round.closes_at).getTime();
 while(Date.now()<deadline+1000) await new Promise(resolve=>setTimeout(resolve,500));
 for(let i=0;i<10;i++){await viewer.refresh();if(stateView.phase==='results')break;await new Promise(resolve=>setTimeout(resolve,500));}
 assert.equal(stateView.results.pointsAwarded,1);assert.equal(stateView.results.revealedAnswer,selected.canonical_answer);assert.equal(stateView.ownStanding.score,1);
 const latest=await api.request('/dashboard/channels/'+channel);
 await api.command('/games/'+latest.game.game_id+'/end',latest.game.version);await viewer.refresh();
 assert.equal(stateView.gameStatus,'ended');assert.equal(stateView.finalLeaderboard[0].score,1);
 console.log('Actual dashboard API + caption queue + viewer JS: OAuth, source intake, prompt, private answer/edit, deadline, correct score, reconnect and final board passed.');
 await api.logout();await assert.rejects(api.session(),{status:401});
} finally {viewer.dispose();}
