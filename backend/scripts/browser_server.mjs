// Disposable browser-test transport only. Never used by the product server or Extension bundle.
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {createAppHandler} from '../../scripts/app-handler.mjs';
const context=JSON.parse(process.env.BROWSER_STACK_CONTEXT || '{}');
if (!context.channel || !process.env.API_ORIGIN?.startsWith('http://127.0.0.1:')) throw new Error('Fixture backend required');
const app=createAppHandler({apiOrigin:process.env.API_ORIGIN});
const helper=`(() => {
 const users=${JSON.stringify(context.viewers)};
 const selected=new URLSearchParams(location.search).get('viewer')==='2'?users[1]:users[0];
 let callback=null,cursor=0,count=0;
 window.Twitch={ext:{viewer:{isLinked:true,id:selected.id},onAuthorized:fn=>fn({channelId:${JSON.stringify(context.channel)},token:selected.token}),
 listen:(topic,fn)=>{if(topic==='broadcast')callback=fn;},actions:{},onVisibilityChanged:()=>{}}};
 setInterval(async()=>{if(!callback)return;try{
  const packet=await(await fetch('/test-events?after='+cursor)).json();cursor=packet.cursor;
  for(const event of packet.events){count++;callback('broadcast','application/json',JSON.stringify(event));}
  const badge=document.getElementById('fixture-notices');if(badge)badge.textContent=' · Public notices: '+count;
 }catch{}},400);
})();`;
const player=`(() => {class Player{static READY='ready';static CAPTIONS='captions';static OFFLINE='offline';constructor(id){this.listeners={};const root=document.getElementById(id);root.textContent='Synthetic captioned broadcast fixture — not live Twitch';const button=document.createElement('button');button.textContent='Send synthetic captions';button.onclick=()=>this.listeners.captions?.('The incredible championship finished with a brilliant victory for our team.');root.append(button);}addEventListener(name,fn){this.listeners[name]=fn;if(name==='ready')setTimeout(fn,0);}enableCaptions(){}pause(){}}window.Twitch={Player};})();`;
createServer(async(req,res)=>{
 const path=new URL(req.url,'http://127.0.0.1').pathname;
 const send=(type,body)=>{res.writeHead(200,{'Content-Type':type,'Cache-Control':'no-store'});res.end(body);};
 if(path==='/test-helper.js')return send('text/javascript',helper);
 if(path==='/test-player.js')return send('text/javascript',player);
 if(path==='/test-events'){
  if(!context.eventsUrl?.startsWith('http://127.0.0.1:')){res.writeHead(503).end();return;}
  const after=Number(new URL(req.url,'http://127.0.0.1').searchParams.get('after')||0);
  const response=await fetch(context.eventsUrl+'?after='+Math.max(0,after));
  return send('application/json',await response.text());
 }
 // Disable fallback polling only in this harness, proving notices drive updates.
 if(path==='/api-adapter.mjs'){
  const code=await readFile(new URL('../../public/api-adapter.mjs',import.meta.url),'utf8');
  if(!code.includes('pollMs = 3000'))throw new Error('Viewer poll setting changed; update test instrumentation');
  return send('text/javascript',code.replace('pollMs = 3000','pollMs = 3600000'));
 }
 if(path==='/dashboard/live.js'){
  const code=await readFile(new URL('../../apps/dashboard/live.js',import.meta.url),'utf8');
  return send('text/javascript',code.replace('https://player.twitch.tv/js/embed/v1.js','/test-player.js'));
 }
 if(['/viewer.html','/mobile.html'].includes(path)){
  let html=await readFile(new URL('../../public'+path,import.meta.url),'utf8');
  html=html.replace('https://extension-files.twitch.tv/helper/v1/twitch-ext.min.js','/test-helper.js');
  html=html.replace('<body ', '<body style="padding-top:50px" ').replace('<main ', '<div style="position:fixed;top:0;left:0;right:0;background:#412d65;color:white;padding:12px;z-index:1000;text-align:center">LOCAL INTEGRATION TEST · Synthetic Twitch identity and caption source<span id="fixture-notices"></span></div><main ');
  return send('text/html',html);
 }
 app(req,res);
}).listen(Number(process.env.PORT),'127.0.0.1',()=>console.log('Disposable browser stack ready at http://127.0.0.1:'+process.env.PORT));
