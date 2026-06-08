-- 0003_prep_progress.sql — live prep progress + input-quality warnings.
-- Adds two jsonb arrays to public.sessions:
--   progress      — ordered list of completed prep step keys
--                   (subset of cv_analysis/jd_analysis/company_research/
--                    gap_matching/question_planner) for the live progress UI.
--   prep_warnings — human-readable input-quality warnings (noisy CV/JD/company).
alter table public.sessions
  add column if not exists progress jsonb not null default '[]'::jsonb;
alter table public.sessions
  add column if not exists prep_warnings jsonb not null default '[]'::jsonb;
