import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';

const files = [
  's3fifo_visualization/index.html',
  's3fifo_visualization/styles.css',
  's3fifo_visualization/script.js',
];

const [html, css, js] = await Promise.all(files.map((file) => readFile(file, 'utf8')));
const failures = [];

if (!html.includes('href="styles.css"')) failures.push('index.html must link styles.css');
if (!html.includes('src="script.js"')) failures.push('index.html must load script.js');
if (!html.includes('Small FIFO') || !html.includes('Main FIFO') || !html.includes('Ghost FIFO')) {
  failures.push('index.html must render all three FIFO queue rows');
}
if (!html.includes('aria-label="Play simulation"')) failures.push('control buttons must expose aria-labels');
if (!css.includes('@media (prefers-reduced-motion: reduce)')) failures.push('styles.css must support prefers-reduced-motion');
if (!css.includes('overflow-x: auto')) failures.push('styles.css must allow narrow-screen horizontal scrolling');
if (!js.includes('state.isAnimating') || !js.includes('lockDuringAnimation')) {
  failures.push('script.js must guard animation state to avoid races');
}

const syntax = spawnSync(process.execPath, ['--check', 's3fifo_visualization/script.js'], { encoding: 'utf8' });
if (syntax.status !== 0) failures.push(syntax.stderr || syntax.stdout || 'script.js syntax check failed');

if (failures.length) {
  console.error(failures.map((failure) => `- ${failure}`).join('\n'));
  process.exit(1);
}

console.log('Static S3-FIFO visualization build checks passed.');
