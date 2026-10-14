type RumRuntimeConfig = {
  applicationId: string;
  datakitOrigin: string;
  service?: string;
  env?: string;
  version?: string;
  sessionSampleRate?: number;
};

declare global {
  interface Window {
    __RUM_CONFIG__?: RumRuntimeConfig;
    __RUM_START__?: Promise<boolean>;
  }
}

/** One shared startup per page, including repeated calls and module reloads. */
export function startRum(): Promise<boolean> {
  if (typeof window === "undefined") return Promise.resolve(false);
  if (window.__RUM_START__) return window.__RUM_START__;
  const config = window.__RUM_CONFIG__;
  if (!config?.applicationId || !config.datakitOrigin) {
    console.warn("RUM is disabled: runtime configuration is missing.");
    return Promise.resolve(false);
  }
  window.__RUM_START__ = import("@cloudcare/browser-rum")
    .then(({ datafluxRum }) => {
      if (!datafluxRum.getInitConfiguration()) {
        datafluxRum.init({
          applicationId: config.applicationId,
          datakitOrigin: config.datakitOrigin,
          service: config.service || "vue-existing-rum",
          env: config.env,
          version: config.version,
          ...(config.sessionSampleRate !== undefined
            ? { sessionSampleRate: config.sessionSampleRate }
            : {}),
          sessionReplaySampleRate: 0,
          sessionReplayOnErrorSampleRate: 0,
        });
      }
      const initialized = Boolean(datafluxRum.getInitConfiguration());
      if (!initialized) delete window.__RUM_START__;
      return initialized;
    })
    .catch(() => {
      delete window.__RUM_START__;
      console.warn("RUM failed to initialize; application startup can continue.");
      return false;
    });
  return window.__RUM_START__;
}
