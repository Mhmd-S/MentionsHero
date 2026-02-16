/**
 * Composable for trading bot API interactions and SSE streaming
 */

export interface TradingSession {
  id: string
  youtube_url: string
  video_title: string | null
  persona_id: string
  series_id: string | null
  status: string
  config: Record<string, any>
  stage_progress: Record<string, any>
  error_message: string | null
  cancel_requested: boolean
  started_at: string | null
  ended_at: string | null
  created_at: string | null
  updated_at: string | null
  is_simulation?: boolean
  simulation_metadata?: Record<string, any> | null
}

export interface TradingConfig {
  profit_target_pct?: number
  stop_loss_pct?: number
  max_price_to_buy?: number
  buy_amount_usd?: number
  max_concurrent_positions?: number
  price_poll_interval_s?: number
}

export interface Trade {
  id: string
  session_id: string
  market_id: string
  token_id: string | null
  condition_id: string | null
  side: string
  amount_usd: number
  price: number
  shares: number
  order_id: string | null
  status: string
  triggered_by: string
  detected_term: string | null
  simulated_at: number | null
  created_at: string | null
}

export interface TradingPosition {
  id: string
  session_id: string
  market_id: string
  token_id: string | null
  buy_trade_id: string | null
  sell_trade_id: string | null
  buy_price: number
  current_price: number
  shares: number
  profit_loss_pct: number | null
  status: string
  created_at: string | null
  updated_at: string | null
}

export interface SessionLog {
  id: string
  session_id: string
  event_type: string
  payload: Record<string, any>
  created_at: string | null
}

export interface TimelineEvent {
  id: string
  event_type: string
  simulated_timestamp: number
  wall_clock_timestamp: string | null
  market_id: string | null
  payload: Record<string, any>
}

export interface SessionDetail {
  session: TradingSession
  trades: Trade[]
  positions: TradingPosition[]
  logs: SessionLog[]
  timeline_events?: TimelineEvent[]
}

export interface TradingMarket {
  id: string
  condition_id: string | null
  question: string | null
  slug: string | null
  active: boolean
  closed: boolean
  outcome_prices: string | null
  resolved_outcome: string | null
  search_terms: string[]
}

export interface MarketsForSeriesResponse {
  event: Record<string, any> | null
  markets: TradingMarket[]
}

export interface ChannelMonitorStatus {
  running: boolean
  watched_personas: number
  last_video_ids: Record<string, string>
}

export interface StartSessionRequest {
  youtube_url: string
  persona_id: string
  series_id: string
  market_ids?: string[]
  video_title?: string
  config?: TradingConfig
}

export interface StartSimulationRequest {
  youtube_url: string
  persona_id: string
  series_id: string
  event_id: string
  market_ids?: string[]
  video_title?: string
  config?: TradingConfig
}

export interface PolymarketEvent {
  id: string
  slug: string
  title: string | null
  start_date: string | null
  end_date: string | null
  series_id: string | null
}

