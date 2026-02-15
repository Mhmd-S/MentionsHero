<script setup lang="ts">
const route = useRoute()

onMounted(() => {
  const id = route.params.id as string
  navigateTo({ path: '/model', query: { persona: id } }, { replace: true })
})
</script>

<template>
  <div class="flex items-center justify-center p-12">
    <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
  </div>
</template>
