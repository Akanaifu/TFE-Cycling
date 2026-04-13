# Guide de test - TFE Cycling

## Checklist de démarrage

### Étape 1: Préparation de l'environnement

- [ ] Python 3.12+ installé
- [ ] Node.js 18+ installé
- [ ] Répertoire `notebook/rides/cyclist9/` contient des fichiers `.pkl`
- [ ] Git configuré (changements sont pushés)

### Étape 2: Lancer le backend

```bash
cd TFE-Cycling/backend
.\.venv\Scripts\Activate.ps1
fastapi dev
```

**Vérifications:**

- [ ] "Uvicorn running on http://127.0.0.1:8000" s'affiche
- [ ] Pas d'erreurs d'import
- [ ] Vérifier: http://localhost:8000/health → `{"status":"ok"}`
- [ ] Vérifier: http://localhost:8000/docs (swagger UI doit charger)

### Étape 3: Lancer le frontend

**Dans un nouveau terminal:**

```bash
cd TFE-Cycling/frontend
npm install
npm run dev
```

**Vérifications:**

- [ ] "Ready in X.XXs" s'affiche
- [ ] Pas d'erreurs de compilation
- [ ] Frontend accessible: http://localhost:3000
- [ ] Page se charge sans erreurs dans la console

### Étape 4: Test du pipeline

#### Test 4.1: Via le frontend

1. Ouvrir http://localhost:3000
2. Le formulaire doit afficher:
   - [ ] Champ "Chemin du répertoire rides"
   - [ ] Champ "Ride d'entraînement"
   - [ ] Cases à cocher pour les modèles
   - [ ] Bouton "Exécuter le pipeline"

3. Laisser les valeurs par défaut et cliquer sur "Exécuter"
4. Attendre ~10-30 secondes
5. Vérifier les résultats:
   - [ ] Résumé affiche "n_rides" > 0
   - [ ] Les rides apparaissent dans le sélecteur
   - [ ] Graphique SVG est visible
   - [ ] Tableau de données s'affiche
   - [ ] Statistiques (moyenne, RMSE) sont calculées

#### Test 4.2: Via curl (backend uniquement)

```bash
curl -X POST "http://127.0.0.1:8000/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "dir_path": "../DB/rides/cyclist9",
    "selected_models_compute": ["pred_arx_selected"],
    "prev_ride": 1,
    "nan_ratio": 1.0,
    "selected_train_ride": 1,
    "selected_target_rides": null
  }'
```

**Résultat attendu:**

```json
{
  "ok": true,
  "n_rides": 5,
  "models_requested": ["pred_arx_selected"],
  "models_computed": ["pred_arx_selected"],
  "rides": [...]
}
```

### Étape 5: Test des routes additionnelles

#### Lister les rides

```bash
GET http://localhost:8000/rides/list?dir_path=../DB/rides/cyclist9
```

**Vérifier:** Liste les rides avec leurs dates et nombre de points

#### Tester la lecture PKL

```bash
GET http://localhost:8000/pkl/test-read?file_path=../DB/rides/cyclist9/2026-04-02T09_56_36.000000000.pkl
```

**Vérifier:** Retourne les métadonnées du fichier PKL

## Cas de test - Scénarios

### Scénario 1: Un modèle

- Sélectionner: `pred_arx_selected`
- Exécuter
- Vérifier: Une courbe pointillée sur le graphique

### Scénario 2: Plusieurs modèles

- Sélectionner: `pred_hist`, `pred_default`, `pred_no_fuite`, `pred_arx_selected`
- Exécuter
- Vérifier: Quatre courbes pointillées de couleurs différentes

### Scénario 3: Différentes rides d'entraînement

- Sélectionner train ride: 2
- Exécuter
- Comparer le RMSE et les courbes avec scénario 1

### Scénario 4: Autre cyclist

- Changer: `dir_path` → `../DB/rides/cyclist0`
- Exécuter
- Vérifier: Charge les rides du nouveau cyclist

## Dépannage pendant les tests

### Erreur: CORS error

**Cause:** Backend n'est pas en cours d'exécution ou sur le mauvais port
**Solution:**

```bash
# Terminal backend
fastapi dev
```

### Erreur: "No valid rides found"

**Cause:** Chemin incorrect ou pas de fichiers PKL
**Solution:**

```bash
# Vérifier le répertoire
ls ../DB/rides/cyclist9/*.pkl
```

### Erreur: HTTP 400 "Models not computed"

**Cause:** Modèle sélectionné n'est pas implémenté
**Solution:** Vérifier le nom du modèle dans `backend/app/services/notebook.py`

### Erreur: "connect ECONNREFUSED 127.0.0.1:8000"

**Cause:** Backend n'écoute pas le port 8000
**Solution:**

```bash
# Vérifier quel processus écoute le port
netstat -ano | findstr :8000
# Si non vide, tuer le processus et relancer le backend
```

### Graphique n'affiche rien

**Cause:** Données mal formatées ou colonnes manquantes
**Solution:**

```bash
# Vérifier la structure des données via l'API test
curl http://localhost:8000/pkl/test-read?file_path=...
```

## Validation finale

Checklist avant push:

- [ ] Backend compile sans erreurs
- [ ] Frontend compile sans erreurs
- [ ] Pipeline exécutable via frontend
- [ ] Graphique s'affiche correctement
- [ ] Tableau affiche les données
- [ ] Statistiques sont calculées
- [ ] Pas d'erreurs CORS
- [ ] Pas d'erreurs 404/500
- [ ] Documentation à jour (QUICKSTART.md, FRONTEND.md, API_ROUTES.md)

## Performance

**Temps attendus:**

| Action                                       | Temps  |
| -------------------------------------------- | ------ |
| Chargement frontend                          | < 2s   |
| Requête `/rides/list`                        | < 1s   |
| Pipeline `/pipeline/run` (5 rides, 1 modèle) | 10-30s |
| Pipeline (5 rides, 4 modèles)                | 30-90s |

**Optimisations possibles:**

- Augmenter les workers uvicorn: `uvicorn main:app --workers 4`
- Cache des résultats (futures)
- Calcul parallèle des modèles (futures)

## Notes

- Les fichiers PKL doivent être en format pandas DataFrame
- Les colonnes requises: `t`, `hr`, `po`
- Les dates dans les noms de fichiers: `YYYY-MM-DDTHH_MM_SS.microseconds.pkl`
- Tous les chemins sont cross-platform (pathlib.Path)

## Support

Consultez:

- [QUICKSTART.md](QUICKSTART.md) - Démarrage rapide
- [backend/API_ROUTES.md](backend/API_ROUTES.md) - Documentation API
- [frontend/FRONTEND.md](frontend/FRONTEND.md) - Documentation frontend
