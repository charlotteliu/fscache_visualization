import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';

const html = await readFile('s3fifo_visualization/index.html', 'utf8');
const css = await readFile('s3fifo_visualization/styles.css', 'utf8');
const js = await readFile('s3fifo_visualization/script.js', 'utf8');

test('page centers the three required horizontal FIFO queues', () => {
  assert.match(html, /Small FIFO/);
  assert.match(html, /Main FIFO/);
  assert.match(html, /Ghost FIFO/);
  assert.match(html, /FIFO Tail \/ In/);
  assert.match(html, /FIFO Head \/ Out/);
  assert.match(html, /enqueue tail/);
  assert.match(html, /dequeue head/);
  assert.match(css, /\.queue-row\s*\{/);
  assert.match(css, /minmax\(720px, 1fr\)/);
});

test('controls and metrics requested by review are present', () => {
  for (const label of ['Play', 'Pause', 'Step', 'Previous Step', 'Reset', 'Random Trace']) {
    assert.match(html, new RegExp(`>${label}<`));
  }
  for (const metric of ['Total Requests', 'Hits', 'Misses', 'Hit Ratio', 'Evictions', 'Ghost Hits', 'Current Request', 'Current Event']) {
    assert.match(html, new RegExp(metric));
  }
  for (const speed of ['0.25x', '0.5x', '1x', '2x', '4x']) {
    assert.match(html, new RegExp(speed));
  }
});

test('script supports trace parsing, step history, race guard, and requested animations', () => {
  assert.match(js, /split\(\/\[\\s,\]\+\//);
  assert.match(js, /previousStep/);
  assert.match(js, /state\.isAnimating/);
  assert.match(js, /smallToMain/);
  assert.match(js, /smallToGhost/);
  assert.match(js, /mainReinsert/);
  assert.match(js, /ghostHit/);
  assert.match(css, /fly-curve/);
  assert.match(css, /fade-evict/);
  assert.match(css, /pulse/);
});

test('accessibility requirements are covered statically', () => {
  assert.match(html, /aria-label="Play simulation"/);
  assert.match(html, /aria-label="Pause simulation"/);
  assert.match(html, /aria-label="Advance one animation step"/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(js, /keydown/);
  assert.match(js, /status-text-hit/);
});
