const surfaces = {
  overlay: { url: '/preview.html', title: 'Desktop overlay', note: 'Try all three modes and answering, submitted, and results states below the stream.', width: 'fluid' },
  mobile: { url: '/design/mobile.html?demo=1', title: 'Mobile Extension view', note: 'A vertical fixture for chat-region composition. Twitch app and keyboard testing remain pending.', width: 'phone' },
  dashboard: { url: '/dashboard/', title: 'Streamer dashboard', note: 'Review and create fixture questions, explore the bank, and draft a round order. Live controls are disabled.', width: 'fluid' },
};
const frame = document.querySelector('#preview');
const viewport = document.querySelector('#viewport');
function resize() {
  frame.style.width = ({ fluid: '100%', desktop: '1280px', phone: '390px' })[viewport.value];
}
document.querySelectorAll('[data-surface]').forEach(button => {
  button.addEventListener('click', () => {
    const surface = surfaces[button.dataset.surface];
    document.querySelectorAll('[data-surface]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelector('#surface-title').textContent = surface.title;
    document.querySelector('#surface-note').textContent = surface.note;
    document.querySelector('#open-preview').href = surface.url;
    frame.title = `${surface.title} design preview`;
    frame.src = surface.url;
    viewport.value = surface.width;
    resize();
  });
});
viewport.addEventListener('change', resize);
