interface ToolCallData {
  id: string
  name: string
  args: Record<string, any>
  result?: any
}

export interface MessagePart {
  type: 'text' | 'tool-invocation'
  // Text parts
  text?: string
  // Tool parts
  toolInvocationId?: string
  toolName?: string
  state?: 'call' | 'result'
  args?: Record<string, any>
  result?: any
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  parts: MessagePart[]
  // Raw data for DB persistence
  _content?: string | null
  _toolCalls?: ToolCallData[]
  created_at: string
}

interface Conversation {
  id: string
  title: string | null
  created_at: string
  updated_at: string
  messages?: any[]
}

export type ChatStatus = 'ready' | 'streaming' | 'submitted' | 'error'

/** Convert DB message format to parts-based format for Nuxt UI */
function dbMessageToParts(msg: any): ChatMessage {
  const parts: MessagePart[] = []

  // Add tool call parts first
  if (msg.tool_calls?.length) {
    for (const tc of msg.tool_calls) {
      parts.push({
        type: 'tool-invocation',
        toolInvocationId: tc.id,
        toolName: tc.name,
        state: tc.result ? 'result' : 'call',
        args: tc.args,
        result: tc.result,
      })
    }
  }

  // Add text part
  if (msg.content) {
    parts.push({ type: 'text', text: msg.content })
  }

  return {
    id: msg.id,
    role: msg.role,
    parts,
    _content: msg.content,
    _toolCalls: msg.tool_calls,
    created_at: msg.created_at,
  }
}

