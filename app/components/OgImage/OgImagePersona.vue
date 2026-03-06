<script setup lang="ts">
defineOgImageComponent({
  props: {
    name: String,
    description: String,
    imageUrl: String,
  },
})

const props = defineProps<{
  name?: string
  description?: string
  imageUrl?: string
}>()
</script>

<template>
  <div
    class="flex h-full w-full items-center"
    :style="{
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      fontFamily: 'sans-serif',
      padding: '60px',
      gap: '48px',
    }"
  >
    <img
      v-if="props.imageUrl"
      :src="props.imageUrl"
      :style="{
        width: '200px',
        height: '200px',
        borderRadius: '50%',
        objectFit: 'cover',
        border: '4px solid #38bdf8',
      }"
    >
    <div :style="{ flex: '1' }">
      <div
        :style="{
          fontSize: '20px',
          color: '#38bdf8',
          marginBottom: '12px',
          letterSpacing: '0.05em',
        }"
      >
        MentionsHero
      </div>
      <div
        :style="{
          fontSize: '52px',
          fontWeight: 'bold',
          color: '#f1f5f9',
          lineHeight: '1.1',
          marginBottom: '16px',
        }"
      >
        {{ props.name || 'Persona' }}
      </div>
      <div
        v-if="props.description"
        :style="{
          fontSize: '22px',
          color: '#94a3b8',
          lineHeight: '1.4',
          display: '-webkit-box',
          webkitLineClamp: 2,
          webkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }"
      >
        {{ props.description }}
      </div>
    </div>
  </div>
</template>
