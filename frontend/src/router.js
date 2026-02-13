import { createRouter, createWebHistory } from 'vue-router';
import AppLayout from '@/layout/AppLayout.vue';

const router = createRouter({
    history: createWebHistory(),
    routes: [
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

export default router;
