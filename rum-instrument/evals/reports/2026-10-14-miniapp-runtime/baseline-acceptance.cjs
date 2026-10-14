const fs = require('fs');
const assert = require('assert/strict');
const automator = require('./tooling/node_modules/miniprogram-automator');
const out = __dirname + '/logs/';
const result = {status: 'running', checks: [], runtime: {}};
let app;
function save() { fs.writeFileSync(out + 'baseline-result.json', JSON.stringify(result, null, 2)); }
const timer = setTimeout(() => { result.status = 'timeout'; save(); process.exit(124); }, 45000);
async function check(name, fn) {
  try { const evidence = await fn(); result.checks.push({name, status:'passed', evidence}); }
  catch (e) { result.checks.push({name, status:'failed', error:e.message}); }
  save();
}
(async () => {
  app = await automator.connect({wsEndpoint:'ws://127.0.0.1:19534'});
  app.on('exception', e => fs.appendFileSync(out + 'baseline-exceptions.jsonl', JSON.stringify(e) + '\n'));
  await check('app_lifecycle', async () => {
    const value = await app.evaluate(() => ({launchCount:getApp().globalData.launchCount, pages:getCurrentPages().map(p=>p.route)}));
    result.runtime = value;
    assert.equal(value.launchCount, 1); return value;
  });
  await check('page_and_interaction', async () => {
    const page = await app.currentPage();
    assert.ok(page, 'current page must exist');
    assert.equal(page.path, 'pages/index/index');
    const before = await page.data();
    assert.equal(before.status, '已启动');
    const button = await page.$('#action'); assert.ok(button);
    await button.tap();
    const after = await page.data(); assert.equal(after.actions, before.actions + 1);
    return {path:page.path, before, after};
  });
  await check('screenshot', async () => { await app.screenshot({path:out+'baseline.png'}); return 'baseline.png'; });
  const system = await app.systemInfo();
  result.system = {SDKVersion:system.SDKVersion, platform:system.platform, version:system.version};
  result.status = result.checks.every(c=>c.status==='passed') ? 'passed' : 'failed';
  process.exitCode = result.status === 'passed' ? 0 : 1;
})().catch(e => { result.status='failed';result.error=e.message;process.exitCode=1; }).finally(() => {
  clearTimeout(timer); if(app)app.disconnect();save();console.log(JSON.stringify(result,null,2));
});
