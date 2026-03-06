<script setup lang="ts">
defineOgImageComponent({
  props: {
    title: String,
    description: String,
    date: String,
  },
})

const props = defineProps<{
  title?: string
  description?: string
  date?: string
}>()
</script>

<template>
  <div
    class="flex h-full w-full flex-col justify-center"
    :style="{
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      fontFamily: 'sans-serif',
      padding: '60px',
    }"
  >
    <div
      :style="{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        marginBottom: '24px',
      }"
    >
      <div
        :style="{
          fontSize: '20px',
          color: '#38bdf8',
          letterSpacing: '0.05em',
        }"
      >
        MentionsHero Blog
      </div>
      <div
        v-if="props.date"
        :style="{
          fontSize: '18px',
          color: '#64748b',
        }"
      >
        {{ props.date }}
      </div>
    </div>
    <div
      :style="{
        fontSize: '48px',
        fontWeight: 'bold',
        color: '#f1f5f9',
        lineHeight: '1.2',
        marginBottom: '20px',
      }"
    >
      {{ props.title || 'Blog Post' }}
    </div>
    <div
      v-if="props.description"
      :style="{
        fontSize: '22px',
        color: '#94a3b8',
        lineHeight: '1.4',
        maxWidth: '900px',
      }"
    >
      {{ props.description }}
    </div>
  </div>
</template>
