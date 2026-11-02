// Twitch owns the live theme. A query parameter/control supports local review.
(() => {
  let override = new URLSearchParams(location.search).get('theme');
  if (!['light', 'dark'].includes(override)) override = null;
  function apply(theme) {
    if (!['light', 'dark'].includes(theme)) return;
    document.documentElement.dataset.theme = theme;
  }
  apply(override || 'light');
  window.Twitch?.ext?.onContext?.(context => {
    if (!override) apply(context.theme);
  });
  window.StreamGameTheme = Object.freeze({
    set(theme) { if (['light', 'dark'].includes(theme)) { override = theme; apply(theme); } },
  });
})();
