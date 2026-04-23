# Deploiement - TFE Cycling

## Vue d'ensemble

Le repository contient un `docker-compose.yml` qui lance:

- `postgres` (PostgreSQL 16)
- `backend` (FastAPI)

Le frontend est deploie separement (ex: Vercel) et pointe vers l'API backend.

## 1. Deploiement Docker (backend + postgres)

1. Copier le template:

```bash
cp .env.server.example .env.server
```

2. Completer `.env.server` avec au minimum:

- `POSTGRES_PASSWORD`
- `JWT_SECRET_KEY`
- `APP_FERNET_KEY`
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REDIRECT_URI`

3. Lancer:

```bash
docker compose --env-file .env.server up -d --build
```

4. Verifier:

- `http://<host>:8000/health`
- `http://<host>:8000/docs`

Arret:

```bash
docker compose --env-file .env.server down
```

## 2. Variables backend importantes

- `DATABASE_URL` ou `PG*`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM` (defaut `HS256`)
- `JWT_EXPIRE_MINUTES` (defaut `120`)
- `APP_FERNET_KEY`
- `AUTH_COOKIE_SECURE=true` en production
- `TRUST_FORWARDED_HEADERS=true` seulement derriere proxy de confiance
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REDIRECT_URI`
- `STRAVA_SCOPES`

## 3. Base de donnees

Les scripts SQL montes automatiquement par Docker:

- `DB/sql/init.sql`
- `DB/sql/remplissage.sql`

`remplissage.sql` est utile pour demo/tests, pas obligatoire en prod.

## 4. Deploiement frontend

Sur Vercel (ou equivalent):

- Root directory: `frontend`
- Variable d'environnement: `NEXT_PUBLIC_API_URL=https://api.tondomaine.be`

## 5. Configuration Strava

Dans Strava Developer:

- Website: domaine frontend
- Callback: meme URL que `STRAVA_REDIRECT_URI`

Le callback doit matcher exactement (schema + host + path).

## 6. Verification post-deploiement

1. Auth: login/logout/me
2. `/pipeline`, `/fit-import`, `/compare-models`, `/strava` accessibles apres login
3. Sync Strava ecrit des PKL et des lignes en DB
4. Import FIT genere des PKL dans `DB/rides`
5. Pipeline et comparaison de modeles retournent des resultats
