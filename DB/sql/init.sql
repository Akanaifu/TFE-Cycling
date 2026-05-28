-- TFE Cycling PostgreSQL initialization script
-- Safe to run multiple times (CREATE ... IF NOT EXISTS)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name text,
  email text NOT NULL UNIQUE,
  password text NOT NULL,
  role text NOT NULL DEFAULT 'user',
  created_at timestamptz NOT NULL DEFAULT now(),
  verified_at timestamptz,
  cyclist text UNIQUE
);

CREATE TABLE IF NOT EXISTS strava_account (
  user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  athlete_id bigint NOT NULL,
  access_token_enc text NOT NULL,
  refresh_token_enc text NOT NULL,
  expires_at timestamptz NOT NULL,
  scope text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rides (
  activity_id bigint PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  start_date_local timestamptz,
  sport_type text,
  distance_m double precision,
  moving_time_s integer,
  avg_hr double precision,
  avg_watts double precision,
  file_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verif_email (
  user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  code_hash text NOT NULL,
  attempts_left integer NOT NULL DEFAULT 2 CHECK (attempts_left BETWEEN 0 AND 2),
  expires_at timestamptz NOT NULL,
  sent_at timestamptz NOT NULL DEFAULT now(),
  verified_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id);
CREATE INDEX IF NOT EXISTS idx_users_cyclist ON users(cyclist);
CREATE INDEX IF NOT EXISTS idx_strava_account_athlete_id ON strava_account(athlete_id);
CREATE INDEX IF NOT EXISTS idx_verif_email_updated_at ON verif_email(updated_at);
