const fs = require('fs');
const http = require('http');
const assert = require('assert');
const { chromium } = require('../web/test-tools/node_modules/playwright');
const captures = [];
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://localhost').pathname;
  if (name === '/flutter_bootstrap.js') {
    res.setHeader('Content-Type', 'text/javascript');
    return res.end('window.__mockFlutterBootstrap = true;');
  }
  const file = name === '/' ? 'index.html' : name.slice(1);
  if (!['index.html', 'rum.js', 'rum-config.local.js'].includes(file)) {
    res.statusCode = 404; return res.end();
  }
  res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : 'text/html');
  res.end(fs.readFileSync('project/web/' + file));
});
(async () => {
  await new Promise(resolve => server.listen(19635, '127.0.0.1', resolve));
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', args:['--disable-background-networking']});
  try {
    const page = await browser.newPage();
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.href === 'https://static.guance.com/browser-sdk/v3/dataflux-rum.js') {
        return route.fulfill({contentType:'text/javascript', body:fs.readFileSync('sdk/browser-cdn.js','utf8')+'\nwindow.__rumInitCalls=0;const originalInit=window.DATAFLUX_RUM.init;window.DATAFLUX_RUM.init=(c)=>{window.__rumInitCalls++;return originalInit(c)};'});
      }
      if (url.origin === 'http://127.0.0.1:19529') {
        captures.push({path:url.pathname,body:route.request().postData()||''});
        return route.fulfill({status:200,contentType:'application/json',body:'{}'});
      }
      if (url.origin === 'http://127.0.0.1:19635') return route.continue();
      return route.abort();
    });
    await page.goto('http://127.0.0.1:19635/');
    await page.waitForFunction(() => window.__flutterRumInitialized && window.__mockFlutterBootstrap);
    await page.evaluate(() => {
      history.pushState({}, '', '/?q=CANARY_FLUTTER_QUERY#CANARY_FLUTTER_HASH');
      window.DATAFLUX_RUM.addError(new Error('synthetic flutter web error'));
    });
    await page.waitForTimeout(3200);
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted:false})));
    await page.waitForTimeout(1000);
    const initial = await page.evaluate(() => ({calls:window.__rumInitCalls,config:window.DATAFLUX_RUM.getInitConfiguration(),replay:window.DATAFLUX_RUM.isRecording()}));
    assert.equal(initial.calls,1);assert.equal(initial.config.applicationId,'eval_flutter_web');assert.equal(initial.replay,false);
    assert(captures.length > 0, 'real SDK must generate telemetry');
    const raw = JSON.stringify(captures);
    const privacy = Object.fromEntries(['CANARY_FLUTTER_QUERY','CANARY_FLUTTER_HASH'].map(marker=>[marker,!raw.includes(marker)]));
    const result = {real_browser:true,real_browser_sdk:true,flutter_engine:'stub bootstrap only; no Dart or Flutter runtime',receiver:'mocked in Playwright',initial,capture_count:captures.length,privacy,privacy_passed:Object.values(privacy).every(Boolean),remote_ingestion_verified:false};
    fs.writeFileSync('logs/parent-browser-smoke.json',JSON.stringify(result,null,2)+'\n');
    fs.writeFileSync('logs/parent-local-payloads.json',JSON.stringify(captures,null,2)+'\n');
    console.log(JSON.stringify(result,null,2));
    if (!result.privacy_passed) process.exitCode=1;
  } finally { await browser.close();server.close(); }
})().catch(error=>{console.error(error);server.close();process.exitCode=1});
