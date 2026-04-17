"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import ModelComparison from "../components/ModelComparison";
import { commonPipelineStyles } from "../components/pipelineStyles";

export default function CompareModelsPage() {
  const router = useRouter();
  const apiUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_URL || "https://tfe-cycling.onrender.com",
    [],
  );

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
        router.replace("/login?next=/compare-models");
      }
    };

    fetchMe();
  }, [apiUrl, router]);

  if (!authChecked) {
    return <div className="text-center py-8">Vérification...</div>;
  }

  return (
    <div className={commonPipelineStyles.pageContainer}>
      <div className={commonPipelineStyles.pageHeader}>
        <div>
          <h1 className={commonPipelineStyles.pageTitle}>
            Comparaison de Modèles
          </h1>
          <p className={commonPipelineStyles.pageSubtitle}>
            Entraîne deux modèles sur deux sorties différentes et compare leurs
            prédictions sur une troisième sortie
          </p>
        </div>
        <Link
          href="/pipeline"
          className={commonPipelineStyles.redirectButtonSecondary}
        >
          ← Retour au Pipeline
        </Link>
      </div>

      {authChecked && <ModelComparison apiUrl={apiUrl} />}
    </div>
  );
}
