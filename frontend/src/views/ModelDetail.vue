<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { api } from '@/api.js';
import { findPk } from '@/utils.js';

const route = useRoute();
const router = useRouter();
const toast = useToast();
const confirm = useConfirm();

const modelName = ref(route.params.model);
const pk = ref(route.params.pk);
const isCreate = computed(() => !pk.value);

const schema = ref(null);
const fields = ref([]);
const formData = ref({});
const originalData = ref(null);
const errors = ref({});
const fkOptions = ref({});  // { fieldName: [{value, label}] }
const columnLabels = ref({});
const readonlyFields = ref([]);
const loading = ref(false);
const saving = ref(false);
const deleting = ref(false);

// --- FK Create Dialog ---

const dlgVisible = ref(false);
const dlgField = ref(null);      // parent field that triggered the dialog
const dlgSchema = ref(null);
const dlgFields = ref([]);
const dlgFormData = ref({});
const dlgErrors = ref({});
const dlgFkOptions = ref({});
const dlgSaving = ref(false);

// --- Schema parsing ---

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

function extractFkMap(schemaData) {
    const map = {};
    const props = schemaData.properties || {};
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

function resolveFormat(prop) {
    if (prop.format) return prop.format;
    if (prop.anyOf) {
        const nonNull = prop.anyOf.find((t) => t.format);
        if (nonNull) return nonNull.format;
    }
    return null;
}

function buildFields(schemaData, labels, roFields) {
    const props = schemaData.properties || {};
    const required = new Set(schemaData.required || []);
    const roSet = new Set(roFields || []);
    const fkMap = extractFkMap(schemaData);
    const result = [];

    for (const [name, prop] of Object.entries(props)) {
        if (hasRef(prop)) continue;

        const fk = fkMap[name] || null;

        result.push({
            name,
            label: (labels && labels[name]) || prop.title || name,
            type: resolveType(prop),
            format: resolveFormat(prop),
            dbType: prop['x-db-type'] || null,
            isPk: !!prop['x-db-primary-key'],
            isReadonly: !!prop['x-db-readonly'] || roSet.has(name),
            isRequired: required.has(name),
            default: prop.default ?? null,
            maxLength: prop.maxLength || prop['x-db-max-length'] || null,
            fk,
        });
    }

    return result;
}

// --- Form helpers ---

const visibleFields = computed(() => {
    return fields.value.filter((f) => !(f.isPk && isCreate.value));
});

const isDirty = computed(() => {
    if (isCreate.value) return true;
    if (!originalData.value) return false;
    return JSON.stringify(formData.value) !== JSON.stringify(originalData.value);
});

const dlgVisibleFields = computed(() => {
    return dlgFields.value.filter((f) => !f.isPk);
});

function componentType(field) {
    if (field.fk) return 'select';
    if (field.type === 'boolean') return 'boolean';
    if (field.type === 'integer' || field.type === 'number') return 'number';
    if (field.format === 'date-time') return 'datetime';
    if (field.format === 'date') return 'date';
    if (field.type === 'string' && !field.maxLength && (!field.dbType || field.dbType.toUpperCase() === 'TEXT')) return 'textarea';
    return 'text';
}

function initFormData(fieldList, record) {
    const data = {};
    for (const f of fieldList) {
        let val = record ? (record[f.name] ?? f.default) : f.default;
        if (val && (f.format === 'date-time' || f.format === 'date')) {
            val = new Date(val);
        }
        data[f.name] = val;
    }
    return data;
}

function validate(fieldList, data) {
    const errs = {};
    for (const f of fieldList) {
        if (f.isRequired && !f.isPk && !f.isReadonly) {
            const val = data[f.name];
            if (val === null || val === undefined || val === '') {
                errs[f.name] = 'This field is required';
            }
        }
    }
    return errs;
}

function buildPayload() {
    const payload = {};
    for (const f of fields.value) {
        if (f.isReadonly) continue;
        if (f.isPk && isCreate.value) continue;
        let val = formData.value[f.name];
        if (val instanceof Date) {
            val = val.toISOString();
        }
        payload[f.name] = val;
    }
    return payload;
}

// --- API ---

async function loadSchema() {
    const [schemaRes, modelsRes] = await Promise.all([
        api(`/api/${modelName.value}/schema`),
        api('/api/models'),
    ]);
    schema.value = await schemaRes.json();
    const models = await modelsRes.json();
    const meta = models.find((m) => m.name === modelName.value);
    columnLabels.value = meta?.column_labels || {};
    readonlyFields.value = meta?.readonly_fields || [];
    fields.value = buildFields(schema.value, columnLabels.value, readonlyFields.value);
}

async function loadFkOptions() {
    const fkFields = fields.value.filter((f) => f.fk);
    const promises = fkFields.map(async (f) => {
        let url = `/api/${f.fk.model}/options`;
        const currentVal = formData.value?.[f.name];
        if (currentVal != null) {
            url += `?include=${encodeURIComponent(currentVal)}`;
        }
        const res = await api(url);
        fkOptions.value[f.name] = await res.json();
    });
    await Promise.all(promises);
}

let fkSearchTimeout = null;
function onFkSearch(field, event) {
    clearTimeout(fkSearchTimeout);
    const query = event.value;
    fkSearchTimeout = setTimeout(async () => {
        const url = query
            ? `/api/${field.fk.model}/options?search=${encodeURIComponent(query)}`
            : `/api/${field.fk.model}/options`;
        const res = await api(url);
        fkOptions.value[field.name] = await res.json();
    }, 300);
}

async function loadRecord() {
    loading.value = true;
    try {
        const res = await api(`/api/${modelName.value}/${pk.value}`);
        formData.value = initFormData(fields.value, await res.json());
        originalData.value = JSON.parse(JSON.stringify(formData.value));
    } finally {
        loading.value = false;
    }
}

async function save(andContinue = false) {
    const errs = validate(fields.value, formData.value);
    if (Object.keys(errs).length > 0) {
        errors.value = errs;
        return;
    }

    saving.value = true;
    errors.value = {};

    try {
        const url = isCreate.value
            ? `/api/${modelName.value}`
            : `/api/${modelName.value}/${pk.value}`;

        const res = await api(url, {
            method: isCreate.value ? 'POST' : 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildPayload()),
        });

        if (res.status === 422) {
            parseValidationErrors(await res.json());
            return;
        }

        if (!res.ok) {
            const data = await res.json();
            toast.add({ severity: 'error', summary: 'Error', detail: data.detail || 'Unknown error', life: 5000 });
            return;
        }

        const record = await res.json();
        toast.add({ severity: 'success', summary: 'Saved', detail: `${schema.value.title} saved`, life: 3000 });

        navigatingAfterSave.value = true;
        if (isCreate.value) {
            const newPk = findPk(record, fields.value);
            if (newPk !== null) {
                if (andContinue) {
                    router.replace(`/${modelName.value}/${newPk}`);
                } else {
                    router.push(`/${modelName.value}`);
                }
            }
        } else if (andContinue) {
            originalData.value = JSON.parse(JSON.stringify(formData.value));
            navigatingAfterSave.value = false;
        } else {
            router.push(`/${modelName.value}`);
        }
    } finally {
        saving.value = false;
    }
}

