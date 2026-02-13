<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { api } from '@/api.js';

const route = useRoute();
const router = useRouter();
const toast = useToast();

const modelName = ref(route.params.model);
const pk = ref(route.params.pk);
const isCreate = computed(() => !pk.value);

const schema = ref(null);
const fields = ref([]);
const formData = ref({});
const errors = ref({});
const fkOptions = ref({});  // { fieldName: [{value, label}] }
const loading = ref(false);
const saving = ref(false);

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
    // Build a map: column_name -> {model, field} from $ref properties
    // e.g. author has x-db-column: "author_id" and x-db-foreign-key: {model: "authors", field: "id"}
    const map = {};
    const props = schemaData.properties || {};
    for (const [, prop] of Object.entries(props)) {
        if (!hasRef(prop)) continue;
        const fk = prop['x-db-foreign-key'];
        const col = prop['x-db-column'];
        if (fk && col) {
            map[col] = fk; // { model: "authors", field: "id" }
        }
    }
    return map;
}

function buildFields(schemaData) {
    const props = schemaData.properties || {};
    const required = new Set(schemaData.required || []);
    const fkMap = extractFkMap(schemaData);
    const result = [];

    for (const [name, prop] of Object.entries(props)) {
        if (hasRef(prop)) continue;

        const fk = fkMap[name] || null;

        result.push({
            name,
            label: prop.title || name,
            type: resolveType(prop),
            isPk: !!prop['x-db-primary-key'],
            isReadonly: !!prop['x-db-readonly'],
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

function componentType(field) {
    if (field.fk) return 'select';
    if (field.type === 'boolean') return 'boolean';
    if (field.type === 'integer' || field.type === 'number') return 'number';
    return 'text';
}

function initFormData(fieldList, record) {
    const data = {};
    for (const f of fieldList) {
        data[f.name] = record ? (record[f.name] ?? f.default) : f.default;
    }
    return data;
}

function buildPayload() {
    const payload = {};
    for (const f of fields.value) {
        if (f.isReadonly) continue;
        if (f.isPk && isCreate.value) continue;
        payload[f.name] = formData.value[f.name];
    }
    return payload;
}

// --- API ---

async function loadSchema() {
    const res = await api(`/api/${modelName.value}/schema/`);
    schema.value = await res.json();
    fields.value = buildFields(schema.value);
}

async function loadFkOptions() {
    const fkFields = fields.value.filter((f) => f.fk);
    const promises = fkFields.map(async (f) => {
        const res = await api(`/api/${f.fk.model}/options/`);
        fkOptions.value[f.name] = await res.json();
    });
    await Promise.all(promises);
}

async function loadRecord() {
    loading.value = true;
    try {
        const res = await api(`/api/${modelName.value}/${pk.value}/`);
        formData.value = initFormData(fields.value, await res.json());
    } finally {
        loading.value = false;
    }
}

async function save() {
    saving.value = true;
    errors.value = {};

    try {
        const url = isCreate.value
            ? `/api/${modelName.value}/`
            : `/api/${modelName.value}/${pk.value}/`;

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

        if (isCreate.value) {
            const newPk = findPk(record);
            if (newPk !== null) router.replace(`/${modelName.value}/${newPk}`);
        }
    } finally {
        saving.value = false;
    }
}

function findPk(record) {
    for (const f of fields.value) {
        if (f.isPk) return record[f.name];
    }
    return record.id ?? null;
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
    router.push(`/${modelName.value}`);
}

onMounted(async () => {
    await loadSchema();
    await loadFkOptions();
    if (isCreate.value) {
        formData.value = initFormData(fields.value, null);
    } else {
        await loadRecord();
    }
});
</script>

<template>
    <div class="card">
        <div class="flex justify-between items-center mb-4">
            <div class="text-xl font-semibold">
                {{ schema?.title || modelName }} — {{ isCreate ? 'Create' : `#${pk}` }}
            </div>
            <Button label="Back" icon="pi pi-arrow-left" text @click="goBack" />
        </div>

        <div v-if="loading" class="flex justify-center p-8">
            <ProgressSpinner />
        </div>

        <form v-else @submit.prevent="save" class="flex flex-col gap-4 max-w-2xl">
            <div v-for="field in visibleFields" :key="field.name" class="flex flex-col gap-1">
                <label :for="field.name" class="font-semibold">
                    {{ field.label }}
                    <span v-if="field.isRequired" class="text-red-500">*</span>
                </label>

                <!-- FK Select -->
                <Select
                    v-if="componentType(field) === 'select'"
                    :id="field.name"
                    v-model="formData[field.name]"
                    :options="fkOptions[field.name] || []"
                    optionLabel="label"
                    optionValue="value"
                    :showClear="!field.isRequired"
                    placeholder="Select..."
                    :invalid="!!errors[field.name]"
                    fluid
                />

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

            <div class="flex gap-2 mt-2">
                <Button type="submit" :label="isCreate ? 'Create' : 'Save'" icon="pi pi-check" :loading="saving" />
                <Button label="Cancel" icon="pi pi-times" severity="secondary" text @click="goBack" />
            </div>
        </form>
    </div>
</template>
