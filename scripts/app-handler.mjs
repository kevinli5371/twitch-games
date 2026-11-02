import http from 'node:http';
import https from 'node:https';
import {readFile, stat} from 'node:fs/promises';
import {resolve, extname, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const types = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml'};
export function resolveAsset(url) {
  const pathname = decodeURIComponent(new URL(url, 'http://localhost').pathname);
  if (pathname.includes('\\') || pathname.includes('\0')) return null;
  const dashboard = pathname === '/' || pathname.startsWith('/dashboard/');
  const base = resolve(root, dashboard ? 'apps/dashboard' : 'public');
  const path = pathname === '/' ? '/index.html' : dashboard ? pathname.slice('/dashboard'.length) : pathname;
  const target = resolve(base, '.' + path);
  if (!target.startsWith(base + sep) || !Object.hasOwn(types, extname(target))) return null;
  return target;
}
export function createAppHandler({apiOrigin = 'http://127.0.0.1:8000'} = {}) {
  const upstream = new URL(apiOrigin);
  if (!['http:', 'https:'].includes(upstream.protocol) || upstream.username || upstream.password) throw new Error('Invalid API origin');
  return async (req, res) => {
    let pathname, query;
    try { const url = new URL(req.url, 'http://localhost'); pathname = url.pathname; query = url.search; }
    catch { res.writeHead(400).end('Bad request'); return; }
    if (pathname.startsWith('/api/v1/') || pathname.startsWith('/health/')) {
      const transport = upstream.protocol === 'https:' ? https : http;
      const proxy = transport.request(new URL(pathname + query, upstream), {
        method: req.method, headers: {...req.headers, host: upstream.host},
      }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
      proxy.on('error', () => { if (!res.headersSent) res.writeHead(502, {'Content-Type':'application/json'}); res.end(JSON.stringify({error:{code:'backend_unavailable',message:'Start the FastAPI backend on its configured port.'}})); });
      req.on('aborted', () => proxy.destroy());
      req.pipe(proxy); return;
    }
    if (!['GET','HEAD'].includes(req.method)) { res.writeHead(405, {Allow:'GET, HEAD'}).end(); return; }
    if (pathname === '/extension-config.js') {
      res.writeHead(200, {'Content-Type':types['.js'],'Cache-Control':'no-store'});
      res.end(req.method === 'HEAD' ? undefined : 'window.TWITCH_GAMES_CONFIG=Object.freeze({apiBaseUrl:location.origin+"/api/v1"});'); return;
    }
    try {
      const target = resolveAsset(req.url);
      if (!target) { res.writeHead(403).end('Forbidden'); return; }
      const info = await stat(target);
      if (!info.isFile()) throw new Error('Not a file');
      res.writeHead(200, {'Content-Type':types[extname(target)],'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
      res.end(req.method === 'HEAD' ? undefined : await readFile(target));
    } catch (error) { res.writeHead(error instanceof URIError ? 400 : 404).end('Not found'); }
  };
}
