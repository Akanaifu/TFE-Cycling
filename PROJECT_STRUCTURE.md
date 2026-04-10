# Structure du Projet TFE Cycling

## Arborescence

```
TFE-Cycling/
│
├── backend/                        # FastAPI backend (Python)
│   ├── main.py                    # Point d'entrée FastAPI
│   ├── API_ROUTES.md              # Documentation des routes API
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api/                   # (Vide, pour extension futures)
│   │   └── services/
│   │       ├── __init__.py
│   │       └── notebook.py        # Logique ML, prédictions
│   ├── .venv/                     # Environnement virtuel Python
│   └── requirements.txt           # (À créer) Dépendances Python
│
├── frontend/                       # Next.js frontend (TypeScript/React)
│   ├── app/
│   │   ├── page.tsx               # Page d'accueil
│   │   ├── layout.tsx             # Layout racine
│   │   ├── globals.css            # Styles globaux
│   │   └── components/
│   │       ├── PipelineRunner.tsx # Composant principal
│   │       ├── RideSelector.tsx   # Sélecteur de rides
│   │       └── PredictionChart.tsx # Graphique SVG
│   ├── public/                    # Assets statiques
│   ├── node_modules/              # Dépendances JavaScript
│   ├── package.json               # Config npm
│   ├── tsconfig.json              # Config TypeScript
│   ├── next.config.ts             # Config Next.js
│   ├── tailwind.config.ts         # Config Tailwind CSS
│   ├── postcss.config.mjs         # Config PostCSS
│   ├── eslint.config.mjs          # Config ESLint
│   ├── .env.example               # Variables d'environnement (template)
│   ├── FRONTEND.md                # Documentation frontend
│   └── README.md
│
├── notebook/                      # Données et notebook Jupyter
│   ├── algo.ipynb                 # Pipeline ML complet (Python)
│   ├── plot.py                    # Utilitaires de plotting
│   ├── strava_api.py              # (Non utilisé actuellement)
│   ├── strava_sync.py             # (Non utilisé actuellement)
│   ├── README.md
│   ├── rides/                     # Données rides par cyclist
│   │   ├── cyclist0/
│   │   ├── cyclist1/
│   │   ├── ...
│   │   ├── cyclist8/
│   │   └── cyclist9/
│   │       ├── 2026-04-02T09_56_36.000000000.pkl
│   │       ├── 2026-04-07T10_42_02.000000000.pkl
│   │       └── ... (autres rides)
│   └── wahoo/                     # Données brutes FIT
│       ├── dimitri/
│       │   ├── *.fit              # Fichiers Wahoo bruts
│       │   └── ...
│       └── nathan/
│           ├── *.fit
│           └── ...
│
├── doc/                           # Documentation et schémas
│   ├── EA.dio                     # Diagram Enterprise Architect
│   ├── etape_reflexion.md         # Évolution du projet
│   ├── modele.md                  # Documentation modèle
│   ├── model_fitting.html         # Rapport HTML fitting
│   ├── hr_fit_raccourci.html      # Rapport HTML HR fitting
│   ├── schema/
│   │   ├── flux_notebook.dio      # Flux du pipeline
│   │   └── uml.dio                # Diagramme UML
│   └── README.md
│
├── QUICKSTART.md                  # Guide de démarrage rapide
├── TESTING.md                     # Guide de test
├── PROJECT_STRUCTURE.md           # Ce fichier
├── README.md                      # ReadMe général (racine)
└── .gitignore
```

## Description des composants

### Backend (`backend/`)

#### `main.py`

Route principale FastAPI. Expose:

- `GET /` - Status
- `GET /health` - Health check
- `POST /pipeline/run` - Pipeline complet avec prédictions
- `GET /rides/list` - Lister les rides
- `POST/GET /pkl/test-read` - Tester la lecture PKL
- `POST /analysis/run` - Analyse avec statistiques

Middleware CORS pour accès frontend.

#### `app/services/notebook.py`

Cœur du système ML. Contient:

**Classes:**

- `AnalysisConfig` - Configuration d'analyse
- Dataclass pour les paramètres

**Fonctions principales:**

- `extract_donnee_pickle()` - Charge rides depuis PKL
- `add_features_to_rides()` - Feature engineering
- `prediction()` - Régression linéaire
- `prediction_with_prev_rides()` - Avec historique
- `prediction_arx_with_prev_rides_no_fuite()` - ARX sans fuite
- `prediction_arx_from_selected_ride()` - ARX sélectionné
- `run_notebook_analysis()` - Pipeline complet
- `_resolve_data_path()` - Résolution des chemins relatifs

**Helpers:**

- `_warn_and_is_invalid_hr_po()` - Validation rides
- `add_features()` - Features pour une ride
- `ajouter_colonnes_decalees()` - Lags temporels
- `parse_datetime_from_ride_filename()` - Extract datetime

### Frontend (`frontend/`)

#### `app/page.tsx`

Page d'accueil. Importe `PipelineRunner`.

#### `app/layout.tsx`

Layout racine avec métadonnées, Tailwind, polices.

#### `app/components/PipelineRunner.tsx`

Composant principal (~300 lignes). Gère:

- État (dir_path, models, loading, error, results)
- Formulaire de configuration
- Appels API vers `/pipeline/run`
- Sélection des modèles
- Affichage des résultats
- Tableau de données sampé

**Props:** Aucune
**State:**

- `dirPath` - Chemin du répertoire
- `selectedModels` - Modèles sélectionnés
- `selectedTrainRide` - Ride d'entraînement
- `loading` - En cours
- `error` - Message erreur
- `result` - Réponse API
- `selectedRideIndex` - Ride affichée

