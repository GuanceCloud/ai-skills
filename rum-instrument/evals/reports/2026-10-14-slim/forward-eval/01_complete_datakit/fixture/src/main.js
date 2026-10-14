// RUM evaluation fixture: window.DATAFLUX_RUM is a controlled test double.
if (!window.__rumInitialized && window.RUM_CONFIG?.applicationId && window.RUM_CONFIG?.datakitOrigin) {
  try {
    window.DATAFLUX_RUM.init(window.RUM_CONFIG);
    window.__rumInitialized = true;
  } catch (error) {
    console.warn('RUM initialization unavailable');
  }
}
window.appStarted = (window.appStarted || 0) + 1;
document.getElementById('app').textContent = 'Fixture application ready';
window.appRequest = fetch('/api/health').then(response => response.json());
