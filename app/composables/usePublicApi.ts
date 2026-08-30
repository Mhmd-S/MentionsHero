/**
 * Fetch wrapper for the public API. Attaches the access token when the visitor is
 * signed in, so the backend can widen the response for subscribers, and works
 * unauthenticated otherwise.
 */
export function usePublicApi() {
  const session = useSupabaseSession()

  async function publicFetch<T>(url: string, options?: Record<string, unknown>): Promise<T> {
    const token = session.value?.access_token

    return $fetch<T>(url, {
      ...options,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options?.headers,
      },
    })
  }

  return { publicFetch }
}
