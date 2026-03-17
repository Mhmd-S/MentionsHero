<script setup lang="ts">
import type { ChatStatus } from '~/composables/useChat'

defineProps<{
  status: ChatStatus
}>()

defineEmits<{
  stop: []
  reload: []
}>()
</script>

<template>
  <UButton
    v-if="status === 'streaming' || status === 'submitted'"
    icon="i-lucide-square"
    size="xs"
    variant="ghost"
    color="error"
    @click="$emit('stop')"
  />
  <UButton
    v-else-if="status === 'error'"
    icon="i-lucide-refresh-cw"
    size="xs"
    variant="ghost"
    color="neutral"
    @click="$emit('reload')"
  />
  <UButton
    v-else
    icon="i-lucide-arrow-up"
    size="xs"
    variant="soft"
    color="primary"
  />
</template>
