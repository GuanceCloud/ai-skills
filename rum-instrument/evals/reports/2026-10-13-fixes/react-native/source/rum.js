const config = require('./rum-config');
const { installRumErrorHandler } = require('./rum-error-handler.cjs');
const { rumErrorPayload } = require('./rum-error-payload');

// Keep the promise across module reloads; native setup remains wrapper-owned.
const state = globalThis.__APP_RUM_STATE__ || { baseConfigured: false, ready: null };
globalThis.__APP_RUM_STATE__ = state;

function startRum() {
  if (state.ready) return state.ready;
  state.ready = Promise.resolve().then(async () => {
    const { FTMobileReactNative, FTReactNativeRUM } = require('@cloudcare/react-native-mobile');
    if (!state.baseConfigured) {
      await FTMobileReactNative.sdkConfig({
        datakitUrl: config.datakitUrl,
        service: config.service,
        ...(config.env ? { env: config.env } : {}),
        remoteConfiguration: false,
      });
      state.baseConfigured = true;
    }
    await FTReactNativeRUM.setConfig({
      androidAppId: config.androidAppId,
      iOSAppId: config.iOSAppId,
      enableAutoTrackUserAction: true,
      enableAutoTrackError: false, // SDK 0.4.2 does not preserve application error chaining.
      enableNativeUserResource: true,
      // JS owns actions and eventual router views; avoid native duplicates.
      enableNativeUserAction: false,
      enableNativeUserView: false,
      enableTraceWebView: false,
      enableTrackNativeCrash: false,
      enableTrackNativeAppANR: false,
      enableTrackNativeFreeze: false,
    });
    state.disposeErrorHandler = installRumErrorHandler(globalThis.ErrorUtils, (error, isFatal) => {
      const payload = rumErrorPayload(error, isFatal);
      return FTReactNativeRUM.addError(payload.stack, payload.message, payload.properties);
    });
    return true;
  }).catch(() => {
    state.ready = null;
    console.warn('RUM startup failed; application startup may continue.');
    return false;
  });
  return state.ready;
}

module.exports = { startRum };
