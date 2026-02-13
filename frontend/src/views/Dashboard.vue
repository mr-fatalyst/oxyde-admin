<script setup>
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import { useRouter } from 'vue-router'

const router = useRouter()
const models = ref([])

onMounted(async () => {
  const res = await fetch('/api/models/')
  models.value = await res.json()
})
</script>

<template>
  <h1>Oxyde Admin</h1>
  <div class="grid">
    <Card v-for="model in models" :key="model.name" class="model-card">
      <template #title>{{ model.verbose_name }}</template>
      <template #subtitle>{{ model.field_count }} fields</template>
      <template #footer>
        <Button label="View" icon="pi pi-list" @click="router.push('/' + model.name)" />
      </template>
    </Card>
  </div>
</template>

<style scoped>
.grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 1rem;
}
.model-card {
  width: 250px;
}
</style>
