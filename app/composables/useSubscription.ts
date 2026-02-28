/**
 * Subscription state management for Stripe integration.
 */
export function useSubscription() {
  const { publicFetch } = usePublicApi()
  const { session } = useAuth()

  const subscription = useState<Record<string, any> | null>('subscription', () => null)
  const loading = ref(false)

  const isSubscribed = computed(() => subscription.value?.is_subscribed === true)

  async function fetchSubscription() {
    if (!session.value) {
      subscription.value = null
      return
    }

    loading.value = true
    try {
      subscription.value = await publicFetch<Record<string, any>>('/api/stripe/subscription')
    } catch {
      subscription.value = null
    } finally {
      loading.value = false
    }
  }

  async function startCheckout() {
    if (!session.value) {
      navigateTo('/login')
      return
    }

    try {
      const { url } = await publicFetch<{ url: string }>('/api/stripe/checkout', {
        method: 'POST',
      })
      if (url) {
        window.location.href = url
      }
    } catch (err) {
      console.error('Failed to start checkout:', err)
    }
  }

  async function openPortal() {
    try {
      const { url } = await publicFetch<{ url: string }>('/api/stripe/portal', {
        method: 'POST',
      })
      if (url) {
        window.location.href = url
      }
    } catch (err) {
      console.error('Failed to open portal:', err)
    }
  }

  return {
    subscription: readonly(subscription),
    isSubscribed,
    loading: readonly(loading),
    fetchSubscription,
    startCheckout,
    openPortal,
  }
}