export function useTrading() {
  const { authFetch } = useAuthFetch()

  async function getActiveSession(): Promise<TradingSession | null> {
    try {
      const result = await authFetch<{ session: TradingSession | null }>('/api/trading/active')
      return result?.session ?? null
    } catch (e) {
      console.error('Failed to get active session:', e)
      return null
    }
  }

  async function getSessionHistory(): Promise<TradingSession[]> {
    try {
      const result = await authFetch<{ sessions: TradingSession[] }>('/api/trading/history')
      return result?.sessions ?? []
    } catch (e) {
      console.error('Failed to get session history:', e)
      return []
    }
  }

  async function startSession(req: StartSessionRequest): Promise<{ session_id: string; status: string } | null> {
    try {
      return await authFetch('/api/trading/start', {
        method: 'POST',
        body: req,
      })
    } catch (e) {
      console.error('Failed to start session:', e)
      return null
    }
  }

  async function stopSession(): Promise<{ success: boolean; message: string } | null> {
    try {
      return await authFetch('/api/trading/stop', { method: 'POST' })
    } catch (e) {
      console.error('Failed to stop session:', e)
      return null
    }
  }

  async function getSessionDetail(id: string): Promise<SessionDetail | null> {
    try {
      return await authFetch<SessionDetail>(`/api/trading/${id}`)
    } catch (e) {
      console.error('Failed to get session detail:', e)
      return null
    }
  }

  function streamSession(
    id: string,
    onUpdate: (detail: SessionDetail) => void,
  ): () => void {
    const { getAccessToken } = useAuth()
    const token = getAccessToken()
    const url = token
      ? `/api/trading/${id}/stream?token=${encodeURIComponent(token)}`
      : `/api/trading/${id}/stream`
    const es = new EventSource(url)

    const refreshOnClose = async () => {
      const detail = await getSessionDetail(id)
      if (detail) onUpdate(detail)
    }

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.error) {
          console.error('Trading stream error:', data.error)
          es.close()
          refreshOnClose()
          return
        }
        onUpdate(data as SessionDetail)
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      es.close()
      refreshOnClose()
    }

    return () => es.close()
  }

  async function getMarketsForSeries(seriesId: string): Promise<MarketsForSeriesResponse | null> {
    try {
      return await authFetch<MarketsForSeriesResponse>('/api/trading/markets-for-series', {
        query: { series_id: seriesId },
      })
    } catch (e) {
      console.error('Failed to get markets for series:', e)
      return null
    }
  }

  async function getChannelMonitorStatus(): Promise<ChannelMonitorStatus | null> {
    try {
      return await authFetch<ChannelMonitorStatus>('/api/trading/channel-monitor/status')
    } catch (e) {
      console.error('Failed to get channel monitor status:', e)
      return null
    }
  }

  async function toggleAutoTrade(personaId: string, seriesId: string, enabled: boolean): Promise<boolean> {
    try {
      await authFetch('/api/trading/channel-monitor/auto-trade', {
        method: 'POST',
        query: { persona_id: personaId, series_id: seriesId, enabled: String(enabled) },
      })
      return true
    } catch (e) {
      console.error('Failed to toggle auto-trade:', e)
      return false
    }
  }

  // --- Simulation methods ---

  async function startSimulation(req: StartSimulationRequest): Promise<{ session_id: string; status: string } | null> {
    try {
      return await authFetch('/api/trading/simulation/start', {
        method: 'POST',
        body: req,
      })
    } catch (e) {
      console.error('Failed to start simulation:', e)
      return null
    }
  }

  async function getSimulationHistory(): Promise<TradingSession[]> {
    try {
      const result = await authFetch<{ sessions: TradingSession[] }>('/api/trading/simulation/history')
      return result?.sessions ?? []
    } catch (e) {
      console.error('Failed to get simulation history:', e)
      return []
    }
  }

  async function compareSimulations(sessionIds: string[]): Promise<SessionDetail[]> {
    try {
      const result = await authFetch<{ sessions: SessionDetail[] }>('/api/trading/simulation/compare', {
        query: { session_ids: sessionIds.join(',') },
      })
      return result?.sessions ?? []
    } catch (e) {
      console.error('Failed to compare simulations:', e)
      return []
    }
  }

  async function getEventsForSeries(seriesId: string): Promise<PolymarketEvent[]> {
    try {
      const result = await authFetch<{ events: PolymarketEvent[] }>('/api/trading/simulation/events-for-series', {
        query: { series_id: seriesId },
      })
      return result?.events ?? []
    } catch (e) {
      console.error('Failed to get events for series:', e)
      return []
    }
  }

  async function getMarketsForEvent(eventId: string): Promise<MarketsForSeriesResponse | null> {
    try {
      return await authFetch<MarketsForSeriesResponse>('/api/trading/simulation/markets-for-event', {
        query: { event_id: eventId },
      })
    } catch (e) {
      console.error('Failed to get markets for event:', e)
      return null
    }
  }

  return {
    getActiveSession,
    getSessionHistory,
    startSession,
    stopSession,
    getSessionDetail,
    streamSession,
    getMarketsForSeries,
    getChannelMonitorStatus,
    toggleAutoTrade,
    startSimulation,
    getSimulationHistory,
    compareSimulations,
    getEventsForSeries,
    getMarketsForEvent,
  }
}
