import test from 'node:test';
import assert from 'node:assert/strict';
import { createDesignServer } from '../scripts/design-preview.mjs';

test('design workspace serves both fixture surfaces while excluding private project files', async (t) => {
  const server = createDesignServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = `http://127.0.0.1:${server.address().port}`;
  for (const asset of ['/', '/design/workspace.js', '/preview.html', '/dashboard/', '/dashboard/model.mjs', '/design/mobile.html?demo=1']) {
    assert.equal((await fetch(base + asset)).status, 200, asset);
  }
  for (const privatePath of ['/backend/.env', '/.env', '/README.md', '/apps/dashboard/index.html']) {
    assert.equal((await fetch(base + privatePath)).status, 404, privatePath);
  }
  assert.equal((await fetch(base + '/dashboard/..%5c..%5c.env')).status, 403);
  assert.equal((await fetch(base + '/design/%2e%2e%2fbackend/.env')).status, 403);
  assert.equal((await fetch(base + '/', { method: 'POST' })).status, 405);
});
