<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/api.js';

const router = useRouter();
const stats = ref([]);

onMounted(async () => {
    const res = await api('/api/models/');
    const models = await res.json();

    const items = await Promise.all(
        models.map(async (m) => {
            const r = await api(`/api/${m.name}/?per_page=1`);
            const data = await r.json();
            return { name: m.name, verbose_name: m.verbose_name, total: data.total };
        })
    );
    stats.value = items;
});
</script>

<template>
    <div class="card">
        <div class="text-xl font-semibold mb-4">Overview</div>
        <DataTable :value="stats" stripedRows>
            <Column field="verbose_name" header="Model" />
            <Column field="total" header="Records" />
            <Column header="">
                <template #body="{ data }">
                    <Button label="Open" icon="pi pi-arrow-right" text size="small" @click="router.push('/' + data.name)" />
                </template>
            </Column>
        </DataTable>
    </div>
</template>
