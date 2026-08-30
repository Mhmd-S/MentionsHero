/**
 * Stripe subscription state.
 *
 * All state is `useState`, so it is shared across every component in a session and
 * hydrated once by app/plugins/session.client.ts. It used to be a bare `ref` created
 * fresh on each call, which meant `loading` was per-caller and `isSubscribed` was
 * false on any page that forgot to call `fetchSubscription()` — /pricing did exactly
 * that and showed paying subscribers an active Subscribe button.
 */
export interface SubscriptionState {
  is_subscribed?: boolean
  status?: string | null
  current_period_end?: string | null
  [key: string]: unknown
}

export function useSubscription() {
  const session = useSupabaseSession()

  const subscription = useState<SubscriptionState | null>('subscription', () => null)
  const loading = useState<boolean>('subscription-loading', () => false)
  const checkoutPending = useState<boolean>('subscription-checkout', () => false)
  const loaded = useState<boolean>('subscription-loaded', () => false)
  const error = useState<string | null>('subscription-error', () => null)

  const isSubscribed = computed(() => subscription.value?.is_subscribed === true)

  function authHeaders(): Record<string, string> {
    const token = session.value?.access_token
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  async function fetchSubscription() {
    if (!session.value) {
      subscription.value = null
      loaded.value = true
      return
    }

    loading.value = true
    error.value = null
    try {
      subscription.value = await $fetch<SubscriptionState>('/api/stripe/subscription', {
        headers: authHeaders(),
      })
      loaded.value = true
    } catch (e) {
      // Deliberately do NOT null the subscription here. Wiping it on a transient
      // API error would flip isSubscribed to false and re-lock a paying customer's
      // UI with no explanation.
      error.value = e instanceof Error ? e.message : 'Could not load your subscription'
    } finally {
      loading.value = false
    }
  }

  /** Load once per session. Safe to call from any page's onMounted. */
  async function ensureLoaded() {
    if (loaded.value || loading.value) return
    await fetchSubscription()
  }

  async function startCheckout() {
    if (!session.value) {
      return navigateTo('/login?redirect=/pricing')
    }

    checkoutPending.value = true
    error.value = null
    try {
      const { url } = await $fetch<{ url: string }>('/api/stripe/checkout', {
        method: 'POST',
        headers: authHeaders(),
      })
      if (url) {
        window.location.href = url
        return
      }
      error.value = 'Checkout is unavailable right now. Please try again.'
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Could not start checkout'
    } finally {
      checkoutPending.value = false
    }
  }

  async function openPortal() {
    checkoutPending.value = true
    error.value = null
    try {
      const { url } = await $fetch<{ url: string }>('/api/stripe/portal', {
        method: 'POST',
        headers: authHeaders(),
      })
      if (url) {
        window.location.href = url
        return
      }
      error.value = 'We could not open the billing portal. Please try again.'
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Could not open the billing portal'
    } finally {
      checkoutPending.value = false
    }
  }

  function clear() {
    subscription.value = null
    loaded.value = false
    error.value = null
  }

  return {
    subscription,
    isSubscribed,
    loading,
    checkoutPending,
    error,
    fetchSubscription,
    ensureLoaded,
    startCheckout,
    openPortal,
    clear,
  }
}
