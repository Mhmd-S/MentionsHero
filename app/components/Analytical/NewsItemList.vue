<script setup lang="ts">
import type { NewsItem } from '~/composables/useAnalyticalProcurement'

withDefaults(
  defineProps<{ items: NewsItem[]; loading?: boolean }>(),
  { loading: false },
)

function when(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}
</script>

<template>
  <div>
    <div v-if="loading && items.length === 0" class="py-6 flex justify-center">
      <UIcon name="i-lucide-loader" class="size-5 animate-spin" />
    </div>
    <div v-else-if="items.length === 0" class="py-6 text-center text-sm text-gray-500">
      No articles in range yet.
    </div>
    <ul v-else class="divide-y divide-gray-100 dark:divide-gray-800">
      <li v-for="item in items" :key="item.id" class="py-3">
        <div class="flex items-center gap-2 text-xs text-gray-500 mb-1">
          <UBadge v-if="item.source_name" color="error" variant="subtle" size="xs">{{ item.source_name }}</UBadge>
          <span>{{ when(item.published_at) }}</span>
        </div>
        <a
          :href="item.url"
          target="_blank"
          rel="noopener"
          class="text-sm font-medium text-primary hover:underline break-words"
        >
          {{ item.title }}
        </a>
        <p v-if="item.body" class="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-3">
          {{ item.body }}
        </p>
      </li>
    </ul>
  </div>
</template>
