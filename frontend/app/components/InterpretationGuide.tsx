"use client";

import React from "react";
import { commonPipelineStyles } from "./pipelineStyles";

interface Props {
  context?: "pipeline" | "compare";
}

export default function InterpretationGuide({ context = "pipeline" }: Props) {
  return (
    <div className={commonPipelineStyles.card}>
      <h2 className={commonPipelineStyles.sectionTitle}>
        Interpréter les résultats
      </h2>

      <div className="space-y-3">
        <div>
          <h3 className={commonPipelineStyles.subSectionTitle}>
            Prédictions vs réalité
          </h3>
          <p className={commonPipelineStyles.bodyText}>
            Le graphique montre la fréquence cardiaque réelle et les courbes de
            prédiction. Trois cas possibles :
            <ul>
              <li>
                Courbes quasi identiques : pas de changement de la forme
                physique{" "}
              </li>
              <li>
                Courbe de prédiction plus basse : amélioration de la forme
                physique car pour un même effort, le coeur est moins solicité
              </li>
              <li>
                Courbe de prédiction plus haute : dégradation de la forme
                physique car pour un même effort, le coeur est plus solicité
              </li>
            </ul>
          </p>
        </div>

        <div>
          <h3 className={commonPipelineStyles.subSectionTitle}>
            Différences BPM (prédiction − réel)
          </h3>
          <p className={commonPipelineStyles.bodyText}>
            Le diagramme des différences calcule (prédiction − réel) par point.
            <ul>
              <li>
                Valeurs positives : le modèle surestime la FC / dégradation de
                la forme physique
              </li>
              <li>
                Valeurs négatives : le modèle sous‑estime la FC. / amélioration
                de la forme physique
              </li>
              <li>
                Moyenne proche de 0 et faible dispersion → bon ajustement /
                maintient de la forme physique
              </li>
            </ul>
          </p>
          <p className={commonPipelineStyles.mutedText}>
            Résultat à ne pas prendre au pied de la lettre. Ce sont des
            prédictions, des erreurs peuvent arriver. Il y a beaucoup de
            facteurs à prendre en compte en plus de la puissance.
          </p>
        </div>

        {context === "compare" && (
          <div>
            <h3 className={commonPipelineStyles.subSectionTitle}>
              Conseils pratiques
            </h3>
            <ul className={commonPipelineStyles.bodyText}>
              <li>
                Regarder la dispersion des différences plutôt que la seule
                moyenne.
              </li>
              <li>
                Faire attention aux valeurs manquantes ou aux segments
                anaormaux.
              </li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
