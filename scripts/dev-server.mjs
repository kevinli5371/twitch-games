import {createServer} from 'node:https';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createAppHandler} from './app-handler.mjs';
const cert = fileURLToPath(new URL('../certs/', import.meta.url));
let tls;
try { tls = {cert:await readFile(cert+'localhost.pem'), key:await readFile(cert+'localhost-key.pem')}; }
catch { console.error('Run npm run cert and trust the local CA before using the Twitch HTTPS surface.'); process.exit(1); }
const port = Number(process.env.PORT || 4174);
createServer(tls, createAppHandler({apiOrigin:process.env.API_ORIGIN || 'http://127.0.0.1:8000'}))
 .listen(port, '127.0.0.1', () => console.log(`Twitch Testing Base URI: https://localhost:${port}/ · Viewer path: viewer.html · Mobile path: mobile.html`));
