# Structure du projet - TFE Cycling

## Arborescence (principale)

```
TFE-Cycling/
├── backend/
│   ├── main.py
│   ├── API_ROUTES.md
│   ├── requirements.txt
│   └── app/services/
│       ├── auth.py
│       ├── database.py
│       ├── fit_import.py
│       ├── notebook.py
│       ├── security.py
│       └── strava.py
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── pipeline/page.tsx
│   │   ├── fit-import/page.tsx
│   │   ├── compare-models/page.tsx
│   │   ├── strava/page.tsx
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   └── components/
│   ├── package.json
│   ├── FRONTEND.md
│   └── README.md
├── DB/
│   ├── rides/
│   └── sql/
│       ├── init.sql
│       └── remplissage.sql
├── docker-compose.yml
├── DEPLOYMENT.md
├── QUICKSTART.md
├── TESTING.md
└── README.md
```

## Backend

- `main.py`: declaration des routes FastAPI, auth/session, orchestration pipeline
- `app/services/notebook.py`: chargement PKL + modeles ML
- `app/services/fit_import.py`: conversion FIT -> DataFrame projet
- `app/services/strava.py`: OAuth et recuperation d'activites/streams
- `app/services/database.py`: acces PostgreSQL et regles cycliste/utilisateur

## Frontend

- `app/pipeline/page.tsx`: page pipeline principale
- `app/fit-import/page.tsx`: import manuel FIT
- `app/compare-models/page.tsx`: comparaison de modeles
- `app/strava/page.tsx`: parcours Strava
- `app/components/PipelineRunner.tsx`: execution pipeline + visualisations
- `app/components/TrainingRidePreview.tsx`: preview d'une ride d'entrainement

## Donnees

- `DB/rides/cyclistX/*.pkl`: sorties normalisees pour l'analyse
- `DB/sql/init.sql`: schema
- `DB/sql/remplissage.sql`: jeu de donnees de test/demo

## Flux principal

1. L'utilisateur se connecte (`/auth/login`).
2. Le frontend appelle les endpoints proteges avec cookie de session.
3. Le backend charge les PKL du cycliste autorise.
4. Les modeles sont calcules puis renvoyes au frontend.
5. Le frontend affiche courbes, resume et differences BPM.

## Liens

- [README.md](README.md)
- [backend/API_ROUTES.md](backend/API_ROUTES.md)
- [frontend/FRONTEND.md](frontend/FRONTEND.md)

- [QUICKSTART.md](QUICKSTART.md) - Démarrage
- [TESTING.md](TESTING.md) - Tests
- [backend/API_ROUTES.md](backend/API_ROUTES.md) - API
- [frontend/FRONTEND.md](frontend/FRONTEND.md) - Frontend
