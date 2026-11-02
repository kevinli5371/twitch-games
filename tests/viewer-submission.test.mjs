import test from 'node:test';
import assert from 'node:assert/strict';
import {createTwitchAdapter} from '../public/api-adapter.mjs';

const response = (body, status=200) => new Response(JSON.stringify(body), {status});
const state = (roundId, phase, version) => ({
  version, game_id:'sample-game', status:'active',
  round:{round_id:roundId, phase, prompt:'A ____ prompt.',
    ...(phase === 'results' ? {canonical_answer:'sample'} : {})},
});
async function until(predicate) {
  for (let i=0; i<20; i++) {
    if (predicate()) return;
    await new Promise(resolve=>setImmediate(resolve));
  }
  assert.fail('Expected adapter update was not emitted');
}
function harness(t) {
  const callbacks={}; const updates=[];
  let publicState=state('round-a','answering',1), finishSubmission;
  const adapter=createTwitchAdapter({
    extension:{viewer:{isLinked:true,id:'fixture-viewer',onChanged(){}},
      onAuthorized:fn=>callbacks.authorized=fn,listen:(_topic,fn)=>callbacks.pubsub=fn},
    apiBaseUrl:'https://fixture.invalid/api/v1',pollMs:1e6,isDocumentHidden:()=>false,
    fetcher:async(url,options)=>{
      if (options.method==='POST') return new Promise(resolve=>finishSubmission=resolve);
      if (url.endsWith('/game-state')) return response(publicState);
      if (url.endsWith('/leaderboard')) return response({entries:[],own_entry:null});
      return response({receipt:null,answer:null,result:null});
    },
  });
  t.after(()=>adapter.dispose());
  adapter.subscribe(snapshot=>updates.push(snapshot));
  callbacks.authorized({channelId:'fixture-channel',token:'fixture-token'});
  return {adapter,updates,complete:result=>finishSubmission(result),publish(next){
    publicState=next;
    callbacks.pubsub('broadcast','application/json',JSON.stringify({event:'game_state_changed',channel_id:'fixture-channel',version:next.version}));
  }};
}
for (const [label,next] of [
  ['a newer round',state('round-b','answering',2)],
  ['published results',state('round-a','results',2)],
]) {
  test(`a late answer receipt cannot overwrite ${label}`,async t=>{
    const fixture=harness(t);
    await until(()=>fixture.updates.at(-1).roundId==='round-a');
    const submission=fixture.adapter.submit('old answer');
    fixture.publish(next);
    await until(()=>fixture.updates.at(-1).roundId===next.round.round_id && fixture.updates.at(-1).phase===next.round.phase);
    fixture.complete(response({},202)); await submission;
    const latest=fixture.updates.at(-1);
    assert.equal(latest.roundId,next.round.round_id);
    assert.equal(latest.phase,next.round.phase);
    assert.notEqual(latest.ownSubmission?.answer,'old answer');
  });
}
test('a failed submission is never presented as a confirmed receipt',async t=>{
  const fixture=harness(t);
  await until(()=>fixture.updates.at(-1).roundId==='round-a');
  const submission=fixture.adapter.submit('unconfirmed answer');
  fixture.complete(response({},503));
  await assert.rejects(submission,/could not complete/);
  assert.equal(fixture.updates.at(-1).phase,'answering');
  assert.equal(fixture.updates.at(-1).ownSubmission,null);
});
