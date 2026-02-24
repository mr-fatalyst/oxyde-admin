<script setup>
import { ref, inject, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useConfirm } from 'primevue/useconfirm';
import { useToast } from 'primevue/usetoast';
import { api } from '@/api.js';

const appConfig = inject('appConfig', {});

const route = useRoute();
const router = useRouter();
const confirm = useConfirm();
const toast = useToast();

const modelName = ref(route.params.model);
const verboseName = ref('');
const tableName = ref('');
const columns = ref([]);
const records = ref([]);
const totalRecords = ref(0);
const loading = ref(false);
const fkLabels = ref({});  // { column_name: { id: label } } — from list response
const fkModels = ref({});  // { column_name: fk_model_name }
const colProps = ref({});   // { column_name: schema_property }
const searchFields = ref(null);
const exportable = ref(false);
const columnLabels = ref({});
const filters = ref({});       // PrimeVue filter state: { col: { value, matchMode } }
const filterMeta = ref({});    // { col: { type, options? } }
const pkFieldName = ref(null);
const readonlyFieldSet = ref(new Set());

const page = ref(1);
const perPage = ref(25);
const sortField = ref(null);
const sortOrder = ref(null);
const searchQuery = ref('');
const exportChunkSize = ref(appConfig.export_chunk_size || null);
const maxExportRows = ref(appConfig.max_export_rows || null);
let searchTimeout = null;

// --- Selection ---
const selectedRecords = ref([]);
const hasSelection = computed(() => selectedRecords.value.length > 0);

// --- Bulk Update Dialog ---
const bulkDlgVisible = ref(false);
const bulkFields = ref([]);        // fields for the form (from schema)
const bulkFormData = ref({});      // field values
const bulkEnabled = ref({});       // checkbox state per field
const bulkFkOptions = ref({});     // fk options per field
const bulkSaving = ref(false);
const schemaData = ref(null);      // cached schema

function buildColumnProps(schema) {
    const result = {};
    const props = schema.properties || {};
    for (const [fieldName, prop] of Object.entries(props)) {
        const col = prop['x-db-column'] || fieldName;
        result[col] = prop;
    }
    return result;
}

