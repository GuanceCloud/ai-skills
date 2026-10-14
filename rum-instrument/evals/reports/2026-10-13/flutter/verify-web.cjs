const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const code = fs.readFileSync('project/web/rum.js', 'utf8');
for (const mode of ['success', 'missing-config', 'missing-sdk', 'init-failure']) {
  let count=0, options, warnings=0;
  const window={location:{origin:'https://app.example'}};
  const context={window,URL,console:{warn(){warnings++}}};
  if(mode!=='missing-config') vm.runInNewContext(fs.readFileSync('project/web/rum-config.local.js','utf8'),context);
  if(mode!=='missing-sdk')window.DATAFLUX_RUM={init(value){count++; options=value;if(mode==='init-failure')throw Error('synthetic');}};
  vm.runInNewContext(code,context);
  if(mode==='success') {
    vm.runInNewContext(code,context);assert.equal(count,1);
    assert.equal(options.applicationId,'eval_flutter_web');assert.equal(options.datakitOrigin,'http://127.0.0.1:19529');
    assert.equal(options.version,'1.0.0');assert.equal(options.service,'rum_eval_mobile');assert.equal(options.allowedTracingUrls.length,0);
    assert.equal(options.sessionReplaySampleRate,0);assert.equal(options.sessionReplayOnErrorSampleRate,0);
    assert.equal('clientToken' in options,false);assert.equal('site' in options,false);assert.equal('sessionSampleRate' in options,false);
    const event={view:{url:'https://user:CANARY_PASSWORD@app.example/home?q=CANARY_QUERY#CANARY_FRAGMENT',referrer:'https://from.example/?x=CANARY_QUERY'},resource:{url:'https://api.example/resource?q=CANARY_QUERY'}};
    options.beforeSend(event);assert.equal(JSON.stringify(event).includes('CANARY_'),false);
  } else {assert.equal(warnings,1);assert.equal(window.__flutterRumInitialized,undefined);}
  console.log('PASS mocked Browser SDK:',mode);
}
const html=fs.readFileSync('project/web/index.html','utf8');
assert.ok(html.indexOf('rum-config.local.js')<html.indexOf('dataflux-rum.js'));
assert.ok(html.indexOf('dataflux-rum.js')<html.indexOf('src="rum.js"'));
assert.ok(html.indexOf('src="rum.js"')<html.indexOf('flutter_bootstrap.js'));
console.log('PASS maintained HTML loading order; no real Browser SDK/runtime execution is claimed.');
