import test from 'node:test';
import assert from 'node:assert/strict';
import { createPreviewServer, resolveAsset } from '../scripts/preview.mjs';

test('encoded traversal cannot expose workspace files', () => {
  assert.equal(resolveAsset('/..%5c..%5cREADME.md'), null);
});

test('preview rejects mutations and missing assets', async (t) => {
  const server = createPreviewServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const url = `http://127.0.0.1:${server.address().port}`;
  assert.equal((await fetch(url, { method: 'POST' })).status, 405);
  assert.equal((await fetch(url + '/missing-asset.js')).status, 404);
  const module = await fetch(url + '/model.mjs');
  assert.equal(module.status, 200);
  assert.match(module.headers.get('content-type'), /text\/javascript/);
});
