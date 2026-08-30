/**
 * Authenticated fetch for the admin API.
 *
 * On a 401 it refreshes the Supabase session once and retries before giving up and
 * signing the user out — an expired access token should not eject someone who still
 * holds a valid refresh token.
 */
export function useAuthFetch() {
  const client = useSupabaseClient()
  const session = useSupabaseSession()
  const { logout } = useAuth()

  /** Narrow shape of the error ofetch throws — enough to branch on the status. */
  function statusOf(error: unknown): number | undefined {
    return (error as { response?: { status?: number } })?.response?.status
  }

  async function authFetch<T = unknown>(
    url: string,
    opts: Parameters<typeof $fetch>[1] = {},
  ): Promise<T> {
    const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) }

    const token = session.value?.access_token
    if (token) headers.Authorization = `Bearer ${token}`

    try {
      return await $fetch<T>(url, { ...opts, headers })
    } catch (e) {
      if (statusOf(e) !== 401) throw e

      const { data } = await client.auth.refreshSession()
      if (!data.session) {
        await logout()
        throw e
      }

      headers.Authorization = `Bearer ${data.session.access_token}`
      try {
        return await $fetch<T>(url, { ...opts, headers })
      } catch (retryError) {
        if (statusOf(retryError) === 401) await logout()
        throw retryError
      }
    }
  }

  return { authFetch }
}
