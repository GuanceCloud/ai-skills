let startup: Promise<void> | undefined

export function initializeRum(): Promise<void> {
  startup ??= (async () => {
    try {
      const applicationId = import.meta.env.VITE_RUM_APP_ID
      const datakitOrigin = import.meta.env.VITE_RUM_DATAKIT_URL
      if (!applicationId || !datakitOrigin) return
      const { datafluxRum } = await import('@cloudcare/browser-rum')
      datafluxRum.init({
        applicationId,
        datakitOrigin,
        service: __APP_SERVICE__,
        version: __APP_VERSION__,
        env: import.meta.env.MODE,
        sessionReplaySampleRate: 0,
      })
    } catch {
      console.warn('RUM initialization unavailable; application continues')
    }
  })()
  return startup
}
