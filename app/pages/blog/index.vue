<script setup lang="ts">
const { data: posts } = await useAsyncData('blog-list', () =>
  queryCollection('blog').order('date', 'DESC').all()
)

useSeoMeta({
  title: 'Blog',
  description: 'Guides, analysis, and insights on press briefing transcripts, prediction markets, and public figure mentions.',
  ogTitle: 'Blog | MentionsHero',
  ogDescription: 'Guides, analysis, and insights on press briefing transcripts and prediction markets.',
  twitterCard: 'summary_large_image',
  twitterTitle: 'Blog | MentionsHero',
  twitterDescription: 'Guides, analysis, and insights on press briefing transcripts and prediction markets.',
})

defineOgImage({ component: 'OgImageDefault', alt: 'MentionsHero Blog — transcripts and prediction markets' })

useSchemaOrg([
  defineBreadcrumb({
    itemListElement: [
      { name: 'Home', item: '/' },
      { name: 'Blog' },
    ],
  }),
])
</script>

<template>
  <div>
    <UPageHeader title="Blog">
      <template #description>
        <span class="text-sm text-muted">Guides, analysis, and insights on transcripts and prediction markets</span>
      </template>
    </UPageHeader>

    <div v-if="!posts?.length" class="py-16 text-center text-muted">
      <UIcon name="i-lucide-notebook-pen" class="size-12 mx-auto mb-4 opacity-40" />
      <p class="text-sm">No posts yet. Check back soon!</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
      <NuxtLink v-for="post in posts" :key="post.path" :to="post.path">
        <UCard class="h-full hover:ring-primary/50 hover:ring-1 transition-all">
          <div class="space-y-2">
            <div class="flex items-center gap-2 flex-wrap">
              <UBadge v-for="tag in (post.tags || [])" :key="tag" variant="subtle" size="xs">
                {{ tag }}
              </UBadge>
            </div>
            <h2 class="text-lg font-semibold">{{ post.title }}</h2>
            <p class="text-sm text-muted line-clamp-2">{{ post.description }}</p>
            <p class="text-xs text-muted">{{ new Date(post.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) }}</p>
          </div>
        </UCard>
      </NuxtLink>
    </div>
  </div>
</template>
