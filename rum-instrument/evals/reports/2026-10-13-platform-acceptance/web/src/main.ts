import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
window.addEventListener('error', () => { document.documentElement.dataset.appErrors = String(Number(document.documentElement.dataset.appErrors || '0') + 1) })
const rumStartup = import('./rum').then(({ initializeRum }) => initializeRum()).catch(() => {
  console.warn('RUM module unavailable; application continues')
})
// Await ordinary initialization before routing; a stalled SDK cannot prevent startup.
void Promise.race([rumStartup, new Promise<void>((resolve) => setTimeout(resolve, 1500))])
  .then(() => createApp(App).use(router).mount('#app'))
