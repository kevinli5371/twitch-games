import {createServer} from 'node:http';
import {createAppHandler} from './app-handler.mjs';
const port = Number(process.env.PORT || 4173);
createServer(createAppHandler({apiOrigin:process.env.API_ORIGIN || 'http://127.0.0.1:8000'}))
  .listen(port, '127.0.0.1', () => console.log(`Dashboard: http://localhost:${port}/ · API proxied to FastAPI`));
