<script setup>
import { useLayout } from '@/layout/composables/layout';
import { useToast } from 'primevue/usetoast';
import { computed, ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { api, onApiError } from '@/api.js';
import AppFooter from './AppFooter.vue';
import AppSidebar from './AppSidebar.vue';
import AppTopbar from './AppTopbar.vue';

const { layoutConfig, layoutState, hideMobileMenu } = useLayout();
const toast = useToast();

onApiError((message, status) => {
    toast.add({ severity: 'error', summary: `Error ${status}`, detail: message, life: 5000 });
});
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

const breadcrumbHome = { icon: 'pi pi-home', route: '/' };

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
        route: `/${model}`
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
                <Breadcrumb v-if="breadcrumbItems.length > 0" :home="breadcrumbHome" :model="breadcrumbItems" class="mb-4">
                    <template #item="{ item, props }">
                        <router-link v-if="item.route" v-slot="{ href, navigate }" :to="item.route" custom>
                            <a :href="href" v-bind="props.action" @click="navigate">
                                <span v-if="item.icon" :class="[item.icon]" />
                                <span>{{ item.label }}</span>
                            </a>
                        </router-link>
                        <a v-else v-bind="props.action">
                            <span>{{ item.label }}</span>
                        </a>
                    </template>
                </Breadcrumb>
                <router-view :key="$route.fullPath" />
            </div>
            <AppFooter />
        </div>
        <div class="layout-mask animate-fadein" @click="hideMobileMenu" />
    </div>
    <Toast />
</template>