function confirmDelete() {
    confirm.require({
        message: `Are you sure you want to delete this ${schema.value?.title || 'record'}?`,
        header: 'Confirm Delete',
        icon: 'pi pi-exclamation-triangle',
        rejectLabel: 'Cancel',
        rejectProps: { severity: 'secondary', text: true },
        acceptLabel: 'Delete',
        acceptProps: { severity: 'danger' },
        accept: deleteRecord,
    });
}

async function deleteRecord() {
    deleting.value = true;
    try {
        const res = await api(`/api/${modelName.value}/${pk.value}`, { method: 'DELETE' });
        if (!res.ok) {
            const data = await res.json();
            toast.add({ severity: 'error', summary: 'Error', detail: data.detail || 'Delete failed', life: 5000 });
            return;
        }
        toast.add({ severity: 'success', summary: 'Deleted', detail: `${schema.value.title} deleted`, life: 3000 });
        navigatingAfterSave.value = true;
        router.push(`/${modelName.value}`);
    } finally {
        deleting.value = false;
    }
}

function parseValidationErrors(data) {
    if (!Array.isArray(data.detail)) return;
    const errs = {};
    for (const err of data.detail) {
        const loc = err.loc || [];
        const fieldName = loc[loc.length - 1];
        if (fieldName) errs[fieldName] = err.msg;
    }
    errors.value = errs;
}

