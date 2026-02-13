<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const models = ref([]);

onMounted(async () => {
    const res = await fetch('/api/models/');
    models.value = await res.json();
});
</script>

<template>
    <div class="card">
        <h5>Dashboard</h5>
        <p>Registered models</p>
    </div>
    <div class="flex flex-wrap gap-4">
        <Card v-for="model in models" :key="model.name" class="w-64">
            <template #title>{{ model.verbose_name }}</template>
            <template #subtitle>{{ model.field_count }} fields</template>
            <template #footer>
                <Button label="View" icon="pi pi-list" @click="router.push('/' + model.name)" />
            </template>
        </Card>
    </div>
</template>
