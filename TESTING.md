# Guide de test - TFE Cycling

## 1. Smoke test local

### Prerequis

- Backend lance sur `http://localhost:8000`
- Frontend lance sur `http://localhost:3000`
- DB accessible
- Au moins un dossier `DB/rides/cyclistX` avec des PKL valides

### Verification backend

- `GET /health` retourne `status: ok`
- `GET /docs` charge Swagger
- `GET /auth/me` retourne 401 sans session

### Verification frontend

- `/` redirige vers login (ou affiche login)
- login valide redirige vers `/pipeline`
- navbar visible hors page login

## 2. Scenarios fonctionnels UI

### Pipeline

1. Ouvrir `/pipeline` apres login.
2. Choisir ride d'entrainement + modeles.
3. Lancer execution.
4. Verifier:
   - carte resume (`n_rides`, modeles computes)
   - selection de ride
   - graphe prediction
   - visualisation des differences BPM

### Cas dossier vide

Sur une ride preview avec un dossier sans PKL lisibles, verifier le message:

- `Le dossier est vide.`

### Import FIT

1. Ouvrir `/fit-import`.
2. Importer 1 ou plusieurs `.fit`.
3. Verifier compteur `saved/skipped`.

### Comparaison de modeles

1. Ouvrir `/compare-models`.
2. Choisir 2 rides d'entrainement differentes + 1 ride test.
3. Verifier metriques (`RMSE`, `MAE`, `R2`) et courbes A/B.

### Strava

1. Ouvrir `/strava`.
2. Generer URL OAuth.
3. Echanger le code.
4. Lancer sync et verifier ecriture PKL + DB.

## 3. Scenarios API (authentifies)

Utiliser cookie de session (pas de bearer manuel) apres login.

- `GET /cyclists/list`
- `GET /rides/list?dir_path=../DB/rides/cyclistX`
- `GET /rides/training-ride?cyclist=cyclistX&ride_index=1`
- `POST /pipeline/run`
- `POST /pipeline/compare-models-trained`
- `POST /rides/import-fit`

## 4. Cas d'erreur a couvrir

- 401/403 sur endpoints proteges sans session
- Cycliste non autorise pour un user non-admin
- Ride index hors plage
- Upload FIT non `.fit`
- Fichier FIT trop gros (413)

## 5. Checklist avant merge

- [ ] `npm run build` passe
- [ ] backend demarre sans erreur
- [ ] endpoints critiques testes
- [ ] parcours UI principal teste
- [ ] documentation synchronisee