function goBack() {
    if (window.history.state?.back) {
        router.back();
    } else {
        router.push(`/${modelName.value}`);
    }
}

function openFkRecord(field) {
    router.push(`/${field.fk.model}/${formData.value[field.name]}`);
}

// --- FK Create Dialog ---

async function openFkCreate(field) {
    dlgField.value = field;
    dlgErrors.value = {};
    dlgSaving.value = false;

    const res = await api(`/api/${field.fk.model}/schema`);
    dlgSchema.value = await res.json();
    dlgFields.value = buildFields(dlgSchema.value);
    dlgFormData.value = initFormData(dlgFields.value, null);

    // Load initial FK options for fields inside the dialog form
    const nested = dlgFields.value.filter((f) => f.fk);
    const opts = {};
    await Promise.all(nested.map(async (f) => {
        const r = await api(`/api/${f.fk.model}/options`);
        opts[f.name] = await r.json();
    }));
    dlgFkOptions.value = opts;

    dlgVisible.value = true;
}

let dlgFkSearchTimeout = null;
function onDlgFkSearch(field, event) {
    clearTimeout(dlgFkSearchTimeout);
    const query = event.value;
    dlgFkSearchTimeout = setTimeout(async () => {
        const url = query
            ? `/api/${field.fk.model}/options?search=${encodeURIComponent(query)}`
            : `/api/${field.fk.model}/options`;
        const res = await api(url);
        dlgFkOptions.value[field.name] = await res.json();
    }, 300);
}

