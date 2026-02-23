export default defineNuxtRouteMiddleware(async (to) => {
  // Public routes — no auth needed
  if (to.path === "/login") return;
  if (to.path === "/signup") return;
  if (to.path.startsWith("/view/")) return;
  if (to.path === "/" || to.path.startsWith("/p/")) return;

  // Skip on server side
  if (import.meta.server) return;

  const { session, loading, role } = useAuth();

  // While the plugin is still initializing, don't redirect
  if (loading.value) return;

  // If no session in useState, try Supabase directly
  if (!session.value) {
    const supabase = useSupabaseClient();
    const { data } = await supabase.auth.getSession();
    if (data.session) {
      const auth = useAuth();
      await auth.init();
    } else {
      return navigateTo("/login");
    }
  }

  // Admin routes: require admin role from profiles table
  if (to.path.startsWith("/admin")) {
    if (role.value !== "admin") {
      return navigateTo("/");
    }
  }
});
