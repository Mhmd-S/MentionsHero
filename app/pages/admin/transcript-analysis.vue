<script lang="ts">
definePageMeta({ layout: 'admin', ssr: false })
</script>

<script setup lang="ts">
import { marked } from 'marked'

marked.setOptions({ breaks: true })

function renderMarkdown(text: string): string {
  return marked.parse(text, { async: false }) as string
}

const {
  conversations,
  currentConversation,
  messages,
  status,
  error,
  loading,
  sidebarLoading,
  deletingId,
  fetchConversations,
  createConversation,
  loadConversation,
  deleteConversation,
  sendMessage,
  stop,
  regenerate,
} = useChat()

const input = ref('')
const showSidebar = ref(true)

const toolLabels: Record<string, string> = {
  search_term: 'Searching terms',
  search_term_in_context: 'Searching context',
  get_top_terms: 'Analyzing top terms',
  get_ngrams: 'N-gram analysis',
  list_speakers: 'Loading speakers',
  list_personas: 'Loading personas',
  get_persona: 'Loading persona',
  search_personas: 'Searching personas',
  browse_kalshi_events: 'Browsing Kalshi',
  get_kalshi_event: 'Loading Kalshi event',
  search_polymarket: 'Searching Polymarket',
  get_polymarket_event: 'Loading Polymarket event',
  list_folders: 'Loading folders',
  search_folders: 'Searching folders',
  list_transcripts: 'Loading transcripts',
  get_transcript_content: 'Reading transcript',
}

function getToolLabel(part: any): string {
  return toolLabels[part.toolName] || part.toolName || 'Working...'
}

function isToolStreaming(part: any): boolean {
  return part.state === 'call'
}

const chatExamples = [
  { text: 'What are the top terms this week?', icon: 'i-lucide-trending-up' },
  { text: 'How often is "tariff" mentioned?', icon: 'i-lucide-search' },
  { text: 'Show me open Kalshi mention events', icon: 'i-lucide-bar-chart-2' },
  { text: 'Summarize the latest press briefing', icon: 'i-lucide-file-text' },
]

async function handleSubmit() {
  const content = input.value.trim()
  if (!content) return

  if (!currentConversation.value) {
    const conv = await createConversation()
    if (!conv) return
    input.value = ''
    await sendMessage(conv.id, content)
  } else {
    input.value = ''
    await sendMessage(currentConversation.value.id, content)
  }
}

async function handleExampleClick(q: string) {
  input.value = q
  await handleSubmit()
}

async function handleSelectConversation(id: string) {
  if (currentConversation.value?.id === id) return
  await loadConversation(id)
}

async function handleDeleteConversation(id: string, e: Event) {
  e.stopPropagation()
  await deleteConversation(id)
}

async function handleNewConversation() {
  await createConversation()
}

function copyMessage(text: string) {
  navigator.clipboard.writeText(text)
}

function getAssistantActions(msg: any) {
  if (msg.role !== 'assistant') return undefined
  const textContent = msg._content || msg.parts?.find((p: any) => p.type === 'text')?.text
  if (!textContent) return undefined
  return [
    {
      label: 'Copy',
      icon: 'i-lucide-copy',
      onClick: () => copyMessage(textContent),
    },
  ]
}

onMounted(() => {
  if (!conversations.value.length) {
    fetchConversations()
  }
})
</script>

