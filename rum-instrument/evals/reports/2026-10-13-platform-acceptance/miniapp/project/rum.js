let initialized = false

function initializeRum() {
  if (initialized) return
  try {
    const config = require('./config/rum.local')
    if (!config.applicationId || !config.datakitOrigin) {
      throw new Error('Missing RUM configuration')
    }
    const { datafluxRum } = require('@cloudcare/rum-miniapp')
    const miniProgram = wx.getAccountInfoSync().miniProgram
    datafluxRum.init({
      applicationId: config.applicationId,
      datakitOrigin: config.datakitOrigin,
      service: 'miniapp',
      env: miniProgram.envVersion,
      version: miniProgram.version || undefined,
      trackInteractions: true,
      trackResourceQueryString: false,
      trackRequestErrorResponseBody: false,
      trackLaunchOptions: false,
      allowedTracingUrls: [],
      remoteConfiguration: false,
    })
    initialized = true
  } catch (_) {
    // Monitoring failures must not interrupt the MiniApp startup.
    console.warn('[RUM] Initialization failed; check local config and SDK build.')
  }
}

module.exports = { initializeRum }
