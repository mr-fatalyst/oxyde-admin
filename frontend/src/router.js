import { createRouter, createWebHistory } from 'vue-router';
import { BASE } from '@/api.js';
import AppLayout from '@/layout/AppLayout.vue';

let authEnabled = false;

export function setAuthEnabled(value) {
    authEnabled = value;
}

const router = createRouter({
    history: createWebHistory(BASE),
    routes: [
        {
            path: '/login',
            name: 'login',
            component: () => import('@/views/Login.vue'),
        },
        {
            path: '/',
            component: AppLayout,
            children: [
                {
                    path: '/',
                    name: 'dashboard',
                    component: () => import('@/views/Dashboard.vue')
                },
                {
                    path: '/:model',
                    name: 'model-list',
                    component: () => import('@/views/ModelList.vue')
                },
                {
                    path: '/:model/create',
                    name: 'model-create',
                    component: () => import('@/views/ModelDetail.vue')
                },
                {
                    path: '/:model/:pk',
                    name: 'model-detail',
                    component: () => import('@/views/ModelDetail.vue')
                }
            ]
        }
    ]
});

router.beforeEach((to) => {
    if (!authEnabled) return true;
    if (to.name === 'login') return true;
    const token = localStorage.getItem('admin_token');
    if (!token) return { name: 'login' };
    return true;
});

router.previousRoute = null;
router.afterEach((to, from) => {
    router.previousRoute = from.fullPath;
});

export default router;
