// Development-only gateway: expose this listener, never the dashboard/API ports.
import http from 'node:http';
import {pathToFileURL} from 'node:url';
import {createAppHandler} from '../../scripts/app-handler.mjs';

const assets = new Set([
  '/viewer.html', '/mobile.html', '/styles.css', '/overlay-pixel.css',
  '/overlay.js', '/overlay-theme.js', '/demo-adapter.js', '/api-adapter.mjs',
  '/extension-config.js', '/fonts/Silkscreen-Regular.ttf', '/fonts/OFL.txt',
]);
const id = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';
const reads = [
  /^\/api\/v1\/channels\/[0-9]+\/game-state$/,
  new RegExp(`^/api/v1/rounds/${id}/me$`),
  new RegExp(`^/api/v1/games/${id}/leaderboard$`),
];
const answers = new RegExp(`^/api/v1/rounds/${id}/answers$`);
const maxBody = 16 * 1024;

function reply(res, status, code) {
  res.writeHead(status, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
  res.end(JSON.stringify({error: {code, message: code.replaceAll('_', ' ')}}));
}

export function createExtensionGateway({apiOrigin = 'http://127.0.0.1:8000', demoMode = false} = {}) {
  const origin = new URL(apiOrigin);
  if (origin.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(origin.hostname)
      || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash) {
    throw new Error('API_ORIGIN must be a loopback HTTP origin');
  }
  const serveAsset = createAppHandler();
  return http.createServer({maxHeaderSize: 16384}, async (req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    // Match raw paths, without normalizing encoded traversal into an allowed route.
    const path = (req.url || '').split('?')[0];
    if (demoMode && ['GET', 'HEAD'].includes(req.method) && ['/viewer.html', '/mobile.html'].includes(path)) {
      const url = new URL(req.url, 'http://localhost');
      if (url.searchParams.get('demo') !== '1') {
        url.searchParams.set('demo', '1');
        res.writeHead(307, {Location: url.pathname + url.search}); res.end(); return;
      }
    }
    if (demoMode && path.startsWith('/api/')) return reply(res, 503, 'demo_mode_no_backend');
    if ((assets.has(path) || (demoMode && ['/preview.html', '/preview.js'].includes(path))) && ['GET', 'HEAD'].includes(req.method)) {
      await serveAsset(req, res);
      return;
    }
    const allowed = (req.method === 'GET' && reads.some(rule => rule.test(path)))
      || (req.method === 'POST' && answers.test(path));
    if (!allowed || req.url.includes('?')) return reply(res, 404, 'not_found');
    const authorization = req.headers.authorization;
    if (!authorization?.startsWith('Bearer ') || authorization.length > 8192) {
      return reply(res, 401, 'extension_token_required');
    }
    if (req.method === 'POST' && req.headers['content-type']?.split(';')[0].trim() !== 'application/json') {
      return reply(res, 415, 'json_required');
    }
    if (Number(req.headers['content-length'] || 0) > maxBody) return reply(res, 413, 'request_too_large');
    try {
      let size = 0;
      const chunks = [];
      for await (const chunk of req) {
        size += chunk.length;
        if (size > maxBody) { reply(res, 413, 'request_too_large'); return; }
        chunks.push(chunk);
      }
      if (req.method === 'GET' && size) return reply(res, 400, 'unexpected_body');
      const body = Buffer.concat(chunks);
      const upstream = http.request(new URL(path, origin), {
        method: req.method,
        // Never forward dashboard cookies, CSRF values, or caller-supplied proxy headers.
        headers: {Authorization: authorization, 'Content-Type': 'application/json',
          'Content-Length': body.length},
      }, response => {
        res.writeHead(response.statusCode, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
        response.on('error', () => res.destroy());
        response.pipe(res);
      });
      upstream.setTimeout(30000, () => upstream.destroy());
      upstream.on('error', () => {
        if (!res.headersSent) reply(res, 502, 'backend_unavailable'); else res.destroy();
      });
      res.on('close', () => upstream.destroy());
      upstream.end(body);
    } catch {
      if (!res.headersSent && !res.destroyed) reply(res, 400, 'invalid_request');
    }
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const port = Number(process.env.PORT || 4176);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid PORT');
  createExtensionGateway({apiOrigin: process.env.API_ORIGIN, demoMode: process.env.EXTENSION_DEMO_MODE === '1'}).listen(port, '127.0.0.1', () => {
    console.log(`Mode: ${process.env.EXTENSION_DEMO_MODE === '1' ? 'SAMPLE DATA ONLY · no backend forwarding' : 'connected viewer'}`);
    console.log(`Extension-only gateway ready at http://127.0.0.1:${port}; no public tunnel started.`);
  });
}
