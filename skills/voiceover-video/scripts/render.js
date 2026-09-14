#!/usr/bin/env node
/**
 * render.js — drive a composition deterministically in headless Chromium
 *
 *   node render.js stills <index.html> <out-dir> <t1,t2,…>
 *   node render.js frames <index.html> <out-dir> <from-frame> <to-frame>
 *   node render.js cues   <index.html> <cues.json>
 *
 * The page must expose window.renderAt(t) and window.SFX. Viewport size is read from the
 * composition's --W / --H CSS variables so one renderer serves vertical and landscape.
 */
const path = require('path');
const fs = require('fs');
const { chromium } = require(path.join(__dirname, 'node_modules', 'playwright-core'));

const FPS = 30;
const [,, mode, htmlFile, target, a, b] = process.argv;

function usage(message) {
  console.error(message);
  console.error('Usage: render.js stills|frames|cues <index.html> <out> [args]');
  process.exit(1);
}

if (!['stills', 'frames', 'cues'].includes(mode)) usage(`Unknown mode: ${mode}`);
if (!htmlFile || !fs.existsSync(htmlFile)) usage(`No such composition: ${htmlFile}`);
if (mode === 'frames' && (Number.isNaN(Number(a)) || Number.isNaN(Number(b)) || b === undefined)) {
  usage(`frames needs <from-frame> <to-frame> as two separate numbers, got: ${a} ${b}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', request => errors.push(`missing file ${request.url()}`));
  await page.goto('file://' + path.resolve(htmlFile), { waitUntil: 'load' });
  if (!(await page.evaluate(() => typeof window.renderAt === 'function'))) {
    errors.forEach(message => console.error(`PAGE ERROR ${message}`));
    console.error('Composition did not initialise (window.renderAt is missing).');
    console.error('Next: a missing vendor/ file means setup.sh has not completed — re-run it; otherwise fix the first PAGE ERROR');
    await browser.close();
    process.exit(2);
  }
  const size = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    return { width: parseInt(style.getPropertyValue('--W')), height: parseInt(style.getPropertyValue('--H')) };
  });
  await page.setViewportSize(size);
  await page.evaluate(() => document.fonts.ready);

  if (mode === 'cues') {
    const cues = await page.evaluate(() => window.SFX);
    fs.writeFileSync(target, JSON.stringify(cues));
    console.log(`${cues.length} sound cues → ${target}`);
  }

  if (mode === 'stills') {
    fs.mkdirSync(target, { recursive: true });
    const times = (a || '').split(',').filter(Boolean).map(Number);
    for (const t of times) {
      await page.evaluate(x => window.renderAt(x), t);
      await page.screenshot({ path: path.join(target, `t${String(t.toFixed(2)).padStart(7, '0')}.jpg`), type: 'jpeg', quality: 70 });
    }
    console.log(`${times.length} stills → ${target}`);
  }

  if (mode === 'frames') {
    fs.mkdirSync(target, { recursive: true });
    for (let f = Number(a); f < Number(b); f++) {
      await page.evaluate(x => window.renderAt(x), f / FPS);
      await page.screenshot({ path: path.join(target, `f${String(f).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 92 });
    }
  }

  await browser.close();
  if (errors.length) {
    errors.forEach(message => console.error(`PAGE ERROR ${message}`));
    process.exit(2);
  }
})().catch(e => { console.error(e.message); process.exit(1); });
