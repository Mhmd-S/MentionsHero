/**
 * Public API fetch wrapper.
 * Attaches auth token if user is logged in (for subscription-aware responses).
 */
export function usePublicApi() {
  const { session } = useAuth()

  async function publicFetch<T>(url: string, options?: Record<string, any>): Promise<T> {
    const headers: Record<string, string> = {}

    // Attach token if user is logged in
    if (session.value?.access_token) {
      headers.Authorization = `Bearer ${session.value.access_token}`
    }

    return $fetch<T>(url, {
      ...options,
      headers: {
        ...headers,
        ...options?.headers,
      },
    })
  }

  return { publicFetch }
}
