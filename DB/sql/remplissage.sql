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

-- No default users are inserted here.
-- Create users explicitly through /auth/register with bcrypt hashing.

COMMIT;
