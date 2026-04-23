# TFE Cycling

Application web pour analyser des sorties cyclistes et comparer des modeles de prediction de frequence cardiaque.

## Stack

- Backend: FastAPI (Python)
- Frontend: Next.js 16 + React 19 + TypeScript
- Donnees: PostgreSQL + fichiers PKL sous `DB/rides`

## Fonctionnalites principales

- Authentification par cookie HttpOnly
- Gestion role-based:
  - `admin`: peut choisir le cycliste, creer des comptes, importer FIT pour un cycliste cible
  - `user`: est limite a son cycliste assigne
- Execution du pipeline de prediction (`pred_hist`, `pred_default`, `pred_no_fuite`, `pred_arx_selected`)
- Comparaison de deux modeles ARX entraines sur des rides differentes
- Import manuel de fichiers FIT en PKL
- Synchronisation Strava vers PKL + enregistrement DB

## Parcours de navigation

- `/login`: connexion
- `/pipeline`: execution des predictions
- `/fit-import`: import manuel FIT
- `/compare-models`: comparaison de modeles
- `/strava`: connexion/sync Strava
- `/register`: creation de compte (admin uniquement)

## Lancement local (resume)

1. Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
fastapi dev main.py
```

2. Frontend

```bash
cd frontend
npm install
npm run dev
```

3. URLs

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

## Documentation

- [QUICKSTART.md](QUICKSTART.md)
- [TESTING.md](TESTING.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- [backend/API_ROUTES.md](backend/API_ROUTES.md)
- [frontend/FRONTEND.md](frontend/FRONTEND.md)
