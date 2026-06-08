-- 0002_billing.sql — WP-11 payments + plan gating.
-- Extends profiles with credit/period columns, adds a credit ledger and a
-- subscriptions table. Mirrors 0001's RLS posture but writes from the billing
-- webhook go through the service-role key (which bypasses RLS), so end-user
-- policies on the new tables are SELECT-only (clients read their own balance;
-- they can never mint credits or forge a subscription from the browser).

-- gen_random_uuid() lives in pgcrypto. uuid-ossp is already enabled by 0001,
-- but enable pgcrypto explicitly so this migration is self-sufficient.
create extension if not exists "pgcrypto";

-- ── profiles: billing columns ─────────────────────────────────────────────
-- `credits` are non-expiring "interview" credits (overage / non-sub packs).
-- `interviews_used` already exists (0001); it is the monthly metered counter.
-- `usage_period_start` anchors the monthly reset; `plan_renews_at` is the
-- subscription renewal boundary reported by the payment provider.
alter table public.profiles
  add column if not exists credits integer not null default 0;
alter table public.profiles
  add column if not exists usage_period_start date not null default current_date;
alter table public.profiles
  add column if not exists plan_renews_at timestamptz;

-- Monthly reset of the metered counter.
-- Kept deliberately simple: a SQL function that callers (the gate / a cron /
-- a scheduled Edge Function) invoke. It zeroes `interviews_used` and advances
-- the period anchor once 30+ days have elapsed. Credits are NOT reset — they
-- never expire. Safe to call on every gate check (no-op until the period rolls).
create or replace function public.reset_usage_if_due(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.profiles
     set interviews_used = 0,
         usage_period_start = current_date
   where id = p_user_id
     and usage_period_start <= current_date - interval '30 days';
end;
$$;

-- ── credit_ledger ─────────────────────────────────────────────────────────
-- Append-only audit of every credit movement: + on a pack purchase, - on an
-- overage interview consumed. The source of truth for `profiles.credits` is the
-- column; this table is the explainable history behind it.
create table if not exists public.credit_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  delta integer not null,
  reason text,
  created_at timestamptz not null default now()
);
create index if not exists credit_ledger_user_id_idx
  on public.credit_ledger (user_id, created_at desc);

-- ── subscriptions ─────────────────────────────────────────────────────────
-- One row per provider subscription. `id` is the provider's subscription id
-- (e.g. Paddle subscription id) so upserts on webhook are idempotent.
create table if not exists public.subscriptions (
  id text primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  plan text not null,
  status text not null,
  provider text not null default 'paddle',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists subscriptions_user_id_idx
  on public.subscriptions (user_id);

-- ── RLS ───────────────────────────────────────────────────────────────────
alter table public.credit_ledger enable row level security;
alter table public.subscriptions enable row level security;

-- Owner can READ their own ledger / subscriptions. No insert/update/delete
-- policy → clients cannot write. The webhook uses the service-role key, which
-- bypasses RLS entirely, so it is unaffected by the absence of write policies.
drop policy if exists "own credit_ledger read" on public.credit_ledger;
create policy "own credit_ledger read" on public.credit_ledger
  for select using (auth.uid() = user_id);

drop policy if exists "own subscriptions read" on public.subscriptions;
create policy "own subscriptions read" on public.subscriptions
  for select using (auth.uid() = user_id);

-- Keep subscriptions.updated_at fresh (reuses 0001's trigger function).
drop trigger if exists subscriptions_touch on public.subscriptions;
create trigger subscriptions_touch
  before update on public.subscriptions
  for each row execute function public.touch_updated_at();
