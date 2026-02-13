<script setup>
import { ref, onMounted } from 'vue';
import { api } from '@/api.js';
import AppMenuItem from './AppMenuItem.vue';

const model = ref([
    {
        label: 'Home',
        items: [
            {
                label: 'Dashboard',
                icon: 'pi pi-fw pi-home',
                to: '/'
            }
        ]
    },
    {
        label: 'Models',
        items: []
    }
]);

onMounted(async () => {
    try {
        const res = await api('/api/models/');
        const models = await res.json();
        model.value[1].items = models.map((m) => ({
            label: m.verbose_name,
            icon: 'pi pi-fw pi-database',
            to: '/' + m.name
        }));
    } catch (e) {
        console.error('Failed to load models:', e);
    }
});
</script>

<template>
    <ul class="layout-menu">
        <template v-for="(item, i) in model" :key="item">
            <app-menu-item v-if="!item.separator" :item="item" :index="i"></app-menu-item>
            <li v-if="item.separator" class="menu-separator"></li>
        </template>
    </ul>
</template>
