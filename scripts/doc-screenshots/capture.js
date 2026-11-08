// Retakes the documentation screenshots: dashboard tabs and pages of a demo digest EPUB.
//
//   npm i --no-save playwright-core      (uses the installed Google Chrome)
//   node scripts/doc-screenshots/capture.js <unzipped-book-dir> [out-dir]
//
// Start the dashboard first from a checkout whose data/ folder is empty (a fresh git worktree
// works), so no personal settings, feeds or addresses end up in the pictures.
// Build and unzip the book with demo_digest.py; scripts/doc-screenshots/README.md has the steps.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const SCREENS = require('./screens');

const BASE = process.env.DASHBOARD_URL || 'http://127.0.0.1:8765';
const BOOK = process.argv[2];
const OUT = process.argv[3] || path.join(__dirname, '..', '..', 'docs', 'screenshots');
if (!BOOK) throw new Error('usage: capture.js <unzipped-book-dir> [out-dir]');

const LAPTOP = { width: 1440, height: 900 };
// Kindle Paperwhite (11th gen): 1236x1648 px at 300 ppi, shown here at half size in CSS pixels.
const KINDLE = { width: 618, height: 824 };

// A Kindle-like frame around one EPUB page. Grayscale because the screen is e-ink.
function devicePage(src, caption) {
  return `<!doctype html><meta charset="utf-8">
<style>
  body { margin: 0; padding: 32px; background: #f2f1ee; font: 15px -apple-system, system-ui, sans-serif; }
  figure { margin: 0; display: inline-flex; flex-direction: column; align-items: center; gap: 14px; }
  .device { background: #1d1d1f; border-radius: 34px; padding: 44px 30px 60px; box-shadow: 0 12px 30px rgba(0,0,0,.18); }
  iframe, img.page { display: block; width: ${KINDLE.width}px; height: ${KINDLE.height}px; border: 0; background: #fff; filter: grayscale(1); }
  figcaption { color: #555; }
</style>
<figure><div class="device">${src.endsWith('.jpg') ? `<img class="page" src="${src}" style="object-fit:contain;background:#fff">` : `<iframe src="${src}"></iframe>`}</div><figcaption>${caption}</figcaption></figure>`;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome' });

  // Dashboard: light theme, so the pictures match the default look.
  const dash = await browser.newPage({ viewport: LAPTOP, deviceScaleFactor: 2 });
  // A stored token closes the "write token needed" popover; start the dashboard with DASHBOARD_TOKEN=demo.
  const token = process.env.DASHBOARD_TOKEN || 'demo';
  await dash.addInitScript((t) => {
    localStorage.setItem('bitesize_theme', 'light');
    localStorage.setItem('bitesize_dashboard_token', t);
  }, token);
  for (const s of SCREENS.dashboard) {
    await dash.goto(BASE + '/');
    await dash.waitForLoadState('networkidle');
    await dash.click(`button.tab[data-tab="${s.tab}"]`);
    await dash.waitForTimeout(1200);
    await dash.screenshot({ path: path.join(OUT, s.file) });
    console.log('ok', s.file);
  }

  // Book pages inside a Kindle frame. The wrapper is a file next to the book so the iframe can load it.
  const book = await browser.newPage({ viewport: { width: 760, height: 1100 }, deviceScaleFactor: 2 });
  const wrapper = path.join(BOOK, '_device.html');
  for (const s of SCREENS.book) {
    fs.writeFileSync(wrapper, devicePage(s.page, s.caption));
    await book.goto(pathToFileURL(wrapper).href);
    await book.waitForTimeout(600);
    await book.locator('figure').screenshot({ path: path.join(OUT, s.file) });
    console.log('ok', s.file);
  }

  // All four pages side by side, for the top of the README.
  const strip = SCREENS.book.map((s) => devicePage(s.page, s.caption).split('<figure>')[1].replace(/^/, '<figure>')).join('');
  fs.writeFileSync(wrapper, devicePage(SCREENS.book[0].page, '').split('<figure>')[0] +
    `<div style="display:flex;gap:28px">${strip}</div>`);
  const wide = await browser.newPage({ viewport: { width: 3700, height: 1100 }, deviceScaleFactor: 1 });
  await wide.goto(pathToFileURL(wrapper).href);
  await wide.waitForTimeout(800);
  await wide.locator('div[style]').screenshot({ path: path.join(OUT, 'book-tour.png') });
  console.log('ok book-tour.png');

  fs.unlinkSync(wrapper);
  await browser.close();
  console.log('saved to', OUT);
})().catch((e) => { console.error(e); process.exit(1); });
