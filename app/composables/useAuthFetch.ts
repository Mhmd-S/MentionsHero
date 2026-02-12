export function useAuthFetch() {
  const { logout } = useAuth();
  const supabase = useSupabaseClient();

  async function getToken(): Promise<string | null> {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  }

  async function authFetch<T = any>(
    url: string,
    opts: Parameters<typeof $fetch>[1] = {}
  ): Promise<T> {
    const token = await getToken();
    const headers: Record<string, string> = {
      ...(opts.headers as Record<string, string>),
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      return await $fetch<T>(url, { ...opts, headers });
    } catch (e: any) {
      if (e?.response?.status === 401) {
        // Try refreshing the session once before logging out
        const { data } = await supabase.auth.refreshSession();
        if (data.session) {
          headers["Authorization"] = `Bearer ${data.session.access_token}`;
          try {
            return await $fetch<T>(url, { ...opts, headers });
          } catch (retryError: any) {
            if (retryError?.response?.status === 401) {
              await logout();
            }
            throw retryError;
          }
        }
        await logout();
      }
      throw e;
    }
  }

  return { authFetch };
}
