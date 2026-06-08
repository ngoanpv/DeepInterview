create extension if not exists "uuid-ossp";
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text, plan text not null default 'free',
  interviews_used integer not null default 0,
  locale text not null default 'en',
  created_at timestamptz not null default now()
);
create table if not exists public.sessions (
  id text primary key,
  user_id uuid references public.profiles(id) on delete cascade,
  status text not null default 'prep',
  company text, cv_url text, jd_text text,
  language_mode jsonb not null default '{"primary":"en","mixed":false}'::jsonb,
  context jsonb, scorecard jsonb, transcript jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
alter table public.sessions enable row level security;
create policy "own profile" on public.profiles for all using (auth.uid() = id) with check (auth.uid() = id);
create policy "own sessions" on public.sessions for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create or replace function public.touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end; $$;
create trigger sessions_touch before update on public.sessions for each row execute function public.touch_updated_at();
create or replace function public.handle_new_user() returns trigger language plpgsql security definer as $$
begin insert into public.profiles (id, email) values (new.id, new.email) on conflict do nothing; return new; end; $$;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_user();
