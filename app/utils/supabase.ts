import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let _client: SupabaseClient | null = null;

export function useSupabaseClient(): SupabaseClient {
  if (_client) return _client;

  const config = useRuntimeConfig();
  const url = config.public.supabaseUrl as string;
  const key = config.public.supabasePublishableKey as string;

  _client = createClient(url, key, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
    },
  });

  return _client;
}
