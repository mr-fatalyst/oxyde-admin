import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from './views/Dashboard.vue'
import ModelList from './views/ModelList.vue'
import ModelDetail from './views/ModelDetail.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/:model', component: ModelList },
  { path: '/:model/create', component: ModelDetail },
  { path: '/:model/:pk', component: ModelDetail },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
