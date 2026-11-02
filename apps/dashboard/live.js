import {createDashboardAPI} from './api.mjs';
import {createCaptionQueue} from './caption-collector.mjs';
const api = createDashboardAPI();
const $ = id => document.getElementById(id);
let snapshot = null, channel = null, busy = false, epoch = 0, refreshVersion = 0, queue = null, player = null, uploadTimer = null, playerScript = null;
const text = (id, value) => { $(id).textContent = value; };
const error = value => { text('live-error', value || ''); $('live-error').hidden = !value; };
const node = (tag, value) => { const element = document.createElement(tag); element.textContent = value; return element; };
function stopCapture() {
  queue?.stop(); queue = null; clearInterval(uploadTimer); uploadTimer = null;
  if (player) { player.pause?.(); player = null; }
  $('live-player').replaceChildren(); $('live-stop').disabled = true;
  text('live-capture','Caption capture is stopped.');
}
function signedOut() {
  epoch++; loadedSettingsFor = ''; text('live-connection-label','Not connected'); stopCapture(); snapshot = null; channel = null;
  $('live-signed-out').hidden = false; $('live-signed-in').hidden = true;
  document.querySelector('.channel strong').textContent = 'Not signed in';
  document.querySelector('.channel small').textContent = 'Connect in Live game';
  document.querySelector('.sidebar-bottom p').textContent = 'Sign in to access your workspace.';
}
function renderIdentity(identity) {
  $('live-signed-out').hidden = true; $('live-signed-in').hidden = false;
  const workspace = identity.selected_workspace;
  text('live-connection-label','API connected');
  if (!api.allowed('settings') && queue) stopCapture();
  if (!api.allowed('question_review')) { $('live-candidates').replaceChildren(); $('live-alias-list').replaceChildren(); }
  if (workspace.role !== 'owner') $('live-grants').replaceChildren();
  text('live-user', identity.user.display_name || identity.user.login);
  text('live-role', workspace.role+' · '+workspace.permissions.join(', '));
  const selector = $('live-workspace');
  selector.replaceChildren(...identity.workspaces.map(value => {
    const option = node('option', value.display_name || value.channel_id); option.value = value.channel_id; return option;
  })); selector.value = workspace.channel_id;
  document.querySelector('.channel strong').textContent = selector.selectedOptions[0]?.textContent || 'Channel';
  document.querySelector('.channel small').textContent = 'Verified '+workspace.role+' workspace';
  document.querySelector('.sidebar-bottom p').textContent = 'Game service connected · workflow tabs use sample data.';
  $('live-review').hidden = !api.allowed('question_review');
  $('live-team').hidden = workspace.role !== 'owner';
}
function renderSnapshot() {
  if (!snapshot) {
    for (const id of ["live-start","live-round","live-end","live-connect"]) $(id).disabled = true;
    return;
  }
  const game = snapshot.game, round = game.round, answering = round?.phase === 'answering';
  text('live-phase',game.status+' · '+(round?.phase || 'no round'));
  text('live-prompt',round?.phase === 'results' ? round.complete_quote+' — '+round.canonical_answer : round?.prompt || (game.status === 'active' ? 'Open a round to select the next quote.' : 'No game is running.'));
  text('live-submissions',snapshot.submission_count+' private submissions in this round');
  text('live-source',snapshot.transcript.status+(snapshot.transcript.last_received_at ? ' · last received '+new Date(snapshot.transcript.last_received_at).toLocaleTimeString() : ''));
  $('live-connect').disabled = busy || !api.allowed('settings');
  $('live-start').disabled = busy || !api.allowed('live_control') || game.status === 'active' || !snapshot.stream_id;
  $('live-round').disabled = busy || !api.allowed('live_control') || game.status !== 'active' || answering;
  $('live-end').disabled = busy || !api.allowed('live_control') || game.status !== 'active' || answering;
  const host = $('live-candidates'); host.replaceChildren();
  for (const candidate of snapshot.candidates) {
    const card = node('div',''); card.className = 'live-candidate';
    card.append(node('strong',candidate.prompt),node('p','Answer: '+candidate.canonical_answer),node('small',candidate.complete_quote),node('small','Source stream: '+candidate.source.stream_id)); host.append(card);
  }
  if (!snapshot.candidates.length) host.append(node('p',api.allowed('question_review') ? 'Waiting for usable source captions.' : 'Question review permission is required.'));
}
async function refresh() {
  const current = epoch, requestVersion = ++refreshVersion;
  try {
    const identity = await api.session(channel);
    if (current !== epoch || requestVersion !== refreshVersion) return;
    channel = identity.selected_workspace.channel_id; renderIdentity(identity);
    const data = await api.request('/dashboard/channels/'+encodeURIComponent(channel));
    if (current !== epoch || requestVersion !== refreshVersion) return;
    snapshot = data; renderSnapshot();
    if (data.game.game_id) {
      const board = await api.request('/games/'+encodeURIComponent(data.game.game_id)+'/leaderboard');
      if (current !== epoch || requestVersion !== refreshVersion) return;
      $('live-leaderboard').replaceChildren(...board.entries.map(entry => node('li',`#${entry.rank} ${entry.display_name} · ${entry.points} points`)));
    } else $('live-leaderboard').replaceChildren(node('li','No scores yet.'));
  } catch (err) {
    if (current !== epoch || requestVersion !== refreshVersion) return;
    if ([401,403].includes(err.status)) { const initial = !snapshot; signedOut(); if (initial && err.status === 401) return; }
    error(err.message);
  }
}
async function action(fn) {
  if (busy) return;
  busy = true; $('live-workspace').disabled = true; error(''); renderSnapshot();
  try { await fn(); if (api.identity) await refresh(); }
  catch (err) { error(err.message); if ([401,403].includes(err.status)) await refresh(); }
  finally { busy = false; $('live-workspace').disabled = false; renderSnapshot(); }
}
function loadPlayer() {
  if (window.Twitch?.Player) return Promise.resolve();
  if (!playerScript) playerScript = new Promise((resolve,reject) => {
    const script = document.createElement('script'); script.src = 'https://player.twitch.tv/js/embed/v1.js';
    script.onload = resolve; script.onerror = () => { playerScript = null; reject(new Error('Twitch player could not load.')); }; document.head.append(script);
  });
  return playerScript;
}
$('live-connect').addEventListener('click', () => action(async () => {
  stopCapture(); const current = epoch;
  const connected = await api.request('/channels/'+encodeURIComponent(channel)+'/stream',{method:'POST'});
  const workspace = api.identity.workspaces.find(value => value.channel_id === channel);
  if (!workspace?.login) throw new Error('The verified workspace has no Twitch login for the player. Sign in again.');
  await loadPlayer(); if (epoch !== current) return;
  const streamId = connected.stream_id;
  queue = createCaptionQueue({send:batch => api.request('/streams/'+encodeURIComponent(streamId)+'/transcript-batches',{method:'POST',body:batch}),onStatus:value => { if (queue === activeQueue) text('live-capture',value); }});
  const activeQueue = queue;
  player = new window.Twitch.Player('live-player',{channel:workspace.login,width:'100%',height:300,parent:[location.hostname],autoplay:false});
  player.addEventListener(window.Twitch.Player.READY, () => { if (queue === activeQueue) player.enableCaptions(); });
  player.addEventListener(window.Twitch.Player.CAPTIONS, value => { if (queue === activeQueue) activeQueue.push(value); });
  player.addEventListener(window.Twitch.Player.OFFLINE, () => { if (queue === activeQueue) { stopCapture(); text('live-capture','Stream went offline. Reconnect when the next broadcast starts.'); } });
  uploadTimer = setInterval(() => activeQueue.flush(),1000);
  $('live-stop').disabled = false; text('live-capture','Waiting for captions. Play the visible stream and enable its captions.');
}));
$('live-stop').addEventListener('click',stopCapture);
$('live-start').addEventListener('click',() => action(() => api.request('/channels/'+encodeURIComponent(channel)+'/games',{method:'POST',body:{request_id:crypto.randomUUID(),mode:'quote',policy_id:'quote_v1'}})));
$('live-round').addEventListener('click',() => action(() => api.command('/games/'+snapshot.game.game_id+'/rounds',snapshot.game.version)));
$('live-end').addEventListener('click',() => action(() => api.command('/games/'+snapshot.game.game_id+'/end',snapshot.game.version)));
$('live-refresh').addEventListener('click',() => { error(''); refresh(); });
$('live-logout').addEventListener('click',() => action(async () => { await api.logout(); signedOut(); }));
$('live-workspace').addEventListener('change',() => { epoch++; stopCapture(); snapshot = null; renderSnapshot(); channel = $('live-workspace').value; refresh(); });
async function loadSettings() {
  const workspaceChannel = channel, currentEpoch = epoch;
  if (api.allowed('question_review')) {
    const aliases = await api.request('/channels/'+workspaceChannel+'/aliases');
    if (currentEpoch !== epoch || workspaceChannel !== channel) return;
    $('live-alias-list').replaceChildren(...aliases.map(value => node('li',value.canonical+': '+value.aliases.join(', '))));
  }
  if (api.identity?.selected_workspace.role === 'owner') {
    const grants = await api.request('/channels/'+workspaceChannel+'/moderators');
    if (currentEpoch !== epoch || workspaceChannel !== channel) return;
    $('live-grants').replaceChildren(...grants.map(value => {
      const row = node('div',`${value.display_name || value.login}: ${value.permissions.join(', ')}`); row.className='member';
      const revoke = node('button','Revoke'); revoke.addEventListener('click',() => action(async () => { await api.request('/channels/'+channel+'/moderators/'+value.user_id,{method:'DELETE'}); await loadSettings(); })); row.append(revoke); return row;
    }));
  }
}
$('live-alias-form').addEventListener('submit',event => { event.preventDefault(); action(async () => {
  await api.request('/channels/'+channel+'/aliases',{method:'PUT',body:{canonical:$('live-canonical').value,aliases:$('live-aliases').value.split('\n').map(value => value.trim()).filter(Boolean)}}); await loadSettings();
}); });
$('live-grant-form').addEventListener('submit',event => { event.preventDefault(); action(async () => {
  await api.request('/channels/'+channel+'/moderators',{method:'PUT',body:{login:$('live-mod-login').value,permissions:[...document.querySelectorAll('#live-grant-form input[name="permission"]:checked')].map(input=>input.value)}}); await loadSettings();
}); });
let loadedSettingsFor = '';
setInterval(() => {
  if (document.hidden || busy) return;
  refresh().then(() => {
    const key = api.identity?.selected_workspace.channel_id+':'+api.identity?.selected_workspace.permissions.join(',');
    if (snapshot && key !== loadedSettingsFor) { loadedSettingsFor = key; loadSettings().catch(err => error(err.message)); }
  });
},3000);
setInterval(() => {
  const deadline = snapshot?.game.round?.closes_at;
  text('live-countdown',deadline ? Math.max(0,Math.ceil((new Date(deadline).getTime()-Date.now())/1000))+'s remaining' : '');
},500);
window.addEventListener('pagehide',stopCapture);
refresh();
