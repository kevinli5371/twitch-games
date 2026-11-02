import test from 'node:test';
import assert from 'node:assert/strict';
import {fixtureQuestions,bankCounts,validateQuestion,planningRange,isSavedQuestion,apiModeIds} from './model.mjs';
test('approval changes eligible supply only in that mode',()=>{const questions=fixtureQuestions();assert.equal(bankCounts(questions,'quote').eligible,1);questions[0].status='approved';assert.equal(bankCounts(questions,'quote').eligible,2);assert.equal(bankCounts(questions,'niche').eligible,1);});
test('a quote needs one blank, source evidence and a missing word',()=>{const q=fixtureQuestions()[0];assert.equal(validateQuestion(q),'');assert.ok(validateQuestion({...q,source:''}));assert.ok(validateQuestion({...q,answer:''}));assert.ok(validateQuestion({...q,prompt:'No missing word'}));assert.ok(validateQuestion({...q,prompt:'____ and ____'}));});
test('niche list is required without assigning rarity tiers',()=>{const q=fixtureQuestions()[1];assert.equal(validateQuestion(q),'');assert.ok(validateQuestion({...q,valid:[]}));});
test('preview ranges do not draw round lengths or reserve questions',()=>{assert.deepEqual(planningRange(3),{min:9,max:15});for(const invalid of [0,21,2.2,Infinity,NaN])assert.equal(planningRange(invalid),null);});
test('saved fixture rejects malformed status and question payloads',()=>{assert.ok(fixtureQuestions().every(isSavedQuestion));assert.equal(isSavedQuestion({...fixtureQuestions()[0],status:'live'}),false);assert.equal(isSavedQuestion({...fixtureQuestions()[0],mode:'unknown'}),false);});
test('untrusted browser storage cannot break fixture validation',()=>{for(const q of [null,{}, {...fixtureQuestions()[0],source:{}},{...fixtureQuestions()[0],answer:1},{...fixtureQuestions()[0],mode:'__proto__'},{...fixtureQuestions()[1],valid:[null]}])assert.ok(!isSavedQuestion(q));});
test('UI aliases have explicit canonical backend mode mappings',()=>{assert.deepEqual(apiModeIds,{quote:'quote_completion',niche:'niche',hive:'hive_mind'});});
test('optional fields are checked for every mode before renderer access',()=>{
  for (const fixture of fixtureQuestions()) {
    for (const patch of [{valid:'unexpected string'},{valid:{}},{valid:[null]},{valid:[1]},{valid:null},{answer:{}},{answer:17},{answer:null},{source:[]},{source:null}]) {
      assert.equal(isSavedQuestion({...fixture,...patch}),false,`${fixture.mode} must reject ${JSON.stringify(patch)}`);
    }
    const safe={...fixture,valid:['one','two'],answer:'one',source:'Fixture source'};
    assert.equal(isSavedQuestion(safe),true);
    assert.doesNotThrow(()=>safe.valid.join(', '));
  }
});
