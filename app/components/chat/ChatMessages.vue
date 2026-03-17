<script setup lang="ts">
import type { ChatMessage, ChatStatus } from '~/composables/useChat'

const props = defineProps<{
  messages: ChatMessage[]
  status: ChatStatus
}>()

defineSlots<{
  content(props: { message: ChatMessage }): any
}>()

const scrollEl = ref<HTMLElement>()

function isNearBottom(): boolean {
  const el = scrollEl.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 100
}

function scrollToBottom() {
  const el = scrollEl.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

const shouldAutoScroll = ref(true)

function onScroll() {
  shouldAutoScroll.value = isNearBottom()
}

watch(
  () => {
    const last = props.messages[props.messages.length - 1]
    return [props.messages.length, last?.parts?.length, last?.parts?.[last.parts.length - 1]?.text?.length]
  },
  () => {
    if (shouldAutoScroll.value) {
      nextTick(scrollToBottom)
    }
  },
)

const isTyping = computed(() => {
  if (props.status !== 'submitted' && props.status !== 'streaming') return false
  const last = props.messages[props.messages.length - 1]
  if (!last || last.role !== 'assistant') return false
  return !last.parts.length || last.parts.every(p => p.type === 'tool-invocation')
})

function getUserText(message: ChatMessage): string {
  return message.parts.filter(p => p.type === 'text').map(p => p.text).join('') || message._content || ''
}
</script>

<template>
  <div ref="scrollEl" class="overflow-y-auto flex-1 min-h-0" @scroll="onScroll">
    <div class="space-y-4">
      <div
        v-for="message in messages"
        :key="message.id"
        :class="message.role === 'user' ? 'flex justify-end' : 'flex justify-start'"
      >
        <!-- Assistant message -->
        <div v-if="message.role === 'assistant'" class="flex gap-3 max-w-[80%]">
          <div class="size-7 rounded-full bg-muted/20 flex items-center justify-center shrink-0 mt-0.5">
            <UIcon name="i-lucide-bot" class="size-4 text-muted" />
          </div>
          <div class="min-w-0 flex-1">
            <slot name="content" :message="message" />
          </div>
        </div>

        <!-- User message -->
        <div v-else class="max-w-[80%] bg-primary/10 rounded-2xl px-4 py-2.5">
          <p class="text-sm">{{ getUserText(message) }}</p>
        </div>
      </div>

      <!-- Typing indicator -->
      <div v-if="isTyping" class="flex gap-3">
        <div class="size-7 rounded-full bg-muted/20 flex items-center justify-center shrink-0">
          <UIcon name="i-lucide-bot" class="size-4 text-muted" />
        </div>
        <div class="flex items-center gap-1 py-2">
          <span
            v-for="i in 3"
            :key="i"
            class="size-1.5 bg-muted rounded-full animate-bounce"
            :style="{ animationDelay: `${i * 150}ms` }"
          />
        </div>
      </div>
    </div>
  </div>
</template>
