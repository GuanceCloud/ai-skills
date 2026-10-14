'use strict';

// Copy into maintained application source only when the selected SDK's automatic
// error handler fails chaining tests. Disable that SDK hook before installing this.
const marker = Symbol.for('guance.rum.applicationErrorHandler');

function installRumErrorHandler(errorUtils, reportError) {
  if (!errorUtils || typeof errorUtils.getGlobalHandler !== 'function' ||
      typeof errorUtils.setGlobalHandler !== 'function' || typeof reportError !== 'function') {
    throw new TypeError('A working ErrorUtils API and report callback are required');
  }
  const previous = errorUtils.getGlobalHandler();
  if (typeof previous !== 'function') throw new TypeError('Existing error handler is required');
  if (previous[marker]) return previous[marker];

  function handler(error, isFatal) {
    try {
      // Preserve timing, arguments, receiver, return value and thrown exceptions.
      return previous.apply(this, arguments);
    } finally {
      // Monitoring must not delay or replace application error handling.
      Promise.resolve().then(() => reportError(error, isFatal)).catch(() => {});
    }
  }
  const dispose = () => {
    // A later framework/monitoring hook owns its replacement; do not clobber it.
    if (errorUtils.getGlobalHandler() === handler) errorUtils.setGlobalHandler(previous);
  };
  Object.defineProperty(handler, marker, { value: dispose });
  errorUtils.setGlobalHandler(handler);
  return dispose;
}

module.exports = { installRumErrorHandler };
