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

  const [authToken, setAuthToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const authHeaders = useMemo(() => {
    if (!authToken) {
      return {} as Record<string, string>;
    }
    return { Authorization: `Bearer ${authToken}` };
  }, [authToken]);

  useEffect(() => {
    const stored = localStorage.getItem("tfe_access_token");
    if (!stored) {
      router.replace("/login?next=/compare-models");
      return;
    }
    setAuthToken(stored);
    setAuthChecked(true);
  }, [router]);

  useEffect(() => {
    const fetchMe = async () => {
      if (!authToken) {
        return;
      }
      try {
        const response = await fetch(`${apiUrl}/auth/me`, {
          headers: authHeaders,
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail || `HTTP ${response.status}`);
        }
      } catch {
        localStorage.removeItem("tfe_access_token");
        router.replace("/login?next=/compare-models");
      }
    };

    fetchMe();
  }, [apiUrl, authHeaders, authToken, router]);

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

      {authToken && <ModelComparison authToken={authToken} apiUrl={apiUrl} />}
    </div>
  );
}
