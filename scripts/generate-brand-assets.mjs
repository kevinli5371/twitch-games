import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

// Original editable geometry rebuilt from the selected Twillion concept.
// All wordmark letters are outlines: no fonts, raster images, or remote assets.
const mascot = `
    <path fill="#7042CB" d="M5 2h6v1h1v1h1v1h1v6h-1v2h-2v1H5v1H3v-2H2v-2H1V6h1V4h2V3h1Z"/>
    <rect fill="#2DD4A8" x="13" y="0" width="2" height="2"/>
    <path fill="#242131" d="M3 7h3v1H3zM10 5h2v1h-2z"/>
    <path fill="#FAF9F6" d="M3 8h4v3H3zM10 7h3v2h-3z"/>
    <path fill="#242131" d="M5 8h2v3H5v-1H4V9h1zM11 7h2v2h-1V8h-1zM6 13h3v-1h1v-1H9v1H6z"/>`;

const letters = {
  t: { width: 5, d: 'M0 0h2v3h3v2H2v4h3v2H2L0 9Z' },
  w: { width: 8, d: 'M0 3h2v5h1V5h2v3h1V3h2v6l-2 2H2L0 9Z' },
  i: { width: 2, d: 'M0 0h2v2H0zM0 4h2v7H0z' },
  l: { width: 3, d: 'M0 0h2v9l1 1v1H1l-1-1Z' },
  o: { width: 8, d: 'M2 3h4l2 2v4l-2 2H2L0 9V5Zm0 2v4h4V5Z' },
  n: { width: 8, d: 'M0 3h6l2 2v6H6V5H2v6H0Z' },
};

function wordmark() {
  let x = 0;
  return [...'twillion'].map(letter => {
    const glyph = letters[letter];
    const path = `<path data-letter="${letter}" transform="translate(${x} 0)" d="${glyph.d}"/>`;
    x += glyph.width + 1;
    return path;
  }).join('\n      ');
}

function svg({ full, theme }) {
  const transparent = theme.includes('transparent');
  const dark = theme.startsWith('dark');
  const width = full ? 928 : 160;
  const height = full ? 240 : 160;
  const label = `Twillion ${full ? 'full logo' : 'mascot icon'} — ${theme}`;
  const background = transparent ? '' : `\n  <rect width="${width}" height="${height}" fill="${dark ? '#242131' : '#FAF9F6'}"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title desc">
  <title id="title">${label}</title>
  <desc id="desc">A violet pixel mascot head with asymmetric eyes, a crooked smile and a mint pixel,${full ? ' beside an outlined twillion wordmark,' : ''} on ${transparent ? 'a transparent background' : `a ${theme} background`}. Flat editable vector shapes.</desc>${background}
  <g id="mascot" transform="${full ? 'translate(32 24) scale(12)' : 'translate(16 16) scale(8)'}" shape-rendering="crispEdges">${mascot}
  </g>${full ? `
  <g id="wordmark" transform="translate(256 60) scale(13)" fill="${dark ? '#FAF9F6' : '#242131'}" fill-rule="evenodd" aria-label="twillion">
      ${wordmark()}
  </g>` : ''}
</svg>
`;
}

const output = new URL('../public/brand/', import.meta.url);
await mkdir(output, { recursive: true });
for (const full of [false, true]) {
  for (const theme of ['light', 'dark', 'transparent', ...(full ? ['dark-transparent'] : [])]) {
    const filename = `twillion-${full ? 'logo' : 'icon'}-${theme}.svg`;
    await writeFile(new URL(filename, output), svg({ full, theme }));
    console.log(fileURLToPath(new URL(filename, output)));
  }
}
