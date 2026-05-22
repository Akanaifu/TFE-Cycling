# Secrets Management (CI + Deployment)

This project requires secure storage for sensitive configuration.

## Required Secrets

- `APP_FERNET_KEY`
- `JWT_SECRET_KEY`
- `ALERT_WEBHOOK_URL`

## GitHub Secrets (recommended for CI)

Add repository secrets in GitHub:

1. Open repository `Settings` > `Secrets and variables` > `Actions`.
2. Create the three secrets above.
3. Ensure workflow permissions allow reading secrets on protected branches.

### Notes

- Secrets are available on `push`/`schedule` for this repository.
- On pull requests from forks, GitHub does not expose secrets by default.

## Deployment Secrets

Use one of these approaches for production:

- Host-level secret manager (Vault, 1Password Connect, Doppler, AWS/GCP/Azure Secret Manager)
- `.env.server` generated at deploy time (never committed)

### Minimal deploy-time envs

- `APP_FERNET_KEY`: base64 urlsafe 32-byte key for Fernet
- `JWT_SECRET_KEY`: at least 32 random bytes
- `ALERT_WEBHOOK_URL`: webhook endpoint for alerts

## Example generation commands

```bash
# Fernet-compatible key (Python)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT secret (Linux/macOS)
openssl rand -base64 48
```

```powershell
# JWT secret (PowerShell)
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
```
