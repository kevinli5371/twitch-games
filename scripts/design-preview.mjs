import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const project = fileURLToPath(new URL('../', import.meta.url));
const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.mjs': 'text/javascript', '.svg': 'image/svg+xml' };

export function createDesignServer() {
  return http.createServer(async (req, res) => {
    if (!['GET', 'HEAD'].includes(req.method)) {
      res.writeHead(405, { Allow: 'GET, HEAD' }).end();
      return;
    }
    try {
      const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      if (pathname.includes('\\') || pathname.split('/').includes('..')) {
        res.writeHead(403).end('Forbidden');
        return;
      }
      if (['/', '/design', '/dashboard'].includes(pathname)) {
        res.writeHead(302, { Location: pathname === '/' ? '/design/' : `${pathname}/` }).end();
        return;
      }
      const area = pathname.startsWith('/dashboard/') ? 'dashboard' : pathname.startsWith('/design/') ? 'design' : null;
      const root = path.resolve(project, area ? `apps/${area}` : 'public');
      const relative = area ? pathname.slice(area.length + 2) || 'index.html' : pathname.slice(1);
      const target = path.resolve(root, relative);
      if (!target.startsWith(root + path.sep)) {
        res.writeHead(403).end('Forbidden');
        return;
      }
      const body = await readFile(target);
      res.writeHead(200, { 'Content-Type': `${types[path.extname(target)] || 'application/octet-stream'}; charset=utf-8`, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
      res.end(req.method === 'HEAD' ? undefined : body);
    } catch (error) {
      res.writeHead(error instanceof URIError ? 400 : 404).end('Not found');
    }
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 4175);
  createDesignServer().listen(port, '127.0.0.1', () => {
    console.log(`Design workspace: http://127.0.0.1:${port}/`);
  });
}
