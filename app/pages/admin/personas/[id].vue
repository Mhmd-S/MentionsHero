<script lang="ts">
definePageMeta({ layout: 'admin', ssr: false })
</script>

<script setup lang="ts">
import { usePersonas } from '~/composables/usePersonas'

const route = useRoute()
const personaId = route.params.id as string

const { getPersona } = usePersonas()
const { authFetch } = useAuthFetch()

const persona = ref<Awaited<ReturnType<typeof getPersona>>>(null)
const loadingPersona = ref(true)

// Persona transcripts
interface PersonaTranscript {
  id: string
  name: string | null
  youtube_url: string
  created_at: string
  upload_date?: string | null
  is_public?: boolean
  is_premium?: boolean
}

const personaTranscripts = ref<PersonaTranscript[]>([])
const loadingTranscripts = ref(false)

async function loadPersonaTranscripts() {
  loadingTranscripts.value = true
  try {
    personaTranscripts.value = await authFetch<PersonaTranscript[]>(`/api/personas/${personaId}/transcripts`)
  } catch (e) {
    console.error('Failed to load persona transcripts:', e)
  } finally {
    loadingTranscripts.value = false
  }
}

async function toggleTranscriptVisibility(item: PersonaTranscript, field: 'is_public' | 'is_premium', value: boolean) {
  if (field === 'is_premium' && value && !item.is_public) {
    // Turning on premium auto-enables public
    item.is_public = true
    item.is_premium = true
    await authFetch(`/api/transcripts/${item.id}`, {
      method: 'PATCH',
      body: { is_public: true, is_premium: true },
    }).catch(() => {})
  } else if (field === 'is_public' && !value) {
    // Turning off public also turns off premium
    item.is_public = false
    item.is_premium = false
    await authFetch(`/api/transcripts/${item.id}`, {
      method: 'PATCH',
      body: { is_public: false, is_premium: false },
    }).catch(() => {})
  } else {
    item[field] = value
    await authFetch(`/api/transcripts/${item.id}`, {
      method: 'PATCH',
      body: { [field]: value },
    }).catch(() => {})
  }
}

function formatTranscriptDate(dateString: string) {
  if (/^\d{8}$/.test(dateString)) {
    const d = new Date(`${dateString.slice(0, 4)}-${dateString.slice(4, 6)}-${dateString.slice(6)}`)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }
  return new Date(dateString).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

onMounted(async () => {
  loadingPersona.value = true
  try {
    persona.value = await getPersona(personaId)
  } finally {
    loadingPersona.value = false
  }
  await loadPersonaTranscripts()
})
</script>

<template>
  <div class="max-w-7xl w-full">
    <!-- Header with back button -->
    <div class="mb-6">
      <NuxtLink to="/admin/personas"
        class="inline-flex items-center gap-1 text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 transition-colors mb-4">
        <UIcon name="i-lucide-chevron-left" class="w-5 h-5" />
        <span class="text-base">Personas</span>
      </NuxtLink>

      <div v-if="loadingPersona" class="flex items-center justify-center p-8">
        <UIcon name="i-lucide-loader" class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="!persona" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        Persona not found.
      </div>

      <template v-else>
        <h1 class="text-3xl font-bold mb-1">{{ persona.name }}</h1>
        <p v-if="persona.description" class="text-gray-500 text-base">{{ persona.description }}</p>

        <!-- Aliases -->
        <div v-if="persona.aliases.length > 0" class="flex flex-wrap gap-1.5 mt-3">
          <UBadge v-for="alias in persona.aliases" :key="alias" color="neutral" variant="soft">
            {{ alias }}
          </UBadge>
        </div>
      </template>
    </div>

    <!-- Transcripts -->
    <template v-if="persona">
      <div class="flex items-center justify-between mb-3 mt-8">
        <h2 class="text-xl font-semibold">Transcripts</h2>
        <UBadge v-if="personaTranscripts.length > 0" color="neutral" variant="subtle">
          {{ personaTranscripts.length }}
        </UBadge>
      </div>

      <div v-if="loadingTranscripts" class="flex items-center justify-center p-4">
        <UIcon name="i-lucide-loader" class="w-5 h-5 animate-spin" />
      </div>

      <div v-else-if="personaTranscripts.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No transcripts found matching this persona's aliases.
      </div>

      <div v-else class="divide-y divide-gray-100 dark:divide-gray-800">
        <div
          v-for="t in personaTranscripts"
          :key="t.id"
          class="flex flex-wrap items-center gap-3 py-3"
        >
          <NuxtLink
            :to="`/admin/transcripts/${t.id}`"
            class="flex-1 min-w-0 hover:underline"
          >
            <p class="text-sm font-medium truncate">{{ t.name || 'Untitled' }}</p>
            <p class="text-xs text-gray-400 mt-0.5">{{ formatTranscriptDate(t.upload_date || t.created_at) }}</p>
          </NuxtLink>

          <div class="flex items-center gap-2 sm:gap-3 shrink-0">
            <USwitch
              :model-value="t.is_public ?? false"
              size="xs"
              label="Public"
              @update:model-value="toggleTranscriptVisibility(t, 'is_public', $event)"
            />
            <USwitch
              :model-value="t.is_premium ?? false"
              size="xs"
              label="Premium"
              @update:model-value="toggleTranscriptVisibility(t, 'is_premium', $event)"
            />
          </div>
        </div>
      </div>
    </template>

  </div>
</template>