function extractFkColumns(schema) {
    const map = {};
    const props = schema.properties || {};
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

// --- Schema field helpers (shared with ModelDetail logic) ---

function resolveType(prop) {
    if (prop.type) return prop.type;
    if (prop.anyOf) {
        const nonNull = prop.anyOf.find((t) => t.type && t.type !== 'null');
        if (nonNull) return nonNull.type;
    }
    return 'string';
}

function hasRef(prop) {
    if (prop.$ref) return true;
    if (prop.anyOf) return prop.anyOf.some((t) => t.$ref);
    return false;
}

function resolveFormat(prop) {
    if (prop.format) return prop.format;
    if (prop.anyOf) {
        const nonNull = prop.anyOf.find((t) => t.format);
        if (nonNull) return nonNull.format;
    }
    return null;
}

function extractFkMap(schema) {
    const map = {};
    const props = schema.properties || {};
    for (const [, prop] of Object.entries(props)) {
        if (!hasRef(prop)) continue;
        const fk = prop['x-db-foreign-key'];
        const col = prop['x-db-column'];
        if (fk && col) {
            map[col] = fk;
        }
    }
    return map;
}

function buildBulkFields(schema, labels, roFields) {
    const props = schema.properties || {};
    const roSet = new Set(roFields || []);
    const fkMap = extractFkMap(schema);
    const result = [];

    for (const [name, prop] of Object.entries(props)) {
        if (hasRef(prop)) continue;
        const isPk = !!prop['x-db-primary-key'];
        if (isPk) continue;

        const fk = fkMap[name] || null;
        result.push({
            name,
            label: (labels && labels[name]) || prop.title || name,
            type: resolveType(prop),
            format: resolveFormat(prop),
            dbType: prop['x-db-type'] || null,
            isReadonly: !!prop['x-db-readonly'] || roSet.has(name),
            maxLength: prop.maxLength || prop['x-db-max-length'] || null,
            fk,
        });
    }
    return result;
}

function componentType(field) {
    if (field.fk) return 'select';
    if (field.type === 'boolean') return 'boolean';
    if (field.type === 'integer' || field.type === 'number') return 'number';
    if (field.format === 'date-time') return 'datetime';
    if (field.format === 'date') return 'date';
    if (field.type === 'string' && !field.maxLength && (!field.dbType || field.dbType.toUpperCase() === 'TEXT')) return 'textarea';
    return 'text';
}

// --- Load meta & records ---

async function loadMeta() {
    const res = await api('/api/models/');
    const models = await res.json();
    const meta = models.find((m) => m.name === modelName.value);
    if (!meta) return;

    verboseName.value = meta.verbose_name;
    tableName.value = meta.name;
    searchFields.value = meta.search_fields;
    columnLabels.value = meta.column_labels || {};
    exportable.value = meta.exportable !== false;
    readonlyFieldSet.value = new Set(meta.readonly_fields || []);

    const schemaRes = await api(`/api/${modelName.value}/schema/`);
    const schema = await schemaRes.json();
    schemaData.value = schema;

    colProps.value = buildColumnProps(schema);

    for (const [col, prop] of Object.entries(colProps.value)) {
        if (prop['x-db-primary-key']) {
            pkFieldName.value = col;
            break;
        }
    }

    if (meta.list_display && meta.list_display.length > 0) {
        columns.value = meta.list_display;
    } else {
        columns.value = Object.keys(colProps.value);
    }

    // Extract FK column mapping (col → fk model name)
    const fkCols = extractFkColumns(schema);
    fkModels.value = fkCols;

    // Build column filters for filterable columns only
    const fObj = {};
    const fMeta = {};
    const fkFilterPromises = [];
    const filterableCols = meta.list_filter && meta.list_filter.length > 0
        ? columns.value.filter(col => meta.list_filter.includes(col))
        : [];
    for (const col of filterableCols) {
        const type = colType(col);
        if (type === 'datetime') continue;
        fObj[col] = { value: null, matchMode: 'equals' };
        if (type === 'fk') {
            fMeta[col] = { type: 'fk', options: [] };
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

function buildQueryParams(extra = {}) {
    const params = new URLSearchParams(extra);
    if (sortField.value) {
        params.set('ordering', (sortOrder.value === -1 ? '-' : '') + sortField.value);
    }
    if (searchQuery.value) {
        params.set('search', searchQuery.value);
    }
    for (const [col, filter] of Object.entries(filters.value)) {
        if (filter.value !== null && filter.value !== undefined && filter.value !== '') {
            params.set(col, filter.value);
        }
    }
    return params;
}

async function loadRecords() {
    loading.value = true;
    try {
        const params = buildQueryParams({ page: page.value, per_page: perPage.value });
        const res = await api(`/api/${modelName.value}/?${params}`);
        const data = await res.json();
        records.value = data.items;
        totalRecords.value = data.total;
        if (data.fk_labels) {
            fkLabels.value = data.fk_labels;
        }
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

let fkFilterSearchTimeout = null;
function onFkFilterSearch(col, event) {
    clearTimeout(fkFilterSearchTimeout);
    const query = event.value;
    fkFilterSearchTimeout = setTimeout(async () => {
        const fkModel = fkModels.value[col];
        if (!fkModel) return;
        const url = query
            ? `/api/${fkModel}/options/?search=${encodeURIComponent(query)}`
            : `/api/${fkModel}/options/`;
        const res = await api(url);
        filterMeta.value[col].options = await res.json();
    }, 300);
}

function buildExportUrl(format) {
    const params = buildQueryParams({ format });
    if (hasSelection.value && pkFieldName.value) {
        const ids = selectedRecords.value.map((r) => r[pkFieldName.value]).join(',');
        params.set('ids', ids);
    }
    return `/api/${modelName.value}/export/?${params}`;
}

async function doExport(format) {
    const url = buildExportUrl(format);
    const res = await api(url);
    if (!res.ok) return;
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${modelName.value}.${format}`;
    a.click();
    URL.revokeObjectURL(a.href);
}

function exportData(format) {
    if (maxExportRows.value && totalRecords.value > maxExportRows.value) {
        confirm.require({
            message: `Cannot export ${totalRecords.value.toLocaleString()} records. The limit is ${maxExportRows.value.toLocaleString()}.`,
            header: 'Export Limit',
            icon: 'pi pi-exclamation-triangle',
            rejectLabel: 'Close',
            rejectProps: { severity: 'secondary', text: true },
            acceptLabel: 'OK',
        });
    } else if (exportChunkSize.value && totalRecords.value > exportChunkSize.value) {
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
    if (pkFieldName.value) {
        router.push(`/${modelName.value}/${record[pkFieldName.value]}`);
    }
}

// --- Bulk Delete ---

function confirmBulkDelete() {
    const count = selectedRecords.value.length;
    confirm.require({
        message: `Are you sure you want to delete ${count} record(s)?`,
        header: 'Confirm Bulk Delete',
        icon: 'pi pi-exclamation-triangle',
        rejectLabel: 'Cancel',
        rejectProps: { severity: 'secondary', text: true },
        acceptLabel: 'Delete',
        acceptProps: { severity: 'danger' },
        accept: doBulkDelete,
    });
}

async function doBulkDelete() {
    const ids = selectedRecords.value.map((r) => r[pkFieldName.value]);
    const res = await api(`/api/${modelName.value}/bulk-delete/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids }),
    });
    if (!res.ok) return;
    const data = await res.json();
    toast.add({ severity: 'success', summary: 'Deleted', detail: `${data.deleted} record(s) deleted`, life: 3000 });
    selectedRecords.value = [];
    await loadRecords();
}

// --- Bulk Update Dialog ---

function openBulkUpdate() {
    if (!schemaData.value) return;
    bulkFields.value = buildBulkFields(schemaData.value, columnLabels.value, [...readonlyFieldSet.value]);
    const formInit = {};
    const enabledInit = {};
    for (const f of bulkFields.value) {
        const ct = componentType(f);
        if (ct === 'boolean') formInit[f.name] = false;
        else if (ct === 'number') formInit[f.name] = 0;
        else if (ct === 'text') formInit[f.name] = '';
        else formInit[f.name] = null;
        enabledInit[f.name] = false;
    }
    bulkFormData.value = formInit;
    bulkEnabled.value = enabledInit;
    bulkFkOptions.value = {};
    bulkSaving.value = false;

    // Load FK options for fields that have FK
    const fkFields = bulkFields.value.filter((f) => f.fk);
    for (const f of fkFields) {
        api(`/api/${f.fk.model}/options/`).then((r) => r.json()).then((opts) => {
            bulkFkOptions.value[f.name] = opts;
        });
    }

    bulkDlgVisible.value = true;
}

let bulkFkSearchTimeout = null;
function onBulkFkSearch(field, event) {
    clearTimeout(bulkFkSearchTimeout);
    const query = event.value;
    bulkFkSearchTimeout = setTimeout(async () => {
        const url = query
            ? `/api/${field.fk.model}/options/?search=${encodeURIComponent(query)}`
            : `/api/${field.fk.model}/options/`;
        const res = await api(url);
        bulkFkOptions.value[field.name] = await res.json();
    }, 300);
}

const bulkEnabledCount = computed(() => {
    return Object.values(bulkEnabled.value).filter(Boolean).length;
});

async function doBulkUpdate() {
    const data = {};
    for (const f of bulkFields.value) {
        if (bulkEnabled.value[f.name]) {
            let val = bulkFormData.value[f.name];
            if (val instanceof Date) {
                val = val.toISOString();
            }
            data[f.name] = val;
        }
    }
    if (Object.keys(data).length === 0) return;

    bulkSaving.value = true;
    try {
        const ids = selectedRecords.value.map((r) => r[pkFieldName.value]);
        const res = await api(`/api/${modelName.value}/bulk-update/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids, data }),
        });
        if (!res.ok) return;
        const result = await res.json();
        toast.add({ severity: 'success', summary: 'Updated', detail: `${result.updated} record(s) updated`, life: 3000 });
        bulkDlgVisible.value = false;
        selectedRecords.value = [];
        await loadRecords();
    } finally {
        bulkSaving.value = false;
    }
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
                <Tag v-if="hasSelection" :value="`${selectedRecords.length} selected`" severity="info" />
            </div>
            <div class="flex items-center gap-2">
                <IconField v-if="searchFields && searchFields.length > 0">
                    <InputIcon class="pi pi-search" />
                    <InputText :placeholder="`Search ${verboseName}...`" @input="onSearch" />
                </IconField>
                <Button v-if="hasSelection" label="Update" icon="pi pi-pencil" severity="warn" @click="openBulkUpdate" />
                <Button v-if="hasSelection" label="Delete" icon="pi pi-trash" severity="danger" @click="confirmBulkDelete" />
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
            v-model:selection="selectedRecords"
            :dataKey="pkFieldName"
            filterDisplay="row"
            @page="onPage"
            @sort="onSort"
            @filter="onFilter"
            @row-click="onRowClick"
            stripedRows
            rowHover
            class="cursor-pointer"
        >
            <Column selectionMode="multiple" headerStyle="width: 3rem" />
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
                        filter
                        @filter="onFkFilterSearch(col, $event)"
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
                        &rarr; {{ fkLabels[col]?.[data[col]] ?? data[col] }}
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

        <!-- Bulk Update Dialog -->
        <Dialog
            v-model:visible="bulkDlgVisible"
            :header="`Update ${selectedRecords.length} record(s)`"
            modal
            :style="{ width: '36rem' }"
        >
            <form @submit.prevent="doBulkUpdate" class="flex flex-col gap-4">
                <div v-for="field in bulkFields" :key="field.name" class="flex flex-col gap-1">
                    <div class="flex items-center gap-2">
                        <Checkbox
                            v-if="!field.isReadonly"
                            v-model="bulkEnabled[field.name]"
                            :binary="true"
                            :inputId="'bulk-chk-' + field.name"
                        />
                        <label :for="'bulk-chk-' + field.name" class="font-semibold">
                            {{ field.label }}
                        </label>
                        <Tag v-if="field.isReadonly" value="readonly" severity="secondary" class="text-xs" />
                    </div>

                    <!-- FK Select -->
                    <Select
                        v-if="componentType(field) === 'select'"
                        v-model="bulkFormData[field.name]"
                        :options="bulkFkOptions[field.name] || []"
                        optionLabel="label"
                        optionValue="value"
                        showClear
                        placeholder="Select..."
                        filter
                        @filter="onBulkFkSearch(field, $event)"
                        :disabled="field.isReadonly || !bulkEnabled[field.name]"
                        fluid
                    />

                    <!-- Boolean -->
                    <ToggleSwitch
                        v-else-if="componentType(field) === 'boolean'"
                        v-model="bulkFormData[field.name]"
                        :disabled="field.isReadonly || !bulkEnabled[field.name]"
                    />

                    <!-- Number -->
                    <InputNumber
                        v-else-if="componentType(field) === 'number'"
                        v-model="bulkFormData[field.name]"
                        :useGrouping="false"
                        :disabled="field.isReadonly || !bulkEnabled[field.name]"
                        fluid
                    />

                    <!-- DateTime -->
                    <DatePicker
                        v-else-if="componentType(field) === 'datetime'"
                        v-model="bulkFormData[field.name]"
                        showTime
                        hourFormat="24"
                        dateFormat="yy-mm-dd"
                        :disabled="field.isReadonly || !bulkEnabled[field.name]"
                        fluid
                    />

                    <!-- Date -->
                    <DatePicker
                        v-else-if="componentType(field) === 'date'"
                        v-model="bulkFormData[field.name]"
                        dateFormat="yy-mm-dd"
                        :disabled="field.isReadonly || !bulkEnabled[field.name]"
                        fluid
                    />

                    <!-- Textarea -->
                    <Textarea
                        v-else-if="componentType(field) === 'textarea'"
                        v-model="bulkFormData[field.name]"
                        :disabled="field.isReadonly || !bulkEnabled[field.name]"
                        rows="3"
                        autoResize
                        fluid
                    />

                    <!-- Text -->
                    <InputText
                        v-else
                        v-model="bulkFormData[field.name]"
                        :maxlength="field.maxLength"
                        :disabled="field.isReadonly || !bulkEnabled[field.name]"
                        fluid
                    />
                </div>

                <div class="flex justify-end gap-2 mt-2">
                    <Button label="Cancel" severity="secondary" text @click="bulkDlgVisible = false" />
                    <Button type="submit" label="Update" icon="pi pi-check" :loading="bulkSaving" :disabled="bulkEnabledCount === 0" />
                </div>
            </form>
        </Dialog>

        <ConfirmDialog />
    </div>
</template>
