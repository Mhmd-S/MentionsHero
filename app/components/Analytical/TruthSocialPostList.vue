<script setup lang="ts">
import type { TruthSocialPost } from '~/composables/useAnalyticalProcurement'

withDefaults(
  defineProps<{ posts: TruthSocialPost[]; loading?: boolean }>(),
  { loading: false },
)

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function engagementSummary(e: TruthSocialPost['engagement']): string {
  if (!e) return ''
  const parts: string[] = []
  if (e.favourites) parts.push(`♥ ${e.favourites.toLocaleString()}`)
  if (e.reblogs) parts.push(`🔁 ${e.reblogs.toLocaleString()}`)
  if (e.replies) parts.push(`💬 ${e.replies.toLocaleString()}`)
  return parts.join('  ')
}
</script>

<template>
  <div>
    <div v-if="loading && posts.length === 0" class="py-6 flex justify-center">
      <UIcon name="i-lucide-loader" class="size-5 animate-spin" />
    </div>
    <div v-else-if="posts.length === 0" class="py-6 text-center text-sm text-gray-500">
      No posts in range yet.
    </div>
    <ul v-else class="divide-y divide-gray-100 dark:divide-gray-800">
      <li v-for="post in posts" :key="post.id" class="py-3">
        <div class="flex items-center gap-2 text-xs text-gray-500 mb-1">
          <span>{{ when(post.posted_at) }}</span>
          <UBadge v-if="post.is_retruth" color="warning" variant="subtle" size="xs">re-truth</UBadge>
          <span v-if="post.media_urls.length" class="text-gray-400">📎 {{ post.media_urls.length }}</span>
        </div>
        <p class="text-sm whitespace-pre-wrap break-words">{{ post.content || '(no text)' }}</p>
        <div class="flex items-center gap-3 mt-1 text-xs text-gray-500">
          <span v-if="engagementSummary(post.engagement)">{{ engagementSummary(post.engagement) }}</span>
          <a
            v-if="post.post_url"
            :href="post.post_url"
            target="_blank"
            rel="noopener"
            class="text-primary hover:underline"
          >
            View on Truth Social ↗
          </a>
        </div>
      </li>
    </ul>
  </div>
</template>
