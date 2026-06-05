import puppeteer from 'puppeteer';
import { mkdir, readdir } from 'fs/promises';
import { join } from 'path';

const url = process.argv[2] || 'http://localhost:3000';
const label = process.argv[3] || '';

const SCREENSHOTS_DIR = './temporary screenshots';

async function getNextScreenshotNumber() {
  const files = await readdir(SCREENSHOTS_DIR).catch(() => []);
  const numbers = files
    .filter(f => f.startsWith('screenshot-'))
    .map(f => {
      const match = f.match(/screenshot-(\d+)/);
      return match ? parseInt(match[1], 10) : 0;
    });
  return numbers.length > 0 ? Math.max(...numbers) + 1 : 1;
}

async function takeScreenshot() {
  await mkdir(SCREENSHOTS_DIR, { recursive: true });

  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  await page.goto(url, { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 500)); // Wait for any animations

  const screenshotNum = await getNextScreenshotNumber();
  const suffix = label ? `-${label}` : '';
  const filename = `screenshot-${screenshotNum}${suffix}.png`;
  const filepath = join(SCREENSHOTS_DIR, filename);

  await page.screenshot({ path: filepath, fullPage: true });
  console.log(`Screenshot saved: ${filepath}`);

  await browser.close();
}

takeScreenshot().catch(err => {
  console.error('Screenshot failed:', err);
  process.exit(1);
});
