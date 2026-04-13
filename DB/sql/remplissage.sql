BEGIN;

CREATE TABLE IF NOT EXISTS app_config_secrets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  secret_key text NOT NULL UNIQUE,
  value_fernet text NOT NULL,
  source text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'app_config_secrets' AND column_name = 'value_bcrypt'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'app_config_secrets' AND column_name = 'value_fernet'
  ) THEN
    ALTER TABLE app_config_secrets ADD COLUMN value_fernet text;
    UPDATE app_config_secrets SET value_fernet = value_bcrypt WHERE value_fernet IS NULL;
    ALTER TABLE app_config_secrets ALTER COLUMN value_fernet SET NOT NULL;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'app_config_secrets' AND column_name = 'value_bcrypt'
  ) THEN
    ALTER TABLE app_config_secrets ALTER COLUMN value_bcrypt DROP NOT NULL;
  END IF;
END $$;

INSERT INTO app_config_secrets (secret_key, value_fernet, source)
VALUES
  ('STRAVA_CLIENT_ID', 'gAAAAABp3LjLRujS4u4sf_k5RySZ_3wiodAnkDQZZ0fwHfM-SX7PqZIldDY3o2deKujS2dY_KLad8PBw-OyPf0BtylG1uz4KEQ==', 'backend/.env (fernet)'),
  ('STRAVA_CLIENT_SECRET', 'gAAAAABp3LjLS_cdL_nlNNEa-IX_cIwaM8jqLCMGkvna-jXxDceN9n1vIz6ESugV9sr8eWlTJ2IOBPFUccCBeBcdLGKlZhOlcCwFBxIExtRAzieoiN40aCDqIUoeYm6cNJdt5tG7e9iY', 'backend/.env (fernet)'),
  ('STRAVA_REDIRECT_URI', 'gAAAAABp3LjLs0ZWCkNnignjZ7DUEXH-uw78prgPCiBbNKfeFm4KMFTHes_hrwTc5sRMXCLwB88xc_qWp0TsmQ48JsETWiNWg12DOrHiF78hisBKCAvF9tKeL-VAbL95AQ1IBQzl0qC2', 'backend/.env (fernet)')
ON CONFLICT (secret_key) DO UPDATE
SET value_fernet = EXCLUDED.value_fernet,
    source = EXCLUDED.source,
    created_at = now();

INSERT INTO users (email, display_name, password_hash, role)
VALUES (
  'admin@tfe.local',
  'TFE Admin',
  'dev_password_placeholder',
  'admin'
)
ON CONFLICT (email) DO UPDATE
SET display_name = EXCLUDED.display_name,
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role;

DO $$
DECLARE
  v_user_id uuid;
  v_account_id uuid;
BEGIN
  INSERT INTO users (email, display_name, password_hash, role)
  VALUES (
    'shapunaifu_athlete@strava.local',
    'Nathan Lemaire',
    'dev_password_placeholder',
    'user'
  )
  ON CONFLICT (email) DO UPDATE
  SET display_name = EXCLUDED.display_name,
      password_hash = EXCLUDED.password_hash
  RETURNING id INTO v_user_id;

  INSERT INTO strava_accounts (
    user_id,
    athlete_id,
    access_token_enc,
    refresh_token_enc,
    expires_at,
    scope
  )
  VALUES (
    v_user_id,
    51027626,
    'gAAAAABp3LjLaEYZVcmnk4ZE4Z6ZENrH4uyqLfqk-Wil07qPR_dtsd3B6qiXy2PIbHOYDVeWKbaiUhsOllzer6_0bKkkd1Mdm2KvQzOVN1fJrBMt_p1t161Gw0BwseyVCf-aATLJ4oD8',
    'gAAAAABp3LjLR55YdU52_2KXufojLo--HTiVJOcqUt8qsAv3fL9zH9YPaArSMYNhHDAHvtt_exGHWBR9WWF6h9laIgXgnNG6kha6NjVJgf2aEc9-pOEVreuh4CsHl3MZe6dHqgvPDxOS',
    to_timestamp(1776090303),
    'read,activity:read_all'
  )
  ON CONFLICT (athlete_id) DO UPDATE
  SET user_id = EXCLUDED.user_id,
      access_token_enc = EXCLUDED.access_token_enc,
      refresh_token_enc = EXCLUDED.refresh_token_enc,
      expires_at = EXCLUDED.expires_at,
      scope = EXCLUDED.scope,
      updated_at = now()
  RETURNING id INTO v_account_id;

  INSERT INTO sync_jobs (
    user_id,
    strava_account_id,
    requested_limit,
    saved_count,
    skipped_count,
    status,
    started_at,
    finished_at,
    error_message
  )
  VALUES (
    v_user_id,
    v_account_id,
    5,
    5,
    0,
    'done',
    now(),
    now(),
    NULL
  );

  INSERT INTO rides (
    user_id,
    strava_account_id,
    activity_id,
    start_date_local,
    sport_type,
    distance_m,
    moving_time_s,
    avg_hr,
    avg_watts,
    file_path
  )
  VALUES
    (v_user_id, v_account_id, 5102762601, '2026-03-27 14:43:06+00', 'Ride', NULL, NULL, NULL, NULL, 'DB/rides/cyclist1/2026-03-27T14_43_06.000000000.pkl'),
    (v_user_id, v_account_id, 5102762602, '2026-03-31 11:03:45+00', 'Ride', NULL, NULL, NULL, NULL, 'DB/rides/cyclist1/2026-03-31T11_03_45.000000000.pkl'),
    (v_user_id, v_account_id, 5102762603, '2026-04-02 09:56:36+00', 'Ride', NULL, NULL, NULL, NULL, 'DB/rides/cyclist1/2026-04-02T09_56_36.000000000.pkl'),
    (v_user_id, v_account_id, 5102762604, '2026-04-10 14:52:24+00', 'Ride', NULL, NULL, NULL, NULL, 'DB/rides/cyclist1/2026-04-10T14_52_24.000000000.pkl'),
    (v_user_id, v_account_id, 5102762605, '2026-04-10 17:05:47+00', 'Ride', NULL, NULL, NULL, NULL, 'DB/rides/cyclist1/2026-04-10T17_05_47.000000000.pkl')
  ON CONFLICT (user_id, activity_id) DO UPDATE
  SET
    file_path = EXCLUDED.file_path,
    start_date_local = EXCLUDED.start_date_local,
    strava_account_id = EXCLUDED.strava_account_id,
    sport_type = EXCLUDED.sport_type;

  INSERT INTO prediction_runs (
    user_id,
    selected_train_ride_idx,
    selected_models_json,
    target_rides_json,
    status,
    created_at,
    finished_at
  )
  VALUES (
    v_user_id,
    1,
    '["pred_arx_selected", "pred_hist"]'::jsonb,
    '[2,3,4,5]'::jsonb,
    'done',
    now(),
    now()
  );
END $$;

COMMIT;
