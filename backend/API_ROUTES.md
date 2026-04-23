# TFE Cycling - Backend API

## Authentification

Le backend utilise un cookie HttpOnly (`tfe_access_token`).

La plupart des routes metier necessitent une session valide (`credentials: include` cote frontend).

## Endpoints publics

- `GET /api`: statut simple
- `GET /health`: sante API + DB

## Endpoints authentifies

### Auth

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/register` (admin uniquement)

### Cyclistes et rides

- `GET /cyclists/list`
- `GET /rides/list?dir_path=../DB/rides/cyclistX`
- `GET /rides/training-ride?cyclist=cyclistX&ride_index=1`
- `POST /rides/import-fit` (multipart, `.fit`)

### Pipeline / analyse

- `POST /pipeline/run`
- `POST /pipeline/compare-models-trained`
- `POST /analysis/run`

### Strava

- `GET /strava/status`
- `GET /strava/auth-url`
- `POST /strava/exchange-code`
- `GET /strava/activities`

### Diagnostic

- `GET /db/status`
- `GET /pkl/test-read` (admin + feature flag)
- `POST /pkl/test-read` (admin + feature flag)

## `POST /pipeline/run` (principal)

### Body

```json
{
  "dir_path": "../DB/rides/cyclist9",
  "selected_models_compute": ["pred_arx_selected"],
  "prev_ride": 1,
  "nan_ratio": 1.0,
  "selected_train_ride": 1,
  "selected_target_rides": null
}
```

### Modeles supportes

- `pred_hist`
- `pred_default`
- `pred_no_fuite`
- `pred_arx_selected`

### Reponse (extrait)

```json
{
  "ok": true,
  "n_rides": 5,
  "models_requested": ["pred_arx_selected"],
  "models_computed": ["pred_arx_selected"],
  "rides": [
    {
      "datetime": "02/04/2026 09:56:36",
      "n_points": 1250,
      "columns": ["t", "hr", "po", "t_min", "pred_arx_selected"],
      "data": []
    }
  ]
}
```

## Codes de retour frequents

- `200`: succes
- `400`: erreur de validation ou pipeline
- `401`: non authentifie
- `403`: acces refuse (cycliste/role)
- `413`: fichier FIT trop volumineux
- `500`: erreur interne

## Notes pratiques

- Les chemins `dir_path` doivent pointer vers un cycliste (`../DB/rides/cyclistX`).
- Les users non-admin sont limites a leur cycliste assigne.
- Sur dossier vide (pas de PKL lisible), la ride preview retourne `Le dossier est vide.`.