export function useChat() {
  const { authFetch } = useAuthFetch()
  const supabase = useSupabaseClient()

  // SSE streams bypass Nuxt proxy to avoid body timeout (UND_ERR_BODY_TIMEOUT)
  const { backendUrl: backendBase } = useRuntimeConfig().public

  const conversations = useState<Conversation[]>('chat-conversations', () => [])
  const currentConversation = useState<Conversation | null>('chat-current', () => null)
  const messages = useState<ChatMessage[]>('chat-messages', () => [])
  const status = useState<ChatStatus>('chat-status', () => 'ready')
  const error = useState<string | null>('chat-error', () => null)
  const loading = useState<boolean>('chat-loading', () => false)
  const sidebarLoading = useState<boolean>('chat-sidebar-loading', () => false)
  const deletingId = useState<string | null>('chat-deleting-id', () => null)

  // AbortController for the active SSE stream
  let activeAbort: AbortController | null = null
  // Track which conversation the active stream belongs to
  let activeConversationId: string | null = null

  async function getToken(forceRefresh = false): Promise<string | null> {
    if (forceRefresh) {
      const { data } = await supabase.auth.refreshSession()
      return data.session?.access_token ?? null
    }
    const { data } = await supabase.auth.getSession()
    return data.session?.access_token ?? null
  }

  async function fetchConversations() {
    sidebarLoading.value = true
    try {
      conversations.value = await authFetch<Conversation[]>('/api/chat/conversations')
    } catch (e: any) {
      error.value = e?.message || 'Failed to load conversations'
    } finally {
      sidebarLoading.value = false
    }
  }

  async function createConversation(title?: string): Promise<Conversation | null> {
    abortStream()
    loading.value = true
    error.value = null
    messages.value = []
    currentConversation.value = null
    try {
      const conv = await authFetch<Conversation>('/api/chat/conversations', {
        method: 'POST',
        body: { title: title || null },
      })
      conversations.value.unshift(conv)
      currentConversation.value = conv
      return conv
    } catch (e: any) {
      error.value = e?.message || 'Failed to create conversation'
      return null
    } finally {
      loading.value = false
    }
  }

  /** Abort any in-flight SSE stream and reset status. */
  function abortStream() {
    if (activeAbort) {
      activeAbort.abort()
      activeAbort = null
    }
    activeConversationId = null
    if (status.value === 'streaming' || status.value === 'submitted') {
      status.value = 'ready'
    }
  }

  async function loadConversation(id: string) {
    // Abort any active stream before switching
    abortStream()
    error.value = null

    // Preserve title from sidebar list for instant display
    const existing = conversations.value.find((c) => c.id === id)
    currentConversation.value = existing
      ? { ...existing }
      : { id, title: null, created_at: '', updated_at: '' }
    messages.value = []
    loading.value = true

    try {
      const data = await authFetch<Conversation & { messages: any[] }>(
        `/api/chat/conversations/${id}`
      )
      // Guard: user may have switched again while we were fetching
      if (currentConversation.value?.id !== id) return
      currentConversation.value = data
      messages.value = (data.messages || []).map(dbMessageToParts)
    } catch (e: any) {
      if (currentConversation.value?.id !== id) return
      error.value = e?.message || 'Failed to load conversation'
    } finally {
      if (currentConversation.value?.id === id) {
        loading.value = false
      }
    }
  }

  async function deleteConversation(id: string) {
    deletingId.value = id
    try {
      await authFetch(`/api/chat/conversations/${id}`, { method: 'DELETE' })
      conversations.value = conversations.value.filter((c) => c.id !== id)
      if (currentConversation.value?.id === id) {
        abortStream()
        currentConversation.value = null
        messages.value = []
        error.value = null
      }
    } catch (e: any) {
      error.value = e?.message || 'Failed to delete conversation'
    } finally {
      deletingId.value = null
    }
  }

  async function updateTitle(id: string, title: string) {
    try {
      await authFetch(`/api/chat/conversations/${id}`, {
        method: 'PATCH',
        body: { title },
      })
      const conv = conversations.value.find((c) => c.id === id)
      if (conv) conv.title = title
      if (currentConversation.value?.id === id) {
        currentConversation.value = { ...currentConversation.value, title }
      }
    } catch {
      // Non-critical
    }
  }

  async function sendMessage(conversationId: string, content: string) {
    if (status.value === 'streaming' || status.value === 'submitted') return
    error.value = null
    status.value = 'submitted'

    // Add user message optimistically
    const userMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      parts: [{ type: 'text', text: content }],
      _content: content,
      created_at: new Date().toISOString(),
    }
    messages.value = [...messages.value, userMsg]

    // Create placeholder assistant message
    const assistantMsg: ChatMessage = {
      id: `temp-assistant-${Date.now()}`,
      role: 'assistant',
      parts: [],
      _content: '',
      _toolCalls: [],
      created_at: new Date().toISOString(),
    }
    messages.value = [...messages.value, assistantMsg]

    // Abort any previous stream
    abortStream()
    const abort = new AbortController()
    activeAbort = abort
    activeConversationId = conversationId

    try {
      let token = await getToken()
      let response = await fetch(`${backendBase}/api/chat/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ content }),
        signal: abort.signal,
      })

      // Retry once with refreshed token on 401
      if (response.status === 401) {
        token = await getToken(true)
        if (token) {
          response = await fetch(`${backendBase}/api/chat/conversations/${conversationId}/messages`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ content }),
            signal: abort.signal,
          })
        }
      }

      if (!response.ok) {
        const body = await response.text()
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      status.value = 'streaming'
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // Guard: if conversation changed while streaming, stop processing
        if (activeConversationId !== conversationId) {
          reader.cancel()
          break
        }

        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6)
            try {
              const data = JSON.parse(dataStr)
              handleSSEEvent(eventType, data, assistantMsg)
            } catch {
              // malformed SSE data, skip
            }
          }
        }
      }

      // Only update title/status if this stream wasn't superseded
      if (activeConversationId === conversationId) {
        // Auto-generate title for new conversations
        if (currentConversation.value && !currentConversation.value.title && assistantMsg._content) {
          const autoTitle = content.length > 50 ? content.slice(0, 50) + '...' : content
          updateTitle(conversationId, autoTitle)
        }
        status.value = 'ready'
        activeAbort = null
        activeConversationId = null
      }
    } catch (e: any) {
      // Ignore abort errors — expected when switching conversations
      if (e?.name === 'AbortError') return
      error.value = e?.message || 'Failed to send message'
      status.value = 'error'
      activeAbort = null
      activeConversationId = null
      // Remove empty placeholder on error
      if (!assistantMsg.parts.length) {
        messages.value = messages.value.filter((m) => m.id !== assistantMsg.id)
      }
    }
  }

  /** Replace the assistant message in the array with a shallow clone to trigger Vue reactivity. */
  function updateAssistantMsg(assistantMsg: ChatMessage) {
    messages.value = messages.value.map((m) =>
      m.id === assistantMsg.id ? { ...assistantMsg, parts: [...assistantMsg.parts] } : m
    )
  }

  function handleSSEEvent(eventType: string, data: any, assistantMsg: ChatMessage) {
    switch (eventType) {
      case 'text_delta': {
        assistantMsg._content = (assistantMsg._content || '') + (data.text || '')
        // Find or create text part (always last)
        const lastPart = assistantMsg.parts[assistantMsg.parts.length - 1]
        if (lastPart?.type === 'text') {
          lastPart.text = assistantMsg._content
        } else {
          assistantMsg.parts.push({ type: 'text', text: assistantMsg._content })
        }
        updateAssistantMsg(assistantMsg)
        break
      }

      case 'tool_call_start': {
        if (!assistantMsg._toolCalls) assistantMsg._toolCalls = []
        assistantMsg._toolCalls.push({
          id: data.id,
          name: data.name,
          args: data.args || {},
        })
        assistantMsg.parts.push({
          type: 'tool-invocation',
          toolInvocationId: data.id,
          toolName: data.name,
          state: 'call',
          args: data.args || {},
        })
        updateAssistantMsg(assistantMsg)
        break
      }

      case 'tool_call_result': {
        // Update raw data
        if (assistantMsg._toolCalls) {
          const tc = assistantMsg._toolCalls.find((t) => t.id === data.id)
          if (tc) tc.result = data.result
        }
        // Update parts
        const part = assistantMsg.parts.find(
          (p) => p.type === 'tool-invocation' && p.toolInvocationId === data.id
        )
        if (part) {
          part.state = 'result'
          part.result = data.result
        }
        updateAssistantMsg(assistantMsg)
        break
      }

      case 'done':
        if (data.message_id) {
          assistantMsg.id = data.message_id
          updateAssistantMsg(assistantMsg)
        }
        break

      case 'error':
        error.value = data.message || 'An error occurred'
        status.value = 'error'
        break
    }
  }

  function stop() {
    abortStream()
  }

  function regenerate() {
    status.value = 'ready'
    error.value = null
  }

  /** Reset all chat state — call when leaving the page. */
  function reset() {
    abortStream()
    currentConversation.value = null
    messages.value = []
    error.value = null
    loading.value = false
  }

  return {
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
    updateTitle,
    sendMessage,
    stop,
    regenerate,
    reset,
  }
}
