-- Migration script from the legacy schema to the 4-table target schema.
-- Run once on the current database, after taking a backup.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users_new (
  id uuid PRIMARY KEY,
  display_name text,
  email text NOT NULL UNIQUE,
  password text NOT NULL,
  role text NOT NULL DEFAULT 'user',
  created_at timestamptz NOT NULL DEFAULT now(),
  verified_at timestamptz,
  cyclist text UNIQUE
);

CREATE TABLE strava_account_new (
  user_id uuid PRIMARY KEY,
  athlete_id bigint NOT NULL,
  access_token_enc text NOT NULL,
  refresh_token_enc text NOT NULL,
  expires_at timestamptz NOT NULL,
  scope text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rides_new (
  activity_id bigint PRIMARY KEY,
  user_id uuid NOT NULL,
  start_date_local timestamptz,
  sport_type text,
  distance_m double precision,
  moving_time_s integer,
  avg_hr double precision,
  avg_watts double precision,
  file_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_rides_new_user FOREIGN KEY (user_id) REFERENCES users_new(id) ON DELETE CASCADE
);

CREATE TABLE verif_email_new (
  user_id uuid PRIMARY KEY,
  code_hash text NOT NULL,
  attempts_left integer NOT NULL DEFAULT 2 CHECK (attempts_left BETWEEN 0 AND 2),
  expires_at timestamptz NOT NULL,
  sent_at timestamptz NOT NULL DEFAULT now(),
  verified_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_verif_email_new_user FOREIGN KEY (user_id) REFERENCES users_new(id) ON DELETE CASCADE
);

INSERT INTO users_new (id, display_name, email, password, role, created_at, verified_at, cyclist)
SELECT
  u.id,
  u.display_name,
  u.email,
  u.password_hash,
  u.role,
  u.created_at,
  COALESCE(u.email_verified_at, vm.verified_at),
  uc.cyclist
FROM users u
LEFT JOIN user_cyclists uc ON uc.user_id = u.id
LEFT JOIN verif_mail vm ON vm.user_id = u.id;

INSERT INTO strava_account_new (user_id, athlete_id, access_token_enc, refresh_token_enc, expires_at, scope, created_at, updated_at)
SELECT
  sa.user_id,
  sa.athlete_id,
  sa.access_token_enc,
  sa.refresh_token_enc,
  sa.expires_at,
  sa.scope,
  sa.created_at,
  sa.updated_at
FROM strava_accounts sa;

INSERT INTO rides_new (
  activity_id,
  user_id,
  start_date_local,
  sport_type,
  distance_m,
  moving_time_s,
  avg_hr,
  avg_watts,
  file_name,
  created_at
)
SELECT
  r.activity_id,
  r.user_id,
  r.start_date_local,
  r.sport_type,
  r.distance_m,
  r.moving_time_s,
  r.avg_hr,
  r.avg_watts,
  COALESCE(r.file_path, '') AS file_name,
  r.created_at
FROM rides r;

INSERT INTO verif_email_new (user_id, code_hash, attempts_left, expires_at, sent_at, verified_at, updated_at)
SELECT
  v.user_id,
  v.code_hash,
  v.attempts_left,
  v.expires_at,
  v.sent_at,
  v.verified_at,
  v.updated_at
FROM verif_mail v;

DROP TABLE IF EXISTS prediction_runs CASCADE;
DROP TABLE IF EXISTS sync_jobs CASCADE;
DROP TABLE IF EXISTS rides CASCADE;
DROP TABLE IF EXISTS strava_accounts CASCADE;
DROP TABLE IF EXISTS verif_mail CASCADE;
DROP TABLE IF EXISTS user_cyclists CASCADE;
DROP TABLE IF EXISTS app_config_secrets CASCADE;
DROP TABLE IF EXISTS users CASCADE;

ALTER TABLE users_new RENAME TO users;
ALTER TABLE strava_account_new RENAME TO strava_account;
ALTER TABLE rides_new RENAME TO rides;
ALTER TABLE verif_email_new RENAME TO verif_email;

CREATE INDEX idx_rides_user_id ON rides(user_id);
CREATE INDEX idx_users_cyclist ON users(cyclist);
CREATE INDEX idx_strava_account_athlete_id ON strava_account(athlete_id);
CREATE INDEX idx_verif_email_updated_at ON verif_email(updated_at);

COMMIT;
