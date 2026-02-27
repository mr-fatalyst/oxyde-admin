<script setup>
import { ref, onMounted } from 'vue';
import { api } from '@/api.js';
import AppMenuItem from './AppMenuItem.vue';

const model = ref([
    {
        label: 'Main',
        items: [
            { label: 'Dashboard', icon: 'pi pi-home', to: '/' }
        ]
    }
]);

onMounted(async () => {
    try {
        const res = await api('/api/models');
        const models = await res.json();

        const groups = {};
        const ungrouped = [];

        for (const m of models) {
            const item = {
                label: m.verbose_name,
                icon: m.icon || 'pi pi-database',
                to: '/' + m.name
            };

            if (m.group) {
                if (!groups[m.group]) {
                    groups[m.group] = [];
                }
                groups[m.group].push(item);
            } else {
                ungrouped.push(item);
            }
        }

        const modelsItems = [];
        for (const [label, items] of Object.entries(groups)) {
            modelsItems.push({
                label,
                path: '/group-' + label.toLowerCase(),
                items,
            });
        }
        modelsItems.push(...ungrouped);

        model.value = [
            model.value[0],
            { label: 'Models', items: modelsItems },
        ];
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
