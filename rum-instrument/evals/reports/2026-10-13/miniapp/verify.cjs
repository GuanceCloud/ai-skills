const fs = require('fs')
const vm = require('vm')
const assert = require('assert/strict')
const { createRequire } = require('module')
const projectRequire = createRequire(require('path').resolve('project/app.js'))
const source = fs.readFileSync('project/rum.js', 'utf8')
const local = projectRequire('./config/rum.local')
for (const scenario of ['success', 'load-failure', 'init-failure', 'missing-config']) {
  const calls = [], warnings = [], options = []
  const sandbox = {module: {exports: {}}, console: {warn: text => warnings.push(text)}, wx: {getAccountInfoSync: () => ({miniProgram: {envVersion: 'trial', version: '4.5.6'}})}, require(name) {
    if (name === './config/rum.local') return scenario === 'missing-config' ? {} : local
    if (scenario === 'load-failure') throw Error('SDK unavailable')
    return {datafluxRum: {init(config) {calls.push('init'); options.push(config); if (scenario === 'init-failure') throw Error('SDK init failed')}}}
  }}
  vm.runInNewContext(source, sandbox)
  const init = sandbox.module.exports.initializeRum
  const startup = {require: () => ({initializeRum: init}), App: () => calls.push('App')}
  vm.runInNewContext(fs.readFileSync('project/app.js','utf8'), startup)
  if (scenario === 'success') {
    init(); init()
    assert.deepEqual(calls, ['init', 'App'])
    assert.equal(options[0].applicationId, 'eval_miniapp')
    assert.equal(options[0].datakitOrigin, 'http://127.0.0.1:19529')
    assert.equal(options[0].env, 'trial'); assert.equal(options[0].version, '4.5.6')
    assert.equal(options[0].allowedTracingUrls.length, 0)
    for (const key of ['site','clientToken','sampleRate']) assert.equal(key in options[0], false)
    assert.equal(options[0].trackLaunchOptions, false)
    assert.equal(options[0].trackResourceQueryString, false)
    assert.equal(options[0].trackRequestErrorResponseBody, false)
  } else { assert.equal(calls[calls.length - 1], 'App'); assert.equal(warnings.length, 1) }
  console.log(`PASS mock SDK: ${scenario}`)
}
const pkg = projectRequire('@cloudcare/rum-miniapp/package.json')
assert.equal(pkg.version, '2.2.20')
assert.equal(typeof projectRequire('@cloudcare/rum-miniapp').datafluxRum.init, 'function')
console.log('PASS real package: installed 2.2.20 CommonJS API exports init')
console.log('Boundary: mock SDK startup tests and real package import; no MiniApp compilation or real-device proof.')
