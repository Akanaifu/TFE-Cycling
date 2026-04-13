# TFE Cycling - Guide de démarrage

Application full-stack pour l'analyse des prédictions de fréquence cardiaque lors du cyclisme.

## Architecture

```
TFE-Cycling/
├── backend/           # FastAPI (Python)
│   ├── main.py
│   ├── app/
│   │   └── services/
│   │       └── notebook.py   # Logique ML
│   └── .venv/
└── frontend/          # Next.js (TypeScript/React)
    └── app/
        ├── page.tsx
        └── components/
```

## Prérequis

- Python 3.12+
- Node.js 18+
- Windows PowerShell (ou bash)

## Installation et lancement

### 1. Backend FastAPI

#### 1.1 Créer et activer l'environnement virtuel

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### 1.2 Installer les dépendances

```bash
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn pandas numpy scikit-learn scipy
```

#### 1.3 Lancer le serveur

```bash
fastapi dev
```

Le backend sera disponible sur:

- API: `http://localhost:8000`
- Documentation: `http://localhost:8000/docs`

### 2. Frontend Next.js

#### 2.1 Installer les dépendances

```bash
cd frontend
npm install
```

#### 2.2 Lancer le serveur de développement

```bash
npm run dev
```

Le frontend sera disponible sur `http://localhost:3000`

## Utilisation complète

1. **Vérifier que le backend est actif**

   ```
   http://localhost:8000/health
   ```

   Réponse attendue: `{"status":"ok"}`

2. **Ouvrir le frontend**

   ```
   http://localhost:3000
   ```

3. **Configurer et exécuter**
   - Entrez le chemin du répertoire rides (ex: `../DB/rides/cyclist9`)
   - Sélectionnez les modèles à calculer
   - Cliquez sur "Exécuter le pipeline"

## Chemins de données

Les rides sont stockées dans:

```
notebook/rides/
├── cyclist0/
├── cyclist1/
├── ...
└── cyclist9/
    └── *.pkl files
```

Pour accéder aux rides d'un cyclist depuis le backend, utilisez un chemin relatif:

```
../DB/rides/cyclist9
```

## Modèles disponibles

| Modèle              | Description                               |
| ------------------- | ----------------------------------------- |
| `pred_hist`         | Prédiction historique (rides précédentes) |
| `pred_default`      | Régression linéaire simple                |
| `pred_no_fuite`     | ARX sans fuite d'information              |
| `pred_arx_selected` | ARX entraîné sur ride sélectionnée        |

## API principal - Route `/pipeline/run`

### Requête

```bash
curl -X POST "http://localhost:8000/pipeline/run" \
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

### Réponse

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
      "columns": ["t", "hr", "po", "t_min", "work", ..., "pred_arx_selected"],
      "data": [
        {"t": 0, "hr": 60, "po": 0, ..., "pred_arx_selected": 61.5},
        ...
      ]
    }
  ]
}
```

## Routes additionnelles

### `/rides/list` - Lister les rides

```bash
GET http://localhost:8000/rides/list?dir_path=../DB/rides/cyclist9
```

### `/pkl/test-read` - Tester la lecture d'un PKL

```bash
GET http://localhost:8000/pkl/test-read?file_path=../DB/rides/cyclist9/2026-04-02T09_56_36.000000000.pkl
```

### `/analysis/run` - Analyse complète (avec statistiques RMSE)

```bash
POST http://localhost:8000/analysis/run
```

## Dépannage

### Backend

#### Erreur: `ModuleNotFoundError: No module named 'fastapi'`

```bash
.\.venv\Scripts\Activate.ps1
python -m pip install fastapi uvicorn
```

#### Erreur: Port 8000 déjà utilisé

```bash
# Changer le port
fastapi dev --port 8001
```

#### Vérifier les routes

```
http://localhost:8000/docs
```

### Frontend

#### Erreur: `CORS error` ou `fetch failed`

- Vérifier que le backend est lancé sur `http://localhost:8000`
- Vérifier la configuration CORS dans `backend/main.py`

#### Erreur: `npm command not found`

- Installer Node.js depuis https://nodejs.org/

### Données

#### Erreur: `No valid rides found`

- Vérifier le chemin du répertoire
- S'assurer que le répertoire contient des fichiers `.pkl`

## Build pour production

### Backend

```bash
cd backend
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

### Frontend

```bash
cd frontend
npm run build
npm start
```

## Documentation

- [Backend API Routes](backend/API_ROUTES.md)
- [Frontend Documentation](frontend/FRONTEND.md)
- [Notebook Architecture](doc/etape_reflexion.md)

## Technologies

**Backend:**

- FastAPI 0.135.3
- pandas 3.0.2
- scikit-learn 1.8.0
- scipy 1.17.1

**Frontend:**

- Next.js 16.2.2
- React 19.2.4
- Tailwind CSS 4
- TypeScript 5

## Notes de développement

- Les chemins PKL utilisent `/` ou `\` indifféremment (`pathlib.Path`)
- Les prédictions sont calculées line-by-line avec les données réelles
- Le RMSE est calculé côté frontend pour validation rapide
- Les graphiques SVG supportent jusqu'à 10k points

## Support

Consultez le fichier [doc/etape_reflexion.md](doc/etape_reflexion.md) pour comprendre l'évolution du projet et les décisions architecture.
