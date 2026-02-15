<script setup lang="ts">
import { usePersonas } from '~/composables/usePersonas'

const route = useRoute()
const router = useRouter()
const { personas, loading, fetchPersonas } = usePersonas()

const personaOptions = computed(() =>
  personas.value.map(p => ({ label: p.name, value: p.id }))
)

const selectedPersonaId = ref<string | undefined>(undefined)

function setPersonaFromQuery() {
  const id = route.query.persona as string | undefined
  if (id && personas.value.some(p => p.id === id)) {
    selectedPersonaId.value = id
  } else if (personas.value.length > 0 && !selectedPersonaId.value) {
    selectedPersonaId.value = personas.value[0].id
  }
}

watch([() => route.query.persona, personas], setPersonaFromQuery, { immediate: true })

watch(selectedPersonaId, (id) => {
  if (id && route.query.persona !== id) {
    router.replace({ query: { ...route.query, persona: id } })
  }
})

onMounted(() => {
  fetchPersonas()
})
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <h1 class="text-3xl font-bold mb-2">ML Model</h1>
    <p class="text-gray-500 text-base mb-6">
      Train and test LoRA models per persona. In local dev, training runs in the terminal.
    </p>

    <div v-if="loading" class="flex items-center justify-center p-12">
      <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
    </div>

    <div v-else-if="personas.length === 0" class="text-gray-500 text-base p-6 border border-dashed rounded-lg">
      No personas yet. Create a persona first, then come here to train a model.
    </div>

    <template v-else>
      <div class="mb-6">
        <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">Persona</label>
        <USelectMenu
          v-model="selectedPersonaId"
          :items="personaOptions"
          value-key="value"
          placeholder="Select a persona"
          class="w-full max-w-xs"
        />
      </div>

      <ModelTrainingPanel v-if="selectedPersonaId" :persona-id="selectedPersonaId" />
    </template>
  </div>
</template>
