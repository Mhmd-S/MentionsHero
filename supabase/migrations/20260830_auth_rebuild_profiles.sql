-- Auth rebuild: the database owns profile creation, not the browser.
--
-- Before this migration a profile row only existed if the signup page managed to
-- POST /api/profile/init immediately after supabase.auth.signUp(). Any interruption
-- (tab closed, network blip, email confirmed on another device) left an auth.users
-- row with no matching public.profiles row. Those users then hit:
--   * backend/core/auth.py     -> role lookup fails, admin access impossible
--   * backend/routers/profile.py -> GET /api/profile 500s on .single()
--   * backend/services/stripe_service.py -> checkout and portal 500 on .single()
-- i.e. a silently unusable account. The trigger below removes that failure mode
-- entirely: a profile row now exists for every auth user, always.

-- ---------------------------------------------------------------------------
-- 1. Auto-create the profile row whenever an auth user is created
-- ---------------------------------------------------------------------------

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- Values come from supabase.auth.signUp({ options: { data: { ... } } }).
  -- They are optional: the signup form only requires email + password, and any
  -- name the user gives later is written through the backend service key.
  insert into public.profiles (id, role, first_name, last_name, phone)
  values (
    new.id,
    'client',
    nullif(new.raw_user_meta_data ->> 'first_name', ''),
    nullif(new.raw_user_meta_data ->> 'last_name', ''),
    nullif(new.raw_user_meta_data ->> 'phone', '')
  )
  on conflict (id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- 2. Keep updated_at honest
-- ---------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 3. Backfill every existing auth user that never got a profile row
-- ---------------------------------------------------------------------------
-- This is the fix for the accounts already stranded in production. Safe to
-- re-run: the left join means already-present rows are skipped.

insert into public.profiles (id, role, first_name, last_name, phone)
select
  u.id,
  'client',
  nullif(u.raw_user_meta_data ->> 'first_name', ''),
  nullif(u.raw_user_meta_data ->> 'last_name', ''),
  nullif(u.raw_user_meta_data ->> 'phone', '')
from auth.users u
left join public.profiles p on p.id = u.id
where p.id is null;

-- ---------------------------------------------------------------------------
-- 4. Let auth users be deleted again
-- ---------------------------------------------------------------------------
-- profiles.id references auth.users(id) with NO cascade. That was survivable only
-- because most users had no profile row. Now that every user is guaranteed one,
-- deleting a user from the Supabase dashboard would fail on this foreign key.

alter table public.profiles
  drop constraint if exists profiles_id_fkey;

alter table public.profiles
  add constraint profiles_id_fkey
  foreign key (id) references auth.users(id) on delete cascade;

-- ---------------------------------------------------------------------------
-- 5. Lock the table down
-- ---------------------------------------------------------------------------
-- profiles had no RLS, so anyone holding the public anon key could read every
-- user's name and phone number. The only client-side reader was
-- app/pages/login.vue, which the auth rebuild removes — every read and write now
-- goes through the FastAPI backend on the service key, which bypasses RLS.
--
-- Deliberately SELECT-only: there is no UPDATE policy because `role` lives on
-- this table, and a client-side UPDATE policy would let any user promote
-- themselves to admin. Profile edits go through PUT /api/profile instead.

alter table public.profiles enable row level security;

drop policy if exists "Users can read their own profile" on public.profiles;

create policy "Users can read their own profile"
  on public.profiles
  for select
  to authenticated
  using ((select auth.uid()) = id);
