-- 0004_coach_transcript.sql — separate transcript for the spoken study coach.
-- The coach worker reuses the interview session row; without its own column it
-- would overwrite sessions.transcript (the interview record) on shutdown.
alter table public.sessions
  add column if not exists coach_transcript jsonb;
