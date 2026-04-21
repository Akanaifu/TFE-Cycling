BEGIN;

INSERT INTO users (email, display_name, password_hash, role)
VALUES (
  'admin@tfe.local',
  'TFE Admin',
  crypt('AdminChangeMe123!', gen_salt('bf', 12)),
  'admin'
)
ON CONFLICT (email) DO UPDATE
SET
  display_name = EXCLUDED.display_name,
  password_hash = EXCLUDED.password_hash,
  role = EXCLUDED.role;

COMMIT;
