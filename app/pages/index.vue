<script setup lang="ts">
const { publicFetch } = usePublicApi()

interface Persona {
  id: string
  name: string
  description: string | null
  slug: string | null
  image_url: string | null
  aliases: string[]
}

const personas = ref<Persona[]>([])
const loading = ref(true)
const search = ref('')

const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  if (!q) return personas.value
  return personas.value.filter(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      (p.description || '').toLowerCase().includes(q)
  )
})

onMounted(async () => {
  try {
    personas.value = await publicFetch<Persona[]>('/api/public/personas')
  } catch (err) {
    console.error('Failed to load personas:', err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div class="mb-8">
      <h1 class="text-3xl font-bold mb-2">Personas</h1>
      <p class="text-gray-600 dark:text-gray-400">
        Browse transcripts by speaker
      </p>
    </div>

    <UInput
      v-model="search"
      icon="i-heroicons-magnifying-glass"
      placeholder="Search personas..."
      class="mb-6 max-w-md"
    />

    <div v-if="loading" class="flex justify-center py-12">
      <UIcon name="i-heroicons-arrow-path" class="size-6 animate-spin" />
    </div>

    <div v-else-if="filtered.length === 0" class="py-12 text-center text-gray-500">
      <UIcon name="i-heroicons-user-group" class="size-12 mx-auto mb-4 opacity-50" />
      <p>{{ search ? `No personas matching "${search}"` : 'No personas available' }}</p>
    </div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <NuxtLink
        v-for="persona in filtered"
        :key="persona.id"
        :to="`/personas/${persona.slug || persona.id}`"
        class="block p-5 border rounded-lg hover:border-primary-500 hover:shadow-sm transition-all"
      >
        <div class="flex items-start gap-4">
          <div
            v-if="persona.image_url"
            class="w-14 h-14 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden flex-shrink-0"
          >
            <img :src="persona.image_url" :alt="persona.name" class="w-full h-full object-cover" />
          </div>
          <div
            v-else
            class="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0"
          >
            <span class="text-xl font-bold text-primary">{{ persona.name[0] }}</span>
          </div>

          <div class="flex-1 min-w-0">
            <h3 class="font-semibold text-lg truncate">{{ persona.name }}</h3>
            <p v-if="persona.description" class="text-sm text-gray-500 mt-1 line-clamp-2">
              {{ persona.description }}
            </p>
          </div>
        </div>
      </NuxtLink>
    </div>
  </div>
</template>