<template>
  <div class="flex h-svh overflow-hidden">
    <!-- Conversation sidebar -->
    <Transition name="sidebar">
      <div v-if="showSidebar" class="w-64 border-r border-default flex flex-col shrink-0 bg-default">
        <div class="p-3 border-b border-default flex items-center justify-between">
          <h2 class="text-sm font-semibold text-default">Chats</h2>
          <UButton
            icon="i-lucide-plus"
            size="xs"
            variant="ghost"
            color="neutral"
            @click="handleNewConversation"
          />
        </div>

        <div class="flex-1 overflow-y-auto">
          <!-- Sidebar loading skeleton -->
          <template v-if="sidebarLoading">
            <div v-for="i in 5" :key="i" class="flex items-center gap-2 px-3 py-2.5">
              <div class="size-4 rounded bg-muted/30 animate-pulse shrink-0" />
              <div class="h-3.5 rounded bg-muted/30 animate-pulse flex-1" :style="{ width: `${50 + Math.random() * 40}%` }" />
            </div>
          </template>

          <!-- Conversation list -->
          <template v-else>
            <div
              v-for="conv in conversations"
              :key="conv.id"
              class="group flex items-center gap-2 px-3 py-2 text-sm cursor-pointer transition-colors"
              :class="[
                currentConversation?.id === conv.id
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-muted hover:text-default hover:bg-elevated'
              ]"
              @click="handleSelectConversation(conv.id)"
            >
              <UIcon name="i-lucide-message-square" class="size-4 shrink-0 opacity-60" />
              <span class="truncate flex-1">
                {{ conv.title || 'New conversation' }}
              </span>
              <UButton
                v-if="deletingId !== conv.id"
                icon="i-lucide-trash-2"
                size="xs"
                variant="ghost"
                color="error"
                class="opacity-0 group-hover:opacity-100 shrink-0"
                @click="handleDeleteConversation(conv.id, $event)"
              />
              <UIcon
                v-else
                name="i-lucide-loader-circle"
                class="size-3.5 animate-spin text-muted shrink-0"
              />
            </div>

            <div v-if="!conversations.length" class="px-3 py-8 text-center">
              <UIcon name="i-lucide-message-square-dashed" class="size-8 text-muted/40 mx-auto mb-2" />
              <p class="text-xs text-muted">No conversations yet</p>
            </div>
          </template>
        </div>
      </div>
    </Transition>

    <!-- Main chat area -->
    <div class="flex-1 flex flex-col min-w-0 min-h-">
      <!-- Header -->
      <div class="flex items-center gap-2 px-4 h-12 border-b border-default shrink-0">
        <UButton
          :icon="showSidebar ? 'i-lucide-panel-left-close' : 'i-lucide-panel-left-open'"
          size="xs"
          variant="ghost"
          color="neutral"
          @click="showSidebar = !showSidebar"
        />
        <h1 class="text-sm font-semibold truncate text-default">
          {{ currentConversation?.title || 'AI Chat' }}
        </h1>
        <UBadge
          v-if="status === 'streaming'"
          variant="subtle"
          color="primary"
          size="xs"
        >
          Responding...
        </UBadge>
      </div>

      <!-- Loading state -->
      <div v-if="loading" class="flex-1 flex items-center justify-center">
        <div class="flex flex-col items-center gap-3">
          <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-primary" />
          <span class="text-xs text-muted">Loading messages...</span>
        </div>
      </div>

      <!-- Empty state (no conversation selected or conversation has no messages) -->
      <div
        v-else-if="!currentConversation || !messages.length"
        class="flex-1 flex flex-col items-center justify-center px-4"
      >
        <div class="flex flex-col items-center max-w-lg">
          <div class="size-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-5">
            <UIcon name="i-lucide-bot" class="size-8 text-primary" />
          </div>
          <h2 class="text-lg font-semibold mb-1 text-default">AI Transcript Assistant</h2>
          <p class="text-sm text-muted text-center mb-6">
            Analyze press briefing transcripts, search term frequency, and explore prediction markets.
          </p>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full">
            <button
              v-for="q in chatExamples"
              :key="q.text"
              class="flex items-center gap-3 px-4 py-3 rounded-lg border border-default text-sm text-left hover:bg-elevated transition-colors group"
              @click="handleExampleClick(q.text)"
            >
              <UIcon :name="q.icon" class="size-4 text-muted group-hover:text-primary shrink-0 transition-colors" />
              <span class="text-muted group-hover:text-default transition-colors">{{ q.text }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Chat messages -->
      <ChatMessages
        v-else
        :messages="messages"
        :status="status"
        class="flex-1 min-h-0 px-4 py-4"
      >
        <template #content="{ message }">
          <template v-for="(part, index) in message.parts" :key="`${message.id}-${part.toolInvocationId || index}`">
            <div
              v-if="part.type === 'tool-invocation'"
              class="flex items-center gap-2 text-xs py-1 my-0.5"
              :class="isToolStreaming(part) ? 'text-primary' : 'text-muted'"
            >
              <UIcon
                v-if="isToolStreaming(part)"
                name="i-lucide-loader-circle"
                class="size-3.5 animate-spin"
              />
              <UIcon v-else name="i-lucide-check-circle-2" class="size-3.5 text-success" />
              <span>{{ getToolLabel(part) }}</span>
            </div>

            <div
              v-else-if="part.type === 'text' && part.text"
              class="prose prose-sm dark:prose-invert max-w-none wrap-break-word [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
              v-html="renderMarkdown(part.text)"
            />
          </template>
        </template>
      </ChatMessages>

      <!-- Error bar -->
      <div
        v-if="error"
        class="mx-4 mb-2 px-3 py-2 rounded-lg bg-error/10 text-error text-xs flex items-center gap-2"
      >
        <UIcon name="i-lucide-alert-circle" class="size-4 shrink-0" />
        <span class="flex-1">{{ error }}</span>
        <UButton
          icon="i-lucide-x"
          size="xs"
          variant="ghost"
          color="error"
          @click="error = null"
        />
      </div>

      <!-- Chat prompt -->
      <div class="px-4 pb-4 pt-2">
        <ChatPrompt
          v-model="input"
          placeholder="Ask about transcripts, terms, markets..."
          :disabled="loading"
          @submit="handleSubmit"
        >
          <template #footer>
            <div class="flex items-center justify-between w-full">
              <span class="text-[10px] text-muted">
                Press Enter to send
              </span>
              <ChatPromptActions :status="status" @stop="stop()" @reload="regenerate()" />
            </div>
          </template>
        </ChatPrompt>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sidebar-enter-active,
.sidebar-leave-active {
  transition: width 200ms ease, opacity 200ms ease;
  overflow: hidden;
}
.sidebar-enter-from,
.sidebar-leave-to {
  width: 0;
  opacity: 0;
}
</style>
