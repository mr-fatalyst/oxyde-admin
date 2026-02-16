<script setup>
import { useLayout } from '@/layout/composables/layout';
import { computed, ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { api } from '@/api.js';
import AppFooter from './AppFooter.vue';
import AppSidebar from './AppSidebar.vue';
import AppTopbar from './AppTopbar.vue';

const { layoutConfig, layoutState, hideMobileMenu } = useLayout();
const route = useRoute();

const modelsData = ref([]);

onMounted(async () => {
    try {
        const res = await api('/api/models/');
        modelsData.value = await res.json();
    } catch (e) {
        console.error('Failed to load models:', e);
    }
});

const breadcrumbHome = { icon: 'pi pi-home', to: '/' };

const breadcrumbItems = computed(() => {
    const model = route.params.model;
    const pk = route.params.pk;

    if (!model) return [];

    const meta = modelsData.value.find((m) => m.name === model);
    const items = [];

    if (meta?.group) {
        items.push({ label: meta.group });
    }

    items.push({
        label: meta?.verbose_name || model,
        to: `/${model}`
    });

    if (route.name === 'model-create') {
        items.push({ label: 'Create' });
    } else if (pk) {
        items.push({ label: `#${pk}` });
    }

    return items;
});

const containerClass = computed(() => {
    return {
        'layout-overlay': layoutConfig.menuMode === 'overlay',
        'layout-static': layoutConfig.menuMode === 'static',
        'layout-overlay-active': layoutState.overlayMenuActive,
        'layout-mobile-active': layoutState.mobileMenuActive,
        'layout-static-inactive': layoutState.staticMenuInactive
    };
});
</script>

<template>
    <div class="layout-wrapper" :class="containerClass">
        <AppTopbar />
        <AppSidebar />
        <div class="layout-main-container">
            <div class="layout-main">
                <Breadcrumb v-if="breadcrumbItems.length > 0" :home="breadcrumbHome" :model="breadcrumbItems" class="mb-4" />
                <router-view :key="$route.fullPath" />
            </div>
            <AppFooter />
        </div>
        <div class="layout-mask animate-fadein" @click="hideMobileMenu" />
    </div>
    <Toast />
</template>