async function dlgSave() {
    const errs = validate(dlgFields.value, dlgFormData.value);
    if (Object.keys(errs).length > 0) {
        dlgErrors.value = errs;
        return;
    }

    dlgSaving.value = true;
    dlgErrors.value = {};

    try {
        const fkModel = dlgField.value.fk.model;
        const payload = {};
        for (const f of dlgFields.value) {
            if (f.isReadonly || f.isPk) continue;
            payload[f.name] = dlgFormData.value[f.name];
        }

        const res = await api(`/api/${fkModel}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (res.status === 422) {
            const data = await res.json();
            if (Array.isArray(data.detail)) {
                const errs = {};
                for (const err of data.detail) {
                    const loc = err.loc || [];
                    errs[loc[loc.length - 1]] = err.msg;
                }
                dlgErrors.value = errs;
            }
            return;
        }

        if (!res.ok) {
            const data = await res.json();
            toast.add({ severity: 'error', summary: 'Error', detail: data.detail || 'Create failed', life: 5000 });
            return;
        }

        const record = await res.json();
        toast.add({ severity: 'success', summary: 'Created', detail: `${dlgSchema.value.title} created`, life: 3000 });

        const newPk = findPk(record, dlgFields.value);

        // Refresh options for the parent FK field and select the new record
        const parentField = dlgField.value;
        const optRes = await api(`/api/${parentField.fk.model}/options`);
        fkOptions.value[parentField.name] = await optRes.json();
        formData.value[parentField.name] = newPk;

        dlgVisible.value = false;
    } finally {
        dlgSaving.value = false;
    }
}

// --- Navigation guard ---

const navigatingAfterSave = ref(false);

onBeforeRouteLeave(() => {
    if (navigatingAfterSave.value || !isDirty.value || isCreate.value) return true;
    return window.confirm('You have unsaved changes. Leave this page?');
});

onMounted(async () => {
    await loadSchema();
    if (isCreate.value) {
        formData.value = initFormData(fields.value, null);
    } else {
        await loadRecord();
    }
    await loadFkOptions();
});
</script>

<template>
    <div class="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6 items-start">
        <!-- Left: form card -->
        <div class="card">
            <div class="flex justify-between items-center mb-4">
                <div class="text-xl font-semibold">
                    {{ schema?.title || modelName }} {{ isCreate ? 'Create' : `#${pk}` }}
                </div>
                <Button label="Back" icon="pi pi-arrow-left" text @click="goBack" />
            </div>

            <div v-if="loading" class="flex justify-center p-8">
                <ProgressSpinner />
            </div>

            <form v-else @submit.prevent="save(false)" class="flex flex-col gap-4">
                <div v-for="field in visibleFields" :key="field.name" class="flex flex-col gap-1">
                    <label :for="field.name" class="font-semibold">
                        {{ field.label }}
                        <span v-if="field.isRequired" class="text-red-500">*</span>
                    </label>

                    <!-- FK Select -->
                    <div v-if="componentType(field) === 'select'" class="flex gap-2 items-center">
                        <Select
                            :id="field.name"
                            v-model="formData[field.name]"
                            :options="fkOptions[field.name] || []"
                            optionLabel="label"
                            optionValue="value"
                            :showClear="!field.isRequired"
                            placeholder="Select..."
                            filter
                            @filter="onFkSearch(field, $event)"
                            :invalid="!!errors[field.name]"
                            fluid
                        />
                        <Button
                            icon="pi pi-arrow-up-right"
                            severity="secondary"
                            text
                            size="small"
                            :disabled="formData[field.name] == null"
                            @click="openFkRecord(field)"
                            aria-label="Open record"
                        />
                        <Button
                            icon="pi pi-plus"
                            severity="secondary"
                            text
                            size="small"
                            @click="openFkCreate(field)"
                            aria-label="Create new"
                        />
                    </div>

                    <!-- Boolean -->
                    <ToggleSwitch
                        v-else-if="componentType(field) === 'boolean'"
                        :id="field.name"
                        v-model="formData[field.name]"
                        :disabled="field.isReadonly"
                    />

                    <!-- Number -->
                    <InputNumber
                        v-else-if="componentType(field) === 'number'"
                        :id="field.name"
                        v-model="formData[field.name]"
                        :disabled="field.isReadonly"
                        :useGrouping="false"
                        :invalid="!!errors[field.name]"
                        fluid
                    />

                    <!-- DateTime -->
                    <DatePicker
                        v-else-if="componentType(field) === 'datetime'"
                        :id="field.name"
                        v-model="formData[field.name]"
                        :disabled="field.isReadonly"
                        showTime
                        hourFormat="24"
                        dateFormat="yy-mm-dd"
                        :invalid="!!errors[field.name]"
                        fluid
                    />

                    <!-- Date -->
                    <DatePicker
                        v-else-if="componentType(field) === 'date'"
                        :id="field.name"
                        v-model="formData[field.name]"
                        :disabled="field.isReadonly"
                        dateFormat="yy-mm-dd"
                        :invalid="!!errors[field.name]"
                        fluid
                    />

                    <!-- Textarea -->
                    <Textarea
                        v-else-if="componentType(field) === 'textarea'"
                        :id="field.name"
                        v-model="formData[field.name]"
                        :disabled="field.isReadonly"
                        :invalid="!!errors[field.name]"
                        rows="5"
                        autoResize
                        fluid
                    />

                    <!-- Text -->
                    <InputText
                        v-else
                        :id="field.name"
                        v-model="formData[field.name]"
                        :disabled="field.isReadonly"
                        :maxlength="field.maxLength"
                        :invalid="!!errors[field.name]"
                        fluid
                    />

                    <Message v-if="errors[field.name]" severity="error" size="small" variant="simple">
                        {{ errors[field.name] }}
                    </Message>
                </div>
            </form>
        </div>

        <!-- Right: actions card -->
        <div class="card lg:sticky lg:top-24">
            <div class="flex flex-col gap-3">
                <Button
                    :label="isCreate ? 'Create' : 'Save'"
                    icon="pi pi-check"
                    :loading="saving"
                    :disabled="!isDirty"
                    @click="save(false)"
                />
                <Button
                    :label="isCreate ? 'Create & continue' : 'Save & continue'"
                    icon="pi pi-save"
                    severity="secondary"
                    :loading="saving"
                    :disabled="!isDirty"
                    @click="save(true)"
                />
                <Button
                    v-if="!isCreate"
                    label="Delete"
                    icon="pi pi-trash"
                    severity="danger"
                    outlined
                    :loading="deleting"
                    @click="confirmDelete"
                />
            </div>
        </div>

        <!-- FK Create Dialog -->
        <Dialog
            v-model:visible="dlgVisible"
            :header="'Create ' + (dlgSchema?.title || '')"
            modal
            :style="{ width: '32rem' }"
        >
            <form @submit.prevent="dlgSave" class="flex flex-col gap-4">
                <div v-for="field in dlgVisibleFields" :key="field.name" class="flex flex-col gap-1">
                    <label :for="'dlg-' + field.name" class="font-semibold">
                        {{ field.label }}
                        <span v-if="field.isRequired" class="text-red-500">*</span>
                    </label>

                    <Select
                        v-if="componentType(field) === 'select'"
                        :id="'dlg-' + field.name"
                        v-model="dlgFormData[field.name]"
                        :options="dlgFkOptions[field.name] || []"
                        optionLabel="label"
                        optionValue="value"
                        :showClear="!field.isRequired"
                        placeholder="Select..."
                        filter
                        @filter="onDlgFkSearch(field, $event)"
                        :invalid="!!dlgErrors[field.name]"
                        fluid
                    />

                    <ToggleSwitch
                        v-else-if="componentType(field) === 'boolean'"
                        :id="'dlg-' + field.name"
                        v-model="dlgFormData[field.name]"
                    />

                    <InputNumber
                        v-else-if="componentType(field) === 'number'"
                        :id="'dlg-' + field.name"
                        v-model="dlgFormData[field.name]"
                        :useGrouping="false"
                        :invalid="!!dlgErrors[field.name]"
                        fluid
                    />

                    <DatePicker
                        v-else-if="componentType(field) === 'datetime'"
                        :id="'dlg-' + field.name"
                        v-model="dlgFormData[field.name]"
                        showTime
                        hourFormat="24"
                        dateFormat="yy-mm-dd"
                        :invalid="!!dlgErrors[field.name]"
                        fluid
                    />

                    <DatePicker
                        v-else-if="componentType(field) === 'date'"
                        :id="'dlg-' + field.name"
                        v-model="dlgFormData[field.name]"
                        dateFormat="yy-mm-dd"
                        :invalid="!!dlgErrors[field.name]"
                        fluid
                    />

                    <Textarea
                        v-else-if="componentType(field) === 'textarea'"
                        :id="'dlg-' + field.name"
                        v-model="dlgFormData[field.name]"
                        :invalid="!!dlgErrors[field.name]"
                        rows="5"
                        autoResize
                        fluid
                    />

                    <InputText
                        v-else
                        :id="'dlg-' + field.name"
                        v-model="dlgFormData[field.name]"
                        :maxlength="field.maxLength"
                        :invalid="!!dlgErrors[field.name]"
                        fluid
                    />

                    <Message v-if="dlgErrors[field.name]" severity="error" size="small" variant="simple">
                        {{ dlgErrors[field.name] }}
                    </Message>
                </div>

                <div class="flex justify-end gap-2 mt-2">
                    <Button label="Cancel" severity="secondary" text @click="dlgVisible = false" />
                    <Button type="submit" label="Create" icon="pi pi-check" :loading="dlgSaving" />
                </div>
            </form>
        </Dialog>

        <ConfirmDialog />
    </div>
</template>
