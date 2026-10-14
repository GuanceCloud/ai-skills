'use strict';
const assert = require('assert').strict;
const { installRumErrorHandler } = require('../assets/react-native-error-handler.cjs');
const tick = () => new Promise(resolve => setImmediate(resolve));

(async () => {
  for (const mode of ['resolve', 'reject', 'throw', 'pending']) {
    let originalCalls = 0, reports = 0, current;
    const owner = {};
    const error = new Error('synthetic');
    const original = function (...args) {
      originalCalls++;
      assert.equal(this, owner);
      assert.deepEqual(args, [error, true]);
      return 'original-result';
    };
    current = original;
    const api = { getGlobalHandler: () => current, setGlobalHandler: fn => { current = fn; } };
    const report = () => {
      reports++;
      if (mode === 'throw') throw new Error('report failure');
      if (mode === 'reject') return Promise.reject(new Error('report rejection'));
      if (mode === 'pending') return new Promise(() => {});
      return Promise.resolve();
    };
    const cleanup = installRumErrorHandler(api, report);
    const handler = current;
    assert.equal(installRumErrorHandler(api, report), cleanup);
    assert.equal(current, handler);
    assert.equal(current.call(owner, error, true), 'original-result');
    assert.equal(originalCalls, 1);
    await tick();
    assert.equal(reports, 1);
    cleanup(); assert.equal(current, original);
    console.log('PASS original handler preserved:', mode);
  }
  const originalError = new Error('original handler throws');
  let current = () => { throw originalError; }, reports = 0;
  const api = { getGlobalHandler: () => current, setGlobalHandler: fn => { current = fn; } };
  const cleanup = installRumErrorHandler(api, () => { reports++; });
  assert.throws(() => current(new Error('synthetic'), false), error => error === originalError);
  await tick(); assert.equal(reports, 1);
  const other = () => {};
  api.setGlobalHandler(other); cleanup(); assert.equal(current, other);
  assert.throws(() => installRumErrorHandler({}, () => {}), TypeError);
  console.log('PASS thrown original error, cleanup ownership, invalid API');
})().catch(error => { console.error(error); process.exitCode = 1; });
