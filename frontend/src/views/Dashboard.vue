<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/api.js';

const router = useRouter();
const groups = ref([]);

onMounted(async () => {
    try {
        const [modelsRes, countsRes] = await Promise.all([
            api('/api/models'),
            api('/api/models/counts'),
        ]);
        const models = await modelsRes.json();
        const counts = await countsRes.json();
        const items = models.map((m) => ({ ...m, total: counts[m.name] || 0 }));

        const grouped = {};
        const ungrouped = [];
        for (const m of items) {
            if (m.group) {
                if (!grouped[m.group]) grouped[m.group] = [];
                grouped[m.group].push(m);
            } else {
                ungrouped.push(m);
            }
        }

        const sections = [];
        for (const [label, models] of Object.entries(grouped)) {
            sections.push({ label, models });
        }
        if (ungrouped.length > 0) {
            sections.push({ label: 'Models', models: ungrouped });
        }
        groups.value = sections;
    } catch {
        // toast already shown by api()
    }
});
</script>

<template>
    <div class="flex flex-col gap-6">
        <div v-for="group in groups" :key="group.label">
            <div class="text-lg font-semibold mb-3 text-surface-500">{{ group.label }}</div>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                <div
                    v-for="m in group.models"
                    :key="m.name"
                    class="card !mb-0 cursor-pointer hover:border-primary transition-colors"
                    @click="router.push('/' + m.name)"
                >
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div class="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10">
                                <i :class="[m.icon || 'pi pi-database', 'text-primary text-xl']" />
                            </div>
                            <div>
                                <div class="flex items-center gap-2">
                                    <span class="font-semibold">{{ m.verbose_name }}</span>
                                    <Tag :value="m.name" severity="secondary" class="font-mono text-xs" />
                                </div>
                                <div class="text-sm text-surface-500">{{ m.total }} records</div>
                            </div>
                        </div>
                        <i class="pi pi-chevron-right text-surface-400" />
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
