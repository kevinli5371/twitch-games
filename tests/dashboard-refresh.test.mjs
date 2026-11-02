import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRefreshRunner} from '../apps/dashboard/refresh-flight.mjs';

function pending() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}

test('slow dashboard polls share a request instead of invalidating its response', async () => {
  const response = pending(); let calls = 0;
  const refresh = createRefreshRunner(() => { calls++; return response.promise; }, () => 0);
  const first = refresh();
  for (let n = 0; n < 20; n++) assert.equal(refresh(), first);
  await Promise.resolve(); assert.equal(calls, 1);
  response.resolve('authoritative snapshot');
  assert.equal(await first, 'authoritative snapshot');
  await refresh(); assert.equal(calls, 2);
});

test('workspace changes do not wait for old polls or lose the new in-flight request', async () => {
  const old = pending(), current = pending(); let epoch = 0, calls = 0;
  const refresh = createRefreshRunner(() => { calls++; return epoch ? current.promise : old.promise; }, () => epoch);
  const first = refresh(); await Promise.resolve(); epoch++;
  const second = refresh(); await Promise.resolve(); assert.notEqual(first, second);
  old.resolve('old workspace'); await first;
  assert.equal(refresh(), second); assert.equal(calls, 2);
  current.resolve('new workspace'); assert.equal(await second, 'new workspace');
});

test('failed polls release the request so recovery can retry', async () => {
  let calls = 0;
  const refresh = createRefreshRunner(async () => {
    if (++calls === 1) throw new Error('temporary network failure'); return 'recovered';
  }, () => 0);
  await assert.rejects(refresh(), /temporary network failure/);
  assert.equal(await refresh(), 'recovered');
});

test('a completed command starts a fresh snapshot instead of joining a pre-command poll', async () => {
  const old = pending(), updated = pending(); let calls = 0;
  const refresh = createRefreshRunner(() => ++calls === 1 ? old.promise : updated.promise, () => 0);
  const previous = refresh(); await Promise.resolve();
  const afterCommand = refresh({force:true}); await Promise.resolve();
  assert.notEqual(afterCommand, previous); assert.equal(calls, 2);
  old.resolve('before command'); await previous;
  assert.equal(refresh(), afterCommand);
  updated.resolve('after command'); assert.equal(await afterCommand, 'after command');
});
