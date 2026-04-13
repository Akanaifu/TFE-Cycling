# Guide de deploiement (TFE-Cycling)

Ce guide est adapte a ce repo:
- backend FastAPI: `TFE-Cycling/backend`
- frontend Next.js: `TFE-Cycling/frontend`
- scripts SQL: `TFE-Cycling/DB/sql`

## 1. Architecture recommandee

- Frontend: Vercel
- Backend API: Render (Web Service)
- Base de donnees PostgreSQL: Render Postgres ou Neon
- Domaine:
  - `app.tondomaine.be` -> frontend
  - `api.tondomaine.be` -> backend

## 2. Variables d'environnement backend

Configurer ces variables sur le service backend:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM=HS256`
- `JWT_EXPIRE_MINUTES=120`
- `FERNET_KEY` (ou la cle attendue par `backend/app/services/security.py`)
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REDIRECT_URI`
- `STRAVA_SCOPES=read,activity:read_all`

## 3. Initialiser la base de donnees

Les scripts SQL sont ici:

- `DB/sql/init.sql`
- `DB/sql/remplissage.sql`

Ordre recommande:

1. Executer `init.sql`
2. Executer `remplissage.sql` (optionnel en prod, utile pour demo/tests)

## 4. Deployer le backend (Render)

1. Creer un nouveau Web Service sur Render
2. Connecter le repo GitHub
3. Root Directory: `backend`
4. Build Command:
   - `pip install -r requirements.txt`
5. Start Command:
   - `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Ajouter les variables d'environnement backend
7. Verifier:
   - `https://api.tondomaine.be/health`

## 5. Deployer le frontend (Vercel)

1. Importer le repo sur Vercel
2. Root Directory: `frontend`
3. Ajouter la variable d'environnement:
   - `NEXT_PUBLIC_API_URL=https://api.tondomaine.be`
4. Build/deploiement standard Next.js
5. Verifier les routes:
   - `/` -> login
   - `/pipeline` -> protege
   - `/strava` -> protege

## 6. Configurer le domaine (DNS)

Chez ton registrar:

- `CNAME app` -> target Vercel
- `CNAME api` -> target Render

Laisser HTTPS/TLS auto sur Vercel + Render.

## 7. Config Strava Developer

Dans la console Strava:

- Website: `https://app.tondomaine.be`
- Authorization Callback Domain: domaine de callback
- `STRAVA_REDIRECT_URI` doit matcher exactement l'URI utilisee dans ton flow OAuth

Important: exact match (schema `https`, sous-domaine, chemin).

## 8. Verification fonctionnelle post-deploiement

1. Login/register OK
2. `/pipeline` redirige vers login si non connecte
3. `/strava` redirige vers login si non connecte
4. OAuth Strava complet:
   - generation URL
   - autorisation
   - echange code
5. Extraction Strava:
   - activites recuperees
   - PKL crees physiquement
   - chemins ecrits en DB

## 9. Commandes utiles

### Ouvrir psql

```powershell
psql "$env:DATABASE_URL"
```

### Nettoyer rides et donnees liees (sans supprimer users)

```sql
BEGIN;
DELETE FROM strava_accounts;
DELETE FROM prediction_runs;
COMMIT;
```

### Verifier les compteurs

```sql
SELECT COUNT(*) AS users_count FROM users;
SELECT COUNT(*) AS strava_accounts_count FROM strava_accounts;
SELECT COUNT(*) AS rides_count FROM rides;
SELECT COUNT(*) AS sync_jobs_count FROM sync_jobs;
SELECT COUNT(*) AS prediction_runs_count FROM prediction_runs;
```

## 10. Checklist pre-go-live

- Secrets presents en env (pas hardcodes)
- CORS backend autorise le domaine frontend
- Build frontend OK (`npm run build`)
- Backend health OK (`/health`)
- OAuth Strava teste en prod
- Extraction + ecriture DB/PKL valides
- HTTPS actif sur app + api
