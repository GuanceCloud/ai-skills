import { datafluxRum } from '/private/tmp/rum-sdk-types-retest/3.3.21/node_modules/@cloudcare/browser-rum/esm/index.js';
window.__hooks = [];
const mode = window.__probeMode;
const strip = value => { try { const u = new URL(value); u.search = ''; return u.href; } catch { return value; } };
datafluxRum.init({
 applicationId: 'eval_catalog', datakitOrigin: 'http://127.0.0.1:19529',
 service: 'rum-catalog-fixture', env: 'synthetic-test', version: 'fixture',
 sessionReplaySampleRate: 0, sendContentTypeByJson: true,
 beforeSend(event) {
  window.__hooks.push(JSON.parse(JSON.stringify(event)));
  if (mode === 'hook' || mode === 'reject') {
   if (event.view) { event.view.url = strip(event.view.url); event.view.referrer = strip(event.view.referrer); event.view.url_query = ''; }
   if (event.resource) { event.resource.url = strip(event.resource.url); event.resource.url_query = ''; }
  }
  if (mode === 'reject' && event.type === 'view') return false;
 }
});
window.__initCount = 1;
window.__rum = datafluxRum;
