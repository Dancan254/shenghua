#!/usr/bin/env node
/**
 * render.js — drive a composition deterministically in headless Chromium
 *
 *   node render.js stills <index.html> <out-dir> <t1,t2,…>
 *   node render.js frames <index.html> <out-dir> <from-frame> <to-frame> [subframes]  (to-frame is exclusive)
 *   node render.js cues   <index.html> <cues.json>
 *   node render.js check  <index.html> [report.json]
 *   node render.js board  <board.html> <board.png>      (fill_template.py --board writes board.html)
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
const [,, mode, htmlFile, target, a, b, subframeArg] = process.argv;

function usage(message) {
  console.error(message);
  console.error('Usage: render.js stills|frames|cues|check|board <index.html> [out] [args]');
  process.exit(1);
}

if (!['stills', 'frames', 'cues', 'check', 'board'].includes(mode)) usage(`Unknown mode: ${mode}`);
if (mode === 'board' && !target) usage('board needs an output path, e.g. board.png');
if (!htmlFile || !fs.existsSync(htmlFile)) usage(`No such composition: ${htmlFile}`);
if (mode === 'frames' && (Number.isNaN(Number(a)) || Number.isNaN(Number(b)) || b === undefined)) {
  usage(`frames needs <from-frame> <to-frame> as two separate numbers, got: ${a} ${b}`);
}
const subframes = Number(subframeArg ?? 1);
if (mode === 'frames' && !(/^\d+$/.test(String(subframeArg ?? 1)) && subframes >= 1 && subframes <= 16)) {
  usage(`frames [subframes] must be an integer from 1 to 16, got: ${subframeArg}`);
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

  // Load each kit family outright: a family with no faces at all (fonts.css lost it) or a broken file would
  // otherwise render silently in a fallback face. Loading by name also covers families a theme never uses
  const unloaded = await page.evaluate(async () => {
    const missing = [];
    for (const family of (window.BRAND && window.BRAND.fonts) || []) {
      try { if (!(await document.fonts.load(`16px "${family}"`)).length) missing.push(family); }
      catch { missing.push(family); }
    }
    return missing;
  });
  if (unloaded.length && mode !== 'cues') {
    unloaded.forEach(family => console.error(`font ${family} did not load; every word in it would render in a fallback face`));
    console.error('Next: re-run setup.sh with this kit (fill_template.py links the kit into the work folder), or fix its fonts');
    await browser.close();
    process.exit(1);
  }

  if (mode === 'board') {
    await page.screenshot({ path: target, type: 'png', scale: 'css' });
    errors.forEach(message => console.error(`PAGE ERROR ${message}`));
    if (errors.length) {
      console.error('Next: fix the first PAGE ERROR, usually a kit file setup.sh has not installed');
      await browser.close();
      process.exit(1);
    }
    console.log(`brand board → ${target}`);
    console.log('Next: show the board for approval, with brand_kit.py check for the contrast report');
    await browser.close();
    process.exit(0);
  }

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

  if (mode === 'frames' && subframes === 1) {
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

  if (mode === 'frames' && subframes > 1) {
    fs.mkdirSync(target, { recursive: true });
    const [ext, other] = DRAFT ? ['jpg', 'png'] : ['png', 'jpg'];
    // A scale-1 clip captures at CSS size, so the 2x page is supersampled to 1x; the pixels match
    // page.screenshot({ scale: 'css' }) exactly and the speed-optimised PNG encodes ~4x faster
    const clip = { x: 0, y: 0, width: size.width, height: size.height, scale: 1 };
    const cdp = await page.context().newCDPSession(page);
    const blend = await browser.newPage();
    await blend.evaluate(({ width, height }) => {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      window.blendContext = canvas.getContext('2d', { willReadFrequently: true });
      window.blendSum = new Uint32Array(width * height * 4);
    }, size);
    for (let f = Number(a); f < Number(b); f++) {
      await blend.evaluate(() => window.blendSum.fill(0));
      for (let k = 0; k < subframes; k++) {
        // 180° shutter: sub-frames span half a frame, so renderAt's Math.round keeps frame f's grain and footage
        await page.evaluate(x => window.renderAt(x), f / FPS + k / (2 * subframes * FPS));
        const { data: png } = await cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true, clip });
        await blend.evaluate(async data => {
          const image = new Image();
          image.src = 'data:image/png;base64,' + data;
          await image.decode();
          const { width, height } = window.blendContext.canvas;
          if (image.naturalWidth !== width || image.naturalHeight !== height) {
            throw new Error(`sub-frame is ${image.naturalWidth}x${image.naturalHeight}, expected ${width}x${height}`);
          }
          window.blendContext.drawImage(image, 0, 0);
          const pixels = window.blendContext.getImageData(0, 0, width, height).data;
          for (let i = 0; i < pixels.length; i++) window.blendSum[i] += pixels[i];
        }, png);
      }
      const blended = await blend.evaluate(({ count, type }) => {
        const { width, height } = window.blendContext.canvas;
        const averaged = new ImageData(width, height);
        for (let i = 0; i < averaged.data.length; i++) averaged.data[i] = Math.round(window.blendSum[i] / count);
        window.blendContext.putImageData(averaged, 0, 0);
        return window.blendContext.canvas.toDataURL(type, 0.92).split(',')[1];
      }, { count: subframes, type: DRAFT ? 'image/jpeg' : 'image/png' });
      const name = path.join(target, `f${String(f).padStart(5, '0')}`);
      fs.writeFileSync(`${name}.${ext}`, Buffer.from(blended, 'base64'));
      fs.rmSync(`${name}.${other}`, { force: true });
    }
  }

  await browser.close();
  if (errors.length) {
    errors.forEach(message => console.error(`PAGE ERROR ${message}`));
    process.exit(2);
  }
})().catch(e => { console.error(e.message); process.exit(1); });
