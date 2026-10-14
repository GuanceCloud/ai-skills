import { createRouter, createWebHistory } from 'vue-router'
import HomePage from './pages/HomePage.vue'
import DetailsPage from './pages/DetailsPage.vue'
export const router = createRouter({ history: createWebHistory(), routes: [{ path: '/', component: HomePage }, { path: '/details', component: DetailsPage }] })
