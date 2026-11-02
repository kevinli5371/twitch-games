const modes = {
  quote: { name: 'Quote completion', action: 'Complete the quote', hint: 'Remember the missing word from the broadcast.', prompt: 'I cannot believe we won with a ____.', answer: 'spoon', result: 'You got the word!', explanation: 'Your answer matched the missing word.', points: 1, color: '#73e6eb' },
  niche: { name: 'Niche', action: 'Find the uncommon answer', hint: 'Give a valid answer you think fewer viewers will choose.', prompt: 'Name a musical instrument.', answer: 'Theremin', result: 'One of a kind.', explanation: 'A unique valid answer in this sample round.', points: 3, color: '#ff95b4' },
  hive: { name: 'Hive mind', action: 'Think like the crowd', hint: 'Give the answer you think most viewers will choose.', prompt: 'What snack belongs at every game night?', answer: 'Popcorn', result: 'Great minds think alike.', explanation: 'Your answer is in a most-common group in this sample.', points: 1, color: '#f4dd81' },
};
const $ = selector => document.querySelector(selector);
function setTheme(theme) {
  document.documentElement.dataset.theme=theme;
  document.querySelectorAll('.theme-picker button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.theme===theme)));
}
setTheme(new URLSearchParams(location.search).get('theme')==='dark'?'dark':'light');
document.querySelectorAll('.theme-picker button').forEach(button=>button.addEventListener('click',()=>{
  setTheme(button.dataset.theme);
  const url=new URL(location.href);url.searchParams.set('theme',button.dataset.theme);history.replaceState(null,'',url);
}));
let mode = 'quote';
let screen = 'answering';
let draft = '';
let accepted = '';
let pendingTimer;
let hidden = false;
let resultExample = 'success';

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function sprite(key) {
  const host = el('span');
  // Original rect-based sprites; no artwork from the reference is reused.
  const shapes = {
    quote: '<path fill="currentColor" d="M2 3h12v9H8v3H5v-3H2z"/><path fill="#102339" d="M5 6h2v3H5zm4 0h2v3H9z"/>',
    niche: '<path fill="currentColor" d="M5 1h6v2h3v3h1v4h-2v2h-2v2H9v2H7v-2H5v-2H3v-2H1V6h1V3h3z"/><path fill="#fff2" d="M5 3h6v3H5z"/><path fill="#102339" d="M7 6h2v7H7z"/>',
    hive: '<path fill="currentColor" d="M3 2h4v3h2V2h4v4h2v7h-3v2H4v-2H1V6h2z"/><path fill="#102339" d="M5 7h2v6H5zm4 0h2v6H9z"/><path fill="#e8f9ff" d="M2 2h4v3H2zm8 0h4v3h-4z"/>',
    check: '<path fill="currentColor" d="M1 7h3v3h2V8h2V6h2V4h2V2h3v4h-2v2h-2v2H9v2H7v3H4v-3H2v-2H1z"/>',
    trophy: '<path fill="currentColor" d="M4 1h8v2h3v6h-3v2H9v3h3v2H4v-2h3v-3H4V9H1V3h3z"/><path fill="#102339" d="M2 4h2v3H2zm10 0h2v3h-2z"/>',
    pause: '<path fill="currentColor" d="M3 2h4v12H3zm6 0h4v12H9z"/>',
  };
  host.innerHTML = `<svg class="pixel-icon" viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true">${(shapes[key] || shapes.pause).replaceAll('#102339','var(--sprite-cutout, #102339)')}</svg>`;
  return host.firstElementChild;
}
function makeButton(text, action, className = 'pixel-button full') {
  const node = el('button', className, text);node.type = 'button';node.addEventListener('click', action);return node;
}
function setScreen(next, reset = false) {
  clearTimeout(pendingTimer);
  if (reset) { accepted = ''; draft = ''; }
  screen = next;hidden = false;renderLive();
}
function hero(card, icon, title, description) {
  const host = el('div', 'state-hero');host.append(sprite(icon),el('h4','',title),el('p','',description));card.append(host);
}
function echo(card, answer) {
  const host = el('div','answer-echo');host.append(el('small','','YOUR ANSWER'),el('strong','',answer));card.append(host);
}
function board(card, final = false) {
  const table = el('table','board');const caption = el('caption','status-copy',final?'FINAL STANDINGS':'ROUND STANDINGS');table.append(caption);
  const head = el('thead');const tr = el('tr');['#','Player','Pts'].forEach(text=>{const th=el('th','',text);th.scope='col';tr.append(th);});head.append(tr);table.append(head);
  const body = el('tbody');
  [['1','PixelPilot','9'],['2','You','6'],['3','NovaStar','4'],['4','MapleMode','2']].forEach(row=>{const item=el('tr',row[1]==='You'?'self':'');row.forEach(text=>item.append(el('td','',text)));body.append(item);});
  table.append(body);card.append(table);
}
function makeCard(key, phase, interactive = false) {
  const data = modes[key];const card = el('article','game-card');card.dataset.mode = key;card.setAttribute('aria-label',`${data.name}: ${phase}`);
  const top=el('div','card-top');top.append(el('span','','STREAM GAMES / DEMO'));
  if(interactive && $('#stage').dataset.layout==='desktop')top.append(makeButton('Hide −',()=>{hidden=true;renderLive();},'hide-game'));
  card.append(top);
  const heading=el('div','mode-line');const title=el('div');title.append(el('small','','CURRENT GAME'),el('h3','',data.name));heading.append(sprite(key),title);card.append(heading);
  const labels={idle:['WAITING TO PLAY','IDLE'],permission:['PARTICIPATION','PERMISSION'],disconnected:['LAST KNOWN ROUND 2 / 5','OFFLINE'],standings:['GAME COMPLETE','FINAL'],leaderboard:['ROUND 2 / 5','STANDINGS']};
  const round=el('div','round-line');round.append(el('span','',labels[phase]?.[0]||'ROUND 2 / 5'));
  if(['answering','failed','submitted','sending'].includes(phase)){const timer=el('span','timer','00:24');timer.setAttribute('aria-label','Illustrative time remaining: 24 seconds');round.append(timer);}else round.append(el('span','',labels[phase]?.[1]||(phase==='results'?'RESULTS':'PLEASE WAIT')));
  card.append(round);
  if(!['idle','permission','disconnected'].includes(phase)){
    const progress=el('div',`progress-pixels${phase==='standings'?' is-complete':''}`);progress.setAttribute('aria-hidden','true');for(let i=0;i<5;i++)progress.append(el('i'));card.append(progress);
  }

  if(['answering','failed'].includes(phase)){
    const box=el('div','prompt-box');box.append(el('p','prompt-label',data.action));const prompt=el('p','prompt');
    const parts=data.prompt.split('____');prompt.append(document.createTextNode(parts[0]));if(parts.length>1)prompt.append(el('span','blank','????'),document.createTextNode(parts[1]));box.append(prompt);card.append(box,el('p','mode-hint',data.hint));
    const form=el('form');const inputId=interactive?'pixel-answer':`gallery-${key}-answer`;const label=el('label','answer-label','YOUR PRIVATE ANSWER');label.htmlFor=inputId;form.append(label);
    const row=el('div','answer-row');const input=el('input');input.id=inputId;input.name='answer';input.placeholder=key==='quote'?'The missing word…':'Type one answer…';input.maxLength=80;input.required=true;input.autocomplete='off';input.value=interactive?draft:'';
    const send=el('button','pixel-button','Send ▸');send.type='submit';
    if(!interactive){input.readOnly=true;input.tabIndex=-1;send.disabled=true;send.setAttribute('aria-label','Static mockup: send answer');}
    input.addEventListener('input',()=>{draft=input.value;input.setCustomValidity('');});
    form.addEventListener('submit',event=>{
      event.preventDefault();if(!interactive)return;
      const answer=input.value.trim();if(!answer){input.setCustomValidity('Type an answer before sending.');input.reportValidity();return;}
      draft=answer;screen='sending';renderLive();
      pendingTimer=setTimeout(()=>{accepted=answer;screen='submitted';renderLive();},700);
    });
    row.append(input,send);form.append(row);card.append(form);
    if(phase==='failed')card.append(el('p','status-copy','Demo failure: answer not received. Your text is kept above; try Send again.'));
    card.append(el('p','private-copy','Only you can see your answer. One final answer; no edits after sending.'));
    if(key==='quote')card.append(el('p','source','SOURCE: SAMPLE BROADCAST / 04:18'));
  } else if(phase==='submitted'){
    hero(card,'check','Locked in!','Your answer is saved for this sample round.');echo(card,interactive?(accepted||data.answer):data.answer);
    card.append(el('p','wait-note','Keep watching. Your result appears when the round is revealed.'),el('p','sample-note','Simulated receipt · no real submission sent.'));
  } else if(phase==='sending'){
    hero(card,key,'Sending…','Waiting for your sample receipt.');echo(card,draft);card.append(el('p','wait-note','Your answer is not confirmed yet.'));
  } else if(phase==='closed'){
    hero(card,'pause','Answers closed.','The round is over. Results are being prepared.');if(accepted)echo(card,accepted);card.append(el('p','wait-note','No more answers can be sent for this round.'));
  } else if(phase==='results'){
    const variant=interactive?resultExample:'success';
    const noPoints={quote:['Not this time.','Your answer did not match the missing word in this sample.'],niche:['Outside the answer set.','This sample answer is not valid for the question.'],hive:['A different wavelength.','This sample answer was outside the most-common groups.']};
    const [title,description]=variant==='missed'?['This round passed you by.','No answer was submitted in this sample round.']:variant==='zero'?noPoints[key]:[data.result,data.explanation];
    hero(card,key,title,description);
    if(key==='quote'){
      const reveal=el('div','prompt-box');reveal.append(el('p','prompt-label','THE FULL QUOTE'));const text=el('p','prompt');text.append(document.createTextNode('I cannot believe we won with a '),el('span','blank','spoon'),document.createTextNode('.'));reveal.append(text);card.append(reveal);
    } else if(variant!=='missed')echo(card,variant==='zero'?(key==='niche'?'Cloud':'Pretzels'):interactive?(accepted||data.answer):data.answer);
    const points=variant==='success'?data.points:0;
    const result=el('div','result-strip');result.append(el('span','','Sample round score'),el('strong','',`+${points} ${points===1?'point':'points'}`));card.append(result);
    const standing=el('div','round-line');standing.append(el('span','','Your sample standing'),el('span','','#2 · 6 PTS'));card.append(standing);
    card.append(el('p','wait-note','Next round starts when the streamer advances.'));
    const standingsButton=makeButton('Round standings ▸',()=>setScreen('leaderboard'));
    if(!interactive){standingsButton.disabled=true;standingsButton.setAttribute('aria-label','Static mockup: view round standings');}
    card.append(standingsButton,el('p','sample-note','Illustrative outcome · typed answers are not evaluated.'));
  } else if(phase==='leaderboard'){
    hero(card,'trophy','The story so far.','Sample standings after this round.');board(card);
    card.append(el('p','wait-note','You’re #2. There are still rounds to play.'));
    if(interactive)card.append(makeButton('Your round result ◂',()=>setScreen('results')));
  } else if(phase==='standings'){
    hero(card,'trophy','GG, everyone.','That’s a wrap. Here are all four sample players.');board(card,true);card.append(el('p','wait-note','You finished #2 with 6 sample points.'),el('p','sample-note','Scores reset for the next game.'));
  } else if(phase==='idle'){
    hero(card,key,'Next quest soon.','The streamer hasn’t started a game yet.');card.append(el('p','wait-note','Join in here when a round opens.'));
  } else if(phase==='permission'){
    hero(card,key,'Ready to play?','Share your Twitch identity to send a private answer.');
    card.append(el('p','mode-hint','In the live Extension, Twitch will handle this permission. This prototype only simulates the next screen.'));
    if(interactive)card.append(makeButton('Try permission granted ▸',()=>setScreen('answering',true)));
  } else if(phase==='disconnected'){
    hero(card,'pause','Connection lost.','We can’t confirm the current round. Answers are paused here.');
    card.append(el('p','wait-note',accepted?'Your confirmed sample answer is kept.':'Any unsent text is kept in this preview.'));
    if(interactive)card.append(makeButton('Restore demo ↻',()=>setScreen(accepted?'submitted':'answering')));
  }
  return card;
}
function renderLive(){
  const host=$('#live-card');host.replaceChildren();host.hidden=hidden;$('#restore-overlay').hidden=!hidden;
  if(!hidden)host.append(makeCard(mode,screen,true));
  if(screen!=='sending')$('#screen-state').value=screen;
  document.querySelectorAll('[data-mode]').forEach(button=>{if(button.tagName==='BUTTON')button.setAttribute('aria-pressed',String(button.dataset.mode===mode));});
}
document.querySelectorAll('.mode-picker button').forEach(button=>button.addEventListener('click',()=>{mode=button.dataset.mode;setScreen('answering',true);}));
$('#screen-state').addEventListener('change',event=>setScreen(event.target.value,event.target.value==='answering'));
$('#result-example').addEventListener('change',event=>{resultExample=event.target.value;setScreen('results');});
$('#restart-round').addEventListener('click',()=>setScreen('answering',true));
$('#restore-overlay').addEventListener('click',()=>{hidden=false;renderLive();});
document.querySelectorAll('[data-layout]').forEach(button=>{
  if(button.tagName!=='BUTTON')return;
  button.addEventListener('click',()=>{
    $('#stage').dataset.layout=button.dataset.layout;
    document.querySelectorAll('button[data-layout]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
    $('#stage-label').textContent=button.dataset.layout==='mobile'?'MOBILE / CHAT-REGION LAYOUT':'DESKTOP / SAMPLE STREAM';
    hidden=false;renderLive();
  });
});
for(const [key,data] of Object.entries(modes)){
  const group=el('section','gallery-mode');group.dataset.mode=key;group.style.setProperty('--mode-accent',`var(--${key==='quote'?'cyan':key==='niche'?'pink':'yellow'})`);group.append(el('h3','',data.name));const row=el('div','gallery-row');
  [['answering','01 / ANSWER'],['submitted','02 / LOCKED IN'],['results','03 / ROUND RESULT'],['standings','04 / FINAL STANDINGS']].forEach(([phase,label])=>{
    const cell=el('div','gallery-cell');cell.append(el('p','',label),makeCard(key,phase));row.append(cell);
  });group.append(row);$('#gallery').append(group);
}
renderLive();
