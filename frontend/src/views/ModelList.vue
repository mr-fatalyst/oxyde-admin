<script setup>
import { ref, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/api.js';

const route = useRoute();
const router = useRouter();

const modelName = ref(route.params.model);
const verboseName = ref('');
const tableName = ref('');
const columns = ref([]);
const records = ref([]);
const totalRecords = ref(0);
const loading = ref(false);
const fkLookup = ref({});  // { column_name: { id: label } }

const page = ref(1);
const perPage = ref(25);
const sortField = ref(null);
const sortOrder = ref(null);

function extractFkColumns(schemaData) {
    // Build map: column_name -> fk model name from $ref properties
    const map = {};
    const props = schemaData.properties || {};
    for (const [, prop] of Object.entries(props)) {
        const hasRefProp = prop.$ref || (prop.anyOf && prop.anyOf.some((t) => t.$ref));
        if (!hasRefProp) continue;
        const fk = prop['x-db-foreign-key'];
        const col = prop['x-db-column'];
        if (fk && col) {
            map[col] = fk.model;
        }
    }
    return map;
}

async function loadMeta() {
    const res = await api('/api/models/');
    const models = await res.json();
    const meta = models.find((m) => m.name === modelName.value);
    if (!meta) return;

    verboseName.value = meta.verbose_name;
    tableName.value = meta.name;

    const schemaRes = await api(`/api/${modelName.value}/schema/`);
    const schema = await schemaRes.json();

    if (meta.list_display && meta.list_display.length > 0) {
        columns.value = meta.list_display;
    } else {
        columns.value = Object.keys(schema.properties || {});
    }

    // Load FK lookups for columns that are foreign keys
    const fkColumns = extractFkColumns(schema);
    const lookup = {};
    const promises = Object.entries(fkColumns).map(async ([col, fkModel]) => {
        if (!columns.value.includes(col)) return;
        const optRes = await api(`/api/${fkModel}/options/`);
        const options = await optRes.json();
        const map = {};
        for (const opt of options) {
            map[opt.value] = opt.label;
        }
        lookup[col] = map;
    });
    await Promise.all(promises);
    fkLookup.value = lookup;
}

async function loadRecords() {
    loading.value = true;
    try {
        let url = `/api/${modelName.value}/?page=${page.value}&per_page=${perPage.value}`;
        if (sortField.value) {
            const prefix = sortOrder.value === -1 ? '-' : '';
            url += `&ordering=${prefix}${sortField.value}`;
        }
        const res = await api(url);
        const data = await res.json();
        records.value = data.items;
        totalRecords.value = data.total;
    } finally {
        loading.value = false;
    }
}

function onPage(event) {
    page.value = event.page + 1;
    perPage.value = event.rows;
    loadRecords();
}

function onSort(event) {
    sortField.value = event.sortField;
    sortOrder.value = event.sortOrder;
    page.value = 1;
    loadRecords();
}

function onRowClick(event) {
    const record = event.data;
    const pk = findPk(record);
    if (pk !== null) {
        router.push(`/${modelName.value}/${pk}`);
    }
}

function findPk(record) {
    if ('id' in record) return record.id;
    // fallback: first field
    const keys = Object.keys(record);
    return keys.length > 0 ? record[keys[0]] : null;
}

function cellValue(record, col) {
    const raw = record[col];
    const lookup = fkLookup.value[col];
    if (lookup && raw != null) {
        return lookup[raw] ?? raw;
    }
    return raw;
}

watch(
    () => route.params.model,
    async (newModel) => {
        modelName.value = newModel;
        page.value = 1;
        sortField.value = null;
        sortOrder.value = null;
        await loadMeta();
        await loadRecords();
    }
);

onMounted(async () => {
    await loadMeta();
    await loadRecords();
});
</script>

<template>
    <div class="card">
        <div class="flex justify-between items-center mb-4">
            <div class="flex items-center gap-2">
                <span class="text-xl font-semibold">{{ verboseName }}</span>
                <Tag :value="tableName" severity="secondary" class="font-mono text-xs" />
            </div>
            <Button label="Create" icon="pi pi-plus" @click="router.push(`/${modelName}/create`)" />
        </div>

        <DataTable
            :value="records"
            :loading="loading"
            :totalRecords="totalRecords"
            :rows="perPage"
            :first="(page - 1) * perPage"
            :lazy="true"
            :paginator="true"
            :rowsPerPageOptions="[10, 25, 50]"
            :sortField="sortField"
            :sortOrder="sortOrder"
            @page="onPage"
            @sort="onSort"
            @row-click="onRowClick"
            stripedRows
            rowHover
            class="cursor-pointer"
        >
            <Column v-for="col in columns" :key="col" :field="col" :header="col" :sortable="true">
                <template #body="{ data }">{{ cellValue(data, col) }}</template>
            </Column>
        </DataTable>
    </div>
</template>
