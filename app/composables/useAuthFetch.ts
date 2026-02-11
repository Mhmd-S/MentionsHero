export function useAuthFetch() {
  const { getAccessToken, logout } = useAuth();

  async function authFetch<T = any>(
    url: string,
    opts: Parameters<typeof $fetch>[1] = {}
  ): Promise<T> {
    const token = getAccessToken();
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
        await logout();
      }
      throw e;
    }
  }

  return { authFetch };
}
