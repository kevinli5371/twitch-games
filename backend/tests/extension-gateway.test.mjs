import {test} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {createExtensionGateway} from '../scripts/extension_gateway.mjs';

const round = '00000000-0000-4000-8000-000000000001';
async function listen(server) {
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  return `http://127.0.0.1:${server.address().port}`;
}
async function close(server) {
  server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
}

test('real HTTP gateway exposes assets and only the authenticated viewer operations', async () => {
  const received = [];
  const upstream = http.createServer(async (req, res) => {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    received.push({url: req.url, method: req.method, headers: req.headers, body: Buffer.concat(chunks).toString()});
    res.writeHead(200, {'Content-Type': 'application/json', 'Set-Cookie': 'must-not-escape=1'});
    res.end(JSON.stringify({fixture: true}));
  });
  const apiOrigin = await listen(upstream);
  const gateway = createExtensionGateway({apiOrigin});
  const base = await listen(gateway);
  try {
    for (const path of ['/viewer.html', '/mobile.html', '/overlay.js', '/api-adapter.mjs', '/styles.css', '/fonts/Silkscreen-Regular.ttf']) {
      const r = await fetch(base + path); assert.equal(r.status, 200, path); await r.arrayBuffer();
    }
    const config = await (await fetch(base + '/extension-config.js')).text();
    assert.ok(config.includes('location.origin')); assert.ok(!config.includes('localhost'));
    for (const [method, path] of [
      ['GET', '/'], ['GET', '/dashboard/index.html'], ['GET', '/.env'], ['GET', '/backend/.env'],
      ['GET', '/api/v1/auth/me'], ['GET', '/api/v1/dashboard/channels/1602828445'],
      ['POST', '/api/v1/channels/1602828445/games'], ['POST', `/api/v1/rounds/${round}/close`],
      ['POST', `/api/v1/games/${round}/end`], ['GET', '/api/v1/channels/1602828445/moderators'],
      ['GET', '/health/ready'], ['GET', '/docs'], ['GET', '/preview.html'],
      ['GET', '/%76iewer.html'], ['GET', '/api/v1/channels/1602828445/game-state?x=1'],
    ]) {
      const r = await fetch(base + path, {method, headers: {Authorization: 'Bearer fixture'}});
      assert.equal(r.status, 404, path); await r.text();
    }
    const state = '/api/v1/channels/1602828445/game-state';
    assert.equal((await fetch(base + state, {headers: {Cookie: 'dashboard_session=fixture'}})).status, 401);
    assert.equal(received.length, 0);
    for (const path of [state, `/api/v1/rounds/${round}/me`, `/api/v1/games/${round}/leaderboard`]) {
      const r = await fetch(base + path, {headers: {Authorization: 'Bearer fixture', Cookie: 'dashboard_session=fixture', 'X-CSRF-Token': 'fixture'}});
      assert.equal(r.status, 200); assert.equal(r.headers.get('set-cookie'), null); await r.text();
      const forwarded = received.at(-1); assert.equal(forwarded.headers.cookie, undefined);
      assert.equal(forwarded.headers['x-csrf-token'], undefined);
    }
    const body = JSON.stringify({request_id: round, answer: '  Raw Answer  '});
    const submit = `/api/v1/rounds/${round}/answers`;
    const headers = {Authorization: 'Bearer fixture', 'Content-Type': 'application/json'};
    const r = await fetch(base + submit, {method: 'POST', headers, body});
    assert.equal(r.status, 200); await r.text(); assert.equal(received.at(-1).body, body);
    const count = received.length;
    assert.equal((await fetch(base + submit, {method: 'POST', headers: {Authorization: 'Bearer fixture'}, body})).status, 415);
    assert.equal((await fetch(base + submit, {method: 'POST', headers, body: 'x'.repeat(16385)})).status, 413);
    assert.equal(received.length, count);
  } finally { await close(gateway); await close(upstream); }
});

test('gateway rejects non-loopback upstream configuration', () => {
  for (const apiOrigin of ['http://example.com', 'https://localhost:8000', 'http://u:p@localhost:8000', 'http://localhost:8000/api']) {
    assert.throws(() => createExtensionGateway({apiOrigin}));
  }
});
