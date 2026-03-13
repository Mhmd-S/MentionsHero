<script lang="ts">
definePageMeta({ layout: 'admin' })
</script>

<script setup lang="ts">
const {
  conversations,
  currentConversation,
  messages,
  status,
  error,
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

const chatExamples = [
  'What are the top terms this week?',
  'How often is "tariff" mentioned?',
  'Show me open Kalshi mention events',
]

const toolLabels: Record<string, string> = {
  search_term: 'Term Frequency',
  search_term_in_context: 'Context Search',
  get_top_terms: 'Top Terms',
  get_ngrams: 'N-gram Analysis',
  list_speakers: 'Speakers',
  list_personas: 'Personas',
  get_persona: 'Persona Detail',
  browse_kalshi_events: 'Kalshi Events',
  get_kalshi_event: 'Kalshi Event',
  search_polymarket: 'Polymarket Search',
  get_polymarket_event: 'Polymarket Event',
  list_folders: 'Folders',
}

function getToolLabel(part: any): string {
  return toolLabels[part.toolName] || part.toolName || 'Tool'
}

function isToolStreaming(part: any): boolean {
  return part.state === 'call'
}

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

onMounted(() => {
  fetchConversations()
})
</script>

<template>
  <div class="flex h-full">
    <!-- Conversation sidebar -->
    <div
      v-if="showSidebar"
      class="w-64 border-r border-default flex flex-col shrink-0"
    >
      <div class="p-3 border-b border-default flex items-center justify-between">
        <h2 class="text-sm font-semibold">Conversations</h2>
        <UButton
          icon="i-lucide-plus"
          size="xs"
          variant="ghost"
          @click="createConversation()"
        />
      </div>
      <div class="flex-1 overflow-y-auto">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="group flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-elevated transition-colors"
          :class="currentConversation?.id === conv.id ? 'bg-elevated' : ''"
          @click="handleSelectConversation(conv.id)"
        >
          <UIcon name="i-lucide-message-square" class="size-4 text-muted shrink-0" />
          <span class="truncate flex-1">
            {{ conv.title || 'New conversation' }}
          </span>
          <UButton
            icon="i-lucide-trash-2"
            size="xs"
            variant="ghost"
            color="error"
            class="opacity-0 group-hover:opacity-100 shrink-0"
            @click="handleDeleteConversation(conv.id, $event)"
          />
        </div>
        <div
          v-if="!conversations.length"
          class="px-3 py-6 text-center text-sm text-muted"
        >
          No conversations yet
        </div>
      </div>
    </div>

    <!-- Main chat area -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Header -->
      <div class="flex items-center gap-2 px-4 py-3 border-b border-default">
        <UButton
          :icon="showSidebar ? 'i-lucide-panel-left-close' : 'i-lucide-panel-left-open'"
          size="xs"
          variant="ghost"
          @click="showSidebar = !showSidebar"
        />
        <h1 class="text-lg font-semibold truncate">
          {{ currentConversation?.title || 'AI Chat' }}
        </h1>
      </div>

      <!-- Chat messages -->
      <UChatMessages :status="status" class="flex-1">
        <!-- Empty state -->
        <div
          v-if="!messages.length"
          class="flex flex-col items-center justify-center h-full text-center"
        >
          <UIcon name="i-lucide-bot" class="size-12 text-muted mb-4" />
          <h2 class="text-lg font-semibold mb-2">AI Transcript Assistant</h2>
          <p class="text-sm text-muted max-w-md">
            Ask questions about press briefing transcripts, term frequency, market data, and more.
          </p>
          <div class="flex flex-wrap gap-2 mt-4 justify-center">
            <UButton
              v-for="q in chatExamples"
              :key="q"
              variant="outline"
              size="sm"
              @click="handleExampleClick(q)"
            >
              {{ q }}
            </UButton>
          </div>
        </div>

        <!-- Messages -->
        <UChatMessage
          v-for="msg in messages"
          :key="msg.id"
          :id="msg.id"
          :role="msg.role"
          :parts="msg.parts"
          :variant="msg.role === 'user' ? 'soft' : 'naked'"
          :side="msg.role === 'user' ? 'right' : 'left'"
        >
          <template #content>
            <template
              v-for="(part, index) in msg.parts"
              :key="`${msg.id}-${part.type}-${index}`"
            >
              <UChatTool
                v-if="part.type === 'tool-invocation'"
                :text="getToolLabel(part)"
                :streaming="isToolStreaming(part)"
                icon="i-lucide-wrench"
              >
                <div v-if="part.result" class="text-xs">
                  <pre class="overflow-x-auto whitespace-pre-wrap max-h-48 overflow-y-auto">{{ JSON.stringify(part.result, null, 2) }}</pre>
                </div>
              </UChatTool>

              <div
                v-else-if="part.type === 'text' && part.text"
                class="text-sm whitespace-pre-wrap break-words"
              >
                {{ part.text }}
              </div>
            </template>
          </template>
        </UChatMessage>
      </UChatMessages>

      <!-- Error bar -->
      <div v-if="error" class="px-4 py-2 bg-error/10 text-error text-sm flex items-center gap-2">
        <UIcon name="i-lucide-alert-circle" class="size-4" />
        {{ error }}
      </div>

      <!-- Chat prompt -->
      <UChatPrompt
        v-model="input"
        placeholder="Ask about transcripts, terms, markets..."
        :error="error ? new Error(error) : undefined"
        @submit="handleSubmit"
      >
        <UChatPromptSubmit
          :status="status"
          @stop="stop()"
          @reload="regenerate()"
        />
      </UChatPrompt>
    </div>
  </div>
</template>
