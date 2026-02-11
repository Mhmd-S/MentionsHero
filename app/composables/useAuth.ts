import type { User, Session } from "@supabase/supabase-js";

export function useAuth() {
  const user = useState<User | null>("auth-user", () => null);
  const session = useState<Session | null>("auth-session", () => null);
  const loading = useState<boolean>("auth-loading", () => true);
  const error = useState<string | null>("auth-error", () => null);

  async function init() {
    const supabase = useSupabaseClient();

    // Read existing session
    const { data } = await supabase.auth.getSession();
    session.value = data.session;
    user.value = data.session?.user ?? null;
    loading.value = false;

    // Subscribe to auth changes (token refresh, sign-out, etc.)
    supabase.auth.onAuthStateChange((_event, newSession) => {
      session.value = newSession;
      user.value = newSession?.user ?? null;
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
    init,
    login,
    logout,
    getAccessToken,
  };
}
