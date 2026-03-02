import type { User, Session } from "@supabase/supabase-js";

export function useAuth() {
  const user = useState<User | null>("auth-user", () => null);
  const session = useState<Session | null>("auth-session", () => null);
  const loading = useState<boolean>("auth-loading", () => false);
  const error = useState<string | null>("auth-error", () => null);
  const role = useState<string | null>("auth-role", () => null);

  async function fetchRole(accessToken: string) {
    try {
      const data = await $fetch<{ role: string | null }>("/api/profile", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      role.value = data.role;

      console.log("Fetched user role:", data.role);
    } catch {
      role.value = null;
    }
  }

  async function init() {
    loading.value = true;
    const supabase = useSupabaseClient();

    // Read existing session
    const { data } = await supabase.auth.getSession();
    session.value = data.session;
    user.value = data.session?.user ?? null;

    // Fetch role from backend
    if (data.session?.access_token) {
      await fetchRole(data.session.access_token);
    }

    loading.value = false;

    // Subscribe to auth changes (token refresh, sign-out, etc.)
    supabase.auth.onAuthStateChange((_event, newSession) => {
      session.value = newSession;
      user.value = newSession?.user ?? null;
      if (!newSession) {
        role.value = null;
      }
    });
  }

  async function login(email: string, password: string) {
    error.value = null;
    loading.value = true;
    try {
      const supabase = useSupabaseClient();
      const { data, error: authError } =
        await supabase.auth.signInWithPassword({ email, password });

      if (authError) {
        error.value = authError.message;
        return false;
      }

      session.value = data.session;
      user.value = data.user;
      if (data.session?.access_token) {
        await fetchRole(data.session.access_token);
      }
      return true;
    } catch (e: any) {
      error.value = e.message || "Login failed";
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function logout() {
    const supabase = useSupabaseClient();
    await supabase.auth.signOut();
    session.value = null;
    user.value = null;
    role.value = null;
    navigateTo("/login");
  }

  function getAccessToken(): string | null {
    return session.value?.access_token ?? null;
  }

  return {
    user: readonly(user),
    session: readonly(session),
    loading: readonly(loading),
    error: readonly(error),
    role: readonly(role),
    init,
    login,
    logout,
    getAccessToken,
  };
}
