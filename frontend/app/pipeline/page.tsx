"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import PipelineRunner from "../components/PipelineRunner";
import { commonPipelineStyles } from "../components/pipelineStyles";

export default function PredictionPipelinePage() {
  const router = useRouter();
  const apiUrl = useMemo(() => process.env.NEXT_PUBLIC_API_URL, []);

  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const fetchMe = async () => {
      try {
        const response = await fetch(`${apiUrl}/auth/me`, {
          credentials: "include",
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || `HTTP ${response.status}`);
        }
        setAuthChecked(true);
      } catch {
        router.replace("/login?next=/pipeline");
      }
    };

    fetchMe();
  }, [apiUrl, router]);

  if (!authChecked) {
    return (
      <div className={commonPipelineStyles.pageContainer}>
        <section className={commonPipelineStyles.card}>
          <h2 className={commonPipelineStyles.sectionTitleNoMargin}>
            Verification de session...
          </h2>
          <p className={`mt-2 ${commonPipelineStyles.bodyText}`}>
            Redirection vers la page de connexion.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className={commonPipelineStyles.pageContainer}>
      <div>
        <h1 className={commonPipelineStyles.pageTitle}>
          TFE Cycling - Analyse des Prédictions de FC
        </h1>
        <p className={commonPipelineStyles.pageSubtitle}>
          Se connecte au compte du site, crée un modèle sur une sortie choisie
          et l&apos;applique sur les autres sorties
        </p>
        <div className="mt-8">
          <PipelineRunner />
        </div>
      </div>
    </div>
  );
}
