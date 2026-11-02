import {modes,fixtureQuestions,bankCounts,validateQuestion,isSavedQuestion} from './model.mjs';
const $=selector=>document.querySelector(selector);
let dashboardTheme='light';
try{if(localStorage.getItem('stream-games.dashboard.theme')==='dark')dashboardTheme='dark';}catch{/* Theme storage is optional. */}
function applyDashboardTheme(){document.documentElement.dataset.theme=dashboardTheme;$('#theme-toggle').textContent=dashboardTheme==='light'?'Dark mode':'Light mode';$('#theme-toggle').setAttribute('aria-label',`Switch to ${dashboardTheme==='light'?'dark':'light'} mode`);}
applyDashboardTheme();
$('#theme-toggle').addEventListener('click',()=>{dashboardTheme=dashboardTheme==='light'?'dark':'light';applyDashboardTheme();try{localStorage.setItem('stream-games.dashboard.theme',dashboardTheme);}catch{/* Keep theme for this page. */}});
const storageKey='stream-games.dashboard.fixture.v1';
let questions=fixtureQuestions();
let cooldownDraft=null;
try { const saved=JSON.parse(localStorage.getItem(storageKey));if(saved && Array.isArray(saved.questions)&&saved.questions.length<=500&&saved.questions.every(isSavedQuestion)){questions=saved.questions;cooldownDraft=Number.isInteger(saved.cooldownDraft)&&saved.cooldownDraft>=0&&saved.cooldownDraft<=1000?saved.cooldownDraft:null;} }catch{/* Browser storage is optional for the preview. */}
let toastTimer;
function toast(message){$('#toast').textContent=message;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').textContent='',6000);}
function persist(){try{localStorage.setItem(storageKey,JSON.stringify({questions,cooldownDraft}));}catch{toast('Browser storage unavailable. Changes last only until this page closes.');}}
function element(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
function renderHealth(){const host=$('#health-cards');host.replaceChildren();for(const [mode,details]of Object.entries(modes)){const counts=bankCounts(questions,mode);const card=element('article','panel health-card');const title=element('div','mode-head');title.append(element('span',`mode-symbol ${mode}`,details.symbol),element('span','',details.name));const total=element('div','health-total',String(counts.eligible));total.append(element('span','','eligible'));const bar=element('div','supply-bar');bar.setAttribute('aria-hidden','true');const fill=element('span');fill.style.width=`${counts.total?counts.eligible/counts.total*100:0}%`;bar.append(fill);const info=element('div','health-detail');info.append(element('span','',`${counts.pending} awaiting review`),element('span','',`${counts.cooldown} on cooldown`));card.append(title,total,bar,info);host.append(card);}}
function renderPreview(){const host=$('#review-preview');host.replaceChildren();const pending=questions.filter(q=>q.status==='pending');$('#queue-count').textContent=String(pending.length);for(const q of pending.slice(0,3)){const row=element('a','compact-question');row.href='#bank';const text=element('div');text.append(element('strong','',q.prompt),element('small','',`${modes[q.mode].name} · ${q.author}`));row.append(element('span',`mode-symbol ${q.mode}`,modes[q.mode].symbol),text);host.append(row);}if(!pending.length)host.append(element('p','empty','All caught up. Your review queue is empty.'));}
function renderBank(){const status=$('#status-filter').value,mode=$('#mode-filter').value,search=$('#search').value.trim().toLowerCase();const filtered=questions.filter(q=>(status==='all'||q.status===status)&&(mode==='all'||q.mode===mode)&&`${q.prompt} ${q.author}`.toLowerCase().includes(search));$('#bank-summary').textContent=`${filtered.length} ${filtered.length===1?'question':'questions'} · sample bank`;const host=$('#question-list');host.replaceChildren();for(const q of filtered){const card=element('article','question-card');const meta=element('div','question-meta');meta.append(element('span','pill',modes[q.mode].name),element('span','',q.author),element('span','',q.status==='pending'?'Awaiting review':q.status));card.append(meta,element('h3','',q.prompt));if(q.answer)card.append(element('div','question-answer',`Missing word: ${q.answer}`));if(q.valid)card.append(element('div','question-answer',`Valid words: ${q.valid.join(', ')} · rarity is calculated during play`));if(q.source)card.append(element('small','',q.source));if(q.status==='cooldown')card.append(element('small','','On cooldown in this sample bank. Live eligibility is not connected.'));if(q.status==='pending'){const actions=element('div','question-actions');for(const [next,label] of [['approved','Approve question'],['rejected','Reject question']]){const button=element('button',`button ${next==='approved'?'primary':''}`,label);button.type='button';button.addEventListener('click',()=>{q.status=next;persist();renderAll();toast(next==='approved'?'Approved. This question is now in your local bank.':'Question rejected. Find it using the Rejected filter.');});actions.append(button);}card.append(actions);}host.append(card);}if(!filtered.length){const empty=element('div','empty');empty.append(element('p','','No questions match these filters.'));const clear=element('button','button','Show all questions');clear.type='button';clear.addEventListener('click',()=>openBank());empty.append(clear);host.append(empty);}}
function openBank(status='all',mode='all',search=''){
  $('#status-filter').value=status;$('#mode-filter').value=mode;$('#search').value=search;
  renderBank();location.hash='bank';navigate();
  $('#page-title').tabIndex=-1;$('#page-title').focus({preventScroll:true});window.scrollTo(0,0);
}
document.addEventListener('click',event=>{
  const link=event.target.closest('[data-bank-status]');
  if(link){event.preventDefault();openBank(link.dataset.bankStatus,link.dataset.bankMode||'all');}
});
function renderAnalytics(){
  const statusNames={approved:'Approved',pending:'Awaiting review',cooldown:'On cooldown',rejected:'Rejected'};
  const colors={approved:'#a783ff',pending:'#65538a',cooldown:'#39353f',rejected:'#8e555f'};
  const counts=Object.fromEntries(Object.keys(statusNames).map(status=>[status,questions.filter(q=>q.status===status).length]));
  $('#map-total').textContent=`${questions.length} questions`;
  const map=$('#question-map');map.replaceChildren();
  for(const [index,q] of questions.entries()){
    const tile=element('button',`question-tile ${q.status}`);tile.type='button';
    tile.setAttribute('aria-label',`${statusNames[q.status]}: ${q.prompt}`);tile.title=`${statusNames[q.status]} · ${q.prompt}`;
    tile.append(element('span','',String(index+1)));tile.addEventListener('click',()=>openBank('all',q.mode,q.prompt));map.append(tile);
  }
  $('#bank-total').textContent=String(questions.length);
  let start=0;const segments=[];const breakdown=$('#bank-breakdown');breakdown.replaceChildren();
  for(const [status,label] of Object.entries(statusNames)){
    const end=start+(questions.length?counts[status]/questions.length*100:0);segments.push(`${colors[status]} ${start}% ${end}%`);start=end;
    const row=element('a');row.href='#bank';row.dataset.bankStatus=status;
    const name=element('span');const dot=element('i',status);dot.setAttribute('aria-hidden','true');name.append(dot,document.createTextNode(label));
    row.append(name,element('strong','',String(counts[status])));breakdown.append(row);
  }
  $('#bank-donut').style.background=questions.length?`conic-gradient(${segments.join(',')})`:'#39353f';
  $('#bank-donut').setAttribute('role','img');$('#bank-donut').setAttribute('aria-label',`${questions.length} questions: ${Object.entries(statusNames).map(([key,label])=>`${counts[key]} ${label.toLowerCase()}`).join(', ')}`);
  $('#next-step-title').textContent=counts.pending?`${counts.pending} ${counts.pending===1?'question needs':'questions need'} your eye.`:'Your queue is clear.';
  $('#next-step-copy').textContent=counts.pending?'Turn audience ideas into the next great round. Review the waiting questions to grow your bank.':'Keep the bank fresh. Add a question or prepare your next game.';
  const next=$('.insight .button');next.textContent=counts.pending?'Review questions ↗':'Create a question ＋';
  if(counts.pending)next.dataset.bankStatus='pending';else delete next.dataset.bankStatus;
  next.onclick=counts.pending?null:event=>{event.preventDefault();$('#new-question').click();};
  // Categorical snapshot, not a historical activity series. Values come only from the fixture bank.
  const entries=Object.entries(modes);const values=entries.map(([key])=>bankCounts(questions,key).eligible);
  const max=Math.max(2,Math.ceil(Math.max(...values)/2)*2);const positions=[80,290,500];const y=value=>165-value/max*120;
  const points=values.map((value,index)=>`${positions[index]},${y(value)}`).join(' ');
  const labels=entries.map(([,mode],index)=>`<text class="chart-axis" x="${positions[index]}" y="197" text-anchor="middle">${mode.name}</text><text class="chart-count" x="${positions[index]}" y="${y(values[index])-15}" text-anchor="middle">${values[index]}</text><circle cx="${positions[index]}" cy="${y(values[index])}" r="4" fill="#c7b2ff"/>`).join('');
  $('#availability-chart').innerHTML=`<svg viewBox="0 0 580 210" role="img" aria-label="Available questions: ${entries.map(([,mode],index)=>`${mode.name} ${values[index]}`).join(', ')}"><defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#9d75ff" stop-opacity=".38"/><stop offset="1" stop-color="#9d75ff" stop-opacity=".02"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="4"/></filter></defs>${[0,1,2].map(index=>`<line class="chart-grid" x1="30" x2="550" y1="${45+index*60}" y2="${45+index*60}"/><text class="chart-axis" x="5" y="${49+index*60}">${Math.round(max*(1-index/2))}</text>`).join('')}<polygon points="80,165 ${points} 500,165" fill="url(#area)"/><polyline points="${points}" fill="none" stroke="#aa89ff" stroke-width="6" opacity=".35" filter="url(#glow)"/><polyline points="${points}" fill="none" stroke="#cbb5ff" stroke-width="2"/>${labels}</svg>`;
  document.querySelectorAll('.health-card').forEach((card,index)=>{
    const mode=entries[index][0];const link=element('a','metric-arrow','↗');link.href='#bank';link.dataset.bankStatus='approved';link.dataset.bankMode=mode;link.setAttribute('aria-label',`View approved ${modes[mode].name} questions`);card.append(link);
  });
  const pending=questions.filter(q=>q.status==='pending');
  document.querySelectorAll('#review-preview a').forEach((row,index)=>row.addEventListener('click',event=>{event.preventDefault();openBank('pending',pending[index].mode,pending[index].prompt);}));
}
function renderAll(){renderHealth();renderPreview();renderBank();renderAnalytics();}
const views={overview:['Control room','A little preparation. A lot of good games.'],bank:['Question bank','Review suggestions and build a bank worth playing.'],setup:['Game setup','Choose the modes and order for your next game.'],team:['Team & settings','Manage your team and question reuse settings.']};
function navigate(){const requested=location.hash.slice(1);const view=Object.hasOwn(views,requested)?requested:'overview';for(const name of Object.keys(views))$(`#${name}`).hidden=name!==view;document.querySelectorAll('nav a').forEach(a=>{a.classList.toggle('active',a.dataset.view===view);if(a.dataset.view===view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});$('#page-title').textContent=views[view][0];$('#page-subtitle').textContent=views[view][1];document.title=`${views[view][0]} · Stream Games preview`;}
window.addEventListener('hashchange',navigate);
for(const selector of ['#status-filter','#mode-filter','#search'])$(selector).addEventListener(selector==='#search'?'input':'change',renderBank);
$('#new-question').addEventListener('click',()=>{$('#question-form').reset();$('#form-error').textContent='';updateFields();$('#question-dialog').showModal();$('#create-mode').focus();});
for(const id of ['#close-dialog','#cancel-question'])$(id).addEventListener('click',()=>$('#question-dialog').close());
function updateFields(){const mode=$('#create-mode').value;$('#quote-fields').hidden=mode!=='quote';$('#niche-fields').hidden=mode!=='niche';$('#create-answer').required=mode==='quote';$('#create-source').required=mode==='quote';$('#create-valid').required=mode==='niche';}
$('#create-mode').addEventListener('change',updateFields);
$('#question-form').addEventListener('submit',event=>{event.preventDefault();if(questions.length>=500){$('#form-error').textContent='Local preview limit reached. Reset demo data to start again.';return;}const mode=$('#create-mode').value;const question={id:`local-${crypto.randomUUID()}`,mode,prompt:$('#create-prompt').value.trim(),author:'Sample owner · local creation',status:'approved'};if(mode==='quote'){question.answer=$('#create-answer').value.trim();question.source=$('#create-source').value.trim();}if(mode==='niche')question.valid=[...new Set($('#create-valid').value.split('\n').map(s=>s.trim()).filter(Boolean))];const error=validateQuestion(question);if(error){$('#form-error').textContent=error;return;}questions.push(question);persist();renderAll();$('#question-dialog').close();openBank('approved',mode,question.prompt);toast('Created. Your question is in the approved bank.');});
let exactOrder=['quote','niche','hive','quote','niche'];
function updatePlan(){const isRandom=$('input[name="rotation"]:checked').value==='random';$('#random-setup').hidden=!isRandom;$('#exact-setup').hidden=isRandom;const count=isRandom?Number($('#round-count').value):exactOrder.length;const valid=Number.isSafeInteger(count)&&count>=1&&count<=20;$('#plan-rounds').textContent=valid?`${count} ${count===1?'round':'rounds'}`:'Choose a round count';$('#plan-range').textContent=valid?`${isRandom?'Random rotation':'Exact mode order'} · local draft`:'Enter 1–20 rounds for this preview.';}
function renderOrder(){const host=$('#round-order');host.replaceChildren();exactOrder.forEach((mode,index)=>{const row=element('div','round-row');const select=element('select');select.setAttribute('aria-label',`Mode for round ${index+1}`);Object.entries(modes).forEach(([value,details])=>{const option=element('option','',details.name);option.value=value;select.append(option);});select.value=mode;select.addEventListener('change',()=>exactOrder[index]=select.value);const remove=element('button','icon-button','×');remove.setAttribute('aria-label',`Remove round ${index+1}`);remove.disabled=exactOrder.length===1;remove.addEventListener('click',()=>{exactOrder.splice(index,1);renderOrder();updatePlan();});row.append(element('span','',`Round ${index+1}`),select,remove);host.append(row);});$('#add-round').disabled=exactOrder.length>=20;}
document.querySelectorAll('input[name="rotation"]').forEach(input=>input.addEventListener('change',updatePlan));$('#round-count').addEventListener('input',updatePlan);$('#add-round').addEventListener('click',()=>{if(exactOrder.length<20)exactOrder.push('quote');renderOrder();updatePlan();});
if(cooldownDraft!==null)$('#cooldown-games').value=String(cooldownDraft);
$('#cooldown-form').addEventListener('submit',event=>{event.preventDefault();const value=Number($('#cooldown-games').value);if(!Number.isInteger(value)||value<0||value>1000)return;cooldownDraft=value;persist();toast('Cooldown draft saved locally. Existing fixture eligibility is unchanged.');});
$('#reset-demo').addEventListener('click',()=>{questions=fixtureQuestions();cooldownDraft=null;$('#cooldown-games').value='';persist();$('#status-filter').value='pending';$('#mode-filter').value='all';$('#search').value='';renderAll();toast('Sample questions restored. Bank filters cleared.');});
renderAll();renderOrder();updatePlan();navigate();
