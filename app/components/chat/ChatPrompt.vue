<script setup lang="ts">
const props = defineProps<{
  modelValue: string
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  submit: []
}>()

const textareaRef = ref<HTMLTextAreaElement>()

function resize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

function onInput(e: Event) {
  const value = (e.target as HTMLTextAreaElement).value
  emit('update:modelValue', value)
  resize()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (props.modelValue.trim()) {
      emit('submit')
    }
  }
}

watch(() => props.modelValue, () => {
  nextTick(resize)
})
</script>

<template>
  <div class="border border-default rounded-xl bg-default focus-within:ring-2 focus-within:ring-primary/50 transition-shadow">
    <textarea
      ref="textareaRef"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      rows="1"
      class="w-full resize-none bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted disabled:opacity-50 max-h-40 overflow-y-auto"
      @input="onInput"
      @keydown="onKeydown"
    />
    <div v-if="$slots.footer" class="px-3 pb-2">
      <slot name="footer" />
    </div>
  </div>
</template>
