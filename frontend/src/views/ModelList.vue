<script setup>
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useConfirm } from 'primevue/useconfirm';
import { api } from '@/api.js';

const route = useRoute();
const router = useRouter();
const confirm = useConfirm();

const modelName = ref(route.params.model);
const verboseName = ref('');
const tableName = ref('');
const columns = ref([]);
const records = ref([]);
const totalRecords = ref(0);
const loading = ref(false);
const fkLookup = ref({});  // { column_name: { id: label } }
const fkModels = ref({});  // { column_name: fk_model_name }
const colProps = ref({});   // { column_name: schema_property }
const searchFields = ref(null);
const exportable = ref(false);
const columnLabels = ref({});
const filters = ref({});       // PrimeVue filter state: { col: { value, matchMode } }
const filterMeta = ref({});    // { col: { type, options? } }

const page = ref(1);
const perPage = ref(25);
const sortField = ref(null);
const sortOrder = ref(null);
const searchQuery = ref('');
const exportWarnThreshold = ref(null);
let searchTimeout = null;

function buildColumnProps(schemaData) {
    const result = {};
    const props = schemaData.properties || {};
    for (const [fieldName, prop] of Object.entries(props)) {
        const col = prop['x-db-column'] || fieldName;
        result[col] = prop;
    }
    return result;
}

function extractFkColumns(schemaData) {
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

function colType(col) {
    const prop = colProps.value[col];
    if (!prop) return 'default';
    if (prop['x-db-primary-key']) return 'pk';
    if (fkModels.value[col]) return 'fk';
    if (prop.type === 'boolean') return 'boolean';
    if (prop.anyOf && prop.anyOf.some((t) => t.type === 'boolean')) return 'boolean';
    const dbType = (prop['x-db-type'] || '').toLowerCase();
    if (dbType.includes('datetime') || dbType.includes('timestamp') || prop.format === 'date-time') return 'datetime';
    return 'default';
}

function colLabel(col) {
    return columnLabels.value[col] || col;
}

function formatDatetime(val) {
    const d = new Date(val);
    if (isNaN(d)) return val;
    return d.toLocaleString();
}

async function loadMeta() {
    const configRes = await api('/api/config/');
    const config = await configRes.json();
    if (config.export_warn_threshold) {
        exportWarnThreshold.value = config.export_warn_threshold;
    }

    const res = await api('/api/models/');
    const models = await res.json();
    const meta = models.find((m) => m.name === modelName.value);
    if (!meta) return;

    verboseName.value = meta.verbose_name;
    tableName.value = meta.name;
    searchFields.value = meta.search_fields;
    columnLabels.value = meta.column_labels || {};
    exportable.value = meta.exportable !== false;

    const schemaRes = await api(`/api/${modelName.value}/schema/`);
    const schema = await schemaRes.json();

    colProps.value = buildColumnProps(schema);

    if (meta.list_display && meta.list_display.length > 0) {
        columns.value = meta.list_display;
    } else {
        columns.value = Object.keys(colProps.value);
    }

    // Load FK lookups for columns that are foreign keys
    const fkCols = extractFkColumns(schema);
    fkModels.value = fkCols;
    const lookup = {};
    const promises = Object.entries(fkCols).map(async ([col, fkModel]) => {
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

    // Build column filters for all visible columns
    const fObj = {};
    const fMeta = {};
    const fkFilterPromises = [];
    for (const col of columns.value) {
        const type = colType(col);
        if (type === 'datetime') continue;
        fObj[col] = { value: null, matchMode: 'equals' };
        if (type === 'fk') {
            fMeta[col] = { type: 'fk' };
            if (fkCols[col]) {
                fkFilterPromises.push(
                    api(`/api/${fkCols[col]}/options/`).then((r) => r.json()).then((opts) => {
                        fMeta[col].options = opts;
                    })
                );
            }
        } else if (type === 'boolean') {
            fMeta[col] = { type: 'boolean' };
        } else {
            fMeta[col] = { type: 'text' };
        }
    }
    await Promise.all(fkFilterPromises);
    filters.value = fObj;
    filterMeta.value = fMeta;
}

async function loadRecords() {
    loading.value = true;
    try {
        let url = `/api/${modelName.value}/?page=${page.value}&per_page=${perPage.value}`;
        if (sortField.value) {
            const prefix = sortOrder.value === -1 ? '-' : '';
            url += `&ordering=${prefix}${sortField.value}`;
        }
        if (searchQuery.value) {
            url += `&search=${encodeURIComponent(searchQuery.value)}`;
        }
        for (const [col, filter] of Object.entries(filters.value)) {
            if (filter.value !== null && filter.value !== undefined && filter.value !== '') {
                url += `&${col}=${encodeURIComponent(filter.value)}`;
            }
        }
        const res = await api(url);
        const data = await res.json();
        records.value = data.items;
        totalRecords.value = data.total;
    } finally {
        loading.value = false;
    }
}

function onSearch(event) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        searchQuery.value = event.target.value;
        page.value = 1;
        loadRecords();
    }, 300);
}

function onFilter() {
    page.value = 1;
    loadRecords();
}

