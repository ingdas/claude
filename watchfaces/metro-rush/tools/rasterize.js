// Rasterize SVGs to PNGs with Playwright: node rasterize.js in1.svg out1.png [in2.svg out2.png ...]
// Optional helper for docs/previews; not needed to build the watch face.
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 450, height: 450 } });
  for (let i = 2; i < process.argv.length; i += 2) {
    await page.goto('file://' + path.resolve(process.argv[i]));
    await page.screenshot({ path: process.argv[i + 1], omitBackground: true });
  }
  await browser.close();
})();
