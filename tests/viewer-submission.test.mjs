import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../public/overlay.js', import.meta.url), 'utf8');
const response = body => ({ ok: true, status: 200, json: async () => body });
const state = (roundId, phase, version) => ({
  version, game: { id: 'sample-game', status: 'active' },
  round: { id: roundId, mode: 'quote_completion', phase, prompt: { text: 'A ____ prompt.' } },
});
async function until(predicate) {
  for (let i = 0; i < 10; i++) {
    if (predicate()) return;
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.fail('Expected adapter update was not emitted');
}
function harness() {
  const callbacks = {};
  let publicState = state('round-a', 'answering', 1);
  let finishSubmission;
  const context = vm.createContext({
    document: { getElementById: () => null, hidden: false },
    window: {
      location: { search: '' },
      TWITCH_GAMES_CONFIG: { apiBaseUrl: 'https://fixture.invalid' },
      Twitch: { ext: {
        viewer: { isLinked: true, id: 'fixture-viewer', onChanged() {} },
        onAuthorized(callback) { callbacks.authorized = callback; },
        listen(_topic, callback) { callbacks.pubsub = callback; },
      } },
    },
    URLSearchParams,
    setInterval: () => 1, clearInterval() {}, setTimeout: () => 1, clearTimeout() {},
    fetch: async (url, options) => {
      if (options.method === 'POST') return new Promise(resolve => { finishSubmission = resolve; });
      if (url.endsWith('/game-state')) return response(publicState);
      return response({ submission: null });
    },
  });
  vm.runInContext(source, context);
  const adapter = vm.runInContext('createTwitchAdapter()', context);
  const updates = [];
  adapter.subscribe(snapshot => updates.push(snapshot));
  callbacks.authorized({ channelId: 'fixture-channel', token: 'fixture-token' });
  return {
    adapter, updates,
    complete(response) { finishSubmission(response); },
    publish(next) {
      publicState = next;
      callbacks.pubsub('broadcast', 'application/json', JSON.stringify({ type: 'game_updated', version: next.version, snapshot: next }));
    },
  };
}

for (const [label, next] of [
  ['a newer round', state('round-b', 'answering', 2)],
  ['published results', state('round-a', 'results', 2)],
]) {
  test(`a late answer receipt cannot overwrite ${label}`, async () => {
    const fixture = harness();
    await until(() => fixture.updates.at(-1).roundId === 'round-a');
    const submission = fixture.adapter.submit('old answer');
    fixture.publish(next);
    await until(() => fixture.updates.at(-1).roundId === next.round.id && fixture.updates.at(-1).phase === next.round.phase);
    fixture.complete(response({}));
    await submission;
    const latest = fixture.updates.at(-1);
    assert.equal(latest.roundId, next.round.id);
    assert.equal(latest.phase, next.round.phase);
    assert.notEqual(latest.ownSubmission?.answer, 'old answer');
  });
}

test('a failed submission is never presented as a confirmed receipt', async () => {
  const fixture = harness();
  await until(() => fixture.updates.at(-1).roundId === 'round-a');
  const submission = fixture.adapter.submit('unconfirmed answer');
  fixture.complete({ ok: false, status: 503 });
  await assert.rejects(submission, /could not complete/);
  assert.equal(fixture.updates.at(-1).phase, 'answering');
  assert.equal(fixture.updates.at(-1).ownSubmission, null);
});