#### `app/components/RideSelector.tsx`

Sélecteur visuel de rides (~50 lignes).

- Grille 3 colonnes (responsive)
- Date, nombre de points
- Sélection active en bleu

**Props:**

```typescript
{
  rides: RideData[]
  selectedIndex: number
  onSelectRide: (index: number) => void
}
```

#### `app/components/PredictionChart.tsx`

Graphique SVG + statistiques (~400 lignes).

**Affiche:**

- Grille de référence
- Axes avec étiquettes
- Courbe FC réelle (trait plein rouge)
- Courbes prédictions (pointillées, couleurs)
- Légende
- Tableau statistiques (moyenne, RMSE)

**Props:**

```typescript
{
  rideData: RideData
  models: string[]
}
```

**Sous-composant:**

- `StatisticsTable()` - Calcule et affiche stats

### Données (`notebook/`)

#### Rides PKL

- Chemin: `notebook/rides/cyclist{0-9}/`
- Nom: `YYYY-MM-DDTHH_MM_SS.microseconds.pkl`
- Format: pandas DataFrame
- Colonnes: `t`, `hr`, `po` (minimum requis)

#### Notebook Jupyter

- `algo.ipynb` - Pipeline complet (13 cellules)
  - Cell 1: Imports
  - Cell 2-4: Conversion FIT → PKL
  - Cell 5-11: Algo ML (helpers, prédictions)
  - Cell 12: Calcul personnalisé
  - Cell 13: Affichage custom

### Documentation (`doc/`)

- `etape_reflexion.md` - Historique du projet, évolutions
- `modele.md` - Description du modèle ML
- Diagrammes (UML, flux)
- Rapports d'ajustement

## Flux de données

```
notebook/rides/cyclist9/*.pkl
         |
         v
[Frontend: Input form]
         |
         v
/pipeline/run (POST)
         |
         v
[Backend: extract_donnee_pickle]
         |
    [Load PKL] -> [Add features] -> [Validate rides]
         |
         v
[Compute Models]
    - pred_hist
    - pred_default
    - pred_no_fuite
    - pred_arx_selected
         |
         v
[Combine rides + predictions]
         |
         v
[Return JSON]
         |
         v
[Frontend: Display]
    - Chart (SVG)
    - Statistics
    - Data table
```

## Dépendances

### Python (Backend)

```
fastapi==0.135.3
uvicorn
pandas==3.0.2
numpy==2.4.4
scikit-learn==1.8.0
scipy==1.17.1
```

### JavaScript (Frontend)

```
next==16.2.2
react==19.2.4
react-dom==19.2.4
tailwindcss==4
typescript==5
```

## Configuration des environnements

### Backend (.venv)

- Python 3.12.10
- Créé avec `python -m venv .venv`
- Activé: `.\.venv\Scripts\Activate.ps1`

### Frontend

- Node.js 18+
- npm ou yarn
- Dépendances dans `node_modules/`

## Ports

| Service          | Port | URL                        |
| ---------------- | ---- | -------------------------- |
| FastAPI Backend  | 8000 | http://localhost:8000      |
| FastAPI Swagger  | 8000 | http://localhost:8000/docs |
| Next.js Frontend | 3000 | http://localhost:3000      |

## Fichiers clés

| Fichier               | Description      |
| --------------------- | ---------------- |
| `main.py`             | Routes API       |
| `notebook.py`         | Logique ML       |
| `PipelineRunner.tsx`  | UI principale    |
| `PredictionChart.tsx` | Graphique        |
| `.env.example`        | Config template  |
| `QUICKSTART.md`       | Démarrage rapide |
| `API_ROUTES.md`       | Doc API          |
| `FRONTEND.md`         | Doc frontend     |

## Processus de développement

1. **Modification du backend**
   - Éditer `notebook.py` ou `main.py`
   - Backend recharge automatiquement avec `fastapi dev`
   - Tester via `http://localhost:8000/docs`

2. **Modification du frontend**
   - Éditer composants dans `app/components/`
   - Frontend recharge automatiquement avec `npm run dev`
   - Tester sur `http://localhost:3000`

3. **Ajout de modèles**
   - Implanté dans `notebook.py`
   - Ajouter logique dans `run_notebook_analysis()`
   - Ajouter couleur dans `PredictionChart.tsx`
   - Route `/pipeline/run` sélectionne automatiquement

## Points d'extension

### Ajouter une nouvelle route

```python
@app.post("/custom-endpoint")
async def custom_endpoint(payload: CustomRequest) -> dict:
    # Implementation
    return result
```

### Ajouter un nouveau modèle

1. Implanter fonction dans `notebook.py`
2. Ajouter case à cocher dans `PipelineRunner.tsx`
3. Ajouter couleur dans `PredictionChart.tsx`

### Personnaliser l'UI

- Modifier `globals.css` pour styles globaux
- Tailwind classes dans les composants TSX
- Thème: `tailwind.config.ts`

## Troubleshooting

**Q: Comment changer le port?**

- Backend: `fastapi dev --port 8001`
- Frontend: `npm run dev -- -p 3001`

**Q: Comment déboguer les requêtes API?**

- Frontend: Outils développeur (F12) → Network
- Backend: Données sont loggées dans console ou utilisez debugging

**Q: Comment ajouter une dépendance?**

- Backend: `pip install package-name`
- Frontend: `npm install package-name`

## Voir aussi

- [QUICKSTART.md](QUICKSTART.md) - Démarrage
- [TESTING.md](TESTING.md) - Tests
- [backend/API_ROUTES.md](backend/API_ROUTES.md) - API
- [frontend/FRONTEND.md](frontend/FRONTEND.md) - Frontend
