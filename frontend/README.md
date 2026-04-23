# Frontend - TFE Cycling

Frontend Next.js du projet TFE Cycling.

## Scripts

```bash
npm run dev
npm run build
npm run start
npm run lint
```

## Variables d'environnement

Dans `frontend/.env`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Pages

- `/login`
- `/pipeline`
- `/fit-import`
- `/compare-models`
- `/strava`
- `/register` (visible admin)

## Authentification

Le frontend utilise une session via cookie HttpOnly (`credentials: include`).

Il n'y a pas de stockage local du token dans le frontend.

## Documentation detaillee

Voir [FRONTEND.md](FRONTEND.md).
