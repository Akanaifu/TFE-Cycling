"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import PipelineRunner from "../components/PipelineRunner";
import { commonPipelineStyles } from "../components/pipelineStyles";

export default function PredictionPipelinePage() {
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
      router.replace("/login?next=/pipeline");
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
        setAuthToken(null);
        router.replace("/login?next=/pipeline");
      }
    };

    fetchMe();
  }, [apiUrl, authHeaders, authToken, router]);

  if (!authChecked || !authToken) {
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
        <div className={commonPipelineStyles.redirectButtonContainer}>
          <Link
            href="/compare-models"
            className={commonPipelineStyles.redirectButtonSecondary}
          >
            Comparer deux modèles
          </Link>
          <Link
            href="/strava"
            className={commonPipelineStyles.redirectButtonSecondary + " ml-2"}
          >
            Ouvrir le pipeline Strava
          </Link>
          <Link
            href="/register"
            className={commonPipelineStyles.redirectButtonPrimary + " ml-2"}
          >
            Créer un compte
          </Link>
        </div>
        <div className="mt-8">
          <PipelineRunner />
        </div>
      </div>
    </div>
  );
}
