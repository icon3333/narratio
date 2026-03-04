#!/usr/bin/env node
/**
 * Standalone Puppeteer scraper for Economist covers.
 * Usage: node scrape_covers_node.js <year>
 * Outputs JSON array to stdout.
 */

const puppeteer = require('puppeteer');

const year = parseInt(process.argv[2]) || new Date().getFullYear();

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage();

  await page.setUserAgent(
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
  );

  try {
    // Navigate directly with year param to avoid Cloudflare blocking the dropdown reload
    await page.goto(`https://www.economist.com/weeklyedition/archive?year=${year}`, {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    await new Promise(r => setTimeout(r, 1000));

    const data = await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('a[href*="/weeklyedition/20"]'));
      const seen = new Set();
      const editions = [];

      links.forEach(a => {
        const href = a.getAttribute('href') || '';
        const dateMatch = href.match(/(\d{4}-\d{2}-\d{2})/);
        if (!dateMatch || seen.has(dateMatch[1])) return;
        seen.add(dateMatch[1]);
        editions.push({
          date: dateMatch[1],
          title: a.textContent.trim().substring(0, 120),
          edition_url: a.href,
        });
      });

      const images = Array.from(document.querySelectorAll('img'))
        .filter(img => img.src.includes('content-assets') && img.src.includes('DE_'))
        .map(img => img.src);

      return { editions, images };
    });

    const covers = data.editions.map((ed, i) => ({
      date: ed.date,
      title: ed.title,
      image_url: data.images[i] || null,
      edition_url: ed.edition_url,
    })).filter(c => c.image_url);

    covers.sort((a, b) => b.date.localeCompare(a.date));

    process.stdout.write(JSON.stringify(covers));
  } catch (err) {
    process.stderr.write(`Error scraping year ${year}: ${err.message}\n`);
    process.stdout.write('[]');
  } finally {
    await browser.close();
  }
})();
