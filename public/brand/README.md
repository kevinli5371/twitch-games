# Twillion brand assets

Editable SVG reconstructions of the selected pixel-head logo concept. All artwork and wordmark letters are vector paths/rectangles; no embedded bitmap, font dependency, gradients, or external resources.

| Asset | Light background | Dark background | Transparent |
| --- | --- | --- | --- |
| Mascot head | [Icon](twillion-icon-light.svg) | [Icon](twillion-icon-dark.svg) | [Icon](twillion-icon-transparent.svg) |
| Head + wordmark | [Full logo](twillion-logo-light.svg) | [Full logo](twillion-logo-dark.svg) | [Full logo](twillion-logo-transparent.svg) |

The light/dark exports include a solid background. Transparent exports have no background; the transparent full wordmark uses dark ink for placement on light surfaces. The mascot geometry is identical in every variant. The wordmark is a hand-built vector interpretation of the generated concept, not a pixel-for-pixel trace.

[Dark transparent full logo](twillion-logo-dark-transparent.svg) uses white lettering for dark surfaces. The dashboard switches between the two transparent wordmarks with its theme and uses the transparent mascot as its favicon.

Palette: violet `#7042CB`, mint `#2DD4A8`, ink `#242131`, warm white `#FAF9F6`.

Regenerate all six files with `node scripts/generate-brand-assets.mjs`. Edit the geometry in that script to keep variants consistent. Preview `/brand/index.html` using the local design server.
