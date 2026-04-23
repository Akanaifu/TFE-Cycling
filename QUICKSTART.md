# Quickstart - TFE Cycling

## Prerequis

- Python 3.12+
- Node.js 18+
- PostgreSQL (local ou distant)

## 1. Configurer le backend

Depuis `TFE-Cycling/backend`:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Configurer les variables dans `backend/.env` (ou variables systeme):

- `DATABASE_URL` (ou `PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD`)
- `JWT_SECRET_KEY`
- `APP_FERNET_KEY`
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REDIRECT_URI`

Demarrer le backend:

```bash
fastapi dev main.py
```

Verifier:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

## 2. Configurer le frontend

Depuis `TFE-Cycling/frontend`:

```bash
npm install
```

Configurer `frontend/.env` avec:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Demarrer le frontend:

```bash
npm run dev
```

Verifier `http://localhost:3000`.

## 3. Premiere utilisation

1. Ouvrir `/login` et se connecter.
2. Aller sur `/pipeline`.
3. Choisir la ride d'entrainement et les modeles.
4. Lancer "Executer le pipeline".

Note role-based:

- `admin`: choisit le cycliste.
- `user`: travaille sur son cycliste assigne automatiquement.

## 4. Modeles disponibles

- `pred_hist`: historique (rides precedentes)
- `pred_default`: regression simple
- `pred_no_fuite`: ARX sans fuite
- `pred_arx_selected`: ARX entraine sur la ride choisie

## 5. Commandes utiles

Backend:

```bash
cd backend
fastapi dev main.py --port 8001
```

Frontend:

```bash
cd frontend
npm run build
npm start
```

## 6. Erreurs frequentes

- `401/403`: session absente ou expiree.
- `Le dossier est vide.`: aucun PKL lisible dans le dossier cycliste.
- `Failed to list rides`: verifier droits d'acces et presence des PKL.
- CORS: verifier `NEXT_PUBLIC_API_URL` et que le backend tourne.

## Liens utiles

- [README.md](README.md)
- [backend/API_ROUTES.md](backend/API_ROUTES.md)
- [frontend/FRONTEND.md](frontend/FRONTEND.md)
- [TESTING.md](TESTING.md)
