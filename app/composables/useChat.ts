interface ToolCallData {
  id: string
  name: string
  args: Record<string, any>
  result?: any
}

interface MessagePart {
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

interface ChatMessage {
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

type ChatStatus = 'ready' | 'streaming' | 'submitted' | 'error'

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

  const conversations = useState<Conversation[]>('chat-conversations', () => [])
  const currentConversation = useState<Conversation | null>('chat-current', () => null)
  const messages = useState<ChatMessage[]>('chat-messages', () => [])
  const status = useState<ChatStatus>('chat-status', () => 'ready')
  const error = useState<string | null>('chat-error', () => null)

  async function getToken(): Promise<string | null> {
    const { data } = await supabase.auth.getSession()
    return data.session?.access_token ?? null
  }

  async function fetchConversations() {
    try {
      conversations.value = await authFetch<Conversation[]>('/api/chat/conversations')
    } catch (e: any) {
      error.value = e?.message || 'Failed to load conversations'
    }
  }

  async function createConversation(title?: string): Promise<Conversation | null> {
    try {
      const conv = await authFetch<Conversation>('/api/chat/conversations', {
        method: 'POST',
        body: { title: title || null },
      })
      conversations.value.unshift(conv)
      currentConversation.value = conv
      messages.value = []
      return conv
    } catch (e: any) {
      error.value = e?.message || 'Failed to create conversation'
      return null
    }
  }

  async function loadConversation(id: string) {
    try {
      const data = await authFetch<Conversation & { messages: any[] }>(
        `/api/chat/conversations/${id}`
      )
      currentConversation.value = data
      messages.value = (data.messages || []).map(dbMessageToParts)
    } catch (e: any) {
      error.value = e?.message || 'Failed to load conversation'
    }
  }

  async function deleteConversation(id: string) {
    try {
      await authFetch(`/api/chat/conversations/${id}`, { method: 'DELETE' })
      conversations.value = conversations.value.filter((c) => c.id !== id)
      if (currentConversation.value?.id === id) {
        currentConversation.value = null
        messages.value = []
      }
    } catch (e: any) {
      error.value = e?.message || 'Failed to delete conversation'
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
        currentConversation.value.title = title
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

    try {
      const token = await getToken()
      const response = await fetch(`/api/chat/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ content }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      status.value = 'streaming'
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

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
              // Ignore malformed data
            }
          }
        }
      }

      // Auto-generate title for new conversations
      if (currentConversation.value && !currentConversation.value.title && assistantMsg._content) {
        const autoTitle = content.length > 50 ? content.slice(0, 50) + '...' : content
        updateTitle(conversationId, autoTitle)
      }

      status.value = 'ready'
    } catch (e: any) {
      error.value = e?.message || 'Failed to send message'
      status.value = 'error'
      // Remove empty placeholder on error
      const idx = messages.value.findIndex((m) => m.id === assistantMsg.id)
      if (idx !== -1 && !assistantMsg.parts.length) {
        messages.value = messages.value.filter((m) => m.id !== assistantMsg.id)
      }
    }
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
        messages.value = [...messages.value]
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
        messages.value = [...messages.value]
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
        messages.value = [...messages.value]
        break
      }

      case 'done':
        if (data.message_id) {
          assistantMsg.id = data.message_id
          messages.value = [...messages.value]
        }
        break

      case 'error':
        error.value = data.message || 'An error occurred'
        status.value = 'error'
        break
    }
  }

  function stop() {
    // Future: implement abort controller
    status.value = 'ready'
  }

  function regenerate() {
    // Future: re-send last user message
    status.value = 'ready'
    error.value = null
  }

  return {
    conversations,
    currentConversation,
    messages,
    status,
    error,
    fetchConversations,
    createConversation,
    loadConversation,
    deleteConversation,
    updateTitle,
    sendMessage,
    stop,
    regenerate,
  }
}
