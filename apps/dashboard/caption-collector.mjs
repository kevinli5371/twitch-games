// Twitch documents a string payload: https://dev.twitch.tv/docs/embed/video-and-clips/#javascript-events
export function createCaptionQueue({send, onStatus = () => {}, uuid = () => crypto.randomUUID(), now = () => new Date().toISOString()}) {
  const queue = []; let sequence = 0, inFlight = null, stopped = false;
  return {
    push(text) {
      if (stopped || typeof text !== 'string' || !text.trim()) return;
      if (text.length > 4000 || queue.length >= 100) { stopped = true; onStatus('Capture paused: the caption buffer is full or a batch is too large. Reconnect the source.'); return; }
      queue.push({batch_id:uuid(), source:'twitch_player_captions', segments:[{sequence:sequence++, text, observed_at:now()}]});
    },
    flush() {
      if (stopped || inFlight || !queue.length) return inFlight;
      const batch = queue[0];
      inFlight = Promise.resolve().then(() => send(batch)).then(() => {
        queue.shift(); if (!stopped) onStatus('Captions received by the backend.');
      }).catch(error => { if (!stopped) onStatus('Caption upload pending retry: '+error.message); })
        .finally(() => { inFlight = null; });
      return inFlight;
    },
    stop() { stopped = true; queue.length = 0; },
    get pending() { return queue.length; },
  };
}