let filterInputTimeout = null;
function onFilterInput(filterCallback) {
    clearTimeout(filterInputTimeout);
    filterInputTimeout = setTimeout(filterCallback, 300);
}

function buildExportUrl(format) {
    let url = `/api/${modelName.value}/export/?format=${format}`;
    if (sortField.value) {
        const prefix = sortOrder.value === -1 ? '-' : '';
        url += `&ordering=${prefix}${sortField.value}`;
    }
    if (searchQuery.value) {
        url += `&search=${encodeURIComponent(searchQuery.value)}`;
    }
    for (const [col, filter] of Object.entries(filters.value)) {
        if (filter.value !== null && filter.value !== undefined && filter.value !== '') {
            url += `&${col}=${encodeURIComponent(filter.value)}`;
        }
    }
    return url;
}

async function doExport(format) {
    const url = buildExportUrl(format);
    const res = await api(url);
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${modelName.value}.${format}`;
    a.click();
    URL.revokeObjectURL(a.href);
}

function exportData(format) {
    if (exportWarnThreshold.value && totalRecords.value > exportWarnThreshold.value) {
        confirm.require({
            message: `You are about to export ${totalRecords.value.toLocaleString()} records. This may take a while. Continue?`,
            header: 'Large Export',
            icon: 'pi pi-exclamation-triangle',
            rejectLabel: 'Cancel',
            rejectProps: { severity: 'secondary', text: true },
            acceptLabel: 'Export',
            accept: () => doExport(format),
        });
    } else {
        doExport(format);
    }
}

const exportItems = [
    { label: 'Export JSON', icon: 'pi pi-file', command: () => exportData('json') }
];

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
    const keys = Object.keys(record);
    return keys.length > 0 ? record[keys[0]] : null;
}

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
            <div class="flex items-center gap-2">
                <IconField v-if="searchFields && searchFields.length > 0">
                    <InputIcon class="pi pi-search" />
                    <InputText :placeholder="`Search ${verboseName}...`" @input="onSearch" />
                </IconField>
                <SplitButton v-if="exportable" label="CSV" icon="pi pi-download" severity="secondary" @click="exportData('csv')" :model="exportItems" />
                <Button label="Create" icon="pi pi-plus" @click="router.push(`/${modelName}/create`)" />
            </div>
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
            v-model:filters="filters"
            filterDisplay="row"
            @page="onPage"
            @sort="onSort"
            @filter="onFilter"
            @row-click="onRowClick"
            stripedRows
            rowHover
            class="cursor-pointer"
        >
            <Column v-for="col in columns" :key="col" :field="col" :header="colLabel(col)" :sortable="true" :showFilterMenu="false">
                <template v-if="filterMeta[col]" #filter="{ filterModel, filterCallback }">
                    <!-- FK filter -->
                    <Select
                        v-if="filterMeta[col].type === 'fk'"
                        v-model="filterModel.value"
                        @update:modelValue="filterCallback()"
                        :options="filterMeta[col].options"
                        optionLabel="label"
                        optionValue="value"
                        :placeholder="colLabel(col)"
                        showClear
                        class="w-full"
                    />
                    <!-- Boolean filter -->
                    <Select
                        v-else-if="filterMeta[col].type === 'boolean'"
                        v-model="filterModel.value"
                        @update:modelValue="filterCallback()"
                        :options="[{ label: 'Yes', value: true }, { label: 'No', value: false }]"
                        optionLabel="label"
                        optionValue="value"
                        placeholder="All"
                        showClear
                        class="w-full"
                    />
                    <!-- Text filter -->
                    <InputText
                        v-else
                        v-model="filterModel.value"
                        @input="onFilterInput(filterCallback)"
                        placeholder="Filter..."
                        class="w-full"
                    />
                </template>
                <template #body="{ data }">
                    <!-- null -->
                    <span v-if="data[col] == null" class="text-surface-400 italic">NULL</span>

                    <!-- PK -->
                    <router-link
                        v-else-if="colType(col) === 'pk'"
                        :to="`/${modelName}/${data[col]}`"
                        class="font-mono text-primary no-underline hover:underline"
                        @click.stop
                    >
                        {{ data[col] }}
                    </router-link>

                    <!-- FK -->
                    <router-link
                        v-else-if="colType(col) === 'fk'"
                        :to="`/${fkModels[col]}/${data[col]}`"
                        class="text-primary no-underline hover:underline"
                        @click.stop
                    >
                        &rarr; {{ fkLookup[col]?.[data[col]] ?? data[col] }}
                    </router-link>

                    <!-- Boolean -->
                    <i
                        v-else-if="colType(col) === 'boolean'"
                        :class="data[col] ? 'pi pi-check text-green-500' : 'pi pi-times text-red-400'"
                    />

                    <!-- Datetime -->
                    <span v-else-if="colType(col) === 'datetime'" class="font-mono text-sm">
                        {{ formatDatetime(data[col]) }}
                    </span>

                    <!-- Default (string/number) -->
                    <span v-else class="truncate max-w-xs inline-block align-bottom">
                        {{ data[col] }}
                    </span>
                </template>
            </Column>
        </DataTable>

        <ConfirmDialog />
    </div>
</template>
