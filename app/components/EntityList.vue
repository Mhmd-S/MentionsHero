<script setup lang="ts">
import { useAnalysis, type EntityData } from '~/composables/useAnalysis'

const { getEntities, loading, error } = useAnalysis()

const entities = ref<EntityData[]>([])
const selectedTypes = ref<string[]>(['PERSON', 'ORG', 'GPE'])
const filterType = ref<string>('all')

const entityTypeLabels: Record<string, string> = {
  PERSON: 'People',
  ORG: 'Organizations',
  GPE: 'Places',
  NORP: 'Groups/Nationalities',
  LAW: 'Laws/Policies',
  EVENT: 'Events'
}

const filteredEntities = computed(() => {
  if (filterType.value === 'all') return entities.value
  return entities.value.filter(e => e.type === filterType.value)
})

const entityTypes = computed(() => {
  const types = new Set(entities.value.map(e => e.type))
  return Array.from(types)
})

async function loadEntities() {
  entities.value = await getEntities(selectedTypes.value)
}

function getTypeColor(type: string) {
  switch (type) {
    case 'PERSON': return 'primary'
    case 'ORG': return 'info'
    case 'GPE': return 'success'
    case 'NORP': return 'warning'
    case 'LAW': return 'error'
    case 'EVENT': return 'secondary'
    default: return 'neutral'
  }
}

onMounted(() => {
  loadEntities()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between flex-wrap gap-4">
      <div>
        <h2 class="text-xl font-semibold">Named Entities</h2>
        <p class="text-sm text-gray-500">People, organizations, and places mentioned</p>
      </div>
      <div class="flex items-center gap-2">
        <USelect
          v-model="filterType"
          :items="[
            { label: 'All Types', value: 'all' },
            ...entityTypes.map(t => ({ label: entityTypeLabels[t] || t, value: t }))
          ]"
          size="sm"
        />
        <UButton
          variant="outline"
          size="sm"
          :loading="loading"
          @click="loadEntities"
        >
          Refresh
        </UButton>
      </div>
    </div>

    <UAlert
      v-if="error"
      color="warning"
      icon="i-heroicons-exclamation-triangle"
      :title="error"
      description="Entity extraction requires the Python analysis service to be running."
    />

    <div v-if="loading" class="text-center py-8">
      <UIcon name="i-heroicons-arrow-path" class="w-8 h-8 animate-spin mx-auto text-gray-400" />
      <p class="mt-2 text-gray-500">Extracting entities (this may take a moment)...</p>
    </div>

    <div v-else-if="filteredEntities.length === 0 && !error" class="text-center py-8 text-gray-500">
      <UIcon name="i-heroicons-user-group" class="w-12 h-12 mx-auto mb-4 opacity-50" />
      <p>No entities found</p>
    </div>

    <div v-else class="space-y-2">
      <!-- Summary by type -->
      <div class="flex gap-2 flex-wrap mb-4">
        <UBadge
          v-for="type in entityTypes"
          :key="type"
          :color="getTypeColor(type)"
          size="lg"
        >
          {{ entityTypeLabels[type] || type }}: {{ entities.filter(e => e.type === type).length }}
        </UBadge>
      </div>

      <!-- Entity list -->
      <div class="grid gap-2 md:grid-cols-2">
        <UCard
          v-for="entity in filteredEntities.slice(0, 50)"
          :key="entity.entity"
          class="hover:shadow-md transition-shadow"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <UBadge :color="getTypeColor(entity.type)" size="xs">
                {{ entity.type }}
              </UBadge>
              <span class="font-medium">{{ entity.entity }}</span>
            </div>
            <div class="text-right text-sm">
              <div class="font-semibold">{{ entity.count }}</div>
              <div class="text-gray-500 text-xs">{{ entity.percentage.toFixed(0) }}% of briefings</div>
            </div>
          </div>
        </UCard>
      </div>

      <p v-if="filteredEntities.length > 50" class="text-center text-gray-500 text-sm">
        Showing top 50 of {{ filteredEntities.length }} entities
      </p>
    </div>
  </div>
</template>
