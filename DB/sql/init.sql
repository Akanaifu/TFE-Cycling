-- TFE Cycling PostgreSQL initialization script
-- Safe to run multiple times (CREATE ... IF NOT EXISTS)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  display_name text,
  password_hash text NOT NULL,
  role text NOT NULL DEFAULT 'user',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS strava_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  athlete_id bigint NOT NULL UNIQUE,
  access_token_enc text NOT NULL,
  refresh_token_enc text NOT NULL,
  expires_at timestamptz NOT NULL,
  scope text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rides (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  strava_account_id uuid NOT NULL REFERENCES strava_accounts(id) ON DELETE CASCADE,
  activity_id bigint NOT NULL,
  start_date_local timestamptz,
  sport_type text,
  distance_m double precision,
  moving_time_s integer,
  avg_hr double precision,
  avg_watts double precision,
  file_path text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, activity_id)
);

CREATE TABLE IF NOT EXISTS sync_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  strava_account_id uuid NOT NULL REFERENCES strava_accounts(id) ON DELETE CASCADE,
  requested_limit integer NOT NULL,
  saved_count integer NOT NULL DEFAULT 0,
  skipped_count integer NOT NULL DEFAULT 0,
  status text NOT NULL CHECK (status IN ('pending', 'running', 'done', 'failed')),
  started_at timestamptz,
  finished_at timestamptz,
  error_message text
);

CREATE TABLE IF NOT EXISTS prediction_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  selected_train_ride_idx integer NOT NULL,
  selected_models_json jsonb NOT NULL DEFAULT '[]'::jsonb,
  target_rides_json jsonb,
  status text NOT NULL CHECK (status IN ('pending', 'running', 'done', 'failed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id);
CREATE INDEX IF NOT EXISTS idx_rides_strava_account_id ON rides(strava_account_id);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_user_id ON sync_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_prediction_runs_user_id ON prediction_runs(user_id);
