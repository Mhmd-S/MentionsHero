export default defineNuxtRouteMiddleware(async (to) => {
  // Skip auth check for login page
  if (to.path === "/login") return;

  // Skip on server side
  if (import.meta.server) return;

  const { session, loading } = useAuth();

  // While the plugin is still initializing, don't redirect
  if (loading.value) return;

  // If useState session is available, allow through
  if (session.value) return;

  // Fallback: check Supabase directly (session may not be synced to useState yet)
  const supabase = useSupabaseClient();
  const { data } = await supabase.auth.getSession();
  if (data.session) {
    // Sync back to useState
    const auth = useAuth();
    await auth.init();
    return;
  }

  return navigateTo("/login");
});
