import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch (error) {
  console.warn('Playwright package is not installed; skipping browser smoke test in this environment.');
  console.warn('Install with: npm install --save-dev playwright && npx playwright install chromium');
  process.exit(0);
}

const mimeTypes = new Map([
  ['.html', 'text/html; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
]);

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? '/', 'http://127.0.0.1');
  const safePath = normalize(url.pathname === '/' ? '/s3fifo_visualization/index.html' : url.pathname).replace(/^\.\.(\/|\\|$)/, '');
  const filePath = join(process.cwd(), safePath);
  try {
    const body = await readFile(filePath);
    response.writeHead(200, { 'content-type': mimeTypes.get(extname(filePath)) ?? 'application/octet-stream' });
    response.end(body);
  } catch {
    response.writeHead(404);
    response.end('not found');
  }
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const { port } = server.address();
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(`http://127.0.0.1:${port}/s3fifo_visualization/index.html`);
  await page.getByRole('heading', { name: 'How does S3-FIFO work?' }).waitFor();
  await page.getByRole('button', { name: 'Step' }).click();
  await page.getByText('Current Request').waitFor();
  await page.getByText('Small FIFO').waitFor();
  await page.getByText('Main FIFO').waitFor();
  await page.getByText('Ghost FIFO').waitFor();
  console.log('Playwright smoke test passed.');
} finally {
  await browser.close();
  server.close();
}
