#!/usr/bin/env node
/**
 * render.js — drive a composition deterministically in headless Chromium
 *
 *   node render.js stills <index.html> <out-dir> <t1,t2,…>
 *   node render.js frames <index.html> <out-dir> <from-frame> <to-frame>  (to-frame is exclusive)
 *   node render.js cues   <index.html> <cues.json>
 *   node render.js check  <index.html> [report.json]
 *
 * The page must expose window.renderAt(t) and window.SFX. Viewport size is read from the
 * composition's --W / --H CSS variables so one renderer serves vertical and landscape.
 *
 * Frames render at 2x device pixels and are saved at 1x as lossless PNG (supersampled: crisp
 * edges, no JPEG chroma bleed on red text). VV_QUALITY=draft saves 1x JPEG instead, ~4x faster.
 */
const path = require('path');
const fs = require('fs');
const { chromium } = require(path.join(__dirname, 'node_modules', 'playwright-core'));

const FPS = 30;
const DRAFT = process.env.VV_QUALITY === 'draft';
const [,, mode, htmlFile, target, a, b] = process.argv;

function usage(message) {
  console.error(message);
  console.error('Usage: render.js stills|frames|cues|check <index.html> [out] [args]');
  process.exit(1);
}

if (!['stills', 'frames', 'cues', 'check'].includes(mode)) usage(`Unknown mode: ${mode}`);
if (!htmlFile || !fs.existsSync(htmlFile)) usage(`No such composition: ${htmlFile}`);
if (mode === 'frames' && (Number.isNaN(Number(a)) || Number.isNaN(Number(b)) || b === undefined)) {
  usage(`frames needs <from-frame> <to-frame> as two separate numbers, got: ${a} ${b}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: DRAFT ? 1 : 2 });
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

  // Layout QA without eyes: measure every shot at 25%, 50% and 85% of its window and report what a still would show
  if (mode === 'check') {
    const shots = await page.evaluate(() => window.SHOTS || []);
    if (!shots.length) {
      console.error('No shots registered in window.SHOTS');
      console.error('Next: author the timeline with shot()/faceCam(), or re-fill the template if it predates window.SHOTS');
      await browser.close();
      process.exit(2);
    }

    const report = [];
    for (const shotWindow of shots) {
      const samples = [0.25, 0.5, 0.85].map(p => Number((shotWindow.s + p * (shotWindow.e - shotWindow.s)).toFixed(2)));
      const measured = [];
      for (const sampleTime of samples) {
        await page.evaluate(x => window.renderAt(x), sampleTime);
        const found = await page.evaluate(({ id, W, H }) => {
          const section = document.getElementById(id);
          if (!section) return { missing: true, overflow: [], collide: [], visible: 0 };
          const decorative = /gridbg|glow|scan|track|pkt|bars|strike|vhs|ticker/;
          const named = el => (el.id ? '#' + el.id : '.' + ((el.getAttribute('class') || el.tagName.toLowerCase()).split(' ')[0]));
          const capbox = document.getElementById('capbox');
          const capRect = capbox && capbox.style.visibility !== 'hidden' && capbox.children.length
            ? capbox.getBoundingClientRect()
            : null;
          const out = { missing: false, overflow: [], collide: [], visible: 0 };
          const seenNames = new Map();
          for (const el of section.querySelectorAll('*')) {
            // Counted before any filter so an element keeps its index whether or not it offends at this sample
            const label = named(el);
            const nth = seenNames.get(label) || 0;
            seenNames.set(label, nth + 1);
            const classes = el.getAttribute('class') || '';
            if (decorative.test(classes) || el.closest('.ticker')) continue;
            const style = getComputedStyle(el);
            if (style.visibility === 'hidden' || style.display === 'none' || parseFloat(style.opacity) < 0.05) continue;
            const rect = el.getBoundingClientRect();
            if (rect.width < 2 || rect.height < 2) continue;
            const isText = el.children.length === 0 && el.textContent.trim().length > 0;
            const isBlock = el.tagName === 'IMG' || /card|term|logo|stamp|badge/.test(classes);
            if (!isText && !isBlock) continue;
            out.visible += 1;
            // A centred .cx block spans the whole frame even when its text runs past the edge, so
            // measure the text itself; images and cards are measured by their own box
            let box = rect;
            // A pushed-in photo overflows its frame by design; the frame clips it, so measure the frame
            const frame = el.tagName === 'IMG' ? el.parentElement : null;
            if (frame && frame !== section && getComputedStyle(frame).overflow === 'hidden') box = frame.getBoundingClientRect();
            if (isText) {
              const range = document.createRange();
              range.selectNodeContents(el);
              const textRect = range.getBoundingClientRect();
              if (textRect.width > 1 && textRect.height > 1) box = textRect;
            }
            if (box.left < -2 || box.top < -2 || box.right > W + 2 || box.bottom > H + 2) {
              out.overflow.push({ nth, item: `${label} at ${Math.round(box.left)},${Math.round(box.top)} ${Math.round(box.width)}x${Math.round(box.height)}` });
            }
            if (capRect && isText && box.left < capRect.right && box.right > capRect.left && box.top < capRect.bottom && box.bottom > capRect.top) {
              out.collide.push({ nth, item: label });
            }
          }
          return out;
        }, { id: shotWindow.id, W: size.width, H: size.height });
        measured.push(found);
      }
      // One line per element, keyed by name and occurrence so a moving element merges but same-class siblings stay apart; the first box seen is shown
      const merge = key => {
        const byItem = new Map();
        measured.forEach((found, index) => found[key].forEach(({ item, nth }) => {
          const identity = `${item.split(' at ')[0]}#${nth}`;
          const entry = byItem.get(identity) || { item, times: [] };
          entry.times.push(samples[index]);
          byItem.set(identity, entry);
        }));
        return [...byItem.values()];
      };
      // Empty only counts when every sample is empty; a shot empty at 25% is still animating in
      report.push({
        ...shotWindow, samples,
        missing: measured[0].missing,
        visible: Math.max(...measured.map(found => found.visible)),
        overflow: merge('overflow'),
        collide: merge('collide'),
      });
    }

    const flagged = report.filter(r => r.missing || !r.visible || r.overflow.length || r.collide.length);
    const total = key => report.reduce((sum, r) => sum + r[key].length, 0);
    if (target) fs.writeFileSync(target, JSON.stringify(report, null, 2));
    console.log(`${report.length} shots checked · ${total('overflow')} past the frame edge · ${total('collide')} caption collisions · ${report.filter(r => !r.missing && !r.visible).length} empty`);
    for (const r of flagged) {
      const seen = times => `(${times.map(t => t.toFixed(2) + 's').join('·')})`;
      if (r.missing) console.log(`  ${r.id} missing — no element with that id`);
      else if (!r.visible) console.log(`  ${r.id} empty ${seen(r.samples)} — nothing visible`);
      r.overflow.forEach(({ item, times }) => console.log(`  ${r.id} past the edge: ${item} ${seen(times)}`));
      r.collide.forEach(({ item, times }) => console.log(`  ${r.id} under the captions: ${item} ${seen(times)}`));
    }
    errors.forEach(message => console.error(`PAGE ERROR ${message}`));
    await browser.close();
    if (flagged.length || errors.length) {
      console.log('Next: fix those shots (resize the type, move it inside the safe zone, or hide captions with NOCAP), then re-run check');
      process.exit(1);
    }
    console.log('Next: render stills if you can view images, then render frames');
    process.exit(0);
  }

  if (mode === 'stills') {
    fs.mkdirSync(target, { recursive: true });
    if (!a) {
      usage('stills needs a comma-separated timestamp list');
    }
    const times = a.split(',').map(s => Number(s.trim())).filter(t => !Number.isNaN(t));
    if (!times.length) {
      usage('stills timestamp list parsed to zero valid numbers');
    }
    for (const t of times) {
      await page.evaluate(x => window.renderAt(x), t);
      await page.screenshot({ path: path.join(target, `t${String(t.toFixed(2)).padStart(7, '0')}.jpg`), type: 'jpeg', quality: 85, scale: 'css' });
    }
    console.log(`${times.length} stills → ${target}`);
  }

  if (mode === 'frames') {
    fs.mkdirSync(target, { recursive: true });
    const [ext, other] = DRAFT ? ['jpg', 'png'] : ['png', 'jpg'];
    for (let f = Number(a); f < Number(b); f++) {
      await page.evaluate(x => window.renderAt(x), f / FPS);
      const name = path.join(target, `f${String(f).padStart(5, '0')}`);
      await page.screenshot({ path: `${name}.${ext}`, scale: 'css', ...(DRAFT ? { type: 'jpeg', quality: 92 } : { type: 'png' }) });
      // A frame from an earlier render in the other quality would be encoded alongside this one
      fs.rmSync(`${name}.${other}`, { force: true });
    }
  }

  await browser.close();
  if (errors.length) {
    errors.forEach(message => console.error(`PAGE ERROR ${message}`));
    process.exit(2);
  }
})().catch(e => { console.error(e.message); process.exit(1); });
