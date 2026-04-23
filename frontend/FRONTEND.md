# Frontend - Documentation

## Objectif

Le frontend Next.js fournit une interface unifiee pour:

- executer le pipeline de prediction
- previsualiser la ride d'entrainement
- comparer deux modeles
- importer des FIT
- synchroniser des activites Strava

## Pages

- `app/page.tsx`: redirige vers login
- `app/login/page.tsx`: connexion
- `app/pipeline/page.tsx`: pipeline principal
- `app/fit-import/page.tsx`: import FIT
- `app/compare-models/page.tsx`: comparaison A/B
- `app/strava/page.tsx`: workflow Strava
- `app/register/page.tsx`: creation de compte (admin uniquement)

## Composants cles

- `PipelineRunner.tsx`
  - charge utilisateur (`/auth/me`)
  - gere selection cycliste, ride d'entrainement, modeles
  - appelle `/pipeline/run`
  - affiche resume + graphe + differences BPM
- `CyclistSelector.tsx`
  - recupere cyclistes via `/cyclists/list`
  - calcule `maxTrainRideIndex` via `/rides/list`
- `TrainingRidePreview.tsx`
  - appelle `/rides/training-ride`
  - affiche stats + echantillon de points
- `FitImportRunner.tsx`
  - upload `multipart/form-data` vers `/rides/import-fit`
- `ModelComparison.tsx`
  - appelle `/pipeline/compare-models-trained`

## Auth et permissions

- Toutes les routes metier utilisent `credentials: include`.
- Les pages proteges redirigent vers `/login?next=...` si session invalide.
- Le bouton `Nouveau compte` n'est visible que pour un admin.

## Erreurs et UX

- Messages backend affiches dans les panneaux d'erreur.
- Cas "dossier sans PKL" affiche: `Le dossier est vide.`
- Si cycliste/ride indisponible, les composants reviennent a un etat neutre.

## Lancement local

```bash
cd frontend
npm install
npm run dev
```

Variable requise:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Build

```bash
npm run build
npm start
```
