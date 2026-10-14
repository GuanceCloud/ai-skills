window.appStarted = (window.appStarted || 0) + 1;
document.getElementById('app').textContent = 'Fixture application ready';
window.appRequest = fetch('/api/health').then(response => response.json());
