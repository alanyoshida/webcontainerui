import { chromium } from 'playwright';
const U = 'http://localhost:4398/webcontainerui';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
const errors = [], external = [];
p.on('console', m => m.type() === 'error' && errors.push(m.text()));
p.on('pageerror', e => errors.push(String(e)));
p.on('request', r => { const h = new URL(r.url()).host; if (h !== 'localhost:4398') external.push(r.url()); });
p.on('response', r => r.status() >= 400 && errors.push(r.status() + ' ' + r.url()));
const out = {};
for (const path of ['/', '/pt-br/', '/getting-started/introduction/', '/pt-br/architecture/overview/', '/security/audits/', '/pt-br/security/audits/', '/operations/rollback/', '/pt-br/operations/environment-variables/', '/reference/capabilities/', '/pt-br/reference/development/']) {
  const r = await p.goto(U + path, { waitUntil: 'networkidle' });
  out[path] = [r.status(), await p.evaluate(() => document.documentElement.lang), await p.evaluate(() => document.documentElement.dataset.theme), (await p.title()).slice(0, 40)];
}
// troca de idioma preserva a página
await p.goto(U + '/security/audits/', { waitUntil: 'networkidle' });
await p.locator('starlight-lang-select select').first().selectOption({ index: 1 });
await p.waitForURL('**/pt-br/security/audits/');
out.langSwitch = p.url();
// busca
await p.goto(U + '/pt-br/getting-started/introduction/', { waitUntil: 'networkidle' });
await p.locator('button[data-open-modal]').first().click();
await p.locator('input[type=search], .pagefind-ui__search-input').first().fill('forward_auth');
await p.waitForSelector('.pagefind-ui__result-link', { timeout: 15000 });
out.search = await p.locator('.pagefind-ui__result-link').evaluateAll(a => a.slice(0, 4).map(x => x.getAttribute('href')));
// tema: padrão escuro, alterna e persiste
await p.goto(U + '/', { waitUntil: 'networkidle' });
await p.locator('[data-theme-toggle]').first().click();
out.afterToggle = await p.evaluate(() => document.documentElement.dataset.theme);
await p.goto(U + '/architecture/overview/', { waitUntil: 'networkidle' });
out.persistedInDocs = await p.evaluate(() => document.documentElement.dataset.theme);
// landing: links para repo, docs, aviso
await p.goto(U + '/', { waitUntil: 'networkidle' });
out.landing = await p.evaluate(() => ({ h1: document.querySelector('h1').textContent, github: !!document.querySelector('a[href="https://github.com/alanyoshida/webcontainerui"]'), warning: document.querySelector('.warning h2')?.textContent, warningLink: document.querySelector('.warning a')?.getAttribute('href'), imgsNoAlt: [...document.images].filter(i => !i.alt).length }));
out.fonts = await p.evaluate(() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family).filter((v, i, a) => a.indexOf(v) === i));
console.log(JSON.stringify({ out, errors, external }, null, 1));
await b.close();
