## Maintenance Checklist

Quarterly tasks:

- `pip list --outdated` → update and test
- `npm outdated` in `frontend/` → update and test
- Review base Docker images and PostgreSQL minor/major versions
- Check CVEs on https://osv.dev for critical packages
- Run `scripts/backup/pg_restore_test.sh` and store the report

Operational tasks:

- Ensure dependabot PRs are reviewed and merged regularly
- Run vulnerability scans (pip-audit, npm audit) weekly via CI

- Rotate secrets according to `docs/rotation.md` (if present)
