<template>
  <div>
    <div class="mb-8">
      <h1 class="text-2xl font-bold">All Transcripts</h1>
      <p class="text-gray-500 mt-1">Browse your previously generated transcripts</p>
    </div>

    <div v-if="pending" class="flex justify-center py-8">
      <UIcon name="i-heroicons-arrow-path" class="size-6 animate-spin" />
    </div>

    <div v-else-if="error" class="py-8">
      <UAlert color="error" :title="error.message" />
    </div>

    <div v-else-if="!transcripts?.length" class="py-8 text-center text-gray-500">
      <UIcon name="i-heroicons-document-text" class="size-12 mx-auto mb-4 opacity-50" />
      <p>No transcripts yet</p>
      <UButton to="/" variant="link" class="mt-2">Create your first transcript</UButton>
    </div>

    <div v-else class="space-y-4">
      <UCard
        v-for="item in transcripts"
        :key="item.id"
        class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer"
        @click="navigateTo(`/transcripts/${item.id}`)"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-500 truncate mb-1">{{ item.youtube_url }}</p>
            <p class="text-sm line-clamp-2">{{ item.transcript }}</p>
          </div>
          <div class="text-xs text-gray-400 whitespace-nowrap">
            {{ formatDate(item.created_at) }}
          </div>
        </div>
      </UCard>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Transcript {
  id: string
  youtube_url: string
  transcript: string
  created_at: string
}

const { data: transcripts, pending, error } = await useFetch<Transcript[]>('/api/transcripts')

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}
</script>
