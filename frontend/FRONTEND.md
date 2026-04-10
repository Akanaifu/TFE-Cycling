# Frontend - Affichage des prédictions

Ce frontend Next.js affiche les prédictions de fréquence cardiaque générées par le backend FastAPI.

## Structure

### Composants

1. **`PipelineRunner.tsx`** - Composant principal
   - Formulaire de configuration (chemin du répertoire, modèles, ride d'entraînement)
   - Appelle l'API `/pipeline/run`
   - Affiche les résultats

2. **`RideSelector.tsx`** - Sélecteur de rides
   - Affiche toutes les rides disponibles
   - Permet de sélectionner la ride active
   - Montre la date/heure et le nombre de points

3. **`PredictionChart.tsx`** - Graphique des prédictions
   - Trace un graphique SVG de la FC réelle vs prédictions
   - Affiche des courbes pour chaque modèle
   - Calcule les statistiques (moyenne, RMSE)

## Installation et lancement

### 1. Installer les dépendances

```bash
cd frontend
npm install
```

### 2. Lancer le serveur de développement

```bash
npm run dev
```

Le frontend sera disponible sur `http://localhost:3000`

## Utilisation

### Configuration

1. **Chemin du répertoire**: Entrez le chemin vers le dossier contenant les PKL
   - Exemple: `../../notebook/rides/cyclist9`
   - Les chemins relatifs sont résolus depuis le répertoire backend

2. **Ride d'entraînement**: Index 1-based de la ride utilisée pour l'entraînement
   - Par défaut: `1`

3. **Modèles**: Sélectionnez les modèles à calculer
   - **Historique**: Utilise les rides précédentes
   - **Régression simple**: Régression linéaire standard
   - **ARX sans fuite**: Modèle ARX sans information future
   - **ARX sélectionné**: ARX entraîné sur la ride sélectionnée

### Exécution du pipeline

1. Cliquez sur le bouton "Exécuter le pipeline"
2. Attendez le calcul (peut prendre quelques secondes selon le nombre de points)
3. Les résultats s'affichent automatiquement

### Visualisation des résultats

#### Résumé

- Nombre de rides chargées
- Modèles calculés
- Points par ride

#### Sélecteur de rides

- 3 colonnes affichant chaque ride
- Cliquez pour sélectionner la ride active
- Affiche la date/heure et le nombre de points

#### Graphique

- Courbe rouge: FC réelle (trait plein)
- Courbes pointillées colorées: Prédictions des modèles
- Grille de référence
- Échelles sur les axes

#### Statistiques

- **Moyenne**: Valeur moyenne de FC
- **RMSE**: Erreur quadratique moyenne (pour les prédictions)

#### Tableau de données

- Affiche tous les points de la ride
- Affiche chaque {n} points pour lisibilité (sampé automatiquement)
- Colonnes: t, t_min, po, hr, et prédictions

## Configuration du backend

Assurez-vous que le backend FastAPI est en cours d'exécution:

```bash
cd backend
.\.venv\Scripts\Activate.ps1
fastapi dev
```

Le backend doit être accessible sur `http://localhost:8000`

## Gestion des erreurs

- **Erreur: "Failed to list rides"**: Le chemin du répertoire n'existe pas
- **Erreur HTTP 400**: Vérifiez que le backend est en cours d'exécution
- **Erreur: "No valid rides"**: Aucun fichier .pkl trouvé dans le répertoire

## Développement

### Ajouter un nouveau modèle

1. Assurez-vous que le modèle est implémenté dans `notebook.py`
2. Ajoutez une couleur dans `PredictionChart.tsx`:
   ```typescript
   const colors: Record<string, string> = {
     // ...
     pred_new_model: "#yourcolor",
   };
   ```
3. Le modèle apparaîtra automatiquement dans la liste de sélection

### Modifier le style

- Tous les styles utilisent Tailwind CSS
- Fichier de configuration: `tailwind.config.ts`
- Styles globaux: `globals.css`

## Performance

- Les données sont sampées automatiquement pour les tableaux (affiche ~50 points)
- Les graphiques SVG sont optimisés pour les datasets jusqu'à 10k points
- Pour les performances optimales, évitez d'ouvrir plus de 3-4 modèles simultanément

## Améliorations futures

- [ ] Export des résultats en CSV/PNG
- [ ] Comparaison entre modèles (différences RMSE)
- [ ] Sélection de plages de temps (zoom)
- [ ] Analyse des résidus
- [ ] Support du dark mode
