-- =====================================================
-- SUPABASE DATABASE SCHEMA
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- =====================================================

-- Create videos table (main metadata)
create table public.videos (
  id uuid primary key default gen_random_uuid(),
  filename text not null,
  duration_seconds integer,
  status text default 'uploading', -- uploading, processing, ready, error
  segment_count integer default 0,
  user_id text,
  created_at timestamp default now(),
  processed_at timestamp,
  updated_at timestamp default now()
);

-- Create segments table (transcription + emotions)
create table public.segments (
  id uuid primary key default gen_random_uuid(),
  video_id uuid not null references public.videos(id) on delete cascade,
  segment_id text not null, -- seg_0000, seg_0001, etc
  start_sec float not null,
  end_sec float not null,
  transcript text not null,
  emotions text[] default '{}', -- array of emotion strings
  emotion_scores jsonb, -- {"surprise": 0.95, "laughter": 0.3}
  visual_emotions text[] default '{}',
  emotion_intensity float,
  avg_emotion_confidence float,
  created_at timestamp default now(),
  unique(video_id, segment_id)
);

-- Create speakers table (for Phase 5)
create table public.speakers (
  id uuid primary key default gen_random_uuid(),
  video_id uuid not null references public.videos(id) on delete cascade,
  speaker_id text not null, -- Speaker 1, Speaker 2, etc
  name text, -- custom speaker name
  total_duration integer, -- seconds
  emotion_profile jsonb, -- how this speaker typically responds
  created_at timestamp default now(),
  unique(video_id, speaker_id)
);

-- Create query results (for analytics)
create table public.query_results (
  id uuid primary key default gen_random_uuid(),
  video_id uuid not null references public.videos(id) on delete cascade,
  question text not null,
  answer text,
  confidence float,
  segment_count integer,
  queried_at timestamp default now()
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Fast video lookup by status
create index idx_videos_status on public.videos(status);
create index idx_videos_user_id on public.videos(user_id);

-- Fast segment lookup
create index idx_segments_video_id on public.segments(video_id);
create index idx_segments_emotions on public.segments using gin(emotions);

-- Fast speaker lookup
create index idx_speakers_video_id on public.speakers(video_id);

-- Fast query lookups
create index idx_query_results_video_id on public.query_results(video_id);

-- =====================================================
-- ENABLE REALTIME (for live updates)
-- =====================================================

alter publication supabase_realtime add table public.videos;
alter publication supabase_realtime add table public.segments;
alter publication supabase_realtime add table public.speakers;

-- =====================================================
-- ROW LEVEL SECURITY (Optional - for multi-user)
-- =====================================================

-- Videos: Users can only see their own
alter table public.videos enable row level security;

create policy "Users can see their own videos"
  on public.videos
  for select
  using (auth.uid()::text = user_id or user_id is null);

create policy "Users can insert their own videos"
  on public.videos
  for insert
  with check (auth.uid()::text = user_id or user_id is null);

-- Segments: Public read, controlled write
alter table public.segments enable row level security;

create policy "Anyone can read segments"
  on public.segments
  for select
  using (true);

-- Speakers: Public read
alter table public.speakers enable row level security;

create policy "Anyone can read speakers"
  on public.speakers
  for select
  using (true);

-- Query results: Public read
alter table public.query_results enable row level security;

create policy "Anyone can read query results"
  on public.query_results
  for select
  using (true);

-- =====================================================
-- SAMPLE DATA (FOR TESTING)
-- =====================================================

-- Insert a test video
insert into public.videos (filename, duration_seconds, status, segment_count) values
  ('test_video.mp4', 180, 'ready', 3);

-- Get the video ID for reference
-- SELECT id FROM public.videos WHERE filename = 'test_video.mp4';

-- =====================================================
-- USEFUL QUERIES
-- =====================================================

-- List all videos with segment count
-- SELECT filename, duration_seconds, segment_count, status, created_at FROM public.videos ORDER BY created_at DESC;

-- List all segments for a video
-- SELECT * FROM public.segments WHERE video_id = '550e8400-e29b-41d4-a716-446655440000' ORDER BY start_sec;

-- Find segments with specific emotions
-- SELECT segment_id, transcript, emotions FROM public.segments WHERE emotions && ARRAY['surprise','shock'];

-- Get query history
-- SELECT question, confidence, segment_count FROM public.query_results ORDER BY queried_at DESC LIMIT 10;

-- =====================================================
-- BACKUP & RESTORE
-- =====================================================

-- Backup database (in terminal):
-- pg_dump --clean --if-exists postgresql://user:password@db.supabase.co:5432/postgres > backup.sql

-- Restore from backup (in terminal):
-- psql postgresql://user:password@db.supabase.co:5432/postgres < backup.sql
