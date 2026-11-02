export const modes = {quote: {name:'Quote completion', symbol:'“'}, niche:{name:'Niche',symbol:'◇'},hive:{name:'Hive mind',symbol:'✳'}};
// UI-only aliases. Future API integration must use these canonical contract IDs.
export const apiModeIds = Object.freeze({quote:'quote_completion',niche:'niche',hive:'hive_mind'});
export function fixtureQuestions() { return [
{id:'q1',mode:'quote',prompt:'I cannot believe we won with a ____.',answer:'spoon',source:'Fixture broadcast · example-001 · 00:42:18',author:'AI candidate · sample',status:'pending'},
{id:'q2',mode:'niche',prompt:'Name a fruit you would put in a smoothie.',valid:['banana','mango','strawberry','blueberry','peach'],author:'Viewer suggestion · sample',status:'pending'},
{id:'q3',mode:'hive',prompt:'What is the first thing you do after winning a match?',author:'Viewer suggestion · sample',status:'pending'},
{id:'q4',mode:'quote',prompt:'The real final boss was the ____.',answer:'door',source:'Fixture broadcast · example-002 · 01:12:09',author:'Moderator · sample',status:'approved'},
{id:'q5',mode:'niche',prompt:'Name a musical instrument.',valid:['piano','guitar','violin','flute','trumpet','drums'],author:'Moderator · sample',status:'approved'},
{id:'q6',mode:'hive',prompt:'What snack belongs at every game night?',author:'Moderator · sample',status:'approved'},
{id:'q7',mode:'quote',prompt:'Never trust a ____ with a map.',answer:'wizard',source:'Fixture broadcast · example-003 · 00:18:25',author:'AI candidate · sample',status:'cooldown'},
{id:'q8',mode:'niche',prompt:'Name a planet in our solar system.',valid:['mercury','venus','earth','mars','jupiter','saturn','uranus','neptune'],author:'Moderator · sample',status:'cooldown'}]; }
export function bankCounts(questions, mode) { const selected=questions.filter(q=>q.mode===mode); return {eligible:selected.filter(q=>q.status==='approved').length,pending:selected.filter(q=>q.status==='pending').length,cooldown:selected.filter(q=>q.status==='cooldown').length,total:selected.length}; }
export function validateQuestion(question) { if(!question || !Object.hasOwn(modes,question.mode)) return 'Choose a supported mode.'; if(typeof question.prompt!=='string' || !question.prompt.trim() || question.prompt.length>500) return 'Enter a question up to 500 characters.'; if(question.mode==='quote' && (typeof question.answer!=='string' || !question.answer.trim() || question.answer.length>100 || typeof question.source!=='string' || !question.source.trim() || question.source.length>200 || (question.prompt.match(/____/g)||[]).length!==1)) return 'Quote questions need exactly one ____ blank, a canonical answer and a broadcast reference.'; if(question.mode==='niche' && (!Array.isArray(question.valid) || !question.valid.length || !question.valid.every(word=>typeof word==='string' && word.trim().length>0))) return 'Niche questions need a list of valid words.'; return ''; }
export function planningRange(count) { if(!Number.isSafeInteger(count)||count<1||count>20) return null;return {min:count*3,max:count*5}; }
export function isSavedQuestion(q){
  if (!q || typeof q.id!=='string' || typeof q.author!=='string' || !['pending','approved','cooldown','rejected'].includes(q.status)) return false;
  // All optional rendered fields are checked regardless of mode. Storage is
  // untrusted: a hive fixture carrying a non-array valid field must not reach
  // the renderer, which joins valid words for any record that includes them.
  if (q.answer!==undefined && (typeof q.answer!=='string' || q.answer.length>100)) return false;
  if (q.source!==undefined && (typeof q.source!=='string' || q.source.length>200)) return false;
  if (q.valid!==undefined && (!Array.isArray(q.valid) || !q.valid.every(word=>typeof word==='string' && word.trim().length>0))) return false;
  return !validateQuestion(q);
}
